"""Cognitive Integration — wires all cognitive modules into ChatSession.

This module provides the CognitiveLayer that integrates:
- CognitiveLoop: state machine for structured collaboration
- SharedState: observable plan/artifact container
- ReasoningTrace: DAG of AI reasoning steps
- KnowledgeStore: stratified project knowledge
- DesignVerifier: architecture constraint checking
- AmbiguityDetector: underspecification detection
- MemoryMesh: multi-agent memory with lineage

The integration is designed to be non-intrusive: ChatSession works fine
without it (plain chat), but when cognitive mode is active, every user
message flows through the cognitive pipeline first.
"""
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .loop import CognitiveLoop, CognitiveState, _AutoApproveHuman, LoopMetrics
from .state import SharedState, PlanStep, Artifact, ArtifactType, Clarification
from .trace import ReasoningTrace, TraceNode, TraceNodeType
from .knowledge import KnowledgeStore, KnowledgeEntry, KnowledgeLayer
from .verification import (
    DesignVerifier, DesignConstraint, ConstraintSeverity, VerificationReport,
)
from .clarification import (
    AmbiguityDetector, AmbiguitySignal, ClarificationDialog, AmbiguityType,
)
from .memory import MemoryMesh, MemoryBank, MemoryEntry, MemoryType, MemoryScope

logger = logging.getLogger(__name__)


class CognitiveMode(Enum):
    """How deeply cognitive features are engaged."""
    OFF = "off"              # Pure chat — no cognitive pipeline
    PASSIVE = "passive"      # Detect ambiguity + trace reasoning, no enforced loop
    GUIDED = "guided"        # Full cognitive loop: UNDERSTAND→PROPOSE→...→REVIEW
    AUTONOMOUS = "autonomous"  # Cognitive loop + auto-approve (testing/CI)


@dataclass
class CognitiveEvent:
    """An event from the cognitive layer during a chat turn."""
    event: str               # "ambiguity_detected", "plan_proposed", "trace_updated", etc.
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class CognitiveLayer:
    """Integrates all cognitive modules for use by ChatSession.

    Usage:
        layer = CognitiveLayer(workspace="/my/project")
        layer.mode = CognitiveMode.PASSIVE

        # During a chat turn:
        events = layer.analyze_message("Refactor auth module")
        # → may produce ambiguity signals, knowledge lookups, etc.

        events = layer.before_tool_call("file_write", {"path": "...", "content": "..."})
        # → may produce verification warnings

        layer.after_tool_call("file_write", {"path": "..."}, result="ok")
        # → updates knowledge store, traces, memory
    """

    def __init__(self, workspace: str = "."):
        self.workspace = workspace
        self.mode = CognitiveMode.PASSIVE

        # Core modules
        self.loop = CognitiveLoop(human=_AutoApproveHuman(), max_cycles=10)
        self.state = self.loop.state
        self.trace = ReasoningTrace()
        self.knowledge = KnowledgeStore()
        self.verifier = DesignVerifier()
        self.detector = AmbiguityDetector()
        self.memory = MemoryMesh()

        # Session memory bank
        self.memory.create_bank("session", scope=MemoryScope.PRIVATE, owner="nexus")

        # Load built-in verification constraints
        self.verifier.load_builtin()

        # Stats
        self._messages_analyzed = 0
        self._ambiguities_detected = 0
        self._verifications_run = 0
        self._knowledge_queries = 0

    # -----------------------------------------------------------------------
    # Message analysis — run before the LLM generates a response
    # -----------------------------------------------------------------------

    def analyze_message(self, message: str, *,
                        context: Optional[Dict[str, Any]] = None) -> List[CognitiveEvent]:
        """Analyze an incoming user message through the cognitive pipeline.

        In PASSIVE mode: detect ambiguity, search knowledge/memory
        In GUIDED mode: also advance the cognitive loop state

        Returns a list of events that ChatSession can act on.
        """
        self._messages_analyzed += 1
        events: List[CognitiveEvent] = []

        if self.mode == CognitiveMode.OFF:
            return events

        # 1. Check for ambiguity
        if self.detector.quick_check(message):
            signals = self.detector.analyze(message, min_confidence=0.5)
            if signals:
                self._ambiguities_detected += 1
                dialog = self.detector.generate_dialog(message, signals=signals, max_questions=3)
                events.append(CognitiveEvent(
                    event="ambiguity_detected",
                    data={
                        "signals": [{"type": s.type.value, "confidence": s.confidence,
                                     "description": s.description} for s in signals],
                        "dialog": dialog.to_dict(),
                        "question_count": len(dialog.questions),
                    },
                ))

        # 2. Search knowledge for relevant context
        relevant = self.knowledge.query(search=message, limit=5)
        if relevant:
            self._knowledge_queries += 1
            events.append(CognitiveEvent(
                event="knowledge_retrieved",
                data={
                    "entries": [{"id": e.id, "layer": e.layer.value,
                                 "content": e.content[:200]} for e in relevant],
                    "count": len(relevant),
                },
            ))

        # 3. Search memory for related past context
        memories = self.memory.search("session", query=message, limit=3)
        if memories:
            events.append(CognitiveEvent(
                event="memory_recalled",
                data={
                    "memories": [{"id": m.id, "type": m.type.value,
                                  "summary": m.summary or m.content[:100]} for m in memories],
                    "count": len(memories),
                },
            ))

        # 4. Add reasoning trace node
        self.trace.observe(
            f"User message: {message[:200]}",
            detail=f"Turn {self._messages_analyzed}",
            metadata=context or {},
        )

        # 5. In GUIDED mode, update the cognitive loop
        if self.mode == CognitiveMode.GUIDED:
            if self.loop.current == CognitiveState.IDLE:
                self.loop.set_goal(message)
                events.append(CognitiveEvent(
                    event="goal_set",
                    data={"goal": message, "state": "understand"},
                ))
            elif self.loop.current == CognitiveState.PAUSED:
                events.append(CognitiveEvent(
                    event="loop_resumed",
                    data={"state": self.loop.current.value, "input": message[:100]},
                ))

        # 6. Store as episodic memory
        self.memory.store("session", MemoryEntry(
            type=MemoryType.EPISODIC,
            content=message,
            summary=f"User turn {self._messages_analyzed}",
            tags=["user_message"],
            importance=0.5,
        ))

        return events

    # -----------------------------------------------------------------------
    # Pre/Post tool call hooks
    # -----------------------------------------------------------------------

    def before_tool_call(self, tool_name: str,
                          args: Dict[str, Any]) -> List[CognitiveEvent]:
        """Run cognitive checks before a tool executes.

        Primarily: verify file writes against design constraints.
        """
        events: List[CognitiveEvent] = []

        if self.mode == CognitiveMode.OFF:
            return events

        # Verify file writes against design constraints
        if tool_name == "file_write" and "content" in args and "path" in args:
            self._verifications_run += 1
            report = self.verifier.verify({args["path"]: args["content"]})
            if report.violations:
                events.append(CognitiveEvent(
                    event="verification_warning",
                    data={
                        "report": report.to_dict(),
                        "summary": report.summary(),
                        "passed": report.passed,
                        "error_count": report.error_count,
                        "warning_count": report.warning_count,
                    },
                ))

        # Trace the tool call
        self.trace.record_action(
            f"Tool call: {tool_name}",
            detail=", ".join(f"{k}={repr(v)[:50]}" for k, v in args.items()),
            metadata={"tool": tool_name, "args_keys": list(args.keys())},
        )

        return events

    def after_tool_call(self, tool_name: str, args: Dict[str, Any],
                         result: str, *, success: bool = True) -> List[CognitiveEvent]:
        """Update cognitive state after a tool execution.

        - Record result in trace
        - Update knowledge store if relevant
        - Store in memory
        """
        events: List[CognitiveEvent] = []

        if self.mode == CognitiveMode.OFF:
            return events

        # Trace the result
        self.trace.record_outcome(
            f"Tool result ({tool_name}): {result[:300]}",
            success=success,
            metadata={"tool": tool_name},
        )

        # Store tool execution in memory
        self.memory.store("session", MemoryEntry(
            type=MemoryType.PROCEDURAL,
            content=f"{tool_name}: {result[:500]}",
            summary=f"Executed {tool_name}" + (" ✓" if success else " ✗"),
            tags=["tool_execution", tool_name],
            importance=0.6 if success else 0.8,  # Failures are more important to remember
        ))

        # Learn from file reads — add to knowledge store
        if tool_name == "file_read" and success and "path" in args:
            path = args["path"]
            # Determine knowledge layer from content
            layer = KnowledgeLayer.SYNTAX  # Default to lowest layer
            if any(kw in result.lower() for kw in ["class", "def", "import", "function"]):
                layer = KnowledgeLayer.FLOW
            if any(kw in result.lower() for kw in ["pattern", "factory", "singleton", "observer"]):
                layer = KnowledgeLayer.PATTERNS

            self.knowledge.add(KnowledgeEntry(
                layer=layer,
                content=f"File {path}: {result[:300]}",
                tags=[path.split("/")[-1] if "/" in path else path],
                confidence=0.8,
            ))

        return events

    # -----------------------------------------------------------------------
    # Response analysis — run after the LLM generates a response
    # -----------------------------------------------------------------------

    def analyze_response(self, response: str) -> List[CognitiveEvent]:
        """Analyze the AI's response through the cognitive lens.

        - Trace the reasoning
        - Check for plan proposals
        - Store as episodic memory
        """
        events: List[CognitiveEvent] = []

        if self.mode == CognitiveMode.OFF:
            return events

        # Trace the response
        self.trace.hypothesize(
            f"AI response: {response[:300]}",
            confidence=0.7,
            metadata={"response_length": len(response)},
        )

        # Store as episodic memory
        self.memory.store("session", MemoryEntry(
            type=MemoryType.EPISODIC,
            content=response[:500],
            summary=f"AI response (turn {self._messages_analyzed})",
            tags=["ai_response"],
            importance=0.4,
        ))

        return events

    # -----------------------------------------------------------------------
    # Cognitive loop controls
    # -----------------------------------------------------------------------

    def set_mode(self, mode: str) -> str:
        """Set the cognitive mode. Returns confirmation."""
        try:
            self.mode = CognitiveMode(mode.lower())
            return f"Cognitive mode: {self.mode.value}"
        except ValueError:
            return f"Unknown mode '{mode}'. Options: off, passive, guided, autonomous"

    def get_plan(self) -> List[Dict[str, Any]]:
        """Get the current cognitive plan steps."""
        return [s.to_dict() for s in self.state.plan_steps]

    def get_trace_summary(self) -> str:
        """Get a summary of the reasoning trace."""
        nodes = self.trace.nodes  # Dict[str, TraceNode]
        if not nodes:
            return "No reasoning trace yet."
        node_list = list(nodes.values())
        lines = [f"Reasoning trace ({len(node_list)} nodes):"]
        for n in node_list[-10:]:  # Last 10
            lines.append(f"  [{n.type.value}] {n.content[:80]}")
        if len(node_list) > 10:
            lines.insert(1, f"  ... ({len(node_list) - 10} earlier nodes)")
        return "\n".join(lines)

    def get_knowledge_summary(self) -> str:
        """Get knowledge store summary."""
        return self.knowledge.summary()

    def get_memory_summary(self) -> str:
        """Get memory mesh summary."""
        return self.memory.summary()

    def get_verification_status(self) -> Dict[str, Any]:
        """Get verification constraint summary."""
        return {
            "constraints": len(self.verifier.constraints),
            "categories": list({c.category.value for c in self.verifier.constraints if c.category}),
            "verifications_run": self._verifications_run,
        }

    # -----------------------------------------------------------------------
    # Knowledge management
    # -----------------------------------------------------------------------

    def learn(self, content: str, *, layer: str = "domain",
              tags: Optional[List[str]] = None) -> str:
        """Explicitly teach Nexus something. Returns entry ID."""
        try:
            kl = KnowledgeLayer(layer)
        except ValueError:
            kl = KnowledgeLayer.DOMAIN

        entry = self.knowledge.add(KnowledgeEntry(
            layer=kl,
            content=content,
            tags=tags or [],
            confidence=1.0,  # Explicit teaching = full confidence
        ))
        return entry.id

    def remember(self, content: str, *, memory_type: str = "semantic",
                  tags: Optional[List[str]] = None,
                  importance: float = 0.7) -> str:
        """Explicitly store a memory. Returns memory ID."""
        try:
            mt = MemoryType(memory_type)
        except ValueError:
            mt = MemoryType.SEMANTIC

        entry = self.memory.store("session", MemoryEntry(
            type=mt,
            content=content,
            tags=tags or [],
            importance=importance,
        ))
        return entry.id if entry else ""

    # -----------------------------------------------------------------------
    # Prompt augmentation
    # -----------------------------------------------------------------------

    def get_context_augmentation(self, message: str) -> str:
        """Generate additional system prompt context from cognitive modules.

        This is injected into the system prompt to give the LLM access to
        cognitive state, relevant knowledge, and memory.
        """
        if self.mode == CognitiveMode.OFF:
            return ""

        sections = []

        # Cognitive loop state
        if self.mode == CognitiveMode.GUIDED:
            state = self.loop.current.value
            goal = self.state.goal
            if goal:
                sections.append(
                    f"[Cognitive Loop] State: {state} | Goal: {goal}\n"
                    f"You are in a structured collaboration cycle. "
                    f"Current phase: {state.upper()}."
                )

        # Relevant knowledge
        relevant = self.knowledge.query(search=message, limit=3)
        if relevant:
            knowledge_text = "\n".join(f"- {e.content[:150]}" for e in relevant)
            sections.append(f"[Relevant Knowledge]\n{knowledge_text}")

        # Recent memories
        memories = self.memory.search("session", query=message, limit=2)
        if memories:
            memory_text = "\n".join(f"- {m.content[:150]}" for m in memories)
            sections.append(f"[Related Memory]\n{memory_text}")

        # Active plan
        if self.state.plan_steps:
            pending = [s for s in self.state.plan_steps if not s.completed]
            if pending:
                plan_text = "\n".join(
                    f"  {'☐' if not s.completed else '☑'} {s.title}"
                    for s in self.state.plan_steps[:5]
                )
                sections.append(f"[Active Plan]\n{plan_text}")

        if not sections:
            return ""

        return "\n\n".join(sections) + "\n"

    # -----------------------------------------------------------------------
    # Stats & Serialization
    # -----------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Full cognitive layer statistics."""
        return {
            "mode": self.mode.value,
            "loop_state": self.loop.current.value,
            "messages_analyzed": self._messages_analyzed,
            "ambiguities_detected": self._ambiguities_detected,
            "verifications_run": self._verifications_run,
            "knowledge_queries": self._knowledge_queries,
            "trace_nodes": len(self.trace.nodes),
            "knowledge_entries": self.knowledge.total_entries,
            "total_memories": self.memory.total_memories,
            "loop_metrics": self.loop.metrics.to_dict(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the full cognitive state."""
        return {
            "mode": self.mode.value,
            "state": self.state.to_dict(),
            "trace": self.trace.to_dict(),
            "knowledge": self.knowledge.to_dict(),
            "memory": self.memory.to_dict(),
            "stats": {
                "messages_analyzed": self._messages_analyzed,
                "ambiguities_detected": self._ambiguities_detected,
                "verifications_run": self._verifications_run,
                "knowledge_queries": self._knowledge_queries,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], workspace: str = ".") -> "CognitiveLayer":
        """Restore cognitive state from serialized data."""
        layer = cls(workspace=workspace)
        layer.mode = CognitiveMode(data.get("mode", "passive"))
        layer.state = SharedState.from_dict(data.get("state", {}))
        layer.loop.state = layer.state
        layer.trace = ReasoningTrace.from_dict(data.get("trace", {}))
        layer.knowledge = KnowledgeStore.from_dict(data.get("knowledge", {}))
        layer.memory = MemoryMesh.from_dict(data.get("memory", {}))
        stats = data.get("stats", {})
        layer._messages_analyzed = stats.get("messages_analyzed", 0)
        layer._ambiguities_detected = stats.get("ambiguities_detected", 0)
        layer._verifications_run = stats.get("verifications_run", 0)
        layer._knowledge_queries = stats.get("knowledge_queries", 0)
        return layer
