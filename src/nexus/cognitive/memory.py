"""Multi-Memory Architecture — Mesh Memory Protocol.

A mesh of per-agent and shared memory banks with lineage tracking.
Each memory entry knows where it came from, who created it, and how
it has been accessed or modified.

This replaces simplistic "context window" approaches with structured,
persistent, agent-aware memory that supports:
- Per-agent private memory (working memory, scratchpad)
- Shared memory banks (project knowledge, decisions, user preferences)
- Memory lineage: trace how knowledge propagates between agents
- Episodic memory: session-specific memories that can become long-term
- Semantic memory: concept-level knowledge indexed by meaning
- Procedural memory: learned action patterns and preferences
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class MemoryType(Enum):
    """Types of memory in the mesh."""
    EPISODIC = "episodic"       # Session/event memories (what happened)
    SEMANTIC = "semantic"       # Factual knowledge (what we know)
    PROCEDURAL = "procedural"   # Action patterns (how we do things)
    WORKING = "working"         # Current task context (scratchpad)
    PREFERENCE = "preference"   # User/project preferences (learned behavior)


class MemoryScope(Enum):
    """Visibility of a memory entry."""
    PRIVATE = "private"         # Only the creating agent can see it
    SHARED = "shared"           # All agents can see it
    PROJECT = "project"         # Persists across sessions for this project
    GLOBAL = "global"           # Persists across all projects


@dataclass
class MemoryLineage:
    """Tracks how a memory entry was created and propagated."""
    created_by: str = ""        # Agent/user who created it
    created_at: float = field(default_factory=time.time)
    derived_from: List[str] = field(default_factory=list)  # Parent memory IDs
    propagated_to: List[str] = field(default_factory=list)  # Where it was shared
    version: int = 1
    modified_by: List[str] = field(default_factory=list)   # History of editors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created_by": self.created_by, "created_at": self.created_at,
            "derived_from": self.derived_from, "propagated_to": self.propagated_to,
            "version": self.version, "modified_by": self.modified_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryLineage":
        return cls(
            created_by=data.get("created_by", ""),
            created_at=data.get("created_at", time.time()),
            derived_from=data.get("derived_from", []),
            propagated_to=data.get("propagated_to", []),
            version=data.get("version", 1),
            modified_by=data.get("modified_by", []),
        )


@dataclass
class MemoryEntry:
    """A single memory in the mesh."""
    id: str = ""
    type: MemoryType = MemoryType.WORKING
    scope: MemoryScope = MemoryScope.PRIVATE
    content: str = ""
    summary: str = ""           # Short summary for listing
    tags: List[str] = field(default_factory=list)
    relevance: float = 1.0     # Current relevance score (decays over time)
    importance: float = 0.5    # How important this memory is (0-1)
    lineage: MemoryLineage = field(default_factory=MemoryLineage)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    def touch(self) -> None:
        """Mark as recently accessed."""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "type": self.type.value,
            "scope": self.scope.value, "content": self.content,
            "summary": self.summary, "tags": self.tags,
            "relevance": self.relevance, "importance": self.importance,
            "lineage": self.lineage.to_dict(), "metadata": self.metadata,
            "last_accessed": self.last_accessed, "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(
            id=data.get("id", ""),
            type=MemoryType(data.get("type", "working")),
            scope=MemoryScope(data.get("scope", "private")),
            content=data.get("content", ""),
            summary=data.get("summary", ""),
            tags=data.get("tags", []),
            relevance=data.get("relevance", 1.0),
            importance=data.get("importance", 0.5),
            lineage=MemoryLineage.from_dict(data.get("lineage", {})),
            metadata=data.get("metadata", {}),
            last_accessed=data.get("last_accessed", time.time()),
            access_count=data.get("access_count", 0),
        )


class MemoryBank:
    """A single memory bank (one per agent, plus shared banks).

    Banks can be:
    - Agent-private: only accessible by the owning agent
    - Shared: accessible by all agents
    - Project-scoped: persists across sessions
    """

    def __init__(self, owner: str = "", scope: MemoryScope = MemoryScope.PRIVATE):
        self.owner = owner
        self.scope = scope
        self._entries: Dict[str, MemoryEntry] = {}

    def store(self, entry: MemoryEntry) -> MemoryEntry:
        """Store a memory entry."""
        if not entry.id:
            import uuid
            entry.id = str(uuid.uuid4())[:10]
        entry.lineage.created_by = entry.lineage.created_by or self.owner
        self._entries[entry.id] = entry
        return entry

    def recall(self, memory_id: str) -> Optional[MemoryEntry]:
        """Recall a specific memory by ID."""
        entry = self._entries.get(memory_id)
        if entry:
            entry.touch()
        return entry

    def forget(self, memory_id: str) -> Optional[MemoryEntry]:
        """Remove a memory."""
        return self._entries.pop(memory_id, None)

    def search(self, *, query: Optional[str] = None,
               tags: Optional[List[str]] = None,
               memory_type: Optional[MemoryType] = None,
               min_relevance: float = 0.0,
               min_importance: float = 0.0,
               limit: int = 20) -> List[MemoryEntry]:
        """Search memories with filters."""
        results = []
        for entry in self._entries.values():
            if entry.relevance < min_relevance:
                continue
            if entry.importance < min_importance:
                continue
            if memory_type and entry.type != memory_type:
                continue
            if tags and not any(t in entry.tags for t in tags):
                continue
            if query and query.lower() not in entry.content.lower():
                continue
            results.append(entry)

        # Sort by relevance × importance
        results.sort(key=lambda e: e.relevance * e.importance, reverse=True)
        return results[:limit]

    @property
    def size(self) -> int:
        return len(self._entries)

    def all_entries(self) -> List[MemoryEntry]:
        return list(self._entries.values())

    def decay(self, rate: float = 0.01) -> int:
        """Apply relevance decay. Returns count of entries below threshold."""
        below = 0
        for entry in self._entries.values():
            if entry.type != MemoryType.PROCEDURAL:  # Procedural doesn't decay
                entry.relevance = max(0.0, entry.relevance - rate)
                if entry.relevance < 0.1:
                    below += 1
        return below

    def consolidate(self, min_relevance: float = 0.1) -> List[MemoryEntry]:
        """Remove low-relevance entries. Returns removed entries."""
        to_remove = [
            eid for eid, entry in self._entries.items()
            if entry.relevance < min_relevance and entry.importance < 0.5
        ]
        removed = []
        for eid in to_remove:
            entry = self._entries.pop(eid)
            removed.append(entry)
        return removed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "owner": self.owner,
            "scope": self.scope.value,
            "entries": [e.to_dict() for e in self._entries.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryBank":
        bank = cls(
            owner=data.get("owner", ""),
            scope=MemoryScope(data.get("scope", "private")),
        )
        for edata in data.get("entries", []):
            entry = MemoryEntry.from_dict(edata)
            bank._entries[entry.id] = entry
        return bank


class MemoryMesh:
    """The mesh connecting all memory banks with lineage tracking.

    Usage:
        mesh = MemoryMesh()

        # Create agent banks
        mesh.create_bank("developer", scope=MemoryScope.PRIVATE)
        mesh.create_bank("architect", scope=MemoryScope.PRIVATE)
        mesh.create_bank("shared", scope=MemoryScope.SHARED)

        # Store memories
        mesh.store("developer", MemoryEntry(
            type=MemoryType.WORKING,
            content="Found that auth.py uses deprecated API",
            tags=["auth", "deprecation"],
        ))

        # Propagate to shared bank
        mesh.propagate("developer", mem_id, "shared")

        # Search across visible banks
        results = mesh.search("developer", query="auth")
    """

    def __init__(self):
        self._banks: Dict[str, MemoryBank] = {}
        # Always create a shared bank
        self._banks["shared"] = MemoryBank(owner="system", scope=MemoryScope.SHARED)

    def create_bank(self, name: str, *,
                     scope: MemoryScope = MemoryScope.PRIVATE,
                     owner: str = "") -> MemoryBank:
        """Create a new memory bank."""
        bank = MemoryBank(owner=owner or name, scope=scope)
        self._banks[name] = bank
        return bank

    def get_bank(self, name: str) -> Optional[MemoryBank]:
        return self._banks.get(name)

    def remove_bank(self, name: str) -> bool:
        if name == "shared":
            return False  # Can't remove shared bank
        return self._banks.pop(name, None) is not None

    def store(self, bank_name: str, entry: MemoryEntry) -> Optional[MemoryEntry]:
        """Store a memory in a specific bank."""
        bank = self._banks.get(bank_name)
        if not bank:
            return None
        return bank.store(entry)

    def recall(self, bank_name: str, memory_id: str) -> Optional[MemoryEntry]:
        """Recall a memory from a specific bank."""
        bank = self._banks.get(bank_name)
        if not bank:
            return None
        return bank.recall(memory_id)

    def propagate(self, from_bank: str, memory_id: str,
                   to_bank: str) -> Optional[MemoryEntry]:
        """Propagate a memory from one bank to another.

        Creates a derived copy in the target bank with lineage tracking.
        """
        src = self._banks.get(from_bank)
        dst = self._banks.get(to_bank)
        if not src or not dst:
            return None

        original = src.recall(memory_id)
        if not original:
            return None

        # Create derived copy
        import uuid
        copy = MemoryEntry(
            id=str(uuid.uuid4())[:10],
            type=original.type,
            scope=dst.scope,
            content=original.content,
            summary=original.summary,
            tags=list(original.tags),
            relevance=original.relevance,
            importance=original.importance,
            lineage=MemoryLineage(
                created_by=src.owner,
                derived_from=[original.id],
                version=original.lineage.version + 1,
            ),
            metadata=dict(original.metadata),
        )

        # Track propagation
        original.lineage.propagated_to.append(f"{to_bank}:{copy.id}")

        return dst.store(copy)

    def search(self, agent_name: str, *,
               query: Optional[str] = None,
               tags: Optional[List[str]] = None,
               memory_type: Optional[MemoryType] = None,
               include_shared: bool = True,
               limit: int = 20) -> List[MemoryEntry]:
        """Search across all banks visible to an agent."""
        results = []

        # Agent's private bank
        if agent_name in self._banks:
            results.extend(self._banks[agent_name].search(
                query=query, tags=tags, memory_type=memory_type, limit=limit,
            ))

        # Shared banks
        if include_shared:
            for name, bank in self._banks.items():
                if name == agent_name:
                    continue
                if bank.scope in (MemoryScope.SHARED, MemoryScope.PROJECT, MemoryScope.GLOBAL):
                    results.extend(bank.search(
                        query=query, tags=tags, memory_type=memory_type, limit=limit,
                    ))

        # Deduplicate and sort
        seen = set()
        unique = []
        for entry in results:
            if entry.id not in seen:
                seen.add(entry.id)
                unique.append(entry)

        unique.sort(key=lambda e: e.relevance * e.importance, reverse=True)
        return unique[:limit]

    def decay_all(self, rate: float = 0.01) -> Dict[str, int]:
        """Apply relevance decay to all banks. Returns count below threshold per bank."""
        return {name: bank.decay(rate) for name, bank in self._banks.items()}

    def consolidate_all(self, min_relevance: float = 0.1) -> int:
        """Consolidate all banks. Returns total entries removed."""
        total = 0
        for bank in self._banks.values():
            total += len(bank.consolidate(min_relevance))
        return total

    @property
    def bank_names(self) -> List[str]:
        return list(self._banks.keys())

    @property
    def total_memories(self) -> int:
        return sum(bank.size for bank in self._banks.values())

    def stats(self) -> Dict[str, Any]:
        return {
            "banks": len(self._banks),
            "total_memories": self.total_memories,
            "per_bank": {name: bank.size for name, bank in self._banks.items()},
        }

    def summary(self) -> str:
        lines = [f"MemoryMesh: {len(self._banks)} banks, {self.total_memories} total memories"]
        for name, bank in self._banks.items():
            lines.append(f"  {name} ({bank.scope.value}): {bank.size} entries")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "banks": {name: bank.to_dict() for name, bank in self._banks.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryMesh":
        mesh = cls()
        mesh._banks = {}  # Clear default shared bank
        for name, bdata in data.get("banks", {}).items():
            mesh._banks[name] = MemoryBank.from_dict(bdata)
        # Ensure shared bank exists
        if "shared" not in mesh._banks:
            mesh._banks["shared"] = MemoryBank(owner="system", scope=MemoryScope.SHARED)
        return mesh
