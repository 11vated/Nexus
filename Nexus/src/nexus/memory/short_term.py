"""Short-term memory — conversation window and recent context.

Manages the immediate working memory of the agent: recent messages,
step results, and observations within the current session.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    """A single memory entry."""
    content: str
    role: str  # "user", "agent", "tool", "system"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> Dict[str, str]:
        """Convert to LLM message format."""
        role_map = {
            "user": "user",
            "agent": "assistant",
            "tool": "user",  # Tool results appear as user context
            "system": "system",
        }
        return {
            "role": role_map.get(self.role, "user"),
            "content": self.content,
        }


class ShortTermMemory:
    """Rolling window of recent interactions.

    Keeps the last N entries and provides methods to convert
    them into LLM message format for chat completions.
    """

    def __init__(self, window_size: int = 20):
        self._entries: deque[MemoryEntry] = deque(maxlen=window_size)
        self.window_size = window_size

    def add(
        self,
        content: str,
        role: str = "agent",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add an entry to short-term memory."""
        self._entries.append(
            MemoryEntry(
                content=content,
                role=role,
                metadata=metadata or {},
            )
        )

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.add(content, role="user")

    def add_agent_response(self, content: str) -> None:
        """Add an agent response."""
        self.add(content, role="agent")

    def add_tool_result(self, tool_name: str, result: str) -> None:
        """Add a tool execution result."""
        self.add(
            f"[Tool: {tool_name}]\n{result}",
            role="tool",
            metadata={"tool": tool_name},
        )

    def to_messages(self) -> List[Dict[str, str]]:
        """Convert memory to LLM message format."""
        return [entry.to_message() for entry in self._entries]

    def to_context_string(self) -> str:
        """Convert memory to a single context string."""
        parts = []
        for entry in self._entries:
            prefix = {"user": "User", "agent": "Agent", "tool": "Tool", "system": "System"}
            parts.append(f"[{prefix.get(entry.role, entry.role)}]: {entry.content}")
        return "\n\n".join(parts)

    def get_recent(self, n: int = 5) -> List[MemoryEntry]:
        """Get the N most recent entries."""
        entries = list(self._entries)
        return entries[-n:]

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()

    def save(self, path: str) -> None:
        """Save memory to a JSON file."""
        data = [asdict(entry) for entry in self._entries]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str) -> None:
        """Load memory from a JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            self._entries.clear()
            for item in data:
                self._entries.append(MemoryEntry(**item))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def total_chars(self) -> int:
        return sum(len(e.content) for e in self._entries)
