"""Tests for model routing configuration."""
import pytest

from nexus.ui.model_routing import (
    MODEL_REGISTRY,
    TASK_ROUTES,
    get_model_for_task,
    get_fallback_model,
    get_timeout_for_model,
    list_available_models,
    print_model_summary,
    ModelProfile,
)


class TestModelRegistry:
    def test_registry_not_empty(self):
        assert len(MODEL_REGISTRY) > 0

    def test_qwen14b(self):
        m = MODEL_REGISTRY["qwen2.5-coder:14b"]
        assert m.purpose == "Best code generation"
        assert m.timeout_s == 180
        assert m.max_tokens == 8192

    def test_qwen7b(self):
        m = MODEL_REGISTRY["qwen2.5-coder:7b"]
        assert m.purpose == "Fast code tasks, UI, quick edits"
        assert m.timeout_s == 120

    def test_gemma4_variants(self):
        assert "gemma4:e4b" in MODEL_REGISTRY
        assert "gemma4:e2b" in MODEL_REGISTRY
        assert "gemma4:26b" in MODEL_REGISTRY
        # 26b should have the longest timeout
        assert MODEL_REGISTRY["gemma4:26b"].timeout_s == 300

    def test_deepseek_variants(self):
        assert "deepseek-r1:7b" in MODEL_REGISTRY
        assert "deepseek-r1:1.5b" in MODEL_REGISTRY

    def test_all_profiles_have_required_fields(self):
        for name, profile in MODEL_REGISTRY.items():
            assert isinstance(profile, ModelProfile)
            assert profile.name == name
            assert profile.purpose
            assert profile.avg_response_time_s > 0
            assert profile.timeout_s > 0
            assert profile.max_tokens > 0


class TestTaskRoutes:
    def test_code_generation_route(self):
        route = TASK_ROUTES["code_generation"]
        assert route["primary"] == "qwen2.5-coder:14b"
        assert route["fallback"] == "qwen2.5-coder:7b"

    def test_code_review_route(self):
        route = TASK_ROUTES["code_review"]
        assert route["primary"] == "codellama:7b"
        assert route["fallback"] == "qwen2.5-coder:7b"

    def test_planning_route(self):
        route = TASK_ROUTES["planning"]
        assert route["primary"] == "deepseek-r1:7b"
        assert route["fallback"] == "gemma4:e4b"

    def test_ui_generation_route(self):
        route = TASK_ROUTES["ui_generation"]
        assert route["primary"] == "qwen2.5-coder:7b"

    def test_chat_route(self):
        route = TASK_ROUTES["chat"]
        assert route["primary"] == "qwen2.5-coder:7b"
        assert route["fallback"] == "gemma4:e4b"

    def test_summarize_route(self):
        route = TASK_ROUTES["summarize"]
        assert route["primary"] == "gemma4:e2b"

    def test_all_routes_reference_valid_models(self):
        """Every model in routes must exist in registry."""
        for task, route in TASK_ROUTES.items():
            assert route["primary"] in MODEL_REGISTRY, (
                f"{task} primary model {route['primary']} not in registry"
            )
            if route.get("fallback"):
                assert route["fallback"] in MODEL_REGISTRY, (
                    f"{task} fallback model {route['fallback']} not in registry"
                )
            if route.get("ultra_fast"):
                assert route["ultra_fast"] in MODEL_REGISTRY, (
                    f"{task} ultra_fast model {route['ultra_fast']} not in registry"
                )


class TestGetModelForTask:
    def test_normal_quality(self):
        model = get_model_for_task("code_generation")
        assert model == "qwen2.5-coder:14b"

    def test_best_quality(self):
        model = get_model_for_task("code_generation", quality="best")
        assert model == "qwen2.5-coder:14b"

    def test_ultra_fast_quality(self):
        model = get_model_for_task("code_generation", quality="ultra_fast")
        assert model == "qwen2.5-coder:1.5b"

    def test_chat_task(self):
        model = get_model_for_task("chat")
        assert model == "qwen2.5-coder:7b"

    def test_unknown_task_raises(self):
        with pytest.raises(ValueError, match="Unknown task type"):
            get_model_for_task("nonexistent_task_xyz")

    def test_planning_task(self):
        model = get_model_for_task("planning")
        assert model == "deepseek-r1:7b"

    def test_documentation_task(self):
        model = get_model_for_task("documentation")
        assert model == "gemma4:e4b"


class TestGetFallbackModel:
    def test_code_generation_fallback(self):
        fallback = get_fallback_model("code_generation")
        assert fallback == "qwen2.5-coder:7b"

    def test_shell_command_fallback(self):
        fallback = get_fallback_model("shell_command")
        assert fallback is None

    def test_unknown_task(self):
        fallback = get_fallback_model("nonexistent")
        assert fallback is None


class TestGetTimeoutForModel:
    def test_qwen14b_timeout(self):
        assert get_timeout_for_model("qwen2.5-coder:14b") == 180

    def test_qwen7b_timeout(self):
        assert get_timeout_for_model("qwen2.5-coder:7b") == 120

    def test_gemma26b_timeout(self):
        assert get_timeout_for_model("gemma4:26b") == 300

    def test_deepseek7b_timeout(self):
        assert get_timeout_for_model("deepseek-r1:7b") == 240

    def test_unknown_model_default(self):
        assert get_timeout_for_model("nonexistent-model") == 120


class TestListAvailableModels:
    def test_returns_list(self):
        models = list_available_models()
        assert isinstance(models, list)
        assert len(models) == len(MODEL_REGISTRY)

    def test_contains_expected_models(self):
        models = list_available_models()
        assert "qwen2.5-coder:14b" in models
        assert "qwen2.5-coder:7b" in models
        assert "deepseek-r1:7b" in models


class TestPrintModelSummary:
    def test_returns_string(self):
        summary = print_model_summary()
        assert isinstance(summary, str)
        assert "Nexus Model Routing" in summary
        assert "Available Models" in summary
        assert "Task Routing" in summary
