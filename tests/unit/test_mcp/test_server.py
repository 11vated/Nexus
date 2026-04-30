"""Tests for nexus.mcp.server — MCP protocol handler."""
import pytest
from nexus.mcp.server import NexusMCPServer


@pytest.fixture
def server(tmp_path):
    return NexusMCPServer(workspace=str(tmp_path))


class TestMCPInitialize:
    @pytest.mark.asyncio
    async def test_initialize(self, server):
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        response = await server.handle_request(request)
        assert response["id"] == 1
        assert "protocolVersion" in response["result"]
        assert response["result"]["serverInfo"]["name"] == "nexus"

    @pytest.mark.asyncio
    async def test_initialized_notification(self, server):
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        response = await server.handle_request(request)
        assert response is None
        assert server.initialized is True


class TestMCPToolsList:
    @pytest.mark.asyncio
    async def test_tools_list(self, server):
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        response = await server.handle_request(request)
        tools = response["result"]["tools"]
        assert len(tools) > 0
        # Check structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    @pytest.mark.asyncio
    async def test_tools_have_expected_names(self, server):
        request = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        response = await server.handle_request(request)
        names = {t["name"] for t in response["result"]["tools"]}
        assert "shell" in names
        assert "file_read" in names
        assert "file_write" in names
        assert "search" in names


class TestMCPToolsCall:
    @pytest.mark.asyncio
    async def test_call_file_list(self, server, tmp_path):
        # Create a test file
        (tmp_path / "test.txt").write_text("hello")

        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "file_list",
                "arguments": {"path": "."},
            },
        }
        response = await server.handle_request(request)
        result = response["result"]
        assert result["isError"] is False
        assert "test.txt" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_call_file_write_and_read(self, server, tmp_path):
        # Write
        write_req = {
            "jsonrpc": "2.0", "id": 5,
            "method": "tools/call",
            "params": {"name": "file_write", "arguments": {"path": "mcp_test.txt", "content": "mcp works"}},
        }
        resp = await server.handle_request(write_req)
        assert resp["result"]["isError"] is False

        # Read back
        read_req = {
            "jsonrpc": "2.0", "id": 6,
            "method": "tools/call",
            "params": {"name": "file_read", "arguments": {"path": "mcp_test.txt"}},
        }
        resp = await server.handle_request(read_req)
        assert resp["result"]["isError"] is False
        assert "mcp works" in resp["result"]["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, server):
        request = {
            "jsonrpc": "2.0", "id": 7,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        }
        response = await server.handle_request(request)
        assert response["result"]["isError"] is True


class TestMCPProtocol:
    @pytest.mark.asyncio
    async def test_unknown_method(self, server):
        request = {"jsonrpc": "2.0", "id": 8, "method": "unknown/method", "params": {}}
        response = await server.handle_request(request)
        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_ping(self, server):
        request = {"jsonrpc": "2.0", "id": 9, "method": "ping", "params": {}}
        response = await server.handle_request(request)
        assert response["id"] == 9
        assert "result" in response
