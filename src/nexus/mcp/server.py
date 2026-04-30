"""MCP Server — expose Nexus tools via the Model Context Protocol.

Supports two transport modes:
1. stdio:  JSON-RPC over stdin/stdout (for Claude Desktop, Cursor, etc.)
2. http:   JSON-RPC over HTTP (for network clients)

MCP spec: https://modelcontextprotocol.io/

Usage:
    nexus mcp serve                   # stdio mode (default)
    nexus mcp serve --transport http  # HTTP mode on port 3100
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from nexus.tools import create_default_tools
from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)

# MCP Protocol version
MCP_VERSION = "2024-11-05"

# JSON-RPC helpers
JSONRPC_VERSION = "2.0"


def _jsonrpc_response(id: Any, result: Any) -> dict:
    return {"jsonrpc": JSONRPC_VERSION, "id": id, "result": result}


def _jsonrpc_error(id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": JSONRPC_VERSION, "id": id, "error": {"code": code, "message": message}}


class NexusMCPServer:
    """MCP server that exposes Nexus tools.

    Implements the MCP protocol:
    - initialize / initialized handshake
    - tools/list — returns available tools with schemas
    - tools/call — executes a tool and returns the result
    """

    def __init__(self, workspace: str = "."):
        self.workspace = str(Path(workspace).resolve())
        self.tools: Dict[str, BaseTool] = create_default_tools(workspace=self.workspace)
        self.initialized = False
        self.server_info = {
            "name": "nexus",
            "version": "0.1.0",
        }
        self.capabilities = {
            "tools": {},
        }

    # ------------------------------------------------------------------
    # Protocol handlers
    # ------------------------------------------------------------------

    async def handle_request(self, request: dict) -> Optional[dict]:
        """Route a JSON-RPC request to the appropriate handler."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        logger.debug("MCP request: %s (id=%s)", method, req_id)

        # Notifications (no id) — don't send a response
        if req_id is None:
            if method == "notifications/initialized":
                self.initialized = True
                logger.info("MCP client initialized")
            elif method == "notifications/cancelled":
                logger.info("Request cancelled: %s", params.get("requestId"))
            return None

        # Methods that require a response
        handler_map = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "ping": self._handle_ping,
        }

        handler = handler_map.get(method)
        if handler:
            try:
                result = await handler(params)
                return _jsonrpc_response(req_id, result)
            except Exception as e:
                logger.error("Error handling %s: %s", method, e)
                return _jsonrpc_error(req_id, -32603, str(e))
        else:
            return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    async def _handle_initialize(self, params: dict) -> dict:
        """Handle the initialize handshake."""
        client_info = params.get("clientInfo", {})
        logger.info(
            "MCP initialize from %s %s",
            client_info.get("name", "unknown"),
            client_info.get("version", ""),
        )
        return {
            "protocolVersion": MCP_VERSION,
            "capabilities": self.capabilities,
            "serverInfo": self.server_info,
        }

    async def _handle_tools_list(self, params: dict) -> dict:
        """Return available tools in MCP format."""
        tools_list = []
        seen = set()
        for name, tool in self.tools.items():
            if id(tool) in seen:
                continue
            seen.add(id(tool))

            # Build JSON Schema from tool's schema dict
            properties = {}
            required = []
            for param_name, param_desc in tool.schema.items():
                properties[param_name] = {
                    "type": "string",
                    "description": param_desc,
                }
                required.append(param_name)

            tools_list.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })

        return {"tools": tools_list}

    async def _handle_tools_call(self, params: dict) -> dict:
        """Execute a tool and return the result."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        tool = self.tools.get(tool_name)
        if not tool:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            }

        try:
            result = await tool.execute(**arguments)
            return {
                "content": [{"type": "text", "text": result}],
                "isError": False,
            }
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }

    async def _handle_ping(self, params: dict) -> dict:
        """Respond to ping."""
        return {}

    # ------------------------------------------------------------------
    # Transport: stdio
    # ------------------------------------------------------------------

    async def serve_stdio(self) -> None:
        """Run the MCP server over stdin/stdout.

        This is the standard transport for Claude Desktop, Cursor, etc.
        Each line on stdin is a JSON-RPC message, each response is
        written as a line to stdout.
        """
        logger.info("Nexus MCP server starting (stdio mode)")
        logger.info("Workspace: %s", self.workspace)
        logger.info("Tools: %s", ", ".join(t for t in self.tools if t == self.tools[t].name))

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break

                line = line.decode("utf-8").strip()
                if not line:
                    continue

                request = json.loads(line)
                response = await self.handle_request(request)

                if response is not None:
                    output = json.dumps(response) + "\n"
                    writer.write(output.encode("utf-8"))
                    await writer.drain()

            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON: %s", e)
            except Exception as e:
                logger.error("Stdio error: %s", e)
                break

        logger.info("MCP server shutting down")

    # ------------------------------------------------------------------
    # Transport: HTTP
    # ------------------------------------------------------------------

    async def serve_http(self, host: str = "127.0.0.1", port: int = 3100) -> None:
        """Run the MCP server over HTTP.

        Simple HTTP transport — POST JSON-RPC to /.
        """
        try:
            from aiohttp import web
        except ImportError:
            logger.error("aiohttp required for HTTP transport. Install with: pip install aiohttp")
            return

        async def handle_post(request: web.Request) -> web.Response:
            try:
                body = await request.json()
                response = await self.handle_request(body)
                if response is not None:
                    return web.json_response(response)
                return web.Response(status=204)
            except json.JSONDecodeError:
                return web.json_response(
                    _jsonrpc_error(None, -32700, "Parse error"),
                    status=400,
                )

        async def handle_get(request: web.Request) -> web.Response:
            tools = await self._handle_tools_list({})
            return web.json_response({
                "server": self.server_info,
                "tools": len(tools["tools"]),
                "workspace": self.workspace,
            })

        app = web.Application()
        app.router.add_post("/", handle_post)
        app.router.add_get("/", handle_get)

        logger.info("Nexus MCP server starting (HTTP mode) at %s:%d", host, port)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        print(f"Nexus MCP server running at http://{host}:{port}")
        print("Press Ctrl+C to stop")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            await runner.cleanup()
