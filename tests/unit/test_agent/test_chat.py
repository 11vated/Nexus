"""Tests for nexus.agent.chat — ChatSession collaborative mode."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nexus.agent.chat import (
    ChatSession,
    ChatEvent,
    EventType,
    CHAT_SYSTEM_PROMPT,
)
from nexus.agent.models import AgentConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    return AgentConfig(workspace_path="/tmp/test-workspace")


@pytest.fixture
def session(config):
    with patch("nexus.agent.chat.create_default_tools") as mock_tools:
        mock_tools.return_value = {
            "shell": MagicMock(
                name="shell",
                description="Run shell commands",
                aliases=[],
                schema={"command": "str"},
                to_prompt_description=MagicMock(return_value="- shell: Run shell commands"),
                execute=AsyncMock(return_value="command output"),
            ),
            "file_read": MagicMock(
                name="file_read",
                description="Read a file",
                aliases=[],
                schema={"path": "str"},
                to_prompt_description=MagicMock(return_value="- file_read: Read a file"),
                execute=AsyncMock(return_value="file contents here"),
            ),
        }
        s = ChatSession(workspace="/tmp/test-workspace", config=config)
        yield s


# ---------------------------------------------------------------------------
# Construction / setup
# ---------------------------------------------------------------------------

class TestChatSessionInit:
    def test_creates_with_defaults(self, session):
        assert session.workspace == "/tmp/test-workspace"
        assert len(session._tools) == 2
        assert session.turn_count == 0

    def test_history_starts_empty(self, session):
        assert session.history == []
        assert session.get_history() == []

    def test_stats(self, session):
        stats = session.stats()
        assert stats["turns"] == 0
        assert stats["tool_calls"] == 0
        assert "model" in stats

    def test_custom_model(self, config):
        with patch("nexus.agent.chat.create_default_tools", return_value={}):
            s = ChatSession(config=config, model="llama3:8b")
            assert s.model == "llama3:8b"


# ---------------------------------------------------------------------------
# Project rules
# ---------------------------------------------------------------------------

class TestProjectRules:
    def test_load_missing_rules(self, session):
        result = session.load_project_rules()
        assert result == ""
        assert session.project_rules == ""

    def test_load_existing_rules(self, session, tmp_path):
        rules_dir = tmp_path / ".nexus"
        rules_dir.mkdir()
        rules_file = rules_dir / "rules.md"
        rules_file.write_text("Always use type hints.\nPrefer async functions.")

        session.workspace = str(tmp_path)
        result = session.load_project_rules()
        assert "type hints" in result
        assert "async functions" in result

    def test_rules_in_system_prompt(self, session, tmp_path):
        rules_dir = tmp_path / ".nexus"
        rules_dir.mkdir()
        (rules_dir / "rules.md").write_text("Rule: test everything")
        session.workspace = str(tmp_path)
        session.load_project_rules()

        prompt = session._build_system_prompt()
        assert "Rule: test everything" in prompt


# ---------------------------------------------------------------------------
# Tool call parsing
# ---------------------------------------------------------------------------

class TestToolParsing:
    def test_extract_tool_block(self):
        text = '''Here's what I'll do:
```tool
{"tool": "shell", "args": {"command": "ls -la"}}
```
'''
        calls = ChatSession._extract_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool"] == "shell"
        assert calls[0]["args"]["command"] == "ls -la"

    def test_extract_multiple_tool_calls(self):
        text = '''Let me read two files:
```tool
{"tool": "file_read", "args": {"path": "a.py"}}
```
And then:
```tool
{"tool": "file_read", "args": {"path": "b.py"}}
```
'''
        calls = ChatSession._extract_tool_calls(text)
        assert len(calls) == 2

    def test_extract_json_block_with_tool(self):
        text = '''```json
{"tool": "shell", "args": {"command": "pwd"}}
```'''
        calls = ChatSession._extract_tool_calls(text)
        assert len(calls) == 1

    def test_no_tool_calls_in_plain_text(self):
        text = "Just a normal response with no tool calls."
        calls = ChatSession._extract_tool_calls(text)
        assert calls == []

    def test_code_block_without_tool_key(self):
        text = '''```json
{"name": "test", "value": 42}
```'''
        calls = ChatSession._extract_tool_calls(text)
        assert calls == []


# ---------------------------------------------------------------------------
# Plan extraction
# ---------------------------------------------------------------------------

class TestPlanExtraction:
    def test_extract_numbered_plan(self):
        text = """Here's my plan:
1. Read the existing API file
2. Add a /health endpoint
3. Write tests for the endpoint
4. Run the test suite
"""
        plan = ChatSession._extract_plan(text)
        assert len(plan) == 4
        assert "Read the existing API" in plan[0]
        assert "Run the test suite" in plan[3]

    def test_no_plan_in_plain_text(self):
        plan = ChatSession._extract_plan("Just a regular message.")
        assert plan == []

    def test_single_item_not_a_plan(self):
        plan = ChatSession._extract_plan("1. Just one item")
        assert plan == []


# ---------------------------------------------------------------------------
# Chat send (mocked LLM)
# ---------------------------------------------------------------------------

class TestChatSend:
    @pytest.mark.asyncio
    async def test_plain_response(self, session):
        session.llm.chat = AsyncMock(return_value="Hello! How can I help?")

        events = []
        async for event in session.send("Hi"):
            events.append(event)

        assert any(e.type == EventType.TOKEN for e in events)
        assert any(e.type == EventType.DONE for e in events)
        assert session.turn_count == 1
        assert len(session.history) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_response_with_tool_call(self, session):
        # First LLM call returns a tool call, second returns plain text
        session.llm.chat = AsyncMock(side_effect=[
            'I\'ll check:\n```tool\n{"tool": "shell", "args": {"command": "ls"}}\n```',
            "Found 3 files in the directory.",
        ])

        events = []
        async for event in session.send("List files"):
            events.append(event)

        tool_calls = [e for e in events if e.type == EventType.TOOL_CALL]
        tool_results = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert len(tool_calls) == 1
        assert len(tool_results) == 1
        assert tool_calls[0].data["tool"] == "shell"

    @pytest.mark.asyncio
    async def test_unknown_tool(self, session):
        session.llm.chat = AsyncMock(side_effect=[
            '```tool\n{"tool": "unknown_tool", "args": {}}\n```',
            "Sorry, that tool isn't available.",
        ])

        events = []
        async for event in session.send("Do something"):
            events.append(event)

        results = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert len(results) == 1
        assert "Error" in results[0].content or "Unknown" in results[0].content

    @pytest.mark.asyncio
    async def test_plan_detection(self, session):
        plan_text = """Here's my plan:
1. Read the config file
2. Add the new endpoint
3. Write tests
4. Run the tests"""
        session.llm.chat = AsyncMock(return_value=plan_text)

        events = []
        async for event in session.send("Add a health endpoint"):
            events.append(event)

        plans = [e for e in events if e.type == EventType.PLAN]
        assert len(plans) == 1
        assert len(plans[0].data["steps"]) == 4

    @pytest.mark.asyncio
    async def test_llm_error_handling(self, session):
        session.llm.chat = AsyncMock(side_effect=Exception("Connection refused"))

        events = []
        async for event in session.send("Hello"):
            events.append(event)

        errors = [e for e in events if e.type == EventType.ERROR]
        assert len(errors) == 1
        assert "Connection refused" in errors[0].content


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------

class TestHistory:
    @pytest.mark.asyncio
    async def test_clear_history(self, session):
        session.llm.chat = AsyncMock(return_value="Hi there!")
        async for _ in session.send("Hello"):
            pass
        assert session.turn_count == 1

        session.clear_history()
        assert session.turn_count == 0
        assert session.history == []

    @pytest.mark.asyncio
    async def test_multi_turn(self, session):
        session.llm.chat = AsyncMock(return_value="Got it.")
        async for _ in session.send("First message"):
            pass
        async for _ in session.send("Second message"):
            pass

        assert session.turn_count == 2
        assert len(session.history) == 4  # 2 user + 2 assistant
