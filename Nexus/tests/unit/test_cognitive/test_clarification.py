"""Tests for Underspecification Handling."""
import pytest
from nexus.cognitive.clarification import (
    AmbiguityDetector, AmbiguitySignal, AmbiguityType,
    ClarificationDialog, ClarificationQuestion,
    ResolutionMethod,
)


class TestAmbiguityType:
    def test_all_types_exist(self):
        assert len(AmbiguityType) == 10
        assert AmbiguityType.SCOPE.value == "scope"


class TestClarificationQuestion:
    def test_default_unresolved(self):
        q = ClarificationQuestion(id="q1", question="Which files?")
        assert not q.resolved
        assert q.resolution == ResolutionMethod.DEFERRED

    def test_resolve(self):
        q = ClarificationQuestion(id="q1", question="Which files?")
        q.resolve("src/auth.py", ResolutionMethod.USER_ANSWER)
        assert q.resolved
        assert q.answer == "src/auth.py"
        assert q.resolved_at > 0

    def test_serialization_roundtrip(self):
        q = ClarificationQuestion(
            id="q1", question="Which API version?",
            ambiguity_type=AmbiguityType.DEPENDENCY,
            options=["v1", "v2"], default="v2", priority=1,
        )
        q.resolve("v2", ResolutionMethod.USER_ANSWER)
        data = q.to_dict()
        restored = ClarificationQuestion.from_dict(data)
        assert restored.id == "q1"
        assert restored.ambiguity_type == AmbiguityType.DEPENDENCY
        assert restored.answer == "v2"
        assert restored.resolution == ResolutionMethod.USER_ANSWER


class TestClarificationDialog:
    def test_empty_dialog(self):
        d = ClarificationDialog(id="d1", goal="test")
        assert d.all_resolved
        assert d.pending == []

    def test_pending_tracking(self):
        d = ClarificationDialog(id="d1", goal="test", questions=[
            ClarificationQuestion(id="q1", question="A?", priority=1),
            ClarificationQuestion(id="q2", question="B?", priority=2),
        ])
        assert len(d.pending) == 2
        assert len(d.must_answer) == 1

    def test_all_resolved_checks_priority(self):
        d = ClarificationDialog(id="d1", goal="test", questions=[
            ClarificationQuestion(id="q1", question="Must?", priority=1),
            ClarificationQuestion(id="q2", question="Nice?", priority=3),
        ])
        assert not d.all_resolved
        # Resolve only must-answer
        d.questions[0].resolve("yes")
        assert d.all_resolved  # priority=3 doesn't block

    def test_resolve_with_defaults(self):
        d = ClarificationDialog(id="d1", goal="test", questions=[
            ClarificationQuestion(id="q1", question="A?", default="x"),
            ClarificationQuestion(id="q2", question="B?", default="y"),
            ClarificationQuestion(id="q3", question="C?"),  # No default
        ])
        count = d.resolve_with_defaults()
        assert count == 2
        assert d.questions[0].resolution == ResolutionMethod.DEFAULT
        assert not d.questions[2].resolved

    def test_summary(self):
        d = ClarificationDialog(id="d1", goal="test", questions=[
            ClarificationQuestion(id="q1", question="A?", priority=1),
        ])
        s = d.summary()
        assert "0/1 resolved" in s
        assert "1 must-answer" in s

    def test_serialization_roundtrip(self):
        d = ClarificationDialog(id="d1", goal="Refactor auth", questions=[
            ClarificationQuestion(id="q1", question="Which module?"),
        ])
        data = d.to_dict()
        restored = ClarificationDialog.from_dict(data)
        assert restored.id == "d1"
        assert restored.goal == "Refactor auth"
        assert len(restored.questions) == 1


class TestAmbiguityDetector:
    def test_detects_scope_ambiguity(self):
        detector = AmbiguityDetector()
        signals = detector.analyze("Refactor the code to be better")
        types = [s.type for s in signals]
        assert AmbiguityType.SCOPE in types or AmbiguityType.BEHAVIOR in types

    def test_detects_behavior_ambiguity(self):
        detector = AmbiguityDetector()
        signals = detector.analyze("Improve the error handling")
        types = [s.type for s in signals]
        assert AmbiguityType.BEHAVIOR in types

    def test_detects_constraint_ambiguity(self):
        detector = AmbiguityDetector()
        signals = detector.analyze("Make the API fast and efficient")
        types = [s.type for s in signals]
        assert AmbiguityType.CONSTRAINT in types

    def test_specific_goal_fewer_signals(self):
        detector = AmbiguityDetector()
        vague = detector.analyze("Fix everything in the whole codebase to be better")
        specific = detector.analyze("Add type hint to parse_config in src/config.py line 42")
        assert len(vague) >= len(specific)

    def test_confidence_ordering(self):
        detector = AmbiguityDetector()
        signals = detector.analyze("Refactor and improve everything")
        if len(signals) > 1:
            # Should be sorted by confidence descending
            for i in range(len(signals) - 1):
                assert signals[i].confidence >= signals[i + 1].confidence

    def test_deduplicate_by_type(self):
        detector = AmbiguityDetector()
        signals = detector.analyze("Refactor and modify the code to change it")
        # Multiple SCOPE triggers should be deduplicated to one
        scope_count = sum(1 for s in signals if s.type == AmbiguityType.SCOPE)
        assert scope_count <= 1

    def test_min_confidence_filter(self):
        detector = AmbiguityDetector()
        all_signals = detector.analyze("Fix the code", min_confidence=0.0)
        high_signals = detector.analyze("Fix the code", min_confidence=0.9)
        assert len(all_signals) >= len(high_signals)

    def test_custom_rule(self):
        detector = AmbiguityDetector()
        detector.add_rule(lambda text: [
            AmbiguitySignal(
                type=AmbiguityType.NAMING,
                description="Custom rule triggered",
                confidence=0.9,
                suggested_question="Which config?",
            )
        ] if "config" in text.lower() else [])

        signals = detector.analyze("Update the config")
        types = [s.type for s in signals]
        assert AmbiguityType.NAMING in types

    def test_custom_rule_error_handled(self):
        detector = AmbiguityDetector()
        detector.add_rule(lambda text: 1 / 0)  # Bad rule
        # Should not crash
        signals = detector.analyze("Test input")
        assert isinstance(signals, list)

    def test_generate_dialog(self):
        detector = AmbiguityDetector()
        dialog = detector.generate_dialog("Refactor everything to be better and faster")
        assert isinstance(dialog, ClarificationDialog)
        assert dialog.goal == "Refactor everything to be better and faster"
        assert len(dialog.questions) > 0

    def test_generate_dialog_with_signals(self):
        detector = AmbiguityDetector()
        signals = [
            AmbiguitySignal(
                type=AmbiguityType.SCOPE,
                confidence=0.9,
                suggested_question="Which files?",
            ),
        ]
        dialog = detector.generate_dialog("Fix it", signals=signals)
        assert len(dialog.questions) == 1
        assert dialog.questions[0].question == "Which files?"
        assert dialog.questions[0].priority == 1  # High confidence → must-answer

    def test_generate_dialog_max_questions(self):
        detector = AmbiguityDetector()
        signals = [
            AmbiguitySignal(type=AmbiguityType.SCOPE, confidence=0.8, suggested_question=f"Q{i}")
            for i in range(10)
        ]
        dialog = detector.generate_dialog("Test", signals=signals, max_questions=3)
        assert len(dialog.questions) == 3

    def test_quick_check_vague(self):
        detector = AmbiguityDetector()
        assert detector.quick_check("Improve everything in the whole codebase")

    def test_quick_check_specific(self):
        detector = AmbiguityDetector()
        # Very specific goal — less likely to trigger
        result = detector.quick_check("Add 'return None' on line 42 of src/parser.py")
        # This might or might not trigger — just ensure it doesn't crash
        assert isinstance(result, bool)

    def test_priority_assignment(self):
        detector = AmbiguityDetector()
        signals = [
            AmbiguitySignal(type=AmbiguityType.SCOPE, confidence=0.9, suggested_question="High"),
            AmbiguitySignal(type=AmbiguityType.BEHAVIOR, confidence=0.6, suggested_question="Med"),
            AmbiguitySignal(type=AmbiguityType.EDGE_CASE, confidence=0.4, suggested_question="Low"),
        ]
        dialog = detector.generate_dialog("Test", signals=signals)
        assert dialog.questions[0].priority == 1  # 0.9 >= 0.7
        assert dialog.questions[1].priority == 2  # 0.6 >= 0.5
        assert dialog.questions[2].priority == 3  # 0.4 < 0.5
