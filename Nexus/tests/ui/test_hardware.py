"""Tests for hardware detection and auto model routing."""
import pytest
from unittest.mock import patch, MagicMock

from nexus.ui.hardware import (
    HardwareProfile,
    MODEL_SIZES_GB,
    detect_hardware,
    get_recommendations,
    generate_routing_config,
    ModelRecommendation,
)


class TestHardwareProfile:
    def test_default_profile(self):
        profile = HardwareProfile()
        assert profile.os_name == ""
        assert profile.ram_total_gb == 0.0

    def test_tier_low(self):
        profile = HardwareProfile(ram_total_gb=8, ram_available_gb=4)
        assert profile.tier == "low"

    def test_tier_mid(self):
        profile = HardwareProfile(ram_total_gb=16, ram_available_gb=8)
        assert profile.tier == "mid"

    def test_tier_high(self):
        profile = HardwareProfile(ram_total_gb=32, ram_available_gb=16)
        assert profile.tier == "high"

    def test_tier_enthusiast(self):
        profile = HardwareProfile(ram_total_gb=64, ram_available_gb=32)
        assert profile.tier == "enthusiast"

    def test_tier_gpu_priority(self):
        """GPU VRAM should determine tier if larger."""
        profile = HardwareProfile(ram_total_gb=8, gpu_vram_gb=24)
        assert profile.tier == "enthusiast"

    def test_max_model_size_gpu(self):
        """GPU mode: 80% of VRAM."""
        profile = HardwareProfile(gpu_vram_gb=12)
        assert profile.max_model_size_gb == 12 * 0.8

    def test_max_model_size_cpu(self):
        """CPU mode: 70% of total RAM."""
        profile = HardwareProfile(ram_total_gb=16, ram_available_gb=8)
        assert profile.max_model_size_gb == 16 * 0.7


class TestModelSizes:
    def test_all_models_have_sizes(self):
        """Every model in routing should have a size entry."""
        from nexus.ui.model_routing import MODEL_REGISTRY
        for model_name in MODEL_REGISTRY:
            assert model_name in MODEL_SIZES_GB or MODEL_SIZES_GB.get(model_name, 0) > 0

    def test_small_models(self):
        assert MODEL_SIZES_GB["qwen2.5-coder:1.5b"] < 2.0
        assert MODEL_SIZES_GB["deepseek-r1:1.5b"] < 2.0

    def test_medium_models(self):
        assert 3.0 < MODEL_SIZES_GB["qwen2.5-coder:7b"] < 6.0
        assert 3.0 < MODEL_SIZES_GB["deepseek-r1:7b"] < 6.0

    def test_large_models(self):
        assert MODEL_SIZES_GB["qwen2.5-coder:14b"] > 8.0
        assert MODEL_SIZES_GB["gemma4:26b"] > 15.0


class TestRecommendations:
    def test_low_tier_recommendations(self):
        """Low hardware should only recommend small models."""
        hardware = HardwareProfile(ram_total_gb=8, ram_available_gb=4)
        recs = get_recommendations(hardware)
        assert len(recs["all"]) > 0
        # 1.5B and e2b models should always fit
        models = [r.model for r in recs["all"]]
        assert any("1.5b" in m for m in models)

    def test_mid_tier_recommendations(self):
        """Mid hardware should recommend 7B models."""
        hardware = HardwareProfile(ram_total_gb=16, ram_available_gb=8)
        recs = get_recommendations(hardware)
        models = [r.model for r in recs["all"]]
        assert any("7b" in m for m in models)

    def test_high_tier_recommendations(self):
        """High hardware should recommend 14B models."""
        hardware = HardwareProfile(ram_total_gb=32, ram_available_gb=16)
        recs = get_recommendations(hardware)
        models = [r.model for r in recs["all"]]
        assert any("14b" in m for m in models)

    def test_enthusiast_recommendations(self):
        """Enthusiast hardware should recommend 26B model."""
        hardware = HardwareProfile(ram_total_gb=64, ram_available_gb=32)
        recs = get_recommendations(hardware)
        models = [r.model for r in recs["all"]]
        assert "gemma4:26b" in models

    def test_gpu_recommendations(self):
        """GPU VRAM should enable larger models."""
        hardware = HardwareProfile(gpu_vram_gb=12)  # 12GB VRAM = 9.6GB usable
        recs = get_recommendations(hardware)
        models = [r.model for r in recs["all"]]
        # 14B model is ~9GB, should fit with 9.6GB usable
        assert any("14b" in m for m in models)

    def test_best_overall_not_empty(self):
        hardware = HardwareProfile(ram_total_gb=8, ram_available_gb=4)
        recs = get_recommendations(hardware)
        assert len(recs["best_overall"]) > 0

    def test_fastest_not_empty(self):
        hardware = HardwareProfile(ram_total_gb=8, ram_available_gb=4)
        recs = get_recommendations(hardware)
        assert len(recs["fastest"]) > 0

    def test_smartest_not_empty(self):
        hardware = HardwareProfile(ram_total_gb=8, ram_available_gb=4)
        recs = get_recommendations(hardware)
        assert len(recs["smartest"]) > 0

    def test_recommendation_fields(self):
        hardware = HardwareProfile(ram_total_gb=16, ram_available_gb=8)
        recs = get_recommendations(hardware)
        for category in ["best_overall", "fastest", "smartest", "all"]:
            for rec in recs[category]:
                assert isinstance(rec, ModelRecommendation)
                assert rec.model
                assert rec.purpose
                assert rec.reason
                assert rec.fits is True
                assert rec.expected_speed in ("fast", "medium", "slow")


class TestRoutingConfig:
    def test_routing_for_low_tier(self):
        hardware = HardwareProfile(ram_total_gb=8, ram_available_gb=4)
        routing = generate_routing_config(hardware)
        assert "code_generation" in routing
        assert "planning" in routing
        assert "chat" in routing
        # Should use small models
        assert routing["code_generation"] in ["qwen2.5-coder:7b", "qwen2.5-coder:1.5b"]

    def test_routing_for_mid_tier(self):
        hardware = HardwareProfile(ram_total_gb=16, ram_available_gb=8)
        routing = generate_routing_config(hardware)
        # Should use 7B or 14B for code
        assert "coder" in routing["code_generation"]

    def test_routing_for_high_tier(self):
        hardware = HardwareProfile(ram_total_gb=32, ram_available_gb=16)
        routing = generate_routing_config(hardware)
        # Should use 14B for code
        assert "14b" in routing["code_generation"]

    def test_routing_keys(self):
        """Routing should have all expected task types."""
        hardware = HardwareProfile(ram_total_gb=16, ram_available_gb=8)
        routing = generate_routing_config(hardware)
        expected_keys = [
            "code_generation", "code_review", "code_edit",
            "planning", "reasoning", "architecture",
            "ui_generation", "documentation", "summarize",
            "chat", "shell_command",
        ]
        for key in expected_keys:
            assert key in routing, f"Missing routing key: {key}"


class TestReports:
    def test_hardware_report_format(self):
        from nexus.ui.hardware import print_hardware_report
        hardware = HardwareProfile(
            os_name="Windows",
            cpu_name="Intel i7",
            cpu_count=8,
            ram_total_gb=16,
            ram_available_gb=8,
        )
        report = print_hardware_report(hardware)
        assert "NEXUS HARDWARE REPORT" in report
        assert "Windows" in report
        assert "Intel i7" in report
        assert "16.0 GB total" in report

    def test_recommendation_report_format(self):
        from nexus.ui.hardware import print_recommendation_report
        hardware = HardwareProfile(ram_total_gb=16, ram_available_gb=8)
        report = print_recommendation_report(hardware)
        assert "NEXUS MODEL RECOMMENDATIONS" in report
        assert "Best overall" in report
        assert "Fastest" in report
        assert "Smartest" in report
        assert "Recommended routing" in report


class TestDetectHardware:
    @patch("nexus.ui.hardware._detect_cpu_count", return_value=8)
    @patch("nexus.ui.hardware._detect_cpu_name", return_value="Test CPU")
    @patch("nexus.ui.hardware._detect_ram", return_value=(16.0, 8.0))
    @patch("nexus.ui.hardware._detect_gpu", return_value=(False, "", 0.0))
    @patch("nexus.ui.hardware._detect_disk_free", return_value=100.0)
    def test_detect_returns_profile(self, *mocks):
        profile = detect_hardware()
        assert isinstance(profile, HardwareProfile)
        assert profile.cpu_count == 8
        assert profile.cpu_name == "Test CPU"
        assert profile.ram_total_gb == 16.0
        assert profile.ram_available_gb == 8.0
        assert profile.has_gpu is False
        assert profile.disk_free_gb == 100.0
