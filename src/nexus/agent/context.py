"""Context management for the Nexus agent.

Maintains the agent's working context: what it knows, what it's done,
and what's relevant for the current step. Manages the context window
to stay within LLM token limits.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from nexus.agent.models import Step

logger = logging.getLogger(__name__)

# Approximate token limits (characters ≈ tokens × 4)
DEFAULT_MAX_CONTEXT_CHARS = 12000  # ~3000 tokens, leaving room for system prompt


@dataclass
class ContextEntry:
    """A piece of context knowledge."""
    content: str
    source: str  # e.g., "step_result", "file_content", "user_input"
    priority: int = 1  # Higher = more important, kept longer
    char_count: int = 0

    def __post_init__(self) -> None:
        self.char_count = len(self.content)


class ContextManager:
    """Manages the agent's working context window.

    Combines multiple sources of context (goal, steps, file contents,
    memories) into a coherent prompt context that fits within token limits.
    """

    def __init__(self, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS):
        self.max_chars = max_chars
        self._goal: str = ""
        self._workspace_info: str = ""
        self._entries: deque[ContextEntry] = deque(maxlen=100)
        self._pinned: List[ContextEntry] = []  # Always included

    @property
    def goal(self) -> str:
        return self._goal

    @goal.setter
    def goal(self, value: str) -> None:
        self._goal = value

    @property
    def workspace_info(self) -> str:
        return self._workspace_info

    @workspace_info.setter
    def workspace_info(self, value: str) -> None:
        self._workspace_info = value

    def add(self, content: str, source: str, priority: int = 1) -> None:
        """Add a context entry."""
        self._entries.append(ContextEntry(content=content, source=source, priority=priority))

    def pin(self, content: str, source: str) -> None:
        """Pin a context entry (always included in context)."""
        self._pinned.append(ContextEntry(content=content, source=source, priority=10))

    def add_step(self, step: Step) -> None:
        """Add a completed step to context."""
        self.add(step.to_context(), source="step_result", priority=2)

    def add_file_content(self, path: str, content: str) -> None:
        """Add file content to context (truncated if needed)."""
        truncated = content[:2000]
        if len(content) > 2000:
            truncated += f"\n... [{len(content) - 2000} chars truncated]"
        self.add(
            f"File: {path}\n```\n{truncated}\n```",
            source="file_content",
            priority=1,
        )

    def build_prompt_context(self) -> str:
        """Build the full context string for LLM prompts.

        Assembles context in priority order within token budget:
        1. Goal (always)
        2. Pinned entries (always)
        3. Recent steps (high priority)
        4. Other entries by priority
        """
        parts: List[str] = []
        budget = self.max_chars

        # 1. Goal
        if self._goal:
            goal_text = f"Goal: {self._goal}"
            parts.append(goal_text)
            budget -= len(goal_text)

        # 2. Workspace info
        if self._workspace_info and budget > 500:
            ws_text = f"Workspace: {self._workspace_info}"
            parts.append(ws_text)
            budget -= len(ws_text)

        # 3. Pinned entries
        for entry in self._pinned:
            if budget <= 0:
                break
            parts.append(entry.content)
            budget -= entry.char_count

        # 4. Remaining entries by priority (most recent first within priority)
        sorted_entries = sorted(
            self._entries,
            key=lambda e: (e.priority, 0),  # Higher priority first
            reverse=True,
        )

        for entry in sorted_entries:
            if budget <= 0:
                break
            if entry.char_count <= budget:
                parts.append(entry.content)
                budget -= entry.char_count

        return "\n\n".join(parts)

    def get_recent_steps(self, n: int = 5) -> List[str]:
        """Get the N most recent step summaries."""
        step_entries = [
            e for e in self._entries if e.source == "step_result"
        ]
        return [e.content for e in list(step_entries)[-n:]]

    def clear(self) -> None:
        """Clear all non-pinned context."""
        self._entries.clear()
        self._goal = ""
        self._workspace_info = ""

    def summary(self) -> Dict[str, Any]:
        """Get context manager stats."""
        total_chars = sum(e.char_count for e in self._entries)
        return {
            "entries": len(self._entries),
            "pinned": len(self._pinned),
            "total_chars": total_chars,
            "budget_remaining": self.max_chars - total_chars,
            "has_goal": bool(self._goal),
        }
