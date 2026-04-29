"""Tests for the CognitiveLoop engine."""
import asyncio
import pytest
from nexus.cognitive.loop import (
    CognitiveLoop, CognitiveState, InvalidTransitionError,
    _AutoApproveHuman,
)
from nexus.cognitive.state import SharedState, PlanStep, Artifact, ArtifactType


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class MockHuman:
    """Configurable mock HumanInterface for testing."""

    def __init__(self):
        self.ask_responses = []
        self.approval_responses = []
        self.plan_edits = None
        self.diff_responses = []
        self.feedback_response = {"rating": 4, "text": "Good job"}
        self.notifications = []
        self._ask_idx = 0
        self._approval_idx = 0
        self._diff_idx = 0

    async def ask_user(self, question, *, context=""):
        if self._ask_idx < len(self.ask_responses):
            resp = self.ask_responses[self._ask_idx]
            self._ask_idx += 1
            return resp
        return ""

    async def wait_for_approval(self, description, **kw):
        if self._approval_idx < len(self.approval_responses):
            resp = self.approval_responses[self._approval_idx]
            self._approval_idx += 1
            return resp
        return True

    async def present_plan(self, steps):
        if self.plan_edits is not None:
            return self.plan_edits
        return steps

    async def present_diff(self, diff_content, **kw):
        if self._diff_idx < len(self.diff_responses):
            resp = self.diff_responses[self._diff_idx]
            self._diff_idx += 1
            return resp
        return True

    async def collect_feedback(self, summary):
        return self.feedback_response

    async def notify(self, message, **kw):
        self.notifications.append(message)


class MockExecutor:
    """Mock tool executor that tracks calls."""

    def __init__(self, succeed=True):
        self.calls = []
        self.succeed = succeed

    async def __call__(self, step, state):
        self.calls.append(step.id)
        return self.succeed


# ---------------------------------------------------------------------------
# Tests: State machine transitions
# ---------------------------------------------------------------------------

class TestTransitions:
    def test_initial_state_is_idle(self):
        loop = CognitiveLoop()
        assert loop.current == CognitiveState.IDLE

    def test_idle_to_understand(self):
        loop = CognitiveLoop()
        new = loop._transition_to(CognitiveState.UNDERSTAND)
        assert new == CognitiveState.UNDERSTAND
        assert loop.current == CognitiveState.UNDERSTAND

    def test_invalid_transition_raises(self):
        loop = CognitiveLoop()
        with pytest.raises(InvalidTransitionError):
            loop._transition_to(CognitiveState.EXECUTE)

    def test_valid_transition_chain(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop._transition_to(CognitiveState.PROPOSE)
        loop._transition_to(CognitiveState.DISCUSS)
        loop._transition_to(CognitiveState.REFINE)
        loop._transition_to(CognitiveState.EXECUTE)
        loop._transition_to(CognitiveState.REVIEW)
        loop._transition_to(CognitiveState.IDLE)
        assert loop.current == CognitiveState.IDLE

    def test_pause_from_any_active_state(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop._transition_to(CognitiveState.PAUSED)
        assert loop.current == CognitiveState.PAUSED

    def test_resume_from_paused(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop.pause()
        assert loop.current == CognitiveState.PAUSED
        loop.resume(CognitiveState.UNDERSTAND)
        assert loop.current == CognitiveState.UNDERSTAND

    def test_resume_when_not_paused_noop(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        result = loop.resume(CognitiveState.PROPOSE)
        assert result == CognitiveState.UNDERSTAND  # No change

    def test_abort(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop._transition_to(CognitiveState.PROPOSE)
        loop._transition_to(CognitiveState.DISCUSS)
        loop._transition_to(CognitiveState.PAUSED)
        result = loop.abort()
        assert result == CognitiveState.IDLE

    def test_error_state(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop._transition_to(CognitiveState.PROPOSE)
        loop._transition_to(CognitiveState.DISCUSS)
        loop._transition_to(CognitiveState.REFINE)
        loop._transition_to(CognitiveState.EXECUTE)
        loop._transition_to(CognitiveState.ERROR)
        assert loop.current == CognitiveState.ERROR
        # Can go to IDLE from error
        loop._transition_to(CognitiveState.IDLE)
        assert loop.current == CognitiveState.IDLE

    def test_discuss_can_loop_back_to_propose(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop._transition_to(CognitiveState.PROPOSE)
        loop._transition_to(CognitiveState.DISCUSS)
        # User wants a completely new plan
        loop._transition_to(CognitiveState.PROPOSE)
        assert loop.current == CognitiveState.PROPOSE

    def test_review_can_loop_back_to_understand(self):
        """After review, can start a new cycle."""
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop._transition_to(CognitiveState.PROPOSE)
        loop._transition_to(CognitiveState.DISCUSS)
        loop._transition_to(CognitiveState.REFINE)
        loop._transition_to(CognitiveState.EXECUTE)
        loop._transition_to(CognitiveState.REVIEW)
        loop._transition_to(CognitiveState.UNDERSTAND)
        assert loop.current == CognitiveState.UNDERSTAND

    def test_allowed_transitions(self):
        loop = CognitiveLoop()
        allowed = loop.allowed_transitions()
        assert CognitiveState.UNDERSTAND in allowed
        assert CognitiveState.EXECUTE not in allowed


# ---------------------------------------------------------------------------
# Tests: Transition hooks
# ---------------------------------------------------------------------------

class TestTransitionHooks:
    def test_hook_fires_on_transition(self):
        loop = CognitiveLoop()
        transitions = []
        loop.on_transition(lambda old, new, state: transitions.append((old.value, new.value)))
        loop._transition_to(CognitiveState.UNDERSTAND)
        assert transitions == [("idle", "understand")]

    def test_hook_error_doesnt_crash(self):
        loop = CognitiveLoop()
        loop.on_transition(lambda old, new, state: 1 / 0)
        loop._transition_to(CognitiveState.UNDERSTAND)
        assert loop.current == CognitiveState.UNDERSTAND

    def test_trace_records_transitions(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop._transition_to(CognitiveState.PROPOSE)
        checkpoints = loop.state.trace.filter_by_type(
            __import__('nexus.cognitive.trace', fromlist=['TraceNodeType']).TraceNodeType.CHECKPOINT
        )
        assert len(checkpoints) == 2


# ---------------------------------------------------------------------------
# Tests: step() — one state at a time
# ---------------------------------------------------------------------------

class TestStep:
    @pytest.mark.asyncio
    async def test_step_from_idle(self):
        loop = CognitiveLoop()
        result = await loop.step()
        assert result == CognitiveState.UNDERSTAND

    @pytest.mark.asyncio
    async def test_step_understand_to_propose(self):
        human = MockHuman()
        human.ask_responses = ["No special constraints"]
        loop = CognitiveLoop(human=human)
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop.state.set_goal("Fix the bug")
        result = await loop.step()
        assert result == CognitiveState.PROPOSE

    @pytest.mark.asyncio
    async def test_step_paused_stays_paused(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop.pause()
        result = await loop.step()
        assert result == CognitiveState.PAUSED

    @pytest.mark.asyncio
    async def test_step_error_stays_error(self):
        loop = CognitiveLoop()
        loop._transition_to(CognitiveState.UNDERSTAND)
        loop._transition_to(CognitiveState.PROPOSE)
        loop._transition_to(CognitiveState.DISCUSS)
        loop._transition_to(CognitiveState.REFINE)
        loop._transition_to(CognitiveState.EXECUTE)
        loop._transition_to(CognitiveState.ERROR)
        result = await loop.step()
        assert result == CognitiveState.ERROR


# ---------------------------------------------------------------------------
# Tests: Full cycle (run)
# ---------------------------------------------------------------------------

class TestFullCycle:
    @pytest.mark.asyncio
    async def test_full_cycle_auto_approve(self):
        """Run a complete cycle with auto-approve human."""
        loop = CognitiveLoop(max_cycles=1)
        loop.set_goal("Add error handling to parser.py")

        # Add plan steps before running
        loop.state.add_plan_step(PlanStep(title="Add try/except", risk_level="low"))
        loop.state.add_plan_step(PlanStep(title="Add tests", risk_level="low"))

        # Register executor
        executor = MockExecutor(succeed=True)
        loop.register_executor(executor)

        result = await loop.run()
        assert loop.current == CognitiveState.IDLE
        assert loop.metrics.cycles_completed == 1
        assert len(executor.calls) == 2

    @pytest.mark.asyncio
    async def test_full_cycle_with_discussion(self):
        """User provides feedback, loop goes DISCUSS → REFINE → EXECUTE."""
        human = MockHuman()
        human.ask_responses = [
            "",      # UNDERSTAND: no constraints
            "Can you also add logging?",  # DISCUSS: feedback
            "approve",  # DISCUSS (second pass): approve
        ]
        human.feedback_response = {"rating": 5, "text": ""}

        loop = CognitiveLoop(human=human, max_cycles=1)
        loop.set_goal("Improve error handling")
        loop.state.add_plan_step(PlanStep(title="Add try/except"))

        executor = MockExecutor(succeed=True)
        loop.register_executor(executor)

        await loop.run()
        assert loop.metrics.cycles_completed == 1

    @pytest.mark.asyncio
    async def test_max_cycles_limit(self):
        """Loop stops after max_cycles."""
        loop = CognitiveLoop(max_cycles=0)
        loop.set_goal("Test")
        loop._transition_to(CognitiveState.UNDERSTAND)
        await loop.run()
        # Should stop immediately (max_cycles=0)

    @pytest.mark.asyncio
    async def test_executor_failure(self):
        """Failed executor records outcome in trace."""
        human = MockHuman()
        human.ask_responses = [""]  # auto
        loop = CognitiveLoop(human=human, max_cycles=1)
        loop.set_goal("Fix bug")
        loop.state.add_plan_step(PlanStep(title="Apply patch"))

        executor = MockExecutor(succeed=False)
        loop.register_executor(executor)

        await loop.run()
        # Step was attempted but failed
        assert loop.metrics.total_steps_executed == 1

    @pytest.mark.asyncio
    async def test_high_risk_step_rejected(self):
        """High-risk step that user rejects is skipped."""
        human = MockHuman()
        human.ask_responses = ["", "approve"]
        human.approval_responses = [False]  # Reject the high-risk step

        loop = CognitiveLoop(human=human, max_cycles=1)
        loop.set_goal("Dangerous refactor")
        loop.state.add_plan_step(PlanStep(title="Delete old code", risk_level="high"))
        loop.state.add_plan_step(PlanStep(title="Write new code", risk_level="low"))

        executor = MockExecutor(succeed=True)
        loop.register_executor(executor)

        await loop.run()
        assert loop.metrics.steps_rejected == 1
        # Only the low-risk step was executed
        assert loop.metrics.steps_approved == 1


# ---------------------------------------------------------------------------
# Tests: Meta-cognitive reflection
# ---------------------------------------------------------------------------

class TestMetaCognition:
    @pytest.mark.asyncio
    async def test_reflections_generated(self):
        """Meta-cognitive reflections are added during UNDERSTAND and REFINE."""
        loop = CognitiveLoop(meta_reflection=True, max_cycles=1)
        loop.set_goal("Test reflections")
        loop.state.add_plan_step(PlanStep(title="Step 1"))

        executor = MockExecutor(succeed=True)
        loop.register_executor(executor)

        await loop.run()
        assert loop.metrics.reflections_generated >= 2  # UNDERSTAND + REFINE
        assert len(loop.state.meta_reflections) >= 2

    @pytest.mark.asyncio
    async def test_no_reflections_when_disabled(self):
        """No meta-cognitive reflections when meta_reflection=False."""
        loop = CognitiveLoop(meta_reflection=False, max_cycles=1)
        loop.set_goal("No reflections")
        loop.state.add_plan_step(PlanStep(title="Step 1"))

        executor = MockExecutor(succeed=True)
        loop.register_executor(executor)

        await loop.run()
        assert loop.metrics.reflections_generated == 0


# ---------------------------------------------------------------------------
# Tests: Custom handlers
# ---------------------------------------------------------------------------

class TestCustomHandlers:
    @pytest.mark.asyncio
    async def test_custom_understand_handler(self):
        """Custom handler replaces default behavior."""
        called = []

        async def my_handler(loop):
            called.append("custom_understand")
            return CognitiveState.PROPOSE

        loop = CognitiveLoop()
        loop.register_handler(CognitiveState.UNDERSTAND, my_handler)
        loop._transition_to(CognitiveState.UNDERSTAND)
        await loop.step()
        assert called == ["custom_understand"]
        assert loop.current == CognitiveState.PROPOSE

    @pytest.mark.asyncio
    async def test_custom_executor(self):
        """Custom executor is called for each plan step."""
        results = {}

        async def my_executor(step, state):
            results[step.id] = step.title
            return True

        human = MockHuman()
        human.ask_responses = ["", "approve"]
        loop = CognitiveLoop(human=human, max_cycles=1)
        loop.set_goal("Custom executor test")
        s1 = loop.state.add_plan_step(PlanStep(title="Alpha"))
        s2 = loop.state.add_plan_step(PlanStep(title="Beta"))
        loop.register_executor(my_executor)

        await loop.run()
        assert results[s1.id] == "Alpha"
        assert results[s2.id] == "Beta"


# ---------------------------------------------------------------------------
# Tests: Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        loop = CognitiveLoop(max_cycles=1)
        loop.set_goal("Metrics test")
        loop.state.add_plan_step(PlanStep(title="S1"))

        executor = MockExecutor(succeed=True)
        loop.register_executor(executor)

        await loop.run()
        m = loop.metrics
        assert m.cycles_completed == 1
        assert m.total_steps_executed >= 1
        assert m.total_duration_s > 0

    def test_metrics_to_dict(self):
        from nexus.cognitive.loop import LoopMetrics
        m = LoopMetrics(cycles_completed=3, total_duration_s=12.345)
        d = m.to_dict()
        assert d["cycles_completed"] == 3
        assert d["total_duration_s"] == 12.35

    @pytest.mark.asyncio
    async def test_state_durations_tracked(self):
        loop = CognitiveLoop(max_cycles=1)
        loop.set_goal("Duration test")
        loop.state.add_plan_step(PlanStep(title="S1"))
        loop.register_executor(MockExecutor(succeed=True))

        await loop.run()
        # Should have durations for each state visited
        assert len(loop.metrics.state_durations) > 0


# ---------------------------------------------------------------------------
# Tests: Introspection
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_is_running(self):
        loop = CognitiveLoop()
        assert not loop.is_running
        loop._transition_to(CognitiveState.UNDERSTAND)
        assert loop.is_running
        loop.pause()
        assert not loop.is_running

    def test_summary(self):
        loop = CognitiveLoop()
        loop.set_goal("Summarize this")
        s = loop.summary()
        assert "idle" in s
        assert "Summarize this" in s


# ---------------------------------------------------------------------------
# Tests: Low feedback triggers correction
# ---------------------------------------------------------------------------

class TestFeedbackCorrection:
    @pytest.mark.asyncio
    async def test_low_rating_creates_correction(self):
        human = MockHuman()
        human.ask_responses = ["", "approve"]
        human.feedback_response = {"rating": 2, "text": "Wrong approach entirely"}

        loop = CognitiveLoop(human=human, max_cycles=1)
        loop.set_goal("Test correction")
        loop.state.add_plan_step(PlanStep(title="S1"))
        loop.register_executor(MockExecutor(succeed=True))

        await loop.run()
        assert loop.metrics.user_corrections == 1
        assert len(loop.state.trace.corrections) >= 1

    @pytest.mark.asyncio
    async def test_high_rating_no_correction(self):
        human = MockHuman()
        human.ask_responses = ["", "approve"]
        human.feedback_response = {"rating": 5, "text": "Perfect"}

        loop = CognitiveLoop(human=human, max_cycles=1)
        loop.set_goal("Test no correction")
        loop.state.add_plan_step(PlanStep(title="S1"))
        loop.register_executor(MockExecutor(succeed=True))

        await loop.run()
        assert loop.metrics.user_corrections == 0
