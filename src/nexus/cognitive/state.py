"""SharedState — the single observable object shared between human and AI.

Every stage of the Cognitive Loop reads from and writes to SharedState.
It holds the current goal, plan, reasoning trace, memory, preferences,
and all artifacts produced during the session.

SharedState is observable — components can subscribe to changes and
react automatically (TUI updates, hook triggers, memory writes).
"""
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .trace import ReasoningTrace


class ArtifactType(Enum):
    """Types of artifacts produced during a cognitive loop."""
    PLAN = "plan"
    DIFF = "diff"
    TEST_RESULT = "test_result"
    CODE = "code"
    ANALYSIS = "analysis"
    QUESTION = "question"
    FEEDBACK = "feedback"
    DECISION = "decision"


@dataclass
class PlanStep:
    """A single step in a structured plan.

    Plans are not plain text — they are structured cards with
    checkboxes, dependencies, and edit history.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    completed: bool = False
    approved: bool = False
    depends_on: List[str] = field(default_factory=list)  # IDs of prerequisite steps
    risk_level: str = "low"  # low, medium, high
    estimated_effort: str = ""  # e.g. "5 min", "30 min"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title,
            "description": self.description, "completed": self.completed,
            "approved": self.approved, "depends_on": self.depends_on,
            "risk_level": self.risk_level,
            "estimated_effort": self.estimated_effort,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Artifact:
    """A named artifact produced during the cognitive loop."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: ArtifactType = ArtifactType.CODE
    title: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "type": self.type.value,
            "title": self.title, "content": self.content,
            "metadata": self.metadata, "timestamp": self.timestamp,
        }


@dataclass
class Clarification:
    """A clarification question and its answer."""
    question: str = ""
    answer: str = ""
    resolved: bool = False
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Observer pattern for reactive updates
# ---------------------------------------------------------------------------

class _Observable:
    """Mixin that notifies subscribers when attributes change."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event: str, callback: Callable) -> None:
        """Subscribe to an event (e.g. 'goal_changed', 'plan_updated')."""
        self._listeners.setdefault(event, []).append(callback)

    def off(self, event: str, callback: Callable) -> None:
        """Unsubscribe from an event."""
        if event in self._listeners:
            self._listeners[event] = [
                cb for cb in self._listeners[event] if cb is not callback
            ]

    def emit(self, event: str, **kwargs) -> None:
        """Notify all subscribers of an event."""
        for cb in self._listeners.get(event, []):
            try:
                cb(event=event, **kwargs)
            except Exception:
                pass  # Listeners must not crash the loop

    @property
    def listener_count(self) -> int:
        return sum(len(cbs) for cbs in self._listeners.values())


class SharedState(_Observable):
    """The single shared state between human and AI in a cognitive loop.

    Observable — TUI widgets, hooks, and agents subscribe to changes.

    Usage:
        state = SharedState(goal="Refactor the auth module")

        # Subscribe to changes
        state.on("plan_updated", lambda **kw: print("Plan changed!"))

        # Add plan steps
        state.add_plan_step(PlanStep(title="Extract interface", risk_level="medium"))
        state.add_plan_step(PlanStep(title="Update callers", depends_on=[steps[0].id]))

        # AI records reasoning
        state.trace.observe("auth module has 3 concrete implementations")

        # User provides clarification
        state.add_clarification(Clarification(
            question="Should I preserve backward compatibility?",
            answer="Yes, keep the old interface as deprecated"
        ))
    """

    def __init__(self, *, goal: str = "", session_id: str = ""):
        super().__init__()
        self.session_id: str = session_id or str(uuid.uuid4())[:12]
        self.goal: str = goal
        self.constraints: List[str] = []
        self.plan_steps: List[PlanStep] = []
        self.artifacts: List[Artifact] = []
        self.clarifications: List[Clarification] = []
        self.trace: ReasoningTrace = ReasoningTrace()
        self.preferences: Dict[str, Any] = {}  # Loaded from .nexus/profile.yaml
        self.memory_context: List[str] = []  # Relevant memories for this session
        self.meta_reflections: List[str] = []  # Meta-cognitive reflections
        self._history: List[Dict[str, Any]] = []  # Audit log of all mutations
        self.created_at: float = time.time()

    # ─── Goal ──────────────────────────────────────────────────────

    def set_goal(self, goal: str) -> None:
        """Set or update the current goal."""
        old = self.goal
        self.goal = goal
        self._record("goal_changed", old_goal=old, new_goal=goal)
        self.emit("goal_changed", old_goal=old, new_goal=goal)

    def add_constraint(self, constraint: str) -> None:
        """Add a constraint to the current goal."""
        self.constraints.append(constraint)
        self._record("constraint_added", constraint=constraint)
        self.emit("constraint_added", constraint=constraint)

    # ─── Plan ──────────────────────────────────────────────────────

    def add_plan_step(self, step: PlanStep) -> PlanStep:
        """Add a step to the plan."""
        self.plan_steps.append(step)
        self._record("plan_step_added", step_id=step.id, title=step.title)
        self.emit("plan_updated", action="add", step=step)
        return step

    def remove_plan_step(self, step_id: str) -> Optional[PlanStep]:
        """Remove a step from the plan by ID."""
        for i, s in enumerate(self.plan_steps):
            if s.id == step_id:
                removed = self.plan_steps.pop(i)
                # Also remove from other steps' dependencies
                for other in self.plan_steps:
                    if step_id in other.depends_on:
                        other.depends_on.remove(step_id)
                self._record("plan_step_removed", step_id=step_id)
                self.emit("plan_updated", action="remove", step=removed)
                return removed
        return None

    def reorder_plan(self, step_ids: List[str]) -> None:
        """Reorder plan steps by providing new ID order."""
        id_map = {s.id: s for s in self.plan_steps}
        reordered = [id_map[sid] for sid in step_ids if sid in id_map]
        # Append any steps not in the new order at the end
        remaining = [s for s in self.plan_steps if s.id not in step_ids]
        self.plan_steps = reordered + remaining
        self._record("plan_reordered", new_order=step_ids)
        self.emit("plan_updated", action="reorder")

    def complete_step(self, step_id: str) -> bool:
        """Mark a plan step as completed."""
        for s in self.plan_steps:
            if s.id == step_id:
                s.completed = True
                self._record("plan_step_completed", step_id=step_id)
                self.emit("plan_updated", action="complete", step=s)
                return True
        return False

    def approve_step(self, step_id: str) -> bool:
        """User approves a plan step for execution."""
        for s in self.plan_steps:
            if s.id == step_id:
                s.approved = True
                self._record("plan_step_approved", step_id=step_id)
                self.emit("plan_updated", action="approve", step=s)
                return True
        return False

    def approve_all_steps(self) -> int:
        """Approve all unapproved plan steps. Returns count approved."""
        count = 0
        for s in self.plan_steps:
            if not s.approved:
                s.approved = True
                count += 1
        if count:
            self._record("plan_all_approved", count=count)
            self.emit("plan_updated", action="approve_all")
        return count

    def get_next_step(self) -> Optional[PlanStep]:
        """Get the next actionable step (approved, not completed, deps met)."""
        completed_ids = {s.id for s in self.plan_steps if s.completed}
        for s in self.plan_steps:
            if s.completed:
                continue
            if not s.approved:
                continue
            if all(dep in completed_ids for dep in s.depends_on):
                return s
        return None

    @property
    def plan_progress(self) -> tuple:
        """Returns (completed, total) plan step counts."""
        total = len(self.plan_steps)
        completed = sum(1 for s in self.plan_steps if s.completed)
        return completed, total

    # ─── Artifacts ─────────────────────────────────────────────────

    def add_artifact(self, artifact: Artifact) -> Artifact:
        """Add an artifact (diff, test result, analysis, etc.)."""
        self.artifacts.append(artifact)
        self._record("artifact_added", artifact_id=artifact.id, type=artifact.type.value)
        self.emit("artifact_added", artifact=artifact)
        return artifact

    def get_artifacts_by_type(self, artifact_type: ArtifactType) -> List[Artifact]:
        """Get all artifacts of a specific type."""
        return [a for a in self.artifacts if a.type == artifact_type]

    # ─── Clarifications ────────────────────────────────────────────

    def add_clarification(self, clarification: Clarification) -> Clarification:
        """Record a clarification Q&A."""
        self.clarifications.append(clarification)
        self._record("clarification_added", question=clarification.question)
        self.emit("clarification_added", clarification=clarification)
        return clarification

    @property
    def pending_clarifications(self) -> List[Clarification]:
        """Get unanswered clarification questions."""
        return [c for c in self.clarifications if not c.resolved]

    # ─── Meta-Cognitive Reflection ─────────────────────────────────

    def add_reflection(self, reflection: str) -> None:
        """Add a meta-cognitive reflection (agent reasoning about its reasoning)."""
        self.meta_reflections.append(reflection)
        self._record("reflection_added", reflection=reflection)
        self.emit("reflection_added", reflection=reflection)

    # ─── Serialization ─────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire shared state."""
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "constraints": self.constraints,
            "plan_steps": [s.to_dict() for s in self.plan_steps],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "clarifications": [
                {"question": c.question, "answer": c.answer, "resolved": c.resolved}
                for c in self.clarifications
            ],
            "trace": self.trace.to_dict(),
            "preferences": self.preferences,
            "memory_context": self.memory_context,
            "meta_reflections": self.meta_reflections,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SharedState":
        """Deserialize shared state."""
        state = cls(
            goal=data.get("goal", ""),
            session_id=data.get("session_id", ""),
        )
        state.constraints = data.get("constraints", [])
        state.plan_steps = [PlanStep.from_dict(s) for s in data.get("plan_steps", [])]
        state.preferences = data.get("preferences", {})
        state.memory_context = data.get("memory_context", [])
        state.meta_reflections = data.get("meta_reflections", [])
        state.created_at = data.get("created_at", time.time())
        if "trace" in data:
            state.trace = ReasoningTrace.from_dict(data["trace"])
        return state

    # ─── History / Audit ───────────────────────────────────────────

    def _record(self, action: str, **kwargs) -> None:
        """Record a mutation in the audit log."""
        self._history.append({
            "action": action,
            "timestamp": time.time(),
            **kwargs,
        })

    @property
    def history(self) -> List[Dict[str, Any]]:
        """Full audit log of all state mutations."""
        return list(self._history)

    def summary(self) -> str:
        """Human-readable summary of current state."""
        completed, total = self.plan_progress
        lines = [
            f"Goal: {self.goal or '(not set)'}",
            f"Plan: {completed}/{total} steps completed",
            f"Artifacts: {len(self.artifacts)}",
            f"Clarifications: {len(self.clarifications)} ({len(self.pending_clarifications)} pending)",
            f"Trace: {len(self.trace)} nodes",
            f"Reflections: {len(self.meta_reflections)}",
        ]
        return "\n".join(lines)
