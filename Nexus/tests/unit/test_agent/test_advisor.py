"""Tests for Advisor Federation module."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.agent.advisor import (
    AdvisorFederation,
    AdvisorReview,
    CostEntry,
    CostTracker,
    ModelProfile,
    Solution,
    TaskComplexity,
    classify_complexity,
)
from nexus.agent.models import AgentConfig


@pytest.fixture
def config():
    return AgentConfig(
        ollama_url="http://localhost:11434",
        fast_model="qwen2.5-coder:7b",
        coding_model="qwen2.5-coder:14b",
        planning_model="deepseek-r1:7b",
    )


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="test response")
    return llm


class TestTaskComplexity:
    def test_enum_values(self):
        assert TaskComplexity.TRIVIAL.value == "trivial"
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.MODERATE.value == "moderate"
        assert TaskComplexity.COMPLEX.value == "complex"
        assert TaskComplexity.CRITICAL.value == "critical"


class TestClassifyComplexity:
    def test_trivial(self):
        assert classify_complexity("hello") == TaskComplexity.TRIVIAL

    def test_simple_read(self):
        assert classify_complexity("read the config file") == TaskComplexity.SIMPLE

    def test_simple_list(self):
        assert classify_complexity("list files") == TaskComplexity.SIMPLE

    def test_simple_show(self):
        assert classify_complexity("show me the code") == TaskComplexity.SIMPLE

    def test_moderate_create(self):
        assert classify_complexity("create a new endpoint") == TaskComplexity.MODERATE

    def test_moderate_fix(self):
        assert classify_complexity("fix the bug") == TaskComplexity.MODERATE

    def test_moderate_refactor(self):
        assert classify_complexity("refactor the auth module") == TaskComplexity.MODERATE

    def test_complex_architect(self):
        assert classify_complexity("architect a new system") == TaskComplexity.COMPLEX

    def test_complex_migrate(self):
        assert classify_complexity("migrate the database") == TaskComplexity.COMPLEX

    def test_critical_security(self):
        assert classify_complexity("fix security vulnerability") == TaskComplexity.CRITICAL

    def test_critical_production(self):
        assert classify_complexity("deploy to production") == TaskComplexity.CRITICAL

    def test_critical_schema(self):
        assert classify_complexity("change database schema") == TaskComplexity.CRITICAL

    def test_has_risk(self):
        assert classify_complexity("read file", has_risk=True) == TaskComplexity.CRITICAL

    def test_long_context(self):
        result = classify_complexity("add feature", context_length=60000)
        assert result in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)


class TestCostEntry:
    def test_defaults(self):
        entry = CostEntry(
            model="test",
            task_type="test",
            complexity="simple",
            tokens_in=100,
            tokens_out=200,
            duration_ms=50.0,
        )
        assert entry.quality_score == 0.0
        assert entry.timestamp > 0


class TestModelProfile:
    def test_update_single(self):
        profile = ModelProfile(model="test")
        entry = CostEntry(
            model="test",
            task_type="code",
            complexity="simple",
            tokens_in=100,
            tokens_out=200,
            duration_ms=50.0,
            quality_score=0.8,
        )
        profile.update(entry)
        assert profile.total_tasks == 1
        assert profile.avg_quality == 0.8
        assert profile.avg_duration_ms == 50.0

    def test_update_multiple(self):
        profile = ModelProfile(model="test")
        for score in [0.5, 0.7, 0.9]:
            entry = CostEntry(
                model="test",
                task_type="code",
                complexity="simple",
                tokens_in=100,
                tokens_out=200,
                duration_ms=50.0,
                quality_score=score,
            )
            profile.update(entry)

        assert profile.total_tasks == 3
        assert profile.avg_quality == pytest.approx(0.7, abs=0.01)

    def test_complexity_scores(self):
        profile = ModelProfile(model="test")
        entry1 = CostEntry(
            model="test", task_type="code", complexity="simple",
            tokens_in=100, tokens_out=200, duration_ms=50.0, quality_score=0.8,
        )
        entry2 = CostEntry(
            model="test", task_type="code", complexity="complex",
            tokens_in=500, tokens_out=300, duration_ms=200.0, quality_score=0.6,
        )
        profile.update(entry1)
        profile.update(entry2)

        assert profile.complexity_scores["simple"] == 0.8
        assert profile.complexity_scores["complex"] == 0.6


class TestCostTracker:
    def test_record(self):
        tracker = CostTracker()
        tracker.record(
            model="test",
            task_type="code",
            complexity=TaskComplexity.SIMPLE,
            tokens_in=100,
            tokens_out=200,
            duration_ms=50.0,
        )
        assert len(tracker.log) == 1
        assert "test" in tracker.profiles

    def test_get_best_model_no_data(self):
        tracker = CostTracker()
        assert tracker.get_best_model() is None

    def test_get_best_model(self):
        tracker = CostTracker()
        tracker.record("model_a", "code", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.9)
        tracker.record("model_b", "code", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.5)

        assert tracker.get_best_model() == "model_a"

    def test_get_best_model_by_task_type(self):
        tracker = CostTracker()
        tracker.record("model_a", "code", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.3)
        tracker.record("model_a", "test", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.95)
        tracker.record("model_b", "code", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.9)
        tracker.record("model_b", "test", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.4)

        best_code = tracker.get_best_model(task_type="code")
        assert best_code == "model_b"

    def test_summary(self):
        tracker = CostTracker()
        tracker.record("model_a", "code", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.8)
        summary = tracker.summary()

        assert "model_a" in summary
        assert summary["model_a"]["total_tasks"] == 1
        assert summary["model_a"]["avg_quality"] == 0.8

    def test_serialization_roundtrip(self):
        tracker = CostTracker()
        tracker.record("model_a", "code", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.8)
        tracker.record("model_b", "test", TaskComplexity.COMPLEX, 500, 300, 200.0, 0.6)

        data = tracker.to_dict()
        restored = CostTracker.from_dict(data)

        assert len(restored.log) == 2
        assert len(restored.profiles) == 2
        assert "model_a" in restored.profiles
        assert "model_b" in restored.profiles

    def test_from_dict_empty(self):
        tracker = CostTracker.from_dict({})
        assert len(tracker.log) == 0
        assert len(tracker.profiles) == 0


class TestAdvisorReview:
    def test_defaults(self):
        review = AdvisorReview(has_issues=False)
        assert review.issues == []
        assert review.suggestions == []
        assert review.severity == "info"
        assert review.confidence == 0.5


class TestSolution:
    def test_defaults(self):
        sol = Solution(
            content="code",
            model_used="test",
            complexity=TaskComplexity.SIMPLE,
        )
        assert sol.review is None
        assert sol.revision_count == 0


class TestAdvisorFederationInit:
    def test_creates_with_config(self, config):
        fed = AdvisorFederation(config=config)
        assert fed.executor is not None
        assert fed.advisor is not None
        assert isinstance(fed.cost_tracker, CostTracker)

    def test_custom_llm_clients(self, config, mock_llm):
        fed = AdvisorFederation(config=config, executor=mock_llm, advisor=mock_llm)
        assert fed.executor is mock_llm
        assert fed.advisor is mock_llm


class TestAdvisorFederationExecute:
    @pytest.mark.asyncio
    async def test_trivial_no_review(self, config, mock_llm):
        mock_llm.generate = AsyncMock(return_value="simple answer")
        fed = AdvisorFederation(config=config, executor=mock_llm, advisor=mock_llm)

        result = await fed.execute_with_review("list files", task_type="query")

        assert result.content == "simple answer"
        assert result.revision_count == 0
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_moderate_triggers_review(self, config):
        executor = AsyncMock()
        executor.generate = AsyncMock(return_value="initial solution")

        advisor = AsyncMock()
        advisor.generate = AsyncMock(return_value="NO ISSUES FOUND")

        fed = AdvisorFederation(config=config, executor=executor, advisor=advisor)
        result = await fed.execute_with_review("create a new API endpoint", task_type="code")

        assert result.content == "initial solution"
        assert result.review is not None
        assert result.review.has_issues is False
        advisor.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_with_issues(self, config):
        executor = AsyncMock()
        executor.generate = AsyncMock(return_value="initial solution")

        advisor = AsyncMock()
        advisor.generate = AsyncMock(
            return_value=(
                "ISSUES: Missing error handling\n"
                "- No input validation\n"
                "SUGGESTIONS: Add try/except\n"
                "- Use proper logging\n"
                "SEVERITY: warning\n"
                "CONFIDENCE: 0.8"
            )
        )

        fed = AdvisorFederation(config=config, executor=executor, advisor=advisor)
        result = await fed.execute_with_review("create a new API endpoint", task_type="code")

        assert result.review is not None
        assert result.review.has_issues is True
        assert len(result.review.issues) >= 1
        assert result.review.severity == "warning"
        assert result.review.confidence == 0.8

    @pytest.mark.asyncio
    async def test_revision_on_critical_issue(self, config):
        executor = AsyncMock()
        executor.generate = AsyncMock(side_effect=[
            "initial solution",
            "revised solution",
        ])

        advisor = AsyncMock()
        advisor.generate = AsyncMock(
            return_value=(
                "ISSUES: Security vulnerability\n"
                "SEVERITY: critical\n"
                "CONFIDENCE: 0.9"
            )
        )

        fed = AdvisorFederation(config=config, executor=executor, advisor=advisor)
        result = await fed.execute_with_review(
            "implement user authentication",
            task_type="security",
            max_revisions=1,
        )

        assert result.revision_count == 1
        assert result.content == "revised solution"
        assert executor.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_max_revisions_respected(self, config):
        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "initial"
            return "revised"

        executor = AsyncMock()
        executor.generate = AsyncMock(side_effect=mock_generate)

        advisor = AsyncMock()
        advisor.generate = AsyncMock(
            return_value="ISSUES: Problem\nSEVERITY: critical\nCONFIDENCE: 0.9"
        )

        fed = AdvisorFederation(config=config, executor=executor, advisor=advisor)
        result = await fed.execute_with_review(
            "complex task",
            task_type="code",
            max_revisions=0,
        )

        assert result.revision_count == 0

    @pytest.mark.asyncio
    async def test_cost_tracking_after_execution(self, config, mock_llm):
        mock_llm.generate = AsyncMock(return_value="result")
        fed = AdvisorFederation(config=config, executor=mock_llm, advisor=mock_llm)

        await fed.execute_with_review("create feature", task_type="code")

        assert len(fed.cost_tracker.log) == 1
        entry = fed.cost_tracker.log[0]
        assert entry.task_type == "code"


class TestAdvisorFederationConsensus:
    @pytest.mark.asyncio
    async def test_consensus_all_agree(self, config):
        async def mock_same_response(*args, **kwargs):
            return "identical answer"

        executor = AsyncMock()
        executor.generate = AsyncMock(side_effect=mock_same_response)

        fed = AdvisorFederation(config=config, executor=executor, advisor=executor)

        with patch("nexus.agent.advisor.OllamaClient", return_value=executor):
            result = await fed.consensus_route(
                "what is 2+2?",
                models=["model_a", "model_b"],
            )

        assert result["consensus"] is True
        assert len(result["disagreements"]) == 0

    @pytest.mark.asyncio
    async def test_consensus_disagreement(self, config):
        call_count = 0

        async def mock_diff_responses(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return "answer_a" if call_count == 1 else "answer_b"

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=mock_diff_responses)

        fed = AdvisorFederation(config=config, executor=mock_client, advisor=mock_client)

        with patch("nexus.agent.advisor.OllamaClient", return_value=mock_client):
            result = await fed.consensus_route(
                "choose approach",
                models=["model_a", "model_b"],
            )

        assert result["consensus"] is False
        assert len(result["disagreements"]) >= 1

    @pytest.mark.asyncio
    async def test_consensus_default_models(self, config):
        executor = AsyncMock()
        executor.generate = AsyncMock(return_value="same")

        fed = AdvisorFederation(config=config, executor=executor, advisor=executor)

        with patch("nexus.agent.advisor.OllamaClient", return_value=executor):
            result = await fed.consensus_route("task")

        assert result["model_count"] == 3


class TestAdvisorFederationSerialization:
    def test_to_dict(self, config, mock_llm):
        fed = AdvisorFederation(config=config, executor=mock_llm, advisor=mock_llm)
        fed.cost_tracker.record(
            "model_a", "code", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.8,
        )

        data = fed.to_dict()
        assert "cost_tracker" in data
        assert "review_threshold" in data

    def test_from_dict_roundtrip(self, config, mock_llm):
        fed = AdvisorFederation(config=config, executor=mock_llm, advisor=mock_llm)
        fed.cost_tracker.record(
            "model_a", "code", TaskComplexity.SIMPLE, 100, 200, 50.0, 0.8,
        )

        data = fed.to_dict()
        restored = AdvisorFederation.from_dict(data, config, mock_llm, mock_llm)

        assert len(restored.cost_tracker.log) == 1


class TestAdvisorFederationReviewParsing:
    @pytest.mark.asyncio
    async def test_parse_no_issues(self, config):
        advisor = AsyncMock()
        advisor.generate = AsyncMock(return_value="NO ISSUES FOUND")

        fed = AdvisorFederation(config=config, executor=AsyncMock(), advisor=advisor)
        review = await fed._review("task", "solution")

        assert review.has_issues is False

    @pytest.mark.asyncio
    async def test_parse_issues_and_suggestions(self, config):
        advisor = AsyncMock()
        advisor.generate = AsyncMock(
            return_value=(
                "ISSUES:\n"
                "- Missing null check\n"
                "- Race condition possible\n"
                "SUGGESTIONS:\n"
                "- Add validation\n"
                "- Use lock\n"
                "SEVERITY: warning\n"
                "CONFIDENCE: 0.85"
            )
        )

        fed = AdvisorFederation(config=config, executor=AsyncMock(), advisor=advisor)
        review = await fed._review("task", "solution")

        assert review.has_issues is True
        assert len(review.issues) >= 2
        assert len(review.suggestions) >= 2
        assert review.severity == "warning"
        assert review.confidence == 0.85

    @pytest.mark.asyncio
    async def test_parse_invalid_confidence(self, config):
        advisor = AsyncMock()
        advisor.generate = AsyncMock(
            return_value="ISSUES: bad code\nCONFIDENCE: not_a_number"
        )

        fed = AdvisorFederation(config=config, executor=AsyncMock(), advisor=advisor)
        review = await fed._review("task", "solution")

        assert review.has_issues is True
        assert review.confidence == 0.5  # default fallback


class TestAdvisorFederationEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_task(self, config, mock_llm):
        mock_llm.generate = AsyncMock(return_value="")
        fed = AdvisorFederation(config=config, executor=mock_llm, advisor=mock_llm)

        result = await fed.execute_with_review("", task_type="query")
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_very_long_task(self, config, mock_llm):
        mock_llm.generate = AsyncMock(return_value="done")
        fed = AdvisorFederation(config=config, executor=mock_llm, advisor=mock_llm)

        long_task = "x" * 50000
        result = await fed.execute_with_review(long_task, task_type="code")
        assert result.content == "done"

    @pytest.mark.asyncio
    async def test_multiple_revisions_eventually_pass(self, config):
        call_count = 0

        async def mock_executor_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return f"revision_{call_count}"

        async def mock_advisor_generate(*args, **kwargs):
            nonlocal call_count
            if call_count <= 2:
                return "ISSUES: fix needed\nSEVERITY: critical\nCONFIDENCE: 0.7"
            return "NO ISSUES FOUND"

        executor = AsyncMock()
        executor.generate = AsyncMock(side_effect=mock_executor_generate)
        advisor = AsyncMock()
        advisor.generate = AsyncMock(side_effect=mock_advisor_generate)

        fed = AdvisorFederation(config=config, executor=executor, advisor=advisor)
        result = await fed.execute_with_review(
            "create a complex feature",
            task_type="code",
            max_revisions=2,
        )

        assert result.review is not None
        assert result.review.has_issues is False

    @pytest.mark.asyncio
    async def test_review_severity_levels(self, config):
        for severity in ["info", "warning", "critical"]:
            advisor = AsyncMock()
            advisor.generate = AsyncMock(
                return_value=f"ISSUES: test\nSEVERITY: {severity}\nCONFIDENCE: 0.5"
            )

            fed = AdvisorFederation(config=config, executor=AsyncMock(), advisor=advisor)
            review = await fed._review("task", "solution")
            assert review.severity == severity

    def test_cost_tracker_log_limit(self, config):
        tracker = CostTracker()
        for i in range(600):
            tracker.record(
                "model", "task", TaskComplexity.SIMPLE,
                100, 200, 50.0, 0.8,
            )

        data = tracker.to_dict()
        assert len(data["log"]) <= 500
