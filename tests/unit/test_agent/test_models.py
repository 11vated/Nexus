"""Tests for nexus.agent.models — dataclasses and enums."""
import pytest
from nexus.agent.models import (
    AgentConfig,
    AgentState,
    AgentRole,
    TaskStatus,
    QualityLevel,
    Task,
    Step,
    ToolCall,
)


class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig()
        assert cfg.planning_model == "deepseek-r1:7b"
        assert cfg.coding_model == "qwen2.5-coder:14b"
        assert cfg.max_iterations == 25
        assert cfg.reflection_enabled is True
        assert cfg.memory_enabled is True

    def test_override(self):
        cfg = AgentConfig(planning_model="llama3:8b", max_iterations=10)
        assert cfg.planning_model == "llama3:8b"
        assert cfg.max_iterations == 10

    def test_workspace_default(self):
        cfg = AgentConfig()
        assert cfg.workspace_path == "."


class TestAgentState:
    def test_all_states_exist(self):
        expected = {"idle", "planning", "acting", "observing", "reflecting", "correcting", "done", "error"}
        actual = {s.value for s in AgentState}
        assert expected == actual


class TestStep:
    def test_step_creation(self):
        step = Step(action="Write file", tool_name="file_write", success=True, result="OK")
        assert step.action == "Write file"
        assert step.success is True

    def test_step_to_context(self):
        step = Step(action="Run tests", tool_name="test_run", success=False, result="2 failed")
        ctx = step.to_context()
        assert "Run tests" in ctx
        assert "2 failed" in ctx

    def test_step_defaults(self):
        step = Step(action="test", tool_name="shell", success=True, result="done")
        assert step.quality_score == 0.0
        assert step.duration_ms == 0.0


class TestTask:
    def test_task_creation(self):
        task = Task(description="Build API", status=TaskStatus.PENDING)
        assert task.description == "Build API"
        assert task.status == TaskStatus.PENDING


class TestToolCall:
    def test_tool_call(self):
        tc = ToolCall(name="shell", arguments={"command": "ls"})
        assert tc.name == "shell"
        assert tc.arguments["command"] == "ls"

    def test_tool_call_raw(self):
        tc = ToolCall(name="test", arguments={}, raw="raw output")
        assert tc.raw == "raw output"


class TestQualityLevel:
    def test_quality_levels(self):
        assert QualityLevel.GOOD.value == 3
        assert QualityLevel.REJECTED.value == 0
        assert QualityLevel.FAIR.value == 2
        assert QualityLevel.POOR.value == 1
