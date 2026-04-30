"""Tests for the fine-tuning pipeline."""

import json
import pytest
from pathlib import Path


# -- Data Prep Tests ---------------------------------------------------------

class TestSessionDataExtractor:
    def test_extract_tags(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        text = "def my_function():\n    import os\n    pass"
        tags = extractor._extract_tags(text)
        assert "python" in tags

    def test_extract_tags_javascript(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        text = "const myFunc = () => { function helper() {} }"
        tags = extractor._extract_tags(text)
        assert "javascript" in tags

    def test_extract_tags_api(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        text = "Create a new API endpoint for the user route"
        tags = extractor._extract_tags(text)
        assert "api" in tags

    def test_extract_tags_testing(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        text = "Write pytest tests with assert statements"
        tags = extractor._extract_tags(text)
        assert "testing" in tags

    def test_score_quality_high(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        instruction = "Build a Flask API with authentication"
        output = "```python\nfrom flask import Flask, request\n\napp = Flask(__name__)\n\ndef authenticate():\n    pass\n```"
        score = extractor._score_quality(instruction, output)
        assert score >= 0.5

    def test_score_quality_low(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        instruction = "hi"
        output = "hello"
        score = extractor._score_quality(instruction, output)
        assert score < 0.3

    def test_filter_by_quality(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor, TrainingPair

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        pairs = [
            TrainingPair(instruction="a", output="b" * 100, quality_score=0.8),
            TrainingPair(instruction="c", output="d" * 50, quality_score=0.3),
            TrainingPair(instruction="e", output="f" * 200, quality_score=0.6),
        ]

        filtered = extractor.filter_by_quality(pairs, min_score=0.5)
        assert len(filtered) == 2

    def test_filter_by_tags(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor, TrainingPair

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        pairs = [
            TrainingPair(instruction="a", output="b", tags=["python", "api"]),
            TrainingPair(instruction="c", output="d", tags=["javascript"]),
        ]

        filtered = extractor.filter_by_tags(pairs, ["python"])
        assert len(filtered) == 1

    def test_export_alpaca(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor, TrainingPair

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        pairs = [
            TrainingPair(instruction="Do X", output="Here is how: ..."),
            TrainingPair(instruction="Do Y", output="Steps: 1. ..."),
        ]

        output_path = str(tmp_path / "train.json")
        count = extractor.export_alpaca(pairs, output_path)
        assert count == 2

        data = json.loads(Path(output_path).read_text())
        assert len(data) == 2
        assert data[0]["instruction"] == "Do X"

    def test_export_openai(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor, TrainingPair

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        pairs = [
            TrainingPair(instruction="Teach me", output="Sure, here's how..."),
        ]

        output_path = str(tmp_path / "train.jsonl")
        count = extractor.export_openai(pairs, output_path)
        assert count == 1

        lines = Path(output_path).read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert "messages" in data

    def test_get_stats(self, tmp_path):
        from nexus.fine_tuning.data_prep import SessionDataExtractor, TrainingPair

        extractor = SessionDataExtractor(workspace=str(tmp_path))
        pairs = [
            TrainingPair(instruction="a", output="b" * 100, quality_score=0.8, tags=["python"]),
            TrainingPair(instruction="c", output="d" * 200, quality_score=0.6, tags=["python", "api"]),
        ]

        stats = extractor.get_stats(pairs)
        assert stats["total_pairs"] == 2
        assert stats["avg_quality"] == 0.7
        assert "python" in stats["tags"]


# -- Model Registry Tests ----------------------------------------------------

class TestModelRegistry:
    def test_register_model(self, tmp_path):
        from nexus.fine_tuning.model_registry import ModelRegistry

        registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"))
        entry = registry.register(
            name="test-model",
            base_model="qwen2.5-coder:14b",
            training_samples=100,
            training_data_path="/data/train.json",
        )

        assert entry.name == "test-model"
        assert entry.version == "v1"
        assert registry.model_count == 1

    def test_get_model(self, tmp_path):
        from nexus.fine_tuning.model_registry import ModelRegistry

        registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"))
        registry.register("my-model", "qwen2.5-coder:14b", 100, "/data")
        entry = registry.get("my-model")

        assert entry is not None
        assert entry.name == "my-model"

    def test_version_increment(self, tmp_path):
        from nexus.fine_tuning.model_registry import ModelRegistry

        registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"))
        r1 = registry.register("m", "base", 100, "/d")
        r2 = registry.register("m", "base", 200, "/d")

        assert r1.version == "v1"
        assert r2.version == "v2"

    def test_list_models(self, tmp_path):
        from nexus.fine_tuning.model_registry import ModelRegistry

        registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"))
        registry.register("m1", "base", 100, "/d")
        registry.register("m2", "base", 200, "/d")

        models = registry.list_models()
        assert len(models) == 2

    def test_deactivate(self, tmp_path):
        from nexus.fine_tuning.model_registry import ModelRegistry

        registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"))
        registry.register("m", "base", 100, "/d")
        registry.deactivate("m")

        assert registry.get("m") is None

    def test_get_by_tag(self, tmp_path):
        from nexus.fine_tuning.model_registry import ModelRegistry

        registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"))
        registry.register("python-model", "base", 100, "/d", tags=["python"])
        registry.register("js-model", "base", 100, "/d", tags=["javascript"])

        python_models = registry.get_by_tag("python")
        assert len(python_models) == 1

    def test_persistence(self, tmp_path):
        from nexus.fine_tuning.model_registry import ModelRegistry

        path = str(tmp_path / "registry.json")
        registry = ModelRegistry(registry_path=path)
        registry.register("m", "base", 100, "/d")

        # Load fresh registry
        registry2 = ModelRegistry(registry_path=path)
        assert registry2.model_count == 1


# -- Pipeline Tests ----------------------------------------------------------

class TestFineTuningPipeline:
    @pytest.mark.asyncio
    async def test_run_no_data(self, tmp_path):
        from nexus.fine_tuning.pipeline import FineTuningPipeline, TrainingConfig

        pipeline = FineTuningPipeline(workspace=str(tmp_path))
        result = await pipeline.run(TrainingConfig())

        assert result.success is False
        assert "No training data" in result.error

    @pytest.mark.asyncio
    async def test_run_insufficient_data(self, tmp_path):
        from nexus.fine_tuning.pipeline import FineTuningPipeline, TrainingConfig

        # Create a session with very little data (too short to pass quality filter)
        sessions_dir = tmp_path / ".nexus" / "sessions"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "s1.json").write_text(json.dumps({
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hey"},  # Too short, will be filtered
            ]
        }))

        pipeline = FineTuningPipeline(workspace=str(tmp_path))
        result = await pipeline.run(TrainingConfig())

        assert result.success is False
        # Either "No training data" (if filtered out) or "Too few" (if some passed)
        assert "No training data" in result.error or "Too few" in result.error

    def test_get_stats(self, tmp_path):
        from nexus.fine_tuning.pipeline import FineTuningPipeline

        pipeline = FineTuningPipeline(workspace=str(tmp_path))
        stats = pipeline.get_stats()
        assert "pipeline_running" in stats
        assert "registry_stats" in stats


# -- Retraining Trigger Tests -----------------------------------------------

class TestRetrainingTrigger:
    def test_check_no_sessions(self, tmp_path):
        from nexus.fine_tuning.triggers import RetrainingTrigger

        trigger = RetrainingTrigger(workspace=str(tmp_path))
        result = trigger.check()

        assert result.should_retrain is False

    def test_force_trigger(self, tmp_path):
        from nexus.fine_tuning.triggers import RetrainingTrigger

        trigger = RetrainingTrigger(workspace=str(tmp_path))
        result = trigger.force_trigger()

        assert result.should_retrain is True
        assert "Force" in result.reason

    def test_get_stats(self, tmp_path):
        from nexus.fine_tuning.triggers import RetrainingTrigger

        trigger = RetrainingTrigger(workspace=str(tmp_path))
        stats = trigger.get_stats()

        assert "total_sessions" in stats
        assert "current_performance" in stats


# -- Format Converter Tests -------------------------------------------------

class TestFormatConverters:
    def test_alpaca_convert(self):
        from nexus.fine_tuning.formats import AlpacaFormat

        result = AlpacaFormat.convert("Do X", "Result Y", "Input Z")
        assert result["instruction"] == "Do X"
        assert result["input"] == "Input Z"
        assert result["output"] == "Result Y"

    def test_alpaca_export_load(self, tmp_path):
        from nexus.fine_tuning.formats import AlpacaFormat

        pairs = [
            {"instruction": "A", "input": "", "output": "B"},
            {"instruction": "C", "input": "D", "output": "E"},
        ]
        path = str(tmp_path / "alpaca.json")
        AlpacaFormat.export(pairs, path)

        loaded = AlpacaFormat.load(path)
        assert len(loaded) == 2

    def test_openai_convert(self):
        from nexus.fine_tuning.formats import OpenAIFormat

        result = OpenAIFormat.convert("Question?", "Answer!")
        messages = result["messages"]
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_openai_export_load(self, tmp_path):
        from nexus.fine_tuning.formats import OpenAIFormat

        pairs = [
            OpenAIFormat.convert("Q1", "A1"),
            OpenAIFormat.convert("Q2", "A2"),
        ]
        path = str(tmp_path / "openai.jsonl")
        OpenAIFormat.export(pairs, path)

        loaded = OpenAIFormat.load(path)
        assert len(loaded) == 2
