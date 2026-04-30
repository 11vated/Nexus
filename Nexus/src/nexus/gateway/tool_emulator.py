"""Tool use emulation for models without native tool calling."""
import re
import json
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class ToolRequest:
    """A parsed tool use request."""
    tool_name: str
    arguments: Dict[str, Any]
    raw: str


class ToolEmulator:
    """Emulate tool use for models via prompting."""
    
    # Tool use patterns to recognize
    PATTERNS = {
        "execute": r"<execute>(.+?)</execute>",
        "read_file": r"<read_file>(.+?)</read_file>",
        "write_file": r"<write_file(?:\s+path=\"([^\"]+)\")?>(.+?)</write_file>",
        "grep": r"<grep>(.+?)</grep>",
        "bash": r"<bash>(.+?)</bash>",
        "run": r"<run>(.+?)</run>",
    }
    
    def __init__(self, tool_executor: Callable = None):
        self.tool_executor = tool_executor or self._default_executor
    
    def inject_tool_prompt(self, system_message: str = None) -> str:
        """Get system prompt with tool instructions."""
        return f"""You are an expert AI coding assistant. When you need to use tools, ALWAYS use this format:

To run a command:
<execute>npm test</execute>

To read a file:
<read_file>path/to/file.py</read_file>

To write a file:
<write_file path="src/main.py">
def hello():
    print("Hello, World!")
</write_file>

To search code:
<grep>import os</grep>

To run a shell command:
<bash>ls -la</bash>

NEVER use any other format. Always use these XML-like tags."""

    def parse_response(self, response: str) -> List[ToolRequest]:
        """Parse tool requests from model response."""
        requests = []
        
        # Match <execute> tags
        for match in re.finditer(self.PATTERNS["execute"], response, re.DOTALL):
            requests.append(ToolRequest(
                tool_name="execute",
                arguments={"command": match.group(1).strip()},
                raw=match.group(0)
            ))
        
        # Match <read_file> tags
        for match in re.finditer(self.PATTERNS["read_file"], response, re.DOTALL):
            requests.append(ToolRequest(
                tool_name="read_file",
                arguments={"path": match.group(1).strip()},
                raw=match.group(0)
            ))
        
        # Match <write_file> tags
        for match in re.finditer(self.PATTERNS["write_file"], response, re.DOTALL):
            path = match.group(1) if match.group(1) else "unknown"
            content = match.group(2)
            requests.append(ToolRequest(
                tool_name="write_file",
                arguments={"path": path, "content": content.strip()},
                raw=match.group(0)
            ))
        
        # Match <grep> tags
        for match in re.finditer(self.PATTERNS["grep"], response, re.DOTALL):
            requests.append(ToolRequest(
                tool_name="grep",
                arguments={"pattern": match.group(1).strip()},
                raw=match.group(0)
            ))
        
        # Match <bash> tags  
        for match in re.finditer(self.PATTERNS["bash"], response, re.DOTALL):
            requests.append(ToolRequest(
                tool_name="bash",
                arguments={"command": match.group(1).strip()},
                raw=match.group(0)
            ))
        
        return requests
    
    async def execute_tools(self, requests: List[ToolRequest]) -> Dict[str, Any]:
        """Execute all tool requests and return results."""
        results = {}
        
        for request in requests:
            try:
                result = await self.tool_executor(request.tool_name, request.arguments)
                results[request.tool_name] = {
                    "success": True,
                    "result": result,
                    "raw": request.raw
                }
            except Exception as e:
                results[request.tool_name] = {
                    "success": False,
                    "error": str(e),
                    "raw": request.raw
                }
                logger.error(f"Tool {request.tool_name} failed: {e}")
        
        return results
    
    async def _default_executor(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Default execution - raise if no executor provided."""
        raise NotImplementedError(
            "No tool executor configured. Provide a tool_executor function."
        )


class MCPWrapper:
    """Wrap MCP servers for unified access."""
    
    def __init__(self):
        self.servers: Dict[str, Any] = {}
    
    def register_server(self, name: str, server: Any):
        """Register an MCP server."""
        self.servers[name] = server
        logger.info(f"Registered MCP server: {name}")
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Call a tool on a specific server."""
        if server_name not in self.servers:
            raise ValueError(f"Unknown MCP server: {server_name}")
        
        server = self.servers[server_name]
        
        # Standard MCP tool call
        try:
            result = await server.call_tool(tool_name, arguments)
            return result
        except AttributeError:
            # Fallback for simple servers
            return await server[tool_name](**arguments)
    
    def list_available_tools(self) -> Dict[str, List[str]]:
        """List all tools available across servers."""
        tools = {}
        
        for name, server in self.servers.items():
            if hasattr(server, 'list_tools'):
                tools[name] = server.list_tools()
            else:
                # Introspect available methods
                methods = [m for m in dir(server) if not m.startswith('_')]
                tools[name] = methods
        
        return tools


# Global instances
tool_emulator = None
mcp_wrapper = None


def get_tool_emulator(executor: Callable = None) -> ToolEmulator:
    """Get tool emulator instance."""
    global tool_emulator
    if tool_emulator is None:
        tool_emulator = ToolEmulator(executor)
    return tool_emulator


def get_mcp_wrapper() -> MCPWrapper:
    """Get MCP wrapper instance."""
    global mcp_wrapper
    if mcp_wrapper is None:
        mcp_wrapper = MCPWrapper()
    return mcp_wrapper