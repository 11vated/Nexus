"""Tests for the persistent memory and feedback learning system."""

import os
import tempfile
import time
from pathlib import Path

import pytest
import yaml

from nexus.cognitive.feedback import (
    FeedbackCollector,
    FeedbackSignal,
    FeedbackSystem,
    FeedbackType,
    Preference,
    PreferenceCategory,
    PreferenceLearner,
    UserProfile,
)


# ── Preference tests ────────────────────────────────────────────────────────


class TestPreference:
    def test_create_preference(self):
        p = Preference(
            key="naming", value="snake_case",
            category=PreferenceCategory.CODING_STYLE,
        )
        assert p.key == "naming"
        assert p.value == "snake_case"
        assert p.confidence == 0.5
        assert p.signal_count == 0
        assert not p.is_strong

    def test_reinforce_increases_confidence(self):
        p = Preference(
            key="naming", value="snake_case",
            category=PreferenceCategory.CODING_STYLE,
        )
        original_conf = p.confidence
        p.reinforce("example_var")
        assert p.confidence > original_conf
        assert p.signal_count == 1
        assert "example_var" in p.examples

    def test_reinforce_caps_at_5_examples(self):
        p = Preference(key="x", value="y", category=PreferenceCategory.CODING_STYLE)
        for i in range(10):
            p.reinforce(f"example_{i}")
        assert len(p.examples) == 5

    def test_contradict_decreases_confidence(self):
        p = Preference(
            key="naming", value="snake_case",
            category=PreferenceCategory.CODING_STYLE,
            confidence=0.8,
        )
        p.contradict()
        assert p.confidence < 0.8
        assert p.contradictions == 1

    def test_is_strong_requires_confidence_and_count(self):
        p = Preference(
            key="naming", value="snake_case",
            category=PreferenceCategory.CODING_STYLE,
            confidence=0.8,
            signal_count=2,
        )
        assert not p.is_strong  # Not enough signals

        p.signal_count = 3
        assert p.is_strong

        p.confidence = 0.5
        assert not p.is_strong  # Low confidence

    def test_serialization_roundtrip(self):
        p = Preference(
            key="test_key", value="test_val",
            category=PreferenceCategory.TOOLS,
            confidence=0.85,
            signal_count=5,
            contradictions=1,
            examples=["ex1", "ex2"],
        )
        data = p.to_dict()
        p2 = Preference.from_dict(data)
        assert p2.key == "test_key"
        assert p2.value == "test_val"
        assert p2.category == PreferenceCategory.TOOLS
        assert p2.confidence == 0.85
        assert p2.signal_count == 5
        assert p2.contradictions == 1
        assert p2.examples == ["ex1", "ex2"]


# ── UserProfile tests ──────────────────────────────────────────────────────


class TestUserProfile:
    def test_create_empty_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            assert profile.session_count == 0
            assert profile.total_turns == 0
            assert len(profile.preferences) == 0

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save
            profile = UserProfile(workspace=tmpdir)
            profile.session_count = 5
            profile.total_turns = 100
            profile.preferences["naming"] = Preference(
                key="naming", value="snake_case",
                category=PreferenceCategory.CODING_STYLE,
                confidence=0.8,
                signal_count=4,
            )
            profile.record_tool_usage("file_write")
            profile.record_tool_usage("file_write")
            profile.save()

            # Verify file exists
            assert (Path(tmpdir) / ".nexus" / "profile.yaml").exists()

            # Load
            profile2 = UserProfile(workspace=tmpdir)
            assert profile2.session_count == 5
            assert profile2.total_turns == 100
            assert "naming" in profile2.preferences
            assert profile2.preferences["naming"].value == "snake_case"
            assert profile2.preferences["naming"].confidence == 0.8
            assert profile2.tool_usage["file_write"] == 2

    def test_corrupted_file_handled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nexus_dir = Path(tmpdir) / ".nexus"
            nexus_dir.mkdir()
            (nexus_dir / "profile.yaml").write_text("{{invalid yaml!!")
            # Should not raise
            profile = UserProfile(workspace=tmpdir)
            assert profile.session_count == 0

    def test_empty_yaml_handled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nexus_dir = Path(tmpdir) / ".nexus"
            nexus_dir.mkdir()
            (nexus_dir / "profile.yaml").write_text("")
            profile = UserProfile(workspace=tmpdir)
            assert profile.session_count == 0

    def test_get_strong_preferences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            profile.preferences["weak"] = Preference(
                key="weak", value="x",
                category=PreferenceCategory.CODING_STYLE,
                confidence=0.3,
                signal_count=1,
            )
            profile.preferences["strong"] = Preference(
                key="strong", value="y",
                category=PreferenceCategory.CODING_STYLE,
                confidence=0.9,
                signal_count=5,
            )
            strong = profile.get_strong_preferences()
            assert len(strong) == 1
            assert strong[0].key == "strong"

    def test_get_context_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            profile.preferences["naming"] = Preference(
                key="naming", value="snake_case",
                category=PreferenceCategory.CODING_STYLE,
                confidence=0.9,
                signal_count=5,
            )
            prompt = profile.get_context_prompt()
            assert "snake_case" in prompt
            assert "naming" in prompt

    def test_get_context_prompt_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            prompt = profile.get_context_prompt()
            assert prompt == ""

    def test_record_correction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            profile.record_correction("old code", "new code", "context")
            assert len(profile.corrections) == 1
            assert profile.corrections[0]["original"] == "old code"

    def test_corrections_bounded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            for i in range(60):
                profile.record_correction(f"old_{i}", f"new_{i}")
            assert len(profile.corrections) == 50

    def test_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            profile.session_count = 10
            summary = profile.summary()
            assert "10 sessions" in summary

    def test_preferences_by_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            profile.preferences["naming"] = Preference(
                key="naming", value="snake_case",
                category=PreferenceCategory.CODING_STYLE,
            )
            profile.preferences["framework"] = Preference(
                key="framework", value="pytest",
                category=PreferenceCategory.TESTING,
            )
            coding = profile.get_preferences_by_category(PreferenceCategory.CODING_STYLE)
            assert len(coding) == 1
            assert coding[0].key == "naming"


# ── FeedbackCollector tests ─────────────────────────────────────────────────


class TestFeedbackCollector:
    def test_collect_signal(self):
        collector = FeedbackCollector()
        signal = FeedbackSignal(
            feedback_type=FeedbackType.EXPLICIT_POSITIVE,
            category=PreferenceCategory.COMMUNICATION,
            signal="good response",
        )
        collector.collect(signal)
        assert len(collector.signals) == 1

    def test_collect_diff_accepted(self):
        collector = FeedbackCollector()
        collector.collect_diff_accepted("main.py", {"added": 5})
        assert len(collector.signals) == 1
        assert collector.signals[0].feedback_type == FeedbackType.DIFF_ACCEPTED

    def test_collect_diff_rejected(self):
        collector = FeedbackCollector()
        collector.collect_diff_rejected("main.py", "wrong approach")
        assert len(collector.signals) == 1
        assert collector.signals[0].feedback_type == FeedbackType.DIFF_REJECTED

    def test_collect_explicit(self):
        collector = FeedbackCollector()
        collector.collect_explicit("great work", positive=True)
        collector.collect_explicit("that's wrong", positive=False)
        assert len(collector.signals) == 2
        assert collector.signals[0].feedback_type == FeedbackType.EXPLICIT_POSITIVE
        assert collector.signals[1].feedback_type == FeedbackType.EXPLICIT_NEGATIVE

    def test_collect_correction(self):
        collector = FeedbackCollector()
        collector.collect_correction("old code", "new code")
        assert len(collector.signals) == 1
        assert collector.signals[0].feedback_type == FeedbackType.EXPLICIT_CORRECTION

    def test_collect_tool_preference(self):
        collector = FeedbackCollector()
        collector.collect_tool_preference("file_write", used=True)
        assert len(collector.signals) == 1

    def test_collect_style(self):
        collector = FeedbackCollector()
        collector.collect_style("indent", "4_spaces")
        assert len(collector.signals) == 1

    def test_drain_clears_signals(self):
        collector = FeedbackCollector()
        collector.collect_explicit("test", True)
        collector.collect_explicit("test2", True)
        signals = collector.drain()
        assert len(signals) == 2
        assert len(collector.signals) == 0

    def test_bounded_signal_count(self):
        collector = FeedbackCollector()
        for i in range(300):
            collector.collect_explicit(f"signal_{i}", True)
        assert len(collector.signals) == 200


# ── PreferenceLearner tests ─────────────────────────────────────────────────


class TestPreferenceLearner:
    def test_learn_from_style_signal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            learner = PreferenceLearner(profile)

            signals = [FeedbackSignal(
                feedback_type=FeedbackType.STYLE_SIGNAL,
                category=PreferenceCategory.CODING_STYLE,
                signal="indent: 4_spaces",
            )]
            summaries = learner.learn_from_signals(signals)
            assert len(summaries) == 1
            assert "indent" in profile.preferences
            assert profile.preferences["indent"].value == "4_spaces"

    def test_reinforce_existing_preference(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            learner = PreferenceLearner(profile)

            # Create initial preference
            signals = [FeedbackSignal(
                feedback_type=FeedbackType.STYLE_SIGNAL,
                category=PreferenceCategory.CODING_STYLE,
                signal="indent: 4_spaces",
            )]
            learner.learn_from_signals(signals)
            initial_conf = profile.preferences["indent"].confidence

            # Reinforce
            learner.learn_from_signals(signals)
            assert profile.preferences["indent"].confidence > initial_conf

    def test_contradiction_weakens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            learner = PreferenceLearner(profile)

            # Establish preference
            profile.preferences["indent"] = Preference(
                key="indent", value="4_spaces",
                category=PreferenceCategory.CODING_STYLE,
                confidence=0.7,
                signal_count=3,
            )

            # Contradict
            signals = [FeedbackSignal(
                feedback_type=FeedbackType.STYLE_SIGNAL,
                category=PreferenceCategory.CODING_STYLE,
                signal="indent: 2_spaces",
            )]
            learner.learn_from_signals(signals)
            assert profile.preferences["indent"].confidence < 0.7

    def test_learn_from_code_snake_case(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            learner = PreferenceLearner(profile)

            code = """
def my_function():
    my_variable = get_some_data()
    another_var = process_data(my_variable)
    return final_result
"""
            summaries = learner.learn_from_code(code, "main.py")
            assert "naming_convention" in profile.preferences
            assert profile.preferences["naming_convention"].value == "snake_case"

    def test_learn_from_code_type_hints(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            learner = PreferenceLearner(profile)

            code = """
def process(name: str, count: int, data: List[str], flag: bool) -> Optional[Dict]:
    result: Any = None
    return result
"""
            learner.learn_from_code(code)
            assert "type_hints" in profile.preferences
            assert profile.preferences["type_hints"].value == "yes"

    def test_learn_from_code_pytest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            learner = PreferenceLearner(profile)

            code = """
import pytest

def test_something():
    assert True

@pytest.fixture
def sample_data():
    return [1, 2, 3]
"""
            learner.learn_from_code(code)
            assert "test_framework" in profile.preferences
            assert profile.preferences["test_framework"].value == "pytest"

    def test_learn_from_code_google_docstrings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            learner = PreferenceLearner(profile)

            code = '''
def process(name, count):
    """Process something.

    Args:
        name: The name to process.
        count: How many times.
    """
    pass
'''
            learner.learn_from_code(code)
            assert "docstring_style" in profile.preferences
            assert profile.preferences["docstring_style"].value == "google"

    def test_preference_switch_after_many_contradictions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = UserProfile(workspace=tmpdir)
            learner = PreferenceLearner(profile)

            # Establish weak preference
            profile.preferences["indent"] = Preference(
                key="indent", value="tabs",
                category=PreferenceCategory.CODING_STYLE,
                confidence=0.4,
                signal_count=2,
            )

            # Contradict multiple times
            signal = FeedbackSignal(
                feedback_type=FeedbackType.STYLE_SIGNAL,
                category=PreferenceCategory.CODING_STYLE,
                signal="indent: 4_spaces",
            )
            for _ in range(5):
                learner.learn_from_signals([signal])

            # Should have switched
            assert profile.preferences["indent"].value == "4_spaces"


# ── FeedbackSystem tests ───────────────────────────────────────────────────


class TestFeedbackSystem:
    def test_create_system(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            assert fb.profile.session_count == 0

    def test_on_diff_accepted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.on_diff_accepted("main.py", {"added": 5})
            assert len(fb.collector.signals) == 1

    def test_on_diff_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.on_diff_rejected("main.py", "wrong approach")
            assert len(fb.collector.signals) == 1

    def test_on_code_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.on_code_written("def my_func(): pass", "main.py")
            # Queued for processing
            assert len(fb._pending_code) == 1

    def test_process_batch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.on_code_written("""
def my_function():
    my_variable = get_some_data()
    another_var = process_data(my_variable)
    final_result = compute_result()
    return final_result
""", "main.py")
            summaries = fb.process()
            assert len(summaries) > 0

    def test_on_session_start(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.on_session_start()
            assert fb.profile.session_count == 1

    def test_on_turn(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.on_turn()
            fb.on_turn()
            assert fb.profile.total_turns == 2

    def test_on_tool_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.on_tool_used("file_write")
            fb.on_tool_used("file_write")
            fb.on_tool_used("shell")
            assert fb.profile.tool_usage["file_write"] == 2
            assert fb.profile.tool_usage["shell"] == 1

    def test_get_prompt_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.profile.preferences["naming"] = Preference(
                key="naming", value="snake_case",
                category=PreferenceCategory.CODING_STYLE,
                confidence=0.9,
                signal_count=5,
            )
            ctx = fb.get_prompt_context()
            assert "snake_case" in ctx

    def test_get_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            fb.on_session_start()
            summary = fb.get_summary()
            assert "1 sessions" in summary

    def test_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fb = FeedbackSystem(workspace=tmpdir)
            stats = fb.stats()
            assert "session_count" in stats
            assert "preferences_count" in stats

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # First instance
            fb1 = FeedbackSystem(workspace=tmpdir)
            fb1.on_session_start()
            fb1.profile.preferences["test"] = Preference(
                key="test", value="val",
                category=PreferenceCategory.CODING_STYLE,
                confidence=0.8,
                signal_count=3,
            )
            fb1.profile.save()

            # Second instance
            fb2 = FeedbackSystem(workspace=tmpdir)
            assert fb2.profile.session_count == 1
            assert "test" in fb2.profile.preferences
            assert fb2.profile.preferences["test"].value == "val"
