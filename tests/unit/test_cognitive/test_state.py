"""Tests for SharedState — the observable state object."""
import pytest
from nexus.cognitive.state import (
    SharedState, PlanStep, Artifact, ArtifactType, Clarification,
)


class TestPlanStep:
    def test_default_creation(self):
        step = PlanStep()
        assert step.title == ""
        assert not step.completed
        assert not step.approved
        assert step.risk_level == "low"
        assert step.depends_on == []

    def test_custom_creation(self):
        step = PlanStep(
            title="Extract interface",
            description="Pull out IAuth interface",
            risk_level="medium",
            estimated_effort="15 min",
        )
        assert step.title == "Extract interface"
        assert step.risk_level == "medium"

    def test_serialization_roundtrip(self):
        step = PlanStep(
            title="Test step",
            depends_on=["abc"],
            risk_level="high",
            metadata={"file": "auth.py"},
        )
        data = step.to_dict()
        restored = PlanStep.from_dict(data)
        assert restored.title == "Test step"
        assert restored.depends_on == ["abc"]
        assert restored.risk_level == "high"


class TestArtifact:
    def test_creation(self):
        art = Artifact(type=ArtifactType.DIFF, title="cache.py changes")
        assert art.type == ArtifactType.DIFF
        assert art.title == "cache.py changes"

    def test_all_artifact_types(self):
        for t in ArtifactType:
            art = Artifact(type=t, title=t.value)
            assert art.type == t

    def test_to_dict(self):
        art = Artifact(type=ArtifactType.CODE, title="new file", content="print('hi')")
        data = art.to_dict()
        assert data["type"] == "code"
        assert data["content"] == "print('hi')"


class TestSharedState:
    def test_default_state(self):
        state = SharedState()
        assert state.goal == ""
        assert state.plan_steps == []
        assert state.artifacts == []
        assert state.clarifications == []
        assert len(state.trace) == 0

    def test_set_goal(self):
        state = SharedState()
        events = []
        state.on("goal_changed", lambda **kw: events.append(kw))
        state.set_goal("Refactor auth module")
        assert state.goal == "Refactor auth module"
        assert len(events) == 1
        assert events[0]["new_goal"] == "Refactor auth module"

    def test_add_constraint(self):
        state = SharedState()
        events = []
        state.on("constraint_added", lambda **kw: events.append(kw))
        state.add_constraint("Must maintain backward compatibility")
        assert len(state.constraints) == 1
        assert len(events) == 1

    def test_add_plan_step(self):
        state = SharedState()
        events = []
        state.on("plan_updated", lambda **kw: events.append(kw))
        step = state.add_plan_step(PlanStep(title="Step 1"))
        assert len(state.plan_steps) == 1
        assert step.title == "Step 1"
        assert len(events) == 1
        assert events[0]["action"] == "add"

    def test_remove_plan_step(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="Step 1"))
        s2 = state.add_plan_step(PlanStep(title="Step 2", depends_on=[s1.id]))

        removed = state.remove_plan_step(s1.id)
        assert removed is not None
        assert removed.title == "Step 1"
        assert len(state.plan_steps) == 1
        # Dependency should be removed
        assert s1.id not in state.plan_steps[0].depends_on

    def test_remove_nonexistent_step(self):
        state = SharedState()
        assert state.remove_plan_step("nonexistent") is None

    def test_reorder_plan(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="A"))
        s2 = state.add_plan_step(PlanStep(title="B"))
        s3 = state.add_plan_step(PlanStep(title="C"))

        state.reorder_plan([s3.id, s1.id, s2.id])
        assert [s.title for s in state.plan_steps] == ["C", "A", "B"]

    def test_reorder_with_missing_ids(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="A"))
        s2 = state.add_plan_step(PlanStep(title="B"))

        # Only include s2 in new order — s1 should be appended
        state.reorder_plan([s2.id])
        assert [s.title for s in state.plan_steps] == ["B", "A"]

    def test_complete_step(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="Step 1"))
        assert state.complete_step(s1.id)
        assert s1.completed
        assert not state.complete_step("nonexistent")

    def test_approve_step(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="Step 1"))
        assert state.approve_step(s1.id)
        assert s1.approved

    def test_approve_all_steps(self):
        state = SharedState()
        state.add_plan_step(PlanStep(title="A"))
        state.add_plan_step(PlanStep(title="B"))
        state.add_plan_step(PlanStep(title="C"))
        count = state.approve_all_steps()
        assert count == 3
        assert all(s.approved for s in state.plan_steps)
        # Second call returns 0
        assert state.approve_all_steps() == 0

    def test_get_next_step_basic(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="Step 1"))
        s1.approved = True
        next_step = state.get_next_step()
        assert next_step is not None
        assert next_step.id == s1.id

    def test_get_next_step_respects_approval(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="Step 1"))  # Not approved
        assert state.get_next_step() is None

    def test_get_next_step_respects_dependencies(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="Step 1"))
        s2 = state.add_plan_step(PlanStep(title="Step 2", depends_on=[s1.id]))
        s1.approved = True
        s2.approved = True

        # s1 should be next (s2 depends on s1)
        assert state.get_next_step().id == s1.id

        # Complete s1, now s2 should be next
        state.complete_step(s1.id)
        assert state.get_next_step().id == s2.id

    def test_get_next_step_skips_completed(self):
        state = SharedState()
        s1 = state.add_plan_step(PlanStep(title="Done"))
        s2 = state.add_plan_step(PlanStep(title="Todo"))
        s1.approved = True
        s2.approved = True
        state.complete_step(s1.id)
        assert state.get_next_step().id == s2.id

    def test_plan_progress(self):
        state = SharedState()
        state.add_plan_step(PlanStep(title="A"))
        state.add_plan_step(PlanStep(title="B"))
        s3 = state.add_plan_step(PlanStep(title="C"))
        state.complete_step(s3.id)
        completed, total = state.plan_progress
        assert completed == 1
        assert total == 3

    def test_add_artifact(self):
        state = SharedState()
        events = []
        state.on("artifact_added", lambda **kw: events.append(kw))
        art = state.add_artifact(Artifact(type=ArtifactType.DIFF, title="patch"))
        assert len(state.artifacts) == 1
        assert len(events) == 1

    def test_get_artifacts_by_type(self):
        state = SharedState()
        state.add_artifact(Artifact(type=ArtifactType.DIFF, title="d1"))
        state.add_artifact(Artifact(type=ArtifactType.CODE, title="c1"))
        state.add_artifact(Artifact(type=ArtifactType.DIFF, title="d2"))
        diffs = state.get_artifacts_by_type(ArtifactType.DIFF)
        assert len(diffs) == 2

    def test_add_clarification(self):
        state = SharedState()
        events = []
        state.on("clarification_added", lambda **kw: events.append(kw))
        c = state.add_clarification(Clarification(
            question="Which framework?", answer="pytest",
        ))
        assert len(state.clarifications) == 1
        assert len(events) == 1

    def test_pending_clarifications(self):
        state = SharedState()
        state.add_clarification(Clarification(question="Q1", resolved=True))
        state.add_clarification(Clarification(question="Q2", resolved=False))
        state.add_clarification(Clarification(question="Q3", resolved=False))
        assert len(state.pending_clarifications) == 2

    def test_add_reflection(self):
        state = SharedState()
        events = []
        state.on("reflection_added", lambda **kw: events.append(kw))
        state.add_reflection("Am I overcomplicating this?")
        assert len(state.meta_reflections) == 1
        assert len(events) == 1

    def test_observer_subscribe_unsubscribe(self):
        state = SharedState()
        events = []
        handler = lambda **kw: events.append(1)
        state.on("goal_changed", handler)
        state.set_goal("G1")
        assert len(events) == 1
        state.off("goal_changed", handler)
        state.set_goal("G2")
        assert len(events) == 1  # No new event

    def test_observer_error_doesnt_crash(self):
        """A failing listener should not crash the state."""
        state = SharedState()
        state.on("goal_changed", lambda **kw: 1 / 0)
        state.set_goal("Should not crash")
        assert state.goal == "Should not crash"

    def test_listener_count(self):
        state = SharedState()
        state.on("goal_changed", lambda **kw: None)
        state.on("goal_changed", lambda **kw: None)
        state.on("plan_updated", lambda **kw: None)
        assert state.listener_count == 3

    def test_history_audit(self):
        state = SharedState()
        state.set_goal("Goal 1")
        state.add_constraint("Constraint 1")
        state.add_plan_step(PlanStep(title="Step 1"))
        assert len(state.history) == 3
        assert state.history[0]["action"] == "goal_changed"
        assert state.history[1]["action"] == "constraint_added"
        assert state.history[2]["action"] == "plan_step_added"

    def test_serialization_roundtrip(self):
        state = SharedState(goal="Test goal")
        state.add_constraint("Must be fast")
        state.add_plan_step(PlanStep(title="Step A", risk_level="high"))
        state.add_plan_step(PlanStep(title="Step B"))
        state.add_reflection("Thinking about this...")
        state.trace.observe("Found something")

        data = state.to_dict()
        restored = SharedState.from_dict(data)
        assert restored.goal == "Test goal"
        assert len(restored.constraints) == 1
        assert len(restored.plan_steps) == 2
        assert restored.plan_steps[0].risk_level == "high"
        assert len(restored.meta_reflections) == 1
        assert len(restored.trace) == 1

    def test_summary(self):
        state = SharedState(goal="Refactor cache")
        state.add_plan_step(PlanStep(title="S1"))
        state.add_artifact(Artifact(type=ArtifactType.CODE))
        s = state.summary()
        assert "Refactor cache" in s
        assert "0/1" in s  # plan progress
        assert "1" in s  # artifact count

    def test_custom_session_id(self):
        state = SharedState(session_id="custom-123")
        assert state.session_id == "custom-123"
