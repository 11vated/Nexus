"""Reasoning Trace System — structured record of AI decision-making.

Every decision the AI makes is recorded as a TraceNode in a directed graph.
Each node captures:
  - What triggered the decision (observation)
  - What alternatives were considered (and why rejected)
  - What evidence informed the choice
  - Confidence level
  - Causal links to parent decisions

The trace is browsable, searchable, and editable by the user.
When a user corrects the trace ("No, that's wrong because..."),
the correction becomes a memory for future sessions.
"""
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TraceNodeType(Enum):
    """Types of reasoning trace nodes."""
    OBSERVATION = "observation"       # Something the AI noticed
    HYPOTHESIS = "hypothesis"         # A theory about what's happening
    DECISION = "decision"             # A choice the AI made
    ALTERNATIVE = "alternative"       # An option that was considered but rejected
    EVIDENCE = "evidence"             # Data supporting a decision
    ACTION = "action"                 # Something the AI did
    OUTCOME = "outcome"               # Result of an action
    CORRECTION = "correction"         # User override of AI reasoning
    CHECKPOINT = "checkpoint"         # State boundary marker


@dataclass
class TraceNode:
    """A single node in the reasoning trace.

    Forms a directed acyclic graph where each node can have
    multiple parents (causal predecessors) and children (effects).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: TraceNodeType = TraceNodeType.OBSERVATION
    content: str = ""
    detail: str = ""                  # Extended explanation
    confidence: float = 0.5           # 0.0 to 1.0
    timestamp: float = field(default_factory=time.time)
    parent_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # For ALTERNATIVE nodes: why it was rejected
    rejection_reason: str = ""

    # For CORRECTION nodes: what the user said
    user_feedback: str = ""

    # Visual state
    collapsed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "detail": self.detail,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "parent_ids": self.parent_ids,
            "metadata": self.metadata,
            "rejection_reason": self.rejection_reason,
            "user_feedback": self.user_feedback,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceNode":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            type=TraceNodeType(data.get("type", "observation")),
            content=data.get("content", ""),
            detail=data.get("detail", ""),
            confidence=data.get("confidence", 0.5),
            timestamp=data.get("timestamp", time.time()),
            parent_ids=data.get("parent_ids", []),
            metadata=data.get("metadata", {}),
            rejection_reason=data.get("rejection_reason", ""),
            user_feedback=data.get("user_feedback", ""),
        )


class ReasoningTrace:
    """Directed acyclic graph of reasoning steps.

    The trace records the AI's complete thought process:
    observations → hypotheses → decisions → actions → outcomes.

    Users can browse, search, and correct the trace. Corrections
    become memories that influence future sessions.

    Usage:
        trace = ReasoningTrace()

        # AI observes something
        obs = trace.observe("Function cache_evict doesn't release lock on error")

        # AI forms hypothesis
        hyp = trace.hypothesize(
            "Adding a finally block will fix the lock leak",
            parent_ids=[obs.id],
            confidence=0.85
        )

        # AI considers alternatives
        alt = trace.consider_alternative(
            "Refactor to use context manager instead",
            rejection_reason="More invasive change, cache_evict is called from 12 places",
            parent_ids=[obs.id],
            confidence=0.6
        )

        # AI decides
        dec = trace.decide(
            "Add finally block to release lock",
            parent_ids=[hyp.id, alt.id],
            confidence=0.9
        )

        # AI acts
        act = trace.record_action(
            "Added try/finally to cache_evict()",
            parent_ids=[dec.id],
            metadata={"tool": "file_write", "file": "cache.py"}
        )

        # User corrects
        trace.correct(
            dec.id,
            "Actually, the context manager approach is better because "
            "we're planning to refactor cache_evict anyway"
        )
    """

    def __init__(self):
        self._nodes: Dict[str, TraceNode] = {}
        self._root_ids: List[str] = []  # Nodes with no parents
        self._corrections: List[str] = []  # IDs of correction nodes

    @property
    def nodes(self) -> Dict[str, TraceNode]:
        """All nodes in the trace."""
        return dict(self._nodes)

    @property
    def root_ids(self) -> List[str]:
        """IDs of root nodes (no parents)."""
        return list(self._root_ids)

    @property
    def corrections(self) -> List[TraceNode]:
        """All user corrections."""
        return [self._nodes[nid] for nid in self._corrections if nid in self._nodes]

    def __len__(self) -> int:
        return len(self._nodes)

    def _add_node(self, node: TraceNode) -> TraceNode:
        """Add a node to the trace."""
        self._nodes[node.id] = node
        if not node.parent_ids:
            self._root_ids.append(node.id)
        return node

    def get(self, node_id: str) -> Optional[TraceNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def children_of(self, node_id: str) -> List[TraceNode]:
        """Get all direct children of a node."""
        return [
            n for n in self._nodes.values()
            if node_id in n.parent_ids
        ]

    def ancestors_of(self, node_id: str) -> List[TraceNode]:
        """Get all ancestors (transitive parents) of a node."""
        result = []
        visited = set()
        queue = list(self._nodes.get(node_id, TraceNode()).parent_ids)
        while queue:
            pid = queue.pop(0)
            if pid in visited or pid not in self._nodes:
                continue
            visited.add(pid)
            parent = self._nodes[pid]
            result.append(parent)
            queue.extend(parent.parent_ids)
        return result

    def path_to(self, node_id: str) -> List[TraceNode]:
        """Get the path from root to a specific node."""
        ancestors = self.ancestors_of(node_id)
        node = self._nodes.get(node_id)
        if not node:
            return []
        # Sort by timestamp to get chronological path
        path = sorted(ancestors + [node], key=lambda n: n.timestamp)
        return path

    # ─── Convenience Builders ──────────────────────────────────────

    def observe(self, content: str, *, detail: str = "",
                parent_ids: Optional[List[str]] = None,
                metadata: Optional[Dict[str, Any]] = None) -> TraceNode:
        """Record an observation."""
        return self._add_node(TraceNode(
            type=TraceNodeType.OBSERVATION,
            content=content,
            detail=detail,
            confidence=1.0,  # Observations are facts
            parent_ids=parent_ids or [],
            metadata=metadata or {},
        ))

    def hypothesize(self, content: str, *, confidence: float = 0.5,
                    detail: str = "",
                    parent_ids: Optional[List[str]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> TraceNode:
        """Record a hypothesis."""
        return self._add_node(TraceNode(
            type=TraceNodeType.HYPOTHESIS,
            content=content,
            detail=detail,
            confidence=confidence,
            parent_ids=parent_ids or [],
            metadata=metadata or {},
        ))

    def decide(self, content: str, *, confidence: float = 0.8,
               detail: str = "",
               parent_ids: Optional[List[str]] = None,
               metadata: Optional[Dict[str, Any]] = None) -> TraceNode:
        """Record a decision."""
        return self._add_node(TraceNode(
            type=TraceNodeType.DECISION,
            content=content,
            detail=detail,
            confidence=confidence,
            parent_ids=parent_ids or [],
            metadata=metadata or {},
        ))

    def consider_alternative(self, content: str, *,
                              rejection_reason: str = "",
                              confidence: float = 0.3,
                              parent_ids: Optional[List[str]] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> TraceNode:
        """Record an alternative that was considered but rejected."""
        return self._add_node(TraceNode(
            type=TraceNodeType.ALTERNATIVE,
            content=content,
            rejection_reason=rejection_reason,
            confidence=confidence,
            parent_ids=parent_ids or [],
            metadata=metadata or {},
        ))

    def record_action(self, content: str, *, detail: str = "",
                      parent_ids: Optional[List[str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> TraceNode:
        """Record an action taken."""
        return self._add_node(TraceNode(
            type=TraceNodeType.ACTION,
            content=content,
            detail=detail,
            confidence=1.0,
            parent_ids=parent_ids or [],
            metadata=metadata or {},
        ))

    def record_outcome(self, content: str, *, success: bool = True,
                       detail: str = "",
                       parent_ids: Optional[List[str]] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> TraceNode:
        """Record the outcome of an action."""
        return self._add_node(TraceNode(
            type=TraceNodeType.OUTCOME,
            content=content,
            detail=detail,
            confidence=1.0,
            parent_ids=parent_ids or [],
            metadata={**(metadata or {}), "success": success},
        ))

    def checkpoint(self, label: str, *,
                   parent_ids: Optional[List[str]] = None) -> TraceNode:
        """Mark a state boundary in the cognitive loop."""
        return self._add_node(TraceNode(
            type=TraceNodeType.CHECKPOINT,
            content=label,
            confidence=1.0,
            parent_ids=parent_ids or [],
        ))

    def correct(self, target_node_id: str, feedback: str) -> TraceNode:
        """User corrects an AI decision.

        Creates a CORRECTION node linked to the target node.
        The correction is stored as a memory for future sessions.
        """
        node = self._add_node(TraceNode(
            type=TraceNodeType.CORRECTION,
            content=f"Correction for: {self._nodes.get(target_node_id, TraceNode()).content}",
            user_feedback=feedback,
            confidence=1.0,
            parent_ids=[target_node_id],
        ))
        self._corrections.append(node.id)
        return node

    # ─── Search & Filter ──────────────────────────────────────────

    def filter_by_type(self, node_type: TraceNodeType) -> List[TraceNode]:
        """Get all nodes of a specific type."""
        return [n for n in self._nodes.values() if n.type == node_type]

    def filter_by_confidence(self, min_confidence: float = 0.0,
                              max_confidence: float = 1.0) -> List[TraceNode]:
        """Get nodes within a confidence range."""
        return [
            n for n in self._nodes.values()
            if min_confidence <= n.confidence <= max_confidence
        ]

    def search(self, query: str) -> List[TraceNode]:
        """Search nodes by content (case-insensitive)."""
        q = query.lower()
        return [
            n for n in self._nodes.values()
            if q in n.content.lower() or q in n.detail.lower()
        ]

    # ─── Serialization ────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire trace."""
        return {
            "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
            "root_ids": self._root_ids,
            "corrections": self._corrections,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningTrace":
        """Deserialize a trace."""
        trace = cls()
        for nid, ndata in data.get("nodes", {}).items():
            node = TraceNode.from_dict(ndata)
            trace._nodes[nid] = node
        trace._root_ids = data.get("root_ids", [])
        trace._corrections = data.get("corrections", [])
        return trace

    def summary(self) -> str:
        """Human-readable summary of the trace."""
        type_counts = {}
        for n in self._nodes.values():
            t = n.type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        lines = [f"ReasoningTrace: {len(self._nodes)} nodes"]
        for t, count in sorted(type_counts.items()):
            lines.append(f"  {t}: {count}")
        if self._corrections:
            lines.append(f"  user corrections: {len(self._corrections)}")
        return "\n".join(lines)
