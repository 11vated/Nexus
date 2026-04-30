"""Editor Protocol — JSON-RPC bridge between Nexus and editors.

Nexus isn't just a terminal tool. This protocol lets ANY editor
(VS Code, Cursor, Neovim, Sublime) talk to Nexus.

The protocol is simple JSON-RPC over stdio or TCP:

    → {"id": 1, "method": "chat/send", "params": {"message": "Fix this bug"}}
    ← {"id": 1, "result": {"type": "token", "content": "I'll look..."}}
    ← {"id": 1, "result": {"type": "token", "content": " at the code"}}
    ← {"id": 1, "result": {"type": "done"}}

Supported methods:
  - chat/send       — Send a message, stream response
  - chat/clear      — Clear conversation
  - chat/branch     — Create a conversation branch
  - diff/preview    — Get a diff before applying changes
  - diff/apply      — Apply a previewed diff
  - diff/reject     — Reject a diff
  - tools/list      — List available tools
  - tools/call      — Execute a tool directly
  - project/info    — Get project intelligence
  - session/save    — Save current session
  - session/load    — Load a saved session

This is designed to be editor-agnostic — the VS Code extension
just wraps this protocol with UI.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of protocol messages."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"
    STREAM = "stream"


@dataclass
class EditorMessage:
    """A single protocol message.

    Can be a request (from editor), response (from Nexus),
    notification (from either), or stream chunk.
    """
    type: MessageType
    method: str = ""                    # RPC method name
    id: Optional[int] = None           # Request ID (for req/resp pairing)
    params: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        """Serialize to JSON-RPC format."""
        msg: Dict[str, Any] = {}

        if self.type == MessageType.REQUEST:
            msg = {
                "jsonrpc": "2.0",
                "id": self.id,
                "method": self.method,
                "params": self.params,
            }
        elif self.type in (MessageType.RESPONSE, MessageType.STREAM):
            msg = {
                "jsonrpc": "2.0",
                "id": self.id,
                "result": self.result,
            }
        elif self.type == MessageType.ERROR:
            msg = {
                "jsonrpc": "2.0",
                "id": self.id,
                "error": self.error or {"code": -1, "message": "Unknown error"},
            }
        elif self.type == MessageType.NOTIFICATION:
            msg = {
                "jsonrpc": "2.0",
                "method": self.method,
                "params": self.params,
            }

        return json.dumps(msg)

    @classmethod
    def from_json(cls, data: str | dict) -> "EditorMessage":
        """Parse a JSON-RPC message."""
        if isinstance(data, str):
            data = json.loads(data)

        msg_id = data.get("id")

        if "method" in data:
            # Request or notification
            has_id = "id" in data
            return cls(
                type=MessageType.REQUEST if has_id else MessageType.NOTIFICATION,
                method=data["method"],
                id=msg_id,
                params=data.get("params", {}),
            )
        elif "result" in data:
            return cls(
                type=MessageType.RESPONSE,
                id=msg_id,
                result=data["result"],
            )
        elif "error" in data:
            return cls(
                type=MessageType.ERROR,
                id=msg_id,
                error=data["error"],
            )

        raise ValueError(f"Invalid JSON-RPC message: {data}")


class EditorProtocol:
    """Handles JSON-RPC method dispatch.

    Maps method names to handler functions. Handlers can be sync or async.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, Callable] = {}
        self._request_id = 0

    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a handler for a method."""
        self._handlers[method] = handler

    def has_handler(self, method: str) -> bool:
        """Check if a handler is registered."""
        return method in self._handlers

    @property
    def methods(self) -> List[str]:
        """List registered methods."""
        return list(self._handlers.keys())

    async def handle(self, message: EditorMessage) -> EditorMessage:
        """Handle an incoming message and return a response."""
        if message.type not in (MessageType.REQUEST, MessageType.NOTIFICATION):
            return EditorMessage(
                type=MessageType.ERROR,
                id=message.id,
                error={"code": -32600, "message": "Invalid request type"},
            )

        handler = self._handlers.get(message.method)
        if not handler:
            return EditorMessage(
                type=MessageType.ERROR,
                id=message.id,
                error={
                    "code": -32601,
                    "message": f"Method not found: {message.method}",
                    "data": {"available": self.methods},
                },
            )

        try:
            import asyncio
            result = handler(message.params)
            if asyncio.iscoroutine(result):
                result = await result

            return EditorMessage(
                type=MessageType.RESPONSE,
                id=message.id,
                result=result,
            )
        except Exception as exc:
            logger.error("Handler error for %s: %s", message.method, exc)
            return EditorMessage(
                type=MessageType.ERROR,
                id=message.id,
                error={"code": -32603, "message": str(exc)},
            )

    def make_request(self, method: str, params: Optional[Dict] = None) -> EditorMessage:
        """Create an outgoing request message."""
        self._request_id += 1
        return EditorMessage(
            type=MessageType.REQUEST,
            method=method,
            id=self._request_id,
            params=params or {},
        )

    def make_notification(self, method: str, params: Optional[Dict] = None) -> EditorMessage:
        """Create an outgoing notification (no response expected)."""
        return EditorMessage(
            type=MessageType.NOTIFICATION,
            method=method,
            params=params or {},
        )


class EditorServer:
    """Complete Nexus server for editor integration.

    Wires up the ChatSession, DiffEngine, and intelligence layer
    to the protocol, so editors get access to everything.
    """

    # All supported methods and their descriptions
    METHOD_CATALOG = {
        "chat/send": "Send a message to the chat session",
        "chat/clear": "Clear conversation history",
        "chat/stats": "Get session statistics",
        "chat/branch": "Create a conversation branch",
        "chat/switch": "Switch to a branch",
        "chat/branches": "List all branches",
        "diff/preview": "Preview a file diff",
        "diff/apply": "Apply a pending diff",
        "diff/reject": "Reject a pending diff",
        "diff/undo": "Undo the last applied diff",
        "diff/pending": "List pending diffs",
        "tools/list": "List available tools",
        "tools/call": "Execute a tool",
        "project/info": "Get project intelligence summary",
        "project/scan": "Re-scan the project",
        "session/save": "Save current session",
        "session/load": "Load a saved session",
        "session/list": "List saved sessions",
        "safety/audit": "Get tool audit log",
        "safety/trust": "Get or set trust level",
    }

    def __init__(
        self,
        workspace: str = ".",
        config: Optional[Any] = None,
    ):
        self.workspace = workspace
        self.config = config
        self.protocol = EditorProtocol()
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all method handlers."""
        # These are stub handlers — they get wired to real implementations
        # when the server starts with a ChatSession.

        self.protocol.register_handler("initialize", self._handle_initialize)
        self.protocol.register_handler("shutdown", self._handle_shutdown)

        # Register catalog methods as not-yet-implemented
        for method in self.METHOD_CATALOG:
            if not self.protocol.has_handler(method):
                self.protocol.register_handler(method, self._not_implemented)

    async def _handle_initialize(self, params: Dict) -> Dict:
        """Handle initialization handshake."""
        return {
            "name": "nexus",
            "version": "0.1.0",
            "capabilities": {
                "chat": True,
                "diff_preview": True,
                "branching": True,
                "project_intelligence": True,
                "safety": True,
            },
            "methods": list(self.METHOD_CATALOG.keys()),
        }

    async def _handle_shutdown(self, params: Dict) -> Dict:
        """Handle shutdown."""
        return {"status": "ok"}

    async def _not_implemented(self, params: Dict) -> Dict:
        """Placeholder for methods not yet wired."""
        return {"status": "not_implemented", "message": "Wire this to a ChatSession"}

    @property
    def capabilities(self) -> Dict[str, Any]:
        """Server capabilities for the initialize handshake."""
        return {
            "methods": list(self.METHOD_CATALOG.keys()),
            "descriptions": self.METHOD_CATALOG,
        }
