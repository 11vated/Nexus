"""Cognitive Loop Engine — the core state machine for human-AI partnership.

Replaces the linear Plan→Act→Observe→Reflect pipeline with an open,
collaborative loop where every stage is a shared state between human and AI.

The Cognitive Loop:
    UNDERSTAND → PROPOSE → DISCUSS → REFINE → EXECUTE → REVIEW
         ↑                                           │
         └───────────────────────────────────────────┘

Key principle: The AI never advances to the next state without human
awareness and consent. Not because it's less capable, but because
partnership requires transparency.

Each state has:
  - An AI action (what the AI does in this state)
  - A human role (what the human can do)
  - Shared artifacts (what both can see and edit)
  - Transition conditions (when to move to the next state)

The CognitiveLoop also implements a meta-cognitive reflection phase
(inspired by CRDAL) where the agent reasons about its own reasoning
before executing any plan.
"""
import asyncio
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Protocol

from .state import SharedState, PlanStep, Artifact, ArtifactType, Clarification
from .trace import ReasoningTrace, TraceNodeType


class CognitiveState(Enum):
    """States of the Cognitive Loop."""
    IDLE = "idle"                # No active goal
    UNDERSTAND = "understand"    # AI asks clarifying questions
    PROPOSE = "propose"          # AI generates structured plan
    DISCUSS = "discuss"          # AI explains reasoning, answers questions
    REFINE = "refine"            # AI updates plan based on discussion
    EXECUTE = "execute"          # AI performs steps with checkpoints
    REVIEW = "review"            # AI summarizes, human gives feedback
    PAUSED = "paused"            # Waiting for human input
    ERROR = "error"              # Something went wrong


# Allowed transitions
_TRANSITIONS = {
    CognitiveState.IDLE: {CognitiveState.UNDERSTAND},
    CognitiveState.UNDERSTAND: {CognitiveState.PROPOSE, CognitiveState.PAUSED},
    CognitiveState.PROPOSE: {CognitiveState.DISCUSS, CognitiveState.PAUSED},
    CognitiveState.DISCUSS: {CognitiveState.REFINE, CognitiveState.PROPOSE, CognitiveState.PAUSED},
    CognitiveState.REFINE: {CognitiveState.EXECUTE, CognitiveState.DISCUSS, CognitiveState.PAUSED},
    CognitiveState.EXECUTE: {CognitiveState.REVIEW, CognitiveState.PAUSED, CognitiveState.ERROR},
    CognitiveState.REVIEW: {CognitiveState.IDLE, CognitiveState.UNDERSTAND, CognitiveState.REFINE},
    CognitiveState.PAUSED: {
        CognitiveState.UNDERSTAND, CognitiveState.PROPOSE, CognitiveState.DISCUSS,
        CognitiveState.REFINE, CognitiveState.EXECUTE, CognitiveState.REVIEW,
        CognitiveState.IDLE,
    },
    CognitiveState.ERROR: {CognitiveState.IDLE, CognitiveState.UNDERSTAND, CognitiveState.PAUSED},
}


class HumanInterface(Protocol):
    """Protocol for human-in-the-loop callbacks.

    Implementations can be TUI prompts, API endpoints, test stubs, etc.
    """

    async def ask_user(self, question: str, *, context: str = "") -> str:
        """Ask the user a question and return their answer."""
        ...

    async def wait_for_approval(self, description: str, *,
                                 artifacts: Optional[List[Artifact]] = None) -> bool:
        """Wait for user to approve an action. Returns True if approved."""
        ...

    async def present_plan(self, steps: List[PlanStep]) -> List[PlanStep]:
        """Show plan to user. Returns modified plan (user can edit/reorder/delete)."""
        ...

    async def present_diff(self, diff_content: str, *, file_path: str = "") -> bool:
        """Show a diff for review. Returns True if accepted."""
        ...

    async def collect_feedback(self, summary: str) -> Dict[str, Any]:
        """Collect end-of-cycle feedback. Returns {rating: int, text: str}."""
        ...

    async def notify(self, message: str, *, level: str = "info") -> None:
        """Show a notification to the user."""
        ...


class _AutoApproveHuman:
    """Default HumanInterface that auto-approves everything (for testing/autonomous mode)."""

    async def ask_user(self, question: str, *, context: str = "") -> str:
        return ""

    async def wait_for_approval(self, description: str, **kw) -> bool:
        return True

    async def present_plan(self, steps: List[PlanStep]) -> List[PlanStep]:
        return steps

    async def present_diff(self, diff_content: str, **kw) -> bool:
        return True

    async def collect_feedback(self, summary: str) -> Dict[str, Any]:
        return {"rating": 5, "text": ""}

    async def notify(self, message: str, **kw) -> None:
        pass


@dataclass
class LoopMetrics:
    """Metrics collected during a cognitive loop cycle."""
    cycles_completed: int = 0
    total_steps_executed: int = 0
    steps_approved: int = 0
    steps_rejected: int = 0
    clarifications_asked: int = 0
    reflections_generated: int = 0
    user_corrections: int = 0
    total_duration_s: float = 0.0
    state_durations: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycles_completed": self.cycles_completed,
            "total_steps_executed": self.total_steps_executed,
            "steps_approved": self.steps_approved,
            "steps_rejected": self.steps_rejected,
            "clarifications_asked": self.clarifications_asked,
            "reflections_generated": self.reflections_generated,
            "user_corrections": self.user_corrections,
            "total_duration_s": round(self.total_duration_s, 2),
            "state_durations": {k: round(v, 2) for k, v in self.state_durations.items()},
        }


# Type alias for state handlers
StateHandler = Callable[["CognitiveLoop"], Coroutine[Any, Any, CognitiveState]]


class CognitiveLoop:
    """The Cognitive Loop Engine.

    Orchestrates the UNDERSTAND→PROPOSE→DISCUSS→REFINE→EXECUTE→REVIEW cycle,
    ensuring the human is always aware and in control.

    Usage:
        loop = CognitiveLoop(human=my_tui_interface)
        loop.set_goal("Refactor the auth module for better testability")

        # Run the full cycle
        await loop.run()

        # Or step through manually
        await loop.step()  # IDLE → UNDERSTAND
        await loop.step()  # UNDERSTAND → PROPOSE
        # ...

    Extension points:
        # Register custom state handlers
        loop.register_handler(CognitiveState.UNDERSTAND, my_understand_handler)

        # Register execution callbacks (called during EXECUTE for each step)
        loop.register_executor(my_tool_executor)

        # Subscribe to state changes
        loop.on_transition(lambda old, new, state: print(f"{old} → {new}"))
    """

    def __init__(self, *,
                 human: Optional[HumanInterface] = None,
                 state: Optional[SharedState] = None,
                 max_cycles: int = 10,
                 meta_reflection: bool = True):
        self.human: HumanInterface = human or _AutoApproveHuman()
        self.state: SharedState = state or SharedState()
        self.current: CognitiveState = CognitiveState.IDLE
        self.max_cycles: int = max_cycles
        self.meta_reflection: bool = meta_reflection
        self.metrics: LoopMetrics = LoopMetrics()

        # Extension points
        self._handlers: Dict[CognitiveState, StateHandler] = {}
        self._executors: List[Callable] = []
        self._transition_hooks: List[Callable] = []
        self._state_enter_time: float = 0.0

        # Register default handlers
        self._handlers[CognitiveState.UNDERSTAND] = self._handle_understand
        self._handlers[CognitiveState.PROPOSE] = self._handle_propose
        self._handlers[CognitiveState.DISCUSS] = self._handle_discuss
        self._handlers[CognitiveState.REFINE] = self._handle_refine
        self._handlers[CognitiveState.EXECUTE] = self._handle_execute
        self._handlers[CognitiveState.REVIEW] = self._handle_review

    # ─── Public API ────────────────────────────────────────────────

    def set_goal(self, goal: str) -> None:
        """Set the goal and prepare for a new cycle."""
        self.state.set_goal(goal)
        self.state.trace.checkpoint(f"Goal set: {goal}")

    def register_handler(self, state: CognitiveState, handler: StateHandler) -> None:
        """Register a custom handler for a cognitive state."""
        self._handlers[state] = handler

    def register_executor(self, executor: Callable) -> None:
        """Register a tool executor for the EXECUTE state.

        Executor signature: async def executor(step: PlanStep, state: SharedState) -> bool
        Returns True if the step succeeded.
        """
        self._executors.append(executor)

    def on_transition(self, callback: Callable) -> None:
        """Register a state transition callback.

        Signature: callback(old_state, new_state, shared_state)
        """
        self._transition_hooks.append(callback)

    async def step(self) -> CognitiveState:
        """Execute one state transition.

        Returns the new state after the transition.
        """
        handler = self._handlers.get(self.current)
        if handler is None:
            if self.current == CognitiveState.IDLE:
                return self._transition_to(CognitiveState.UNDERSTAND)
            elif self.current == CognitiveState.PAUSED:
                # PAUSED requires explicit resume via resume()
                return self.current
            elif self.current == CognitiveState.ERROR:
                return self.current
            return self.current

        next_state = await handler(self)
        return self._transition_to(next_state)

    async def run(self) -> SharedState:
        """Run the full cognitive loop until completion or max_cycles.

        Returns the final shared state.
        """
        start_time = time.time()
        cycles = 0

        if self.current == CognitiveState.IDLE:
            self._transition_to(CognitiveState.UNDERSTAND)

        while cycles < self.max_cycles:
            if self.current in (CognitiveState.IDLE, CognitiveState.ERROR):
                break
            if self.current == CognitiveState.PAUSED:
                break  # Requires external resume

            await self.step()

            # Count full cycles (UNDERSTAND → REVIEW)
            if self.current == CognitiveState.IDLE:
                cycles += 1
                self.metrics.cycles_completed = cycles

        self.metrics.total_duration_s = time.time() - start_time
        return self.state

    def resume(self, to_state: Optional[CognitiveState] = None) -> CognitiveState:
        """Resume from PAUSED state.

        If to_state is provided, transitions to that state.
        Otherwise, returns to the state before pause.
        """
        if self.current != CognitiveState.PAUSED:
            return self.current

        target = to_state or CognitiveState.UNDERSTAND
        return self._transition_to(target)

    def pause(self) -> CognitiveState:
        """Pause the loop (from any state)."""
        return self._transition_to(CognitiveState.PAUSED)

    def abort(self) -> CognitiveState:
        """Abort the current cycle and return to IDLE."""
        self.state.trace.checkpoint("Cycle aborted by user")
        return self._transition_to(CognitiveState.IDLE)

    # ─── State Transition ──────────────────────────────────────────

    def _transition_to(self, new_state: CognitiveState) -> CognitiveState:
        """Transition to a new state with validation."""
        old = self.current

        # Validate transition
        if new_state not in _TRANSITIONS.get(old, set()):
            raise InvalidTransitionError(
                f"Cannot transition from {old.value} to {new_state.value}. "
                f"Allowed: {[s.value for s in _TRANSITIONS.get(old, set())]}"
            )

        # Record duration in old state
        if self._state_enter_time:
            duration = time.time() - self._state_enter_time
            key = old.value
            self.metrics.state_durations[key] = (
                self.metrics.state_durations.get(key, 0.0) + duration
            )

        self.current = new_state
        self._state_enter_time = time.time()

        # Record in trace
        self.state.trace.checkpoint(f"State: {old.value} → {new_state.value}")

        # Notify hooks
        for hook in self._transition_hooks:
            try:
                hook(old, new_state, self.state)
            except Exception:
                pass

        # Emit on shared state
        self.state.emit("state_changed", old_state=old, new_state=new_state)

        return new_state

    # ─── Default State Handlers ────────────────────────────────────

    async def _handle_understand(self, loop: "CognitiveLoop") -> CognitiveState:
        """UNDERSTAND state: Ask clarifying questions about goal.

        AI action: Analyze goal, identify ambiguities, ask questions
        Human role: Answer questions, provide context
        Artifacts: Goal statement, constraints list, clarifications
        """
        # Record observation about the goal
        self.state.trace.observe(
            f"Analyzing goal: {self.state.goal}",
            metadata={"state": "understand"},
        )

        # Meta-cognitive reflection: What assumptions am I making?
        if self.meta_reflection:
            reflection = (
                f"Meta-reflection before understanding: "
                f"What do I know about this goal? What am I assuming? "
                f"What information am I missing?"
            )
            self.state.add_reflection(reflection)
            self.metrics.reflections_generated += 1

        # Check for underspecification (Ambig-SWE inspired)
        # In production, this would use an LLM to detect ambiguity
        if not self.state.constraints:
            question = (
                f"I want to understand your goal fully before proposing a plan. "
                f"Goal: \"{self.state.goal}\"\n"
                f"Are there any constraints, preferences, or context I should know about?"
            )
            answer = await self.human.ask_user(question, context=self.state.goal)

            if answer:
                self.state.add_clarification(Clarification(
                    question=question, answer=answer, resolved=True,
                ))
                self.state.add_constraint(answer)
                self.metrics.clarifications_asked += 1

        return CognitiveState.PROPOSE

    async def _handle_propose(self, loop: "CognitiveLoop") -> CognitiveState:
        """PROPOSE state: Generate a structured plan.

        AI action: Generate plan with steps, risks, alternatives
        Human role: Review plan card
        Artifacts: Plan card, risk assessment
        """
        self.state.trace.observe(
            "Generating structured plan",
            metadata={"state": "propose", "goal": self.state.goal},
        )

        # In production, this calls an LLM to generate plan steps.
        # The plan is presented as structured cards, not plain text.
        # For now, the plan_steps should be populated by the registered
        # handler or executor before reaching this point.

        # Present plan to human for review
        if self.state.plan_steps:
            modified_steps = await self.human.present_plan(self.state.plan_steps)
            self.state.plan_steps = modified_steps

        await self.human.notify(
            f"Plan proposed with {len(self.state.plan_steps)} steps. "
            f"Review and discuss, or approve to proceed.",
            level="info",
        )

        return CognitiveState.DISCUSS

    async def _handle_discuss(self, loop: "CognitiveLoop") -> CognitiveState:
        """DISCUSS state: Explain reasoning, answer questions.

        AI action: Explain reasoning, answer questions, offer modifications
        Human role: Question, suggest changes
        Artifacts: Discussion thread, decision log
        """
        self.state.trace.observe(
            "Entering discussion phase",
            metadata={"state": "discuss"},
        )

        # Ask user if they have questions or want changes
        response = await self.human.ask_user(
            "Do you have questions about the plan, or would you like to suggest changes? "
            "(Type 'approve' to proceed, or describe your concerns)",
            context=f"Plan has {len(self.state.plan_steps)} steps",
        )

        if response and response.strip().lower() not in ("approve", "ok", "yes", "lgtm", ""):
            # User has feedback — record and go to REFINE
            self.state.add_clarification(Clarification(
                question="User feedback on plan",
                answer=response,
                resolved=False,
            ))
            self.state.trace.observe(
                f"User feedback received: {response[:100]}",
                metadata={"state": "discuss", "action": "feedback"},
            )
            return CognitiveState.REFINE

        # User approved — go to REFINE (which will auto-approve and proceed to EXECUTE)
        self.state.approve_all_steps()
        return CognitiveState.REFINE

    async def _handle_refine(self, loop: "CognitiveLoop") -> CognitiveState:
        """REFINE state: Update plan based on discussion.

        AI action: Modify plan based on feedback
        Human role: Approve final plan
        Artifacts: Approved plan, checkpoints
        """
        self.state.trace.observe(
            "Refining plan based on feedback",
            metadata={"state": "refine"},
        )

        # Check if there are unresolved clarifications
        pending = self.state.pending_clarifications
        if pending:
            # In production, LLM would modify the plan based on feedback
            for c in pending:
                c.resolved = True

        # Meta-cognitive check before execution
        if self.meta_reflection:
            reflection = (
                f"Meta-reflection before execution: "
                f"Am I confident in this plan? What could go wrong? "
                f"Have I addressed the user's concerns? "
                f"Plan has {len(self.state.plan_steps)} steps, "
                f"{sum(1 for s in self.state.plan_steps if s.approved)} approved."
            )
            self.state.add_reflection(reflection)
            self.metrics.reflections_generated += 1

        # If all steps are approved, proceed to execute
        all_approved = all(s.approved for s in self.state.plan_steps)
        if all_approved and self.state.plan_steps:
            return CognitiveState.EXECUTE

        # Otherwise, go back to discussion
        return CognitiveState.DISCUSS

    async def _handle_execute(self, loop: "CognitiveLoop") -> CognitiveState:
        """EXECUTE state: Perform steps with checkpoints.

        AI action: Execute approved steps, pause at high-risk checkpoints
        Human role: Approve/reject actions at checkpoints
        Artifacts: Diffs, test results, logs
        """
        self.state.trace.checkpoint("Execution started")
        failed_ids: set = set()  # Track failed steps to avoid infinite retry

        while True:
            step = self.state.get_next_step()
            if step is None:
                break
            if step.id in failed_ids:
                # Already failed — skip to avoid infinite loop
                self.state.complete_step(step.id)  # Mark done (failed)
                continue

            # High-risk steps require explicit approval
            if step.risk_level in ("medium", "high"):
                approved = await self.human.wait_for_approval(
                    f"About to execute: {step.title} (risk: {step.risk_level})",
                )
                if not approved:
                    self.metrics.steps_rejected += 1
                    self.state.trace.observe(
                        f"Step rejected by user: {step.title}",
                        metadata={"step_id": step.id, "risk": step.risk_level},
                    )
                    failed_ids.add(step.id)
                    self.state.complete_step(step.id)
                    continue

            self.metrics.steps_approved += 1

            # Execute via registered executors
            success = False
            for executor in self._executors:
                try:
                    success = await executor(step, self.state)
                    if success:
                        break
                except Exception as e:
                    self.state.trace.record_outcome(
                        f"Executor error for step: {step.title}",
                        success=False,
                        metadata={"error": str(e), "step_id": step.id},
                    )

            self.state.complete_step(step.id)
            self.metrics.total_steps_executed += 1

            if success:
                self.state.trace.record_action(
                    f"Executed: {step.title}",
                    metadata={"step_id": step.id},
                )
            else:
                failed_ids.add(step.id)
                self.state.trace.record_outcome(
                    f"Step failed: {step.title}",
                    success=False,
                    metadata={"step_id": step.id},
                )

        self.state.trace.checkpoint("Execution completed")
        return CognitiveState.REVIEW

    async def _handle_review(self, loop: "CognitiveLoop") -> CognitiveState:
        """REVIEW state: Summarize outcome, collect feedback.

        AI action: Summarize what was done, highlight deviations
        Human role: Provide feedback, accept/reject outcome
        Artifacts: Outcome summary, feedback
        """
        completed, total = self.state.plan_progress
        summary = (
            f"Cycle complete. {completed}/{total} steps executed.\n"
            f"Trace: {len(self.state.trace)} reasoning nodes.\n"
            f"Artifacts: {len(self.state.artifacts)} produced."
        )

        self.state.trace.checkpoint(f"Review: {summary}")

        # Collect user feedback
        feedback = await self.human.collect_feedback(summary)
        if feedback:
            self.state.add_artifact(Artifact(
                type=ArtifactType.FEEDBACK,
                title="Cycle feedback",
                content=str(feedback),
                metadata=feedback,
            ))

            # Record corrections if rating is low
            rating = feedback.get("rating", 5)
            if isinstance(rating, (int, float)) and rating < 3 and feedback.get("text"):
                self.state.trace.correct(
                    self.state.trace.root_ids[-1] if self.state.trace.root_ids else "",
                    feedback["text"],
                )
                self.metrics.user_corrections += 1

        # Return to IDLE (cycle complete)
        return CognitiveState.IDLE

    # ─── Introspection ─────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """True if the loop is actively processing."""
        return self.current not in (
            CognitiveState.IDLE, CognitiveState.PAUSED, CognitiveState.ERROR
        )

    def allowed_transitions(self) -> List[CognitiveState]:
        """Get allowed transitions from current state."""
        return list(_TRANSITIONS.get(self.current, set()))

    def summary(self) -> str:
        """Human-readable summary of loop status."""
        lines = [
            f"CognitiveLoop: {self.current.value}",
            f"Cycles: {self.metrics.cycles_completed}/{self.max_cycles}",
            self.state.summary(),
        ]
        return "\n".join(lines)


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass
