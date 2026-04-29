"""Context store — task-specific knowledge accumulation.

Derived from the ContextStore pattern in agent-system/profound_system.py.
Accumulates knowledge during a task and provides relevant context
for each step based on role and recency.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContextEntry:
    """A piece of accumulated context."""
    content: str
    role: str  # Which agent role produced this
    category: str  # e.g., "plan", "code", "test_result", "reflection"
    timestamp: float = field(default_factory=time.time)
    relevance_tags: List[str] = field(default_factory=list)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp


class ContextStore:
    """Task-specific context accumulation.

    Tracks knowledge gathered during a task execution session.
    Provides filtered retrieval by role, category, or relevance.
    """

    def __init__(self, max_entries: int = 200):
        self._entries: List[ContextEntry] = []
        self._by_category: Dict[str, List[ContextEntry]] = defaultdict(list)
        self._by_role: Dict[str, List[ContextEntry]] = defaultdict(list)
        self.max_entries = max_entries

    def add(
        self,
        content: str,
        role: str = "agent",
        category: str = "general",
        tags: Optional[List[str]] = None,
    ) -> None:
        """Add a context entry.

        Args:
            content: The context content.
            role: Which role produced this (planner, developer, etc).
            category: Category (plan, code, test_result, etc).
            tags: Optional relevance tags for retrieval.
        """
        entry = ContextEntry(
            content=content,
            role=role,
            category=category,
            relevance_tags=tags or [],
        )
        self._entries.append(entry)
        self._by_category[category].append(entry)
        self._by_role[role].append(entry)

        # Evict old entries if over limit
        if len(self._entries) > self.max_entries:
            self._evict()

    def _evict(self) -> None:
        """Remove oldest, lowest-priority entries."""
        # Keep the newest max_entries
        self._entries = self._entries[-self.max_entries:]
        # Rebuild indices
        self._by_category.clear()
        self._by_role.clear()
        for entry in self._entries:
            self._by_category[entry.category].append(entry)
            self._by_role[entry.role].append(entry)

    def get_by_category(self, category: str, limit: int = 10) -> List[ContextEntry]:
        """Get entries by category, most recent first."""
        entries = self._by_category.get(category, [])
        return list(reversed(entries[-limit:]))

    def get_by_role(self, role: str, limit: int = 10) -> List[ContextEntry]:
        """Get entries by role, most recent first."""
        entries = self._by_role.get(role, [])
        return list(reversed(entries[-limit:]))

    def get_relevant(
        self,
        query: str,
        limit: int = 10,
        max_age_seconds: Optional[float] = None,
    ) -> List[ContextEntry]:
        """Get entries relevant to a query.

        Uses keyword matching on content and tags.
        Optionally filters by age.
        """
        query_words = set(query.lower().split())

        scored: List[tuple[float, ContextEntry]] = []
        for entry in self._entries:
            if max_age_seconds and entry.age_seconds > max_age_seconds:
                continue

            # Score by keyword overlap
            content_words = set(entry.content.lower().split())
            tag_words = set(t.lower() for t in entry.relevance_tags)
            all_words = content_words | tag_words

            overlap = len(query_words & all_words)
            if overlap > 0:
                # Boost recent entries
                recency_factor = 1.0 / (1.0 + entry.age_seconds / 300)
                score = overlap * (1.0 + recency_factor)
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def get_recent(self, limit: int = 10) -> List[ContextEntry]:
        """Get the most recent entries."""
        return list(reversed(self._entries[-limit:]))

    def build_context_string(
        self,
        limit: int = 10,
        categories: Optional[List[str]] = None,
    ) -> str:
        """Build a context string for LLM prompts.

        Args:
            limit: Maximum entries to include.
            categories: Filter by categories (None = all).

        Returns:
            Formatted context string.
        """
        entries = self._entries[-limit:]
        if categories:
            entries = [e for e in entries if e.category in categories]

        if not entries:
            return ""

        parts = []
        for entry in entries[-limit:]:
            parts.append(f"[{entry.role}/{entry.category}] {entry.content}")
        return "\n".join(parts)

    def clear(self) -> None:
        """Clear all context."""
        self._entries.clear()
        self._by_category.clear()
        self._by_role.clear()

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def categories(self) -> List[str]:
        return list(self._by_category.keys())

    def summary(self) -> Dict[str, Any]:
        """Get store statistics."""
        return {
            "total_entries": len(self._entries),
            "categories": {k: len(v) for k, v in self._by_category.items()},
            "roles": {k: len(v) for k, v in self._by_role.items()},
        }
