"""Editor Protocol — connect Nexus to VS Code, Cursor, or any editor.

Instead of being locked into a terminal, Nexus can speak to editors
via a simple JSON-RPC protocol over stdio or TCP.

This is the foundation for "AI that lives in your editor."
"""

from nexus.editor.protocol import (
    EditorMessage,
    EditorProtocol,
    EditorServer,
    MessageType,
)

__all__ = [
    "EditorMessage",
    "EditorProtocol",
    "EditorServer",
    "MessageType",
]
