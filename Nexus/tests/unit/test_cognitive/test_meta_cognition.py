"""Tests for MetaCognitiveEngine module."""

import time
from unittest.mock import AsyncMock

import pytest

from nexus.agent.models import AgentConfig
from nexus.cognitive.meta_cognition import (
    Assumption,
    ConfidenceLevel,
    MetaCognitiveEngine,
    ReasoningEntry,
    ReasoningJournal,
    StrategyProfile,
)


@pytest.fixture
def config():
    return AgentConfig(
        planning_model="deepseek-r1:7b",
        coding_model="qwen2.5-coder:14b",
        fast_model="qwen2.5-coder:7b",
    )


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="test response")
    return llm


class TestConfidenceLevel:
    def test_enum_values(self):
        assert ConfidenceLevel.VERY_LOW.value == 0.1
        assert ConfidenceLevel.LOW.value == 0.3
        assert ConfidenceLevel.MEDIUM.value == 0.5
        assert ConfidenceLevel.HIGH.value == 0.7
        assert ConfidenceLevel.VERY_HIGH.value == 0.9


class TestAssumption:
    def test_defaults(self):
        a = Assumption(id="1", statement="test")
        assert a.confidence == 0.5
        assert a.evidence == ""
        assert a.resolved is False

    def test_to_dict(self):
        a = Assumption(
            id="1",
            statement="Python is the language",
            confidence=0.8,
            evidence=".py files found",
        )
        d = a.to_dict()
        assert d["id"] == "1"
        assert d["confidence"] == 0.8

    def test_from_dict_roundtrip(self):
        a = Assumption(
            id="2",
            statement="User wants tests",
            confidence=0.6,
            falsifiable_by="ask user",
        )
        d = a.to_dict()
        restored = Assumption.from_dict(d)
        assert restored.id == a.id
        assert restored.statement == a.statement
        assert restored.confidence == a.confidence


class TestReasoningEntry:
    def test_defaults(self):
        e = ReasoningEntry(id="1", decision="use pytest", rationale="standard")
        assert e.alternatives_considered == []
        assert e.confidence == 0.5
        assert e.outcome == ""

    def test_to_dict(self):
        e = ReasoningEntry(
            id="1",
            decision="use pytest",
            rationale="standard choice",
            alternatives_considered=["unittest"],
            confidence=0.8,
            tags=["testing"],
        )
        d = e.to_dict()
        assert d["alternatives_considered"] == ["unittest"]
        assert d["tags"] == ["testing"]

    def test_from_dict_roundtrip(self):
        e = ReasoningEntry(
            id="2",
            decision="refactor",
            rationale="clean code",
            alternatives_considered=["rewrite"],
            assumptions=["code is testable"],
            confidence=0.7,
            outcome="success",
            outcome_quality=0.9,
            tags=["refactor"],
        )
        d = e.to_dict()
        restored = ReasoningEntry.from_dict(d)
        assert restored.decision == e.decision
        assert restored.alternatives_considered == e.alternatives_considered
        assert restored.outcome_quality == e.outcome_quality


class TestReasoningJournal:
    def test_add_entry(self):
        journal = ReasoningJournal()
        entry = ReasoningEntry(id="1", decision="test", rationale="reason")
        journal.add(entry)
        assert len(journal.entries) == 1

    def test_max_entries(self):
        journal = ReasoningJournal(max_entries=5)
        for i in range(10):
            journal.add(ReasoningEntry(id=str(i), decision=f"d_{i}", rationale="r"))
        assert len(journal.entries) == 5
        assert journal.entries[0].id == "5"

    def test_get_by_tag(self):
        journal = ReasoningJournal()
        journal.add(ReasoningEntry(id="1", decision="a", rationale="r", tags=["testing"]))
        journal.add(ReasoningEntry(id="2", decision="b", rationale="r", tags=["security"]))
        journal.add(ReasoningEntry(id="3", decision="c", rationale="r", tags=["testing"]))

        results = journal.get_by_tag("testing")
        assert len(results) == 2

    def test_get_recent(self):
        journal = ReasoningJournal()
        for i in range(20):
            journal.add(ReasoningEntry(id=str(i), decision=f"d_{i}", rationale="r"))

        recent = journal.get_recent(5)
        assert len(recent) == 5
        assert recent[-1].id == "19"

    def test_get_low_confidence(self):
        journal = ReasoningJournal()
        journal.add(ReasoningEntry(id="1", decision="a", rationale="r", confidence=0.3))
        journal.add(ReasoningEntry(id="2", decision="b", rationale="r", confidence=0.8))
        journal.add(ReasoningEntry(id="3", decision="c", rationale="r", confidence=0.2))

        low = journal.get_low_confidence(threshold=0.4)
        assert len(low) == 2

    def test_get_failed(self):
        journal = ReasoningJournal()
        journal.add(ReasoningEntry(id="1", decision="a", rationale="r", outcome_quality=0.2))
        journal.add(ReasoningEntry(id="2", decision="b", rationale="r", outcome_quality=0.8))
        journal.add(ReasoningEntry(id="3", decision="c", rationale="r", outcome_quality=0.1))

        failed = journal.get_failed()
        assert len(failed) == 2

    def test_summary_stats_empty(self):
        journal = ReasoningJournal()
        stats = journal.summary_stats()
        assert stats["total"] == 0

    def test_summary_stats(self):
        journal = ReasoningJournal()
        journal.add(ReasoningEntry(id="1", decision="a", rationale="r", confidence=0.8, outcome_quality=0.9))
        journal.add(ReasoningEntry(id="2", decision="b", rationale="r", confidence=0.6, outcome_quality=0.5))

        stats = journal.summary_stats()
        assert stats["total"] == 2
        assert stats["avg_confidence"] == pytest.approx(0.7)

    def test_serialization_roundtrip(self):
        journal = ReasoningJournal(max_entries=100)
        journal.add(ReasoningEntry(id="1", decision="a", rationale="r", confidence=0.8, tags=["test"]))
        journal.add(ReasoningEntry(id="2", decision="b", rationale="r", confidence=0.5))

        data = journal.to_dict()
        restored = ReasoningJournal.from_dict(data)

        assert len(restored.entries) == 2
        assert restored.max_entries == 100


class TestStrategyProfile:
    def test_defaults(self):
        p = StrategyProfile(name="tdd")
        assert p.times_used == 0
        assert p.success_rate == 0.0

    def test_record_outcome_success(self):
        p = StrategyProfile(name="tdd")
        p.record_outcome(quality=0.9, duration_ms=100.0, context="test1")
        assert p.times_used == 1
        assert p.success_count == 1
        assert p.success_rate == 1.0

    def test_record_outcome_failure(self):
        p = StrategyProfile(name="big-bang")
        p.record_outcome(quality=0.3, duration_ms=500.0)
        assert p.times_used == 1
        assert p.success_count == 0
        assert p.success_rate == 0.0

    def test_multiple_outcomes(self):
        p = StrategyProfile(name="incremental")
        p.record_outcome(quality=0.8, duration_ms=100.0)
        p.record_outcome(quality=0.9, duration_ms=80.0)
        p.record_outcome(quality=0.4, duration_ms=200.0)

        assert p.times_used == 3
        assert p.success_count == 2
        assert p.success_rate == pytest.approx(2 / 3, abs=0.01)
        assert p.avg_quality == pytest.approx(0.7, abs=0.01)

    def test_context_tracking(self):
        p = StrategyProfile(name="refactor")
        p.record_outcome(quality=0.8, duration_ms=100.0, context="auth_module")
        p.record_outcome(quality=0.9, duration_ms=80.0, context="api_layer")
        p.record_outcome(quality=0.7, duration_ms=120.0, context="auth_module")

        assert len(p.contexts) == 2
        assert "auth_module" in p.contexts
        assert "api_layer" in p.contexts

    def test_serialization_roundtrip(self):
        p = StrategyProfile(name="tdd")
        p.record_outcome(quality=0.9, duration_ms=100.0, context="test")

        data = p.to_dict()
        restored = StrategyProfile.from_dict(data)

        assert restored.name == "tdd"
        assert restored.times_used == 1
        assert restored.success_rate == 1.0


class TestMetaCognitiveEngineInit:
    def test_creates_with_config(self, config):
        engine = MetaCognitiveEngine(config=config)
        assert engine.llm is not None
        assert engine.journal is not None
        assert engine.assumptions == {}

    def test_custom_llm(self, config, mock_llm):
        engine = MetaCognitiveEngine(config=config, llm=mock_llm)
        assert engine.llm is mock_llm


class TestMetaCognitiveEngineAssumptions:
    def test_add_assumption(self, config):
        engine = MetaCognitiveEngine(config=config)
        a = engine.add_assumption("Python is the language", evidence=".py files")
        assert a.id in engine.assumptions
        assert a.statement == "Python is the language"

    def test_resolve_assumption_correct(self, config):
        engine = MetaCognitiveEngine(config=config)
        a = engine.add_assumption("Python is the language")
        engine.resolve_assumption(a.id, "Confirmed by file extension", was_correct=True)

        assert engine.assumptions[a.id].resolved is True
        assert engine.assumptions[a.id].resolution == "Confirmed by file extension"

    def test_resolve_assumption_incorrect(self, config):
        engine = MetaCognitiveEngine(config=config)
        a = engine.add_assumption("Python is the language", confidence=0.8)
        engine.resolve_assumption(a.id, "Actually it's TypeScript", was_correct=False)

        assert engine.assumptions[a.id].resolved is True
        assert engine.assumptions[a.id].confidence == 0.0

    def test_get_unresolved(self, config):
        engine = MetaCognitiveEngine(config=config)
        a1 = engine.add_assumption("A1")
        a2 = engine.add_assumption("A2")
        engine.resolve_assumption(a1.id, "done", was_correct=True)

        unresolved = engine.get_unresolved_assumptions()
        assert len(unresolved) == 1
        assert unresolved[0].id == a2.id

    def test_get_low_confidence_assumptions(self, config):
        engine = MetaCognitiveEngine(config=config)
        engine.add_assumption("A1", confidence=0.3)
        engine.add_assumption("A2", confidence=0.8)
        engine.add_assumption("A3", confidence=0.2)

        low = engine.get_low_confidence_assumptions(threshold=0.4)
        assert len(low) == 2

    def test_assumption_ids_are_unique(self, config):
        engine = MetaCognitiveEngine(config=config)
        a1 = engine.add_assumption("A1")
        a2 = engine.add_assumption("A2")
        assert a1.id != a2.id


class TestMetaCognitiveEngineJournal:
    def test_log_reasoning(self, config):
        engine = MetaCognitiveEngine(config=config)
        entry = engine.log_reasoning(
            decision="use pytest",
            rationale="industry standard",
            alternatives=["unittest"],
            confidence=0.8,
            tags=["testing"],
        )
        assert entry.id.startswith("reason_")
        assert len(engine.journal.entries) == 1

    def test_log_reasoning_defaults(self, config):
        engine = MetaCognitiveEngine(config=config)
        entry = engine.log_reasoning(decision="x", rationale="y")
        assert entry.alternatives_considered == []
        assert entry.assumptions == []
        assert entry.tags == []

    @pytest.mark.asyncio
    async def test_post_review_update(self, config):
        engine = MetaCognitiveEngine(config=config)
        entry = engine.log_reasoning(
            decision="test", rationale="reason", tags=["tdd"],
        )

        engine.record_strategy_outcome("tdd", 0.9, 100.0, entry.id)
        await engine.post_review_update(entry.id, "passed", 0.9, 100.0)

        updated = engine.journal.entries[0]
        assert updated.outcome == "passed"
        assert updated.outcome_quality == 0.9


class TestMetaCognitiveEngineStrategies:
    def test_record_strategy_outcome(self, config):
        engine = MetaCognitiveEngine(config=config)
        engine.record_strategy_outcome("tdd", 0.9, 100.0)
        assert "tdd" in engine.strategies
        assert engine.strategies["tdd"].times_used == 1

    def test_recommend_strategy(self, config):
        engine = MetaCognitiveEngine(config=config)
        engine.record_strategy_outcome("tdd", 0.9, 100.0)
        engine.record_strategy_outcome("big-bang", 0.3, 500.0)

        recommended = engine.recommend_strategy("any")
        assert recommended == "tdd"

    def test_recommend_strategy_no_data(self, config):
        engine = MetaCognitiveEngine(config=config)
        assert engine.recommend_strategy("any") is None


class TestMetaCognitiveEngineCalibration:
    def test_calibration_not_enough_data(self, config):
        engine = MetaCognitiveEngine(config=config)
        assert engine.calibration_score() == 0.5

    def test_calibration_perfect(self, config):
        engine = MetaCognitiveEngine(config=config)
        for i in range(5):
            engine.log_reasoning(
                decision=f"d_{i}",
                rationale="r",
                confidence=0.8,
            )
            engine.journal.entries[-1].outcome_quality = 0.8

        score = engine.calibration_score()
        assert score == pytest.approx(1.0, abs=0.01)

    def test_calibration_poor(self, config):
        engine = MetaCognitiveEngine(config=config)
        for i in range(5):
            engine.log_reasoning(
                decision=f"d_{i}",
                rationale="r",
                confidence=0.9,
            )
            engine.journal.entries[-1].outcome_quality = 0.1

        score = engine.calibration_score()
        assert score < 0.3


class TestMetaCognitiveEnginePreExecute:
    @pytest.mark.asyncio
    async def test_pre_execute_check(self, config, mock_llm):
        mock_llm.generate = AsyncMock(
            return_value=(
                "Rationale: This is the best approach\n"
                "Alternatives:\n"
                "- Alternative A\n"
                "- Alternative B\n"
                "Assumptions:\n"
                "- User has Python installed\n"
                "Confidence: 0.8\n"
                "Needs_info:\n"
                "- Python version"
            )
        )

        engine = MetaCognitiveEngine(config=config, llm=mock_llm)
        result = await engine.pre_execute_check(
            task="create a script",
            approach="write Python file",
            context="user project",
        )

        assert result["confidence"] == 0.8
        assert len(result["assumptions"]) >= 1
        assert len(result["alternatives"]) >= 2
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_pre_execute_creates_assumptions(self, config, mock_llm):
        mock_llm.generate = AsyncMock(
            return_value=(
                "Assumptions:\n"
                "- Python is installed\n"
                "Confidence: 0.7\n"
                "Rationale: Standard approach"
            )
        )

        engine = MetaCognitiveEngine(config=config, llm=mock_llm)
        await engine.pre_execute_check("task", "approach")

        assert len(engine.get_unresolved_assumptions()) >= 1


class TestMetaCognitiveEngineParseResponse:
    def test_parse_full_response(self, config):
        engine = MetaCognitiveEngine(config=config)
        response = (
            "Rationale: Good choice because X\n"
            "Alternatives:\n"
            "- Option A\n"
            "- Option B\n"
            "Assumptions:\n"
            "- User has tools\n"
            "Confidence: 0.75\n"
            "Needs_info:\n"
            "- Tool availability"
        )
        parsed = engine._parse_meta_response(response)

        assert "X" in parsed["rationale"]
        assert len(parsed["alternatives"]) == 2
        assert len(parsed["assumptions"]) == 1
        assert parsed["confidence"] == 0.75
        assert len(parsed["needs_info"]) == 1

    def test_parse_confidence_as_text(self, config):
        engine = MetaCognitiveEngine(config=config)
        response = "Confidence: not_a_number"
        parsed = engine._parse_meta_response(response)
        assert parsed["confidence"] == 0.5

    def test_parse_minimal_response(self, config):
        engine = MetaCognitiveEngine(config=config)
        response = "Just some text without structure"
        parsed = engine._parse_meta_response(response)
        assert parsed["confidence"] == 0.5
        assert parsed["rationale"] == ""

    def test_parse_bullet_items(self, config):
        engine = MetaCognitiveEngine(config=config)
        response = (
            "Assumptions:\n"
            "- First assumption\n"
            "- Second assumption\n"
            "- Third assumption"
        )
        parsed = engine._parse_meta_response(response)
        assert len(parsed["assumptions"]) == 3


class TestMetaCognitiveEngineSerialization:
    def test_to_dict(self, config):
        engine = MetaCognitiveEngine(config=config)
        engine.add_assumption("test", confidence=0.8)
        engine.log_reasoning("decision", "rationale", tags=["test"])
        engine.record_strategy_outcome("tdd", 0.9, 100.0)

        data = engine.to_dict()
        assert "assumptions" in data
        assert "journal" in data
        assert "strategies" in data

    def test_from_dict_roundtrip(self, config, mock_llm):
        engine = MetaCognitiveEngine(config=config, llm=mock_llm)
        a = engine.add_assumption("Python installed", confidence=0.8)
        engine.resolve_assumption(a.id, "confirmed", was_correct=True)
        engine.log_reasoning("use pytest", "standard", confidence=0.9)
        engine.record_strategy_outcome("tdd", 0.85, 150.0)

        data = engine.to_dict()
        restored = MetaCognitiveEngine.from_dict(data, config, mock_llm)

        assert len(restored.assumptions) == 1
        assert len(restored.journal.entries) == 1
        assert len(restored.strategies) == 1
        assert restored._assumption_counter == engine._assumption_counter

    def test_from_dict_empty(self, config, mock_llm):
        restored = MetaCognitiveEngine.from_dict({}, config, mock_llm)
        assert len(restored.assumptions) == 0
        assert len(restored.journal.entries) == 0


class TestMetaCognitiveEngineEdgeCases:
    def test_many_assumptions(self, config):
        engine = MetaCognitiveEngine(config=config)
        for i in range(100):
            engine.add_assumption(f"Assumption {i}")
        assert len(engine.assumptions) == 100

    def test_journal_with_many_entries(self, config):
        engine = MetaCognitiveEngine(config=config)
        for i in range(500):
            engine.log_reasoning(f"decision_{i}", "rationale")

        assert len(engine.journal.entries) == 500

    def test_strategy_with_many_outcomes(self, config):
        engine = MetaCognitiveEngine(config=config)
        for i in range(100):
            engine.record_strategy_outcome("tdd", 0.5 + (i % 5) * 0.1, 100.0 + i)

        profile = engine.strategies["tdd"]
        assert profile.times_used == 100
        assert profile.success_count > 0

    def test_assumption_resolution_preserves_history(self, config):
        engine = MetaCognitiveEngine(config=config)
        a = engine.add_assumption("test", evidence="initial evidence")
        engine.resolve_assumption(a.id, "resolved correctly", was_correct=True)

        assert a.evidence == "initial evidence"
        assert a.resolution == "resolved correctly"
