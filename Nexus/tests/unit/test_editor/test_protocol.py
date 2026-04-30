"""Tests for the Editor Protocol — JSON-RPC bridge to editors."""

import json

import pytest

from nexus.editor.protocol import (
    EditorMessage,
    EditorProtocol,
    EditorServer,
    MessageType,
)


class TestMessageType:
    """Test MessageType enum."""

    def test_values(self):
        assert MessageType.REQUEST.value == "request"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.NOTIFICATION.value == "notification"
        assert MessageType.ERROR.value == "error"
        assert MessageType.STREAM.value == "stream"


class TestEditorMessage:
    """Test EditorMessage serialization."""

    def test_request_to_json(self):
        msg = EditorMessage(
            type=MessageType.REQUEST,
            method="chat/send",
            id=1,
            params={"message": "hello"},
        )
        j = json.loads(msg.to_json())
        assert j["jsonrpc"] == "2.0"
        assert j["id"] == 1
        assert j["method"] == "chat/send"
        assert j["params"]["message"] == "hello"

    def test_response_to_json(self):
        msg = EditorMessage(
            type=MessageType.RESPONSE,
            id=1,
            result={"content": "response text"},
        )
        j = json.loads(msg.to_json())
        assert j["id"] == 1
        assert j["result"]["content"] == "response text"

    def test_error_to_json(self):
        msg = EditorMessage(
            type=MessageType.ERROR,
            id=1,
            error={"code": -32601, "message": "Method not found"},
        )
        j = json.loads(msg.to_json())
        assert j["error"]["code"] == -32601

    def test_notification_to_json(self):
        msg = EditorMessage(
            type=MessageType.NOTIFICATION,
            method="file/changed",
            params={"path": "src/main.py"},
        )
        j = json.loads(msg.to_json())
        assert "id" not in j or j["id"] is None
        assert j["method"] == "file/changed"

    def test_from_json_request(self):
        data = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/list",
            "params": {},
        }
        msg = EditorMessage.from_json(data)
        assert msg.type == MessageType.REQUEST
        assert msg.id == 5
        assert msg.method == "tools/list"

    def test_from_json_response(self):
        data = {
            "jsonrpc": "2.0",
            "id": 5,
            "result": {"tools": ["shell", "file_read"]},
        }
        msg = EditorMessage.from_json(data)
        assert msg.type == MessageType.RESPONSE
        assert msg.id == 5

    def test_from_json_error(self):
        data = {
            "jsonrpc": "2.0",
            "id": 5,
            "error": {"code": -32600, "message": "Invalid"},
        }
        msg = EditorMessage.from_json(data)
        assert msg.type == MessageType.ERROR

    def test_from_json_notification(self):
        data = {
            "jsonrpc": "2.0",
            "method": "file/changed",
            "params": {"path": "x.py"},
        }
        msg = EditorMessage.from_json(data)
        assert msg.type == MessageType.NOTIFICATION
        assert msg.method == "file/changed"

    def test_from_json_string(self):
        raw = '{"jsonrpc":"2.0","id":1,"method":"test","params":{}}'
        msg = EditorMessage.from_json(raw)
        assert msg.method == "test"

    def test_from_json_invalid(self):
        with pytest.raises(ValueError):
            EditorMessage.from_json({"jsonrpc": "2.0"})

    def test_roundtrip(self):
        original = EditorMessage(
            type=MessageType.REQUEST,
            method="chat/send",
            id=42,
            params={"message": "hello"},
        )
        json_str = original.to_json()
        restored = EditorMessage.from_json(json_str)

        assert restored.method == "chat/send"
        assert restored.id == 42
        assert restored.params["message"] == "hello"


class TestEditorProtocol:
    """Test the protocol handler."""

    @pytest.fixture
    def protocol(self):
        return EditorProtocol()

    def test_register_handler(self, protocol):
        protocol.register_handler("test/method", lambda params: {"ok": True})
        assert protocol.has_handler("test/method")
        assert "test/method" in protocol.methods

    def test_no_handler(self, protocol):
        assert protocol.has_handler("nope") is False

    @pytest.mark.asyncio
    async def test_handle_request(self, protocol):
        protocol.register_handler("greet", lambda params: {"greeting": f"Hello {params.get('name', 'world')}"})

        msg = EditorMessage(
            type=MessageType.REQUEST,
            method="greet",
            id=1,
            params={"name": "Nexus"},
        )
        response = await protocol.handle(msg)

        assert response.type == MessageType.RESPONSE
        assert response.id == 1
        assert response.result["greeting"] == "Hello Nexus"

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self, protocol):
        msg = EditorMessage(
            type=MessageType.REQUEST,
            method="unknown/method",
            id=1,
        )
        response = await protocol.handle(msg)

        assert response.type == MessageType.ERROR
        assert response.error["code"] == -32601

    @pytest.mark.asyncio
    async def test_handle_async_handler(self, protocol):
        async def async_handler(params):
            return {"async": True}

        protocol.register_handler("async/test", async_handler)

        msg = EditorMessage(
            type=MessageType.REQUEST,
            method="async/test",
            id=1,
        )
        response = await protocol.handle(msg)

        assert response.type == MessageType.RESPONSE
        assert response.result["async"] is True

    @pytest.mark.asyncio
    async def test_handle_handler_error(self, protocol):
        def bad_handler(params):
            raise ValueError("Something went wrong")

        protocol.register_handler("bad", bad_handler)

        msg = EditorMessage(
            type=MessageType.REQUEST,
            method="bad",
            id=1,
        )
        response = await protocol.handle(msg)

        assert response.type == MessageType.ERROR
        assert "Something went wrong" in response.error["message"]

    @pytest.mark.asyncio
    async def test_handle_invalid_type(self, protocol):
        msg = EditorMessage(type=MessageType.RESPONSE, id=1)
        response = await protocol.handle(msg)
        assert response.type == MessageType.ERROR

    def test_make_request(self, protocol):
        msg = protocol.make_request("test/method", {"key": "value"})
        assert msg.type == MessageType.REQUEST
        assert msg.method == "test/method"
        assert msg.id is not None

    def test_make_notification(self, protocol):
        msg = protocol.make_notification("event", {"data": 123})
        assert msg.type == MessageType.NOTIFICATION
        assert msg.method == "event"

    def test_request_id_increments(self, protocol):
        msg1 = protocol.make_request("a")
        msg2 = protocol.make_request("b")
        assert msg2.id > msg1.id


class TestEditorServer:
    """Test the EditorServer."""

    @pytest.fixture
    def server(self, tmp_path):
        return EditorServer(workspace=str(tmp_path))

    @pytest.mark.asyncio
    async def test_initialize(self, server):
        msg = EditorMessage(
            type=MessageType.REQUEST,
            method="initialize",
            id=1,
        )
        response = await server.protocol.handle(msg)

        assert response.type == MessageType.RESPONSE
        result = response.result
        assert result["name"] == "nexus"
        assert "chat" in result["capabilities"]
        assert "diff_preview" in result["capabilities"]

    @pytest.mark.asyncio
    async def test_shutdown(self, server):
        msg = EditorMessage(
            type=MessageType.REQUEST,
            method="shutdown",
            id=1,
        )
        response = await server.protocol.handle(msg)
        assert response.result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_unimplemented_method(self, server):
        msg = EditorMessage(
            type=MessageType.REQUEST,
            method="chat/send",
            id=1,
            params={"message": "hello"},
        )
        response = await server.protocol.handle(msg)
        assert response.result["status"] == "not_implemented"

    def test_capabilities(self, server):
        caps = server.capabilities
        assert "methods" in caps
        assert "descriptions" in caps
        assert "chat/send" in caps["methods"]
        assert "diff/preview" in caps["methods"]
        assert "tools/list" in caps["methods"]
        assert "safety/audit" in caps["methods"]

    def test_method_catalog(self, server):
        catalog = EditorServer.METHOD_CATALOG
        assert len(catalog) > 10
        assert all(isinstance(v, str) for v in catalog.values())
