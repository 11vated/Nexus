"""Nexus MCP (Model Context Protocol) — expose tools as an MCP server.

This allows external MCP clients (Claude, Cursor, etc.) to call
Nexus tools over stdin/stdout or HTTP.
"""

from nexus.mcp.server import NexusMCPServer

__all__ = ["NexusMCPServer"]
