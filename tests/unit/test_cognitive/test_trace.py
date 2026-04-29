"""Tests for the ReasoningTrace system."""
import pytest
from nexus.cognitive.trace import ReasoningTrace, TraceNode, TraceNodeType


class TestTraceNode:
    def test_default_creation(self):
        node = TraceNode()
        assert node.type == TraceNodeType.OBSERVATION
        assert node.content == ""
        assert node.confidence == 0.5
        assert node.parent_ids == []
        assert len(node.id) == 8

    def test_custom_creation(self):
        node = TraceNode(
            type=TraceNodeType.DECISION,
            content="Use pytest",
            confidence=0.9,
            detail="Better fixtures",
        )
        assert node.type == TraceNodeType.DECISION
        assert node.content == "Use pytest"
        assert node.confidence == 0.9
        assert node.detail == "Better fixtures"

    def test_serialization_roundtrip(self):
        node = TraceNode(
            type=TraceNodeType.ALTERNATIVE,
            content="Use unittest",
            rejection_reason="Less ergonomic",
            confidence=0.3,
            parent_ids=["abc"],
            metadata={"source": "review"},
        )
        data = node.to_dict()
        restored = TraceNode.from_dict(data)
        assert restored.type == TraceNodeType.ALTERNATIVE
        assert restored.content == "Use unittest"
        assert restored.rejection_reason == "Less ergonomic"
        assert restored.confidence == 0.3
        assert restored.parent_ids == ["abc"]

    def test_correction_node(self):
        node = TraceNode(
            type=TraceNodeType.CORRECTION,
            user_feedback="Actually use pytest-bdd",
        )
        assert node.type == TraceNodeType.CORRECTION
        assert node.user_feedback == "Actually use pytest-bdd"


class TestReasoningTrace:
    def test_empty_trace(self):
        trace = ReasoningTrace()
        assert len(trace) == 0
        assert trace.root_ids == []
        assert trace.corrections == []

    def test_observe(self):
        trace = ReasoningTrace()
        obs = trace.observe("Function has no error handling")
        assert obs.type == TraceNodeType.OBSERVATION
        assert obs.confidence == 1.0
        assert obs.id in trace.root_ids
        assert len(trace) == 1

    def test_hypothesize(self):
        trace = ReasoningTrace()
        obs = trace.observe("Tests failing on CI")
        hyp = trace.hypothesize(
            "Timezone issue in date comparison",
            confidence=0.7,
            parent_ids=[obs.id],
        )
        assert hyp.type == TraceNodeType.HYPOTHESIS
        assert hyp.confidence == 0.7
        assert hyp.id not in trace.root_ids  # Has parent

    def test_decide_with_alternative(self):
        trace = ReasoningTrace()
        obs = trace.observe("Cache miss rate is 40%")
        alt1 = trace.consider_alternative(
            "Increase cache TTL",
            rejection_reason="Would serve stale data",
            confidence=0.3,
            parent_ids=[obs.id],
        )
        dec = trace.decide(
            "Add LRU eviction policy",
            confidence=0.85,
            parent_ids=[obs.id, alt1.id],
        )
        assert dec.type == TraceNodeType.DECISION
        assert alt1.rejection_reason == "Would serve stale data"
        assert len(trace) == 3

    def test_action_and_outcome(self):
        trace = ReasoningTrace()
        act = trace.record_action(
            "Added try/finally block",
            metadata={"tool": "file_write", "file": "cache.py"},
        )
        outcome = trace.record_outcome(
            "Tests pass after fix",
            success=True,
            parent_ids=[act.id],
        )
        assert act.type == TraceNodeType.ACTION
        assert outcome.metadata["success"] is True

    def test_checkpoint(self):
        trace = ReasoningTrace()
        cp = trace.checkpoint("Entering EXECUTE state")
        assert cp.type == TraceNodeType.CHECKPOINT
        assert cp.content == "Entering EXECUTE state"

    def test_correct(self):
        trace = ReasoningTrace()
        dec = trace.decide("Use Redis for caching", confidence=0.8)
        correction = trace.correct(
            dec.id,
            "We can't use Redis — no Redis instance in production",
        )
        assert correction.type == TraceNodeType.CORRECTION
        assert correction.user_feedback.startswith("We can't use Redis")
        assert correction.parent_ids == [dec.id]
        assert len(trace.corrections) == 1

    def test_children_of(self):
        trace = ReasoningTrace()
        root = trace.observe("Starting analysis")
        c1 = trace.hypothesize("Issue A", parent_ids=[root.id])
        c2 = trace.hypothesize("Issue B", parent_ids=[root.id])
        c3 = trace.decide("Fix A", parent_ids=[c1.id])
        children = trace.children_of(root.id)
        assert len(children) == 2
        assert {c.id for c in children} == {c1.id, c2.id}

    def test_ancestors_of(self):
        trace = ReasoningTrace()
        root = trace.observe("Root")
        mid = trace.hypothesize("Mid", parent_ids=[root.id])
        leaf = trace.decide("Leaf", parent_ids=[mid.id])
        ancestors = trace.ancestors_of(leaf.id)
        assert len(ancestors) == 2
        assert {a.id for a in ancestors} == {root.id, mid.id}

    def test_path_to(self):
        trace = ReasoningTrace()
        a = trace.observe("A")
        b = trace.hypothesize("B", parent_ids=[a.id])
        c = trace.decide("C", parent_ids=[b.id])
        path = trace.path_to(c.id)
        assert len(path) == 3
        # Chronological order
        assert path[0].id == a.id
        assert path[-1].id == c.id

    def test_filter_by_type(self):
        trace = ReasoningTrace()
        trace.observe("O1")
        trace.observe("O2")
        trace.decide("D1")
        trace.hypothesize("H1")
        observations = trace.filter_by_type(TraceNodeType.OBSERVATION)
        assert len(observations) == 2

    def test_filter_by_confidence(self):
        trace = ReasoningTrace()
        trace.observe("High conf")  # 1.0
        trace.hypothesize("Med conf", confidence=0.5)
        trace.consider_alternative("Low conf", confidence=0.2)
        high = trace.filter_by_confidence(min_confidence=0.8)
        assert len(high) == 1

    def test_search(self):
        trace = ReasoningTrace()
        trace.observe("Cache performance is poor")
        trace.decide("Implement LRU cache")
        trace.observe("Authentication module needs refactor")
        results = trace.search("cache")
        assert len(results) == 2  # "Cache" and "cache"

    def test_serialization_roundtrip(self):
        trace = ReasoningTrace()
        obs = trace.observe("Observation")
        dec = trace.decide("Decision", parent_ids=[obs.id])
        trace.correct(dec.id, "User says no")

        data = trace.to_dict()
        restored = ReasoningTrace.from_dict(data)
        assert len(restored) == 3  # obs + dec + correction
        assert len(restored.corrections) == 1
        assert restored.get(obs.id).content == "Observation"

    def test_summary(self):
        trace = ReasoningTrace()
        trace.observe("O1")
        trace.decide("D1")
        trace.record_action("A1")
        s = trace.summary()
        assert "3 nodes" in s
        assert "observation" in s
        assert "decision" in s
        assert "action" in s

    def test_get_nonexistent(self):
        trace = ReasoningTrace()
        assert trace.get("nonexistent") is None

    def test_all_node_types(self):
        """Verify all 9 node types can be created."""
        types = list(TraceNodeType)
        assert len(types) == 9
        trace = ReasoningTrace()
        for t in types:
            trace._add_node(TraceNode(type=t, content=t.value))
        assert len(trace) == 9
