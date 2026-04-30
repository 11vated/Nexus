"""Tests for nexus.agent.context — context window management."""
import pytest
from nexus.agent.context import ContextManager, ContextEntry
from nexus.agent.models import Step


class TestContextManager:
    def test_empty_context(self):
        ctx = ContextManager()
        result = ctx.build_prompt_context()
        assert result == ""

    def test_goal_always_included(self):
        ctx = ContextManager()
        ctx.goal = "Build a Flask app"
        result = ctx.build_prompt_context()
        assert "Build a Flask app" in result

    def test_workspace_info(self):
        ctx = ContextManager()
        ctx.goal = "test"
        ctx.workspace_info = "/home/user/project"
        result = ctx.build_prompt_context()
        assert "/home/user/project" in result

    def test_add_entry(self):
        ctx = ContextManager()
        ctx.goal = "test"
        ctx.add("Some context", source="test")
        result = ctx.build_prompt_context()
        assert "Some context" in result

    def test_pin_always_included(self):
        ctx = ContextManager()
        ctx.goal = "test"
        ctx.pin("Important fact", source="memory")
        result = ctx.build_prompt_context()
        assert "Important fact" in result

    def test_budget_respected(self):
        ctx = ContextManager(max_chars=100)
        ctx.goal = "short"
        # Add a very long entry that exceeds budget
        ctx.add("x" * 200, source="big")
        result = ctx.build_prompt_context()
        # The big entry should be excluded since it exceeds remaining budget
        assert len(result) <= 200  # goal + some overhead

    def test_add_step(self):
        ctx = ContextManager()
        ctx.goal = "test"
        step = Step(action="Read file", tool_name="file_read", success=True, result="contents here")
        ctx.add_step(step)
        result = ctx.build_prompt_context()
        assert "Read file" in result

    def test_add_file_content_truncation(self):
        ctx = ContextManager()
        long_content = "a" * 5000
        ctx.add_file_content("big.py", long_content)
        # Check it was truncated
        entries = list(ctx._entries)
        assert len(entries) == 1
        assert "truncated" in entries[0].content

    def test_get_recent_steps(self):
        ctx = ContextManager()
        for i in range(10):
            step = Step(action=f"Step {i}", tool_name="shell", success=True, result="ok")
            ctx.add_step(step)
        recent = ctx.get_recent_steps(3)
        assert len(recent) == 3
        assert "Step 9" in recent[-1]

    def test_clear(self):
        ctx = ContextManager()
        ctx.goal = "test"
        ctx.add("data", source="test")
        ctx.clear()
        assert ctx.goal == ""
        result = ctx.build_prompt_context()
        assert result == ""

    def test_summary(self):
        ctx = ContextManager()
        ctx.goal = "test"
        ctx.add("data", source="test")
        ctx.pin("pinned", source="test")
        s = ctx.summary()
        assert s["entries"] == 1
        assert s["pinned"] == 1
        assert s["has_goal"] is True

    def test_priority_ordering(self):
        ctx = ContextManager(max_chars=500)
        ctx.goal = "test"
        ctx.add("low priority", source="test", priority=1)
        ctx.add("high priority", source="test", priority=10)
        result = ctx.build_prompt_context()
        # Both should be included when budget allows
        assert "high priority" in result
        assert "low priority" in result
