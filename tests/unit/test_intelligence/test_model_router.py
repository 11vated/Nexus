"""Tests for the multi-model intelligence router."""

import pytest
from nexus.intelligence.model_router import ModelRouter, TaskIntent, ModelProfile, RoutingDecision
from nexus.agent.models import AgentConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    return AgentConfig(
        planning_model="deepseek-r1:7b",
        coding_model="qwen2.5-coder:14b",
        fast_model="qwen2.5-coder:7b",
    )


@pytest.fixture
def router(config):
    return ModelRouter(config)


# ---------------------------------------------------------------------------
# Intent detection tests
# ---------------------------------------------------------------------------

class TestIntentDetection:
    """Tests for detecting user intent from messages."""

    def test_detect_code_generation(self, router):
        intent, conf = router.detect_intent("Write a function to sort a list")
        assert intent == TaskIntent.CODE_GENERATION
        assert conf > 0

    def test_detect_code_generation_create(self, router):
        intent, conf = router.detect_intent("Create a new class for user authentication")
        assert intent == TaskIntent.CODE_GENERATION

    def test_detect_debugging(self, router):
        intent, conf = router.detect_intent("This function crashes with a NoneType error")
        assert intent == TaskIntent.DEBUGGING

    def test_detect_debugging_fix(self, router):
        intent, conf = router.detect_intent("Fix the bug in the login handler")
        assert intent == TaskIntent.DEBUGGING

    def test_detect_architecture(self, router):
        intent, conf = router.detect_intent("How should I structure the microservice architecture?")
        assert intent == TaskIntent.ARCHITECTURE

    def test_detect_code_review(self, router):
        intent, conf = router.detect_intent("Review this code for bugs and issues")
        assert intent == TaskIntent.CODE_REVIEW

    def test_detect_explanation(self, router):
        intent, conf = router.detect_intent("Explain how async/await works in Python")
        assert intent == TaskIntent.EXPLANATION

    def test_detect_refactor(self, router):
        intent, conf = router.detect_intent("Refactor this class to follow SOLID principles")
        assert intent == TaskIntent.REFACTOR

    def test_detect_testing(self, router):
        intent, conf = router.detect_intent("Run pytest tests and check coverage on the auth spec")
        assert intent == TaskIntent.TESTING

    def test_detect_quick_task(self, router):
        intent, conf = router.detect_intent("Just add a quick fix to the import")
        assert intent == TaskIntent.QUICK_TASK

    def test_detect_general_fallback(self, router):
        intent, conf = router.detect_intent("Hello there!")
        assert intent == TaskIntent.GENERAL
        assert conf == 0.3  # Default confidence for general

    def test_confidence_higher_for_strong_signals(self, router):
        _, conf_strong = router.detect_intent("Write a new function to handle API authentication requests")
        _, conf_weak = router.detect_intent("Hello")
        assert conf_strong > conf_weak


# ---------------------------------------------------------------------------
# Model routing tests
# ---------------------------------------------------------------------------

class TestModelRouting:
    """Tests for routing tasks to the correct model."""

    def test_routes_architecture_to_reasoning_model(self, router, config):
        decision = router.route("Design the system architecture for a microservice")
        assert decision.model == config.planning_model
        assert decision.intent == TaskIntent.ARCHITECTURE

    def test_routes_code_gen_to_coding_model(self, router, config):
        decision = router.route("Write a function to parse JSON")
        assert decision.model == config.coding_model
        assert decision.intent == TaskIntent.CODE_GENERATION

    def test_routes_quick_task_to_fast_model(self, router, config):
        decision = router.route("Just quick fix the import statement")
        assert decision.model == config.fast_model
        assert decision.intent == TaskIntent.QUICK_TASK

    def test_routes_debugging_to_reasoning_model(self, router, config):
        decision = router.route("Debug this crash: NoneType has no attribute 'get'")
        assert decision.model == config.planning_model

    def test_routing_decision_has_reasoning(self, router):
        decision = router.route("Explain how decorators work")
        assert decision.reasoning  # Not empty
        assert "explanation" in decision.reasoning.lower() or "teaching" in decision.reasoning.lower()

    def test_routing_decision_has_confidence(self, router):
        decision = router.route("Write a REST API endpoint")
        assert 0 <= decision.confidence <= 1

    def test_routing_records_history(self, router):
        assert len(router.history) == 0
        router.route("Write a function")
        router.route("Fix this bug")
        assert len(router.history) == 2


# ---------------------------------------------------------------------------
# Available models filtering
# ---------------------------------------------------------------------------

class TestAvailableModels:
    """Tests for filtering by available models."""

    def test_filters_to_available_models(self, config):
        router = ModelRouter(config)
        # Only fast model is available
        router.set_available_models(["qwen2.5-coder:7b"])
        decision = router.route("Design the architecture")
        # Should fall back to available model
        assert decision.model == "qwen2.5-coder:7b"

    def test_no_filter_uses_all_models(self, router, config):
        decision = router.route("Design the architecture")
        assert decision.model == config.planning_model


# ---------------------------------------------------------------------------
# Custom profiles
# ---------------------------------------------------------------------------

class TestCustomProfiles:
    """Tests for adding custom model profiles."""

    def test_add_custom_profile(self, router):
        profile = ModelProfile(
            name="custom-model:latest",
            strengths=[TaskIntent.CODE_GENERATION, TaskIntent.TESTING],
            temperature=0.1,
            speed_tier=1,
            reasoning_depth=1,
        )
        router.add_profile(profile)
        # It should be available as an option now
        assert "custom-model:latest" in router._profiles


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestRouterStats:
    """Tests for routing statistics."""

    def test_stats_empty(self, router):
        stats = router.stats()
        assert stats["total_routes"] == 0

    def test_stats_after_routing(self, router):
        router.route("Write a function")
        router.route("Fix this bug")
        router.route("Write a function")
        stats = router.stats()
        assert stats["total_routes"] == 3
        assert "intent_distribution" in stats
        assert "model_distribution" in stats
        assert 0 <= stats["avg_confidence"] <= 1
