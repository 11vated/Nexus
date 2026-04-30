"""Stratified Knowledge Architecture — multi-layer knowledge with membranes.

Inspired by the ALMA (Abstraction-Level Membrane Architecture) framework.
Knowledge is organized into 5 layers of increasing abstraction, with
selectively permeable membranes controlling information flow between layers.

Layers:
    0: Syntax & Types        — concrete tokens, signatures, type definitions
    1: Control & Data Flow   — call graphs, data dependencies, module relationships
    2: Design Patterns       — repository pattern, factory, event sourcing, etc.
    3: Domain Concepts       — business logic, domain terminology, invariants
    4: Intent & Philosophy   — why the codebase exists, design decisions, principles

Membranes:
    Each membrane controls what information can flow UP (generalize) or
    DOWN (specialize). The Developer agent operates primarily at Layers 0-2,
    the Architect at Layers 2-4, but insights can cross boundaries.

This is NOT a traditional vector database. It is a structured, layered
knowledge graph where the abstraction level determines how information
is stored, retrieved, and shared between agents.
"""
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Set


class KnowledgeLayer(IntEnum):
    """The five layers of the knowledge stratification."""
    SYNTAX = 0          # Concrete code: tokens, types, signatures
    FLOW = 1            # Control flow, data flow, call graphs
    PATTERNS = 2        # Design patterns, architectural styles
    DOMAIN = 3          # Domain concepts, business logic
    INTENT = 4          # Design philosophy, principles, "why"


# Layer descriptions for UI/display
LAYER_DESCRIPTIONS = {
    KnowledgeLayer.SYNTAX: "Syntax & Types — concrete code tokens, signatures, type definitions",
    KnowledgeLayer.FLOW: "Control & Data Flow — call graphs, dependencies, module relationships",
    KnowledgeLayer.PATTERNS: "Design Patterns — architectural styles, common abstractions",
    KnowledgeLayer.DOMAIN: "Domain Concepts — business logic, domain terminology, invariants",
    KnowledgeLayer.INTENT: "Intent & Philosophy — design decisions, principles, \"why\" behind code",
}


@dataclass
class KnowledgeEntry:
    """A single piece of knowledge at a specific abstraction layer.

    Knowledge entries are tagged with their layer and can reference
    other entries (cross-layer or within-layer).
    """
    id: str = ""
    layer: KnowledgeLayer = KnowledgeLayer.SYNTAX
    content: str = ""
    source: str = ""            # Where this knowledge came from (file, agent, user)
    confidence: float = 1.0     # How certain we are (0-1)
    tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)  # IDs of related entries
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "layer": self.layer.value,
            "content": self.content, "source": self.source,
            "confidence": self.confidence, "tags": self.tags,
            "references": self.references, "metadata": self.metadata,
            "created_at": self.created_at, "last_accessed": self.last_accessed,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        return cls(
            id=data.get("id", ""),
            layer=KnowledgeLayer(data.get("layer", 0)),
            content=data.get("content", ""),
            source=data.get("source", ""),
            confidence=data.get("confidence", 1.0),
            tags=data.get("tags", []),
            references=data.get("references", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            last_accessed=data.get("last_accessed", time.time()),
            access_count=data.get("access_count", 0),
        )


@dataclass
class MembraneRule:
    """A rule controlling knowledge flow between layers.

    Membranes are selectively permeable: they allow certain types of
    knowledge to flow up (generalize) or down (specialize) while
    blocking others.
    """
    name: str = ""
    from_layer: KnowledgeLayer = KnowledgeLayer.SYNTAX
    to_layer: KnowledgeLayer = KnowledgeLayer.FLOW
    direction: str = "up"       # "up" (generalize) or "down" (specialize)
    allowed_tags: List[str] = field(default_factory=list)   # Empty = allow all
    blocked_tags: List[str] = field(default_factory=list)   # Tags that can't cross
    transform: Optional[str] = None   # Name of transform function to apply
    enabled: bool = True

    def allows(self, entry: KnowledgeEntry) -> bool:
        """Check if an entry can pass through this membrane."""
        if not self.enabled:
            return False
        if self.blocked_tags:
            if any(tag in self.blocked_tags for tag in entry.tags):
                return False
        if self.allowed_tags:
            return any(tag in self.allowed_tags for tag in entry.tags)
        return True  # No restrictions = allow all


class KnowledgeStore:
    """Multi-layer knowledge store with membrane-controlled flow.

    The store organizes knowledge into 5 abstraction layers (0-4).
    Membranes control what information can flow between layers.

    Usage:
        store = KnowledgeStore()

        # Add knowledge at different layers
        store.add(KnowledgeEntry(
            id="fn-parse_config",
            layer=KnowledgeLayer.SYNTAX,
            content="def parse_config(path: str) -> Config",
            source="parser.py",
            tags=["function", "parser"],
        ))

        store.add(KnowledgeEntry(
            id="pattern-factory",
            layer=KnowledgeLayer.PATTERNS,
            content="ConfigFactory creates Config objects from various sources",
            source="architecture-review",
            tags=["pattern", "factory", "config"],
        ))

        # Query within a layer
        syntax = store.query(layer=KnowledgeLayer.SYNTAX, tags=["parser"])

        # Query across layers (membrane-controlled)
        related = store.query_cross_layer(
            entry_id="fn-parse_config",
            target_layer=KnowledgeLayer.PATTERNS,
        )

        # Get layer summary for an agent
        architect_view = store.layer_summary(
            layers=[KnowledgeLayer.PATTERNS, KnowledgeLayer.DOMAIN, KnowledgeLayer.INTENT]
        )
    """

    def __init__(self):
        # Knowledge entries indexed by layer
        self._layers: Dict[KnowledgeLayer, Dict[str, KnowledgeEntry]] = {
            layer: {} for layer in KnowledgeLayer
        }
        # All entries indexed by ID for fast lookup
        self._index: Dict[str, KnowledgeEntry] = {}
        # Membrane rules
        self._membranes: List[MembraneRule] = []
        # Transform functions
        self._transforms: Dict[str, Callable] = {}
        # Default membranes
        self._init_default_membranes()

    def _init_default_membranes(self):
        """Set up default membrane rules between adjacent layers."""
        # By default, knowledge can flow freely between adjacent layers
        for i in range(4):
            lower = KnowledgeLayer(i)
            upper = KnowledgeLayer(i + 1)
            # Upward flow (generalization)
            self._membranes.append(MembraneRule(
                name=f"{lower.name}→{upper.name}",
                from_layer=lower, to_layer=upper,
                direction="up",
            ))
            # Downward flow (specialization)
            self._membranes.append(MembraneRule(
                name=f"{upper.name}→{lower.name}",
                from_layer=upper, to_layer=lower,
                direction="down",
            ))

    # ─── CRUD ──────────────────────────────────────────────────────

    def add(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """Add a knowledge entry to the appropriate layer."""
        if not entry.id:
            import uuid
            entry.id = str(uuid.uuid4())[:10]
        self._layers[entry.layer][entry.id] = entry
        self._index[entry.id] = entry
        return entry

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get an entry by ID (from any layer)."""
        entry = self._index.get(entry_id)
        if entry:
            entry.last_accessed = time.time()
            entry.access_count += 1
        return entry

    def remove(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Remove an entry by ID."""
        entry = self._index.pop(entry_id, None)
        if entry:
            self._layers[entry.layer].pop(entry_id, None)
        return entry

    def update(self, entry_id: str, **kwargs) -> Optional[KnowledgeEntry]:
        """Update fields of an existing entry."""
        entry = self._index.get(entry_id)
        if not entry:
            return None
        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)
        return entry

    # ─── Query ─────────────────────────────────────────────────────

    def query(self, *, layer: Optional[KnowledgeLayer] = None,
              tags: Optional[List[str]] = None,
              source: Optional[str] = None,
              min_confidence: float = 0.0,
              search: Optional[str] = None,
              limit: int = 50) -> List[KnowledgeEntry]:
        """Query knowledge entries with filters.

        Args:
            layer: Filter by specific layer
            tags: Filter by tags (any match)
            source: Filter by source
            min_confidence: Minimum confidence threshold
            search: Text search in content (case-insensitive)
            limit: Maximum results
        """
        if layer is not None:
            candidates = list(self._layers[layer].values())
        else:
            candidates = list(self._index.values())

        results = []
        for entry in candidates:
            if entry.confidence < min_confidence:
                continue
            if tags and not any(t in entry.tags for t in tags):
                continue
            if source and entry.source != source:
                continue
            if search and search.lower() not in entry.content.lower():
                continue
            results.append(entry)
            if len(results) >= limit:
                break

        return results

    def query_cross_layer(self, entry_id: str,
                           target_layer: KnowledgeLayer) -> List[KnowledgeEntry]:
        """Find related knowledge in another layer, respecting membranes.

        Traces references and membrane rules to find knowledge in the
        target layer that is related to the given entry.
        """
        entry = self._index.get(entry_id)
        if not entry:
            return []

        # Direct references that are in the target layer
        direct = [
            self._index[ref_id]
            for ref_id in entry.references
            if ref_id in self._index and self._index[ref_id].layer == target_layer
        ]

        # Check if membrane allows crossing
        if entry.layer != target_layer:
            direction = "up" if target_layer > entry.layer else "down"
            # Find relevant membrane
            membrane = self._find_membrane(entry.layer, target_layer, direction)
            if membrane and not membrane.allows(entry):
                return []  # Membrane blocks this

        # Also find entries with matching tags in target layer
        tag_matches = self.query(
            layer=target_layer,
            tags=entry.tags[:3],  # Use first 3 tags
            limit=10,
        )

        # Combine, deduplicate, and return
        seen = set()
        results = []
        for e in direct + tag_matches:
            if e.id not in seen:
                seen.add(e.id)
                results.append(e)

        return results

    def _find_membrane(self, from_layer: KnowledgeLayer,
                        to_layer: KnowledgeLayer,
                        direction: str) -> Optional[MembraneRule]:
        """Find the membrane rule between two layers."""
        for m in self._membranes:
            if (m.from_layer == from_layer and
                m.to_layer == to_layer and
                m.direction == direction):
                return m
        return None

    # ─── Agent Views ───────────────────────────────────────────────

    def layer_summary(self, layers: Optional[List[KnowledgeLayer]] = None) -> Dict[str, Any]:
        """Get a summary of knowledge by layer.

        Used to give different agents different views:
        - Developer: layers [0, 1, 2]
        - Architect: layers [2, 3, 4]
        - Reviewer: all layers
        """
        target_layers = layers or list(KnowledgeLayer)
        summary = {}
        for layer in target_layers:
            entries = self._layers[layer]
            summary[layer.name] = {
                "count": len(entries),
                "description": LAYER_DESCRIPTIONS[layer],
                "top_tags": self._top_tags(entries),
                "sources": list(set(e.source for e in entries.values() if e.source)),
            }
        return summary

    def _top_tags(self, entries: Dict[str, KnowledgeEntry], n: int = 5) -> List[str]:
        """Get the most common tags in a set of entries."""
        tag_counts: Dict[str, int] = {}
        for e in entries.values():
            for tag in e.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return sorted(tag_counts, key=tag_counts.get, reverse=True)[:n]

    # ─── Membrane Management ──────────────────────────────────────

    def add_membrane(self, rule: MembraneRule) -> None:
        """Add a custom membrane rule."""
        self._membranes.append(rule)

    def get_membranes(self) -> List[MembraneRule]:
        """Get all membrane rules."""
        return list(self._membranes)

    def disable_membrane(self, name: str) -> bool:
        """Disable a membrane by name."""
        for m in self._membranes:
            if m.name == name:
                m.enabled = False
                return True
        return False

    def enable_membrane(self, name: str) -> bool:
        """Enable a membrane by name."""
        for m in self._membranes:
            if m.name == name:
                m.enabled = True
                return True
        return False

    # ─── Stats & Serialization ─────────────────────────────────────

    @property
    def total_entries(self) -> int:
        return len(self._index)

    def layer_counts(self) -> Dict[str, int]:
        return {layer.name: len(entries) for layer, entries in self._layers.items()}

    def prune(self, *, max_age_s: float = 86400 * 30,
              min_access_count: int = 0) -> int:
        """Remove stale entries. Returns count removed."""
        now = time.time()
        to_remove = []
        for entry_id, entry in self._index.items():
            age = now - entry.last_accessed
            if age > max_age_s and entry.access_count <= min_access_count:
                to_remove.append(entry_id)
        for eid in to_remove:
            self.remove(eid)
        return len(to_remove)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire knowledge store."""
        return {
            "entries": [e.to_dict() for e in self._index.values()],
            "membranes": [
                {
                    "name": m.name, "from_layer": m.from_layer.value,
                    "to_layer": m.to_layer.value, "direction": m.direction,
                    "allowed_tags": m.allowed_tags, "blocked_tags": m.blocked_tags,
                    "enabled": m.enabled,
                }
                for m in self._membranes
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeStore":
        """Deserialize a knowledge store."""
        store = cls()
        # Replace default membranes with serialized ones if present
        if "membranes" in data:
            store._membranes = []
        for edata in data.get("entries", []):
            store.add(KnowledgeEntry.from_dict(edata))
        for mdata in data.get("membranes", []):
            store._membranes.append(MembraneRule(
                name=mdata.get("name", ""),
                from_layer=KnowledgeLayer(mdata.get("from_layer", 0)),
                to_layer=KnowledgeLayer(mdata.get("to_layer", 1)),
                direction=mdata.get("direction", "up"),
                allowed_tags=mdata.get("allowed_tags", []),
                blocked_tags=mdata.get("blocked_tags", []),
                enabled=mdata.get("enabled", True),
            ))
        return store

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [f"KnowledgeStore: {self.total_entries} entries across {len(KnowledgeLayer)} layers"]
        for layer in KnowledgeLayer:
            count = len(self._layers[layer])
            if count:
                lines.append(f"  Layer {layer.value} ({layer.name}): {count} entries")
        lines.append(f"  Membranes: {len(self._membranes)} rules")
        return "\n".join(lines)
