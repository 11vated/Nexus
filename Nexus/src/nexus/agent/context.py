"""Context management for the Nexus agent.

Maintains the agent's working context: what it knows, what it's done,
and what's relevant for the current step. Manages the context window
to stay within LLM token limits.

Supports the 5-stage Context Compaction Pipeline for long conversations.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

    Supports the 5-stage compaction pipeline when context exceeds thresholds.
    """

    def __init__(self, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS):
        self.max_chars = max_chars
        self._goal: str = ""
        self._workspace_info: str = ""
        self._entries: deque[ContextEntry] = deque(maxlen=100)
        self._pinned: List[ContextEntry] = []  # Always included
        # Compaction pipeline state
        self._compaction_summary: str = ""
        self._compaction_residual: Optional[Any] = None

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

    @property
    def compaction_summary(self) -> str:
        """Summary from the last compaction, if any."""
        return self._compaction_summary

    @property
    def compaction_residual(self) -> Optional[Any]:
        """Residual state from the last compaction, if any."""
        return self._compaction_residual

    def set_compaction_state(self, summary: str, residual: Optional[Any] = None) -> None:
        """Set the compaction summary and residual state.

        Called after the compaction pipeline runs.
        """
        self._compaction_summary = summary
        self._compaction_residual = residual

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

    def needs_compaction(self, history_chars: int, model_window: int = 16000) -> bool:
        """Check if the combined context exceeds compaction threshold.

        Args:
            history_chars: Character count of conversation history.
            model_window: Model's context window in characters.

        Returns:
            True if compaction should be triggered.
        """
        # Calculate current context size
        context_chars = self._current_chars()
        total = history_chars + context_chars
        threshold = int(model_window * 0.70)
        return total > threshold

    def _current_chars(self) -> int:
        """Calculate total characters in current context."""
        total = 0
        if self._goal:
            total += len(f"Goal: {self._goal}")
        if self._workspace_info:
            total += len(f"Workspace: {self._workspace_info}")
        for entry in self._pinned:
            total += entry.char_count
        for entry in self._entries:
            total += entry.char_count
        return total

    def build_prompt_context(self, include_compaction_state: bool = True) -> str:
        """Build the full context string for LLM prompts.

        Assembles context in priority order within token budget:
        1. Goal (always)
        2. Compaction residual state (if available)
        3. Compaction summary (if available)
        4. Pinned entries (always)
        5. Recent steps (high priority)
        6. Other entries by priority
        """
        parts: List[str] = []
        budget = self.max_chars

        # 1. Goal
        if self._goal:
            goal_text = f"Goal: {self._goal}"
            parts.append(goal_text)
            budget -= len(goal_text)

        # 2. Compaction residual state
        if include_compaction_state and self._compaction_residual:
            residual_text = self._compaction_residual.to_prompt()
            if residual_text and len(residual_text) < budget:
                parts.append(residual_text)
                budget -= len(residual_text)

        # 3. Compaction summary
        if include_compaction_state and self._compaction_summary:
            summary_text = f"[Previous conversation summary]\n{self._compaction_summary}"
            if len(summary_text) < budget:
                parts.append(summary_text)
                budget -= len(summary_text)

        # 4. Workspace info
        if self._workspace_info and budget > 500:
            ws_text = f"Workspace: {self._workspace_info}"
            parts.append(ws_text)
            budget -= len(ws_text)

        # 5. Pinned entries
        for entry in self._pinned:
            if budget <= 0:
                break
            parts.append(entry.content)
            budget -= entry.char_count

        # 6. Remaining entries by priority (most recent first within priority)
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

    def clear(self, keep_compaction_state: bool = True) -> None:
        """Clear all non-pinned context.

        Args:
            keep_compaction_state: Whether to preserve compaction summary/residual.
        """
        self._entries.clear()
        self._goal = ""
        self._workspace_info = ""
        if not keep_compaction_state:
            self._compaction_summary = ""
            self._compaction_residual = None

    def summary(self) -> Dict[str, Any]:
        """Get context manager stats."""
        total_chars = sum(e.char_count for e in self._entries)
        result = {
            "entries": len(self._entries),
            "pinned": len(self._pinned),
            "total_chars": total_chars,
            "budget_remaining": self.max_chars - total_chars,
            "has_goal": bool(self._goal),
        }
        if self._compaction_summary:
            result["compaction_summary_chars"] = len(self._compaction_summary)
        if self._compaction_residual:
            result["has_residual_state"] = True
        return result
