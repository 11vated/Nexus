"""Tests for nexus.memory.short_term — session-scoped rolling window."""
import json
import pytest
from nexus.memory.short_term import ShortTermMemory, MemoryEntry


class TestMemoryEntry:
    def test_to_message_user(self):
        entry = MemoryEntry(content="hello", role="user")
        msg = entry.to_message()
        assert msg["role"] == "user"
        assert msg["content"] == "hello"

    def test_to_message_agent(self):
        entry = MemoryEntry(content="response", role="agent")
        msg = entry.to_message()
        assert msg["role"] == "assistant"

    def test_to_message_tool(self):
        entry = MemoryEntry(content="result", role="tool")
        msg = entry.to_message()
        assert msg["role"] == "user"  # Tool results map to user


class TestShortTermMemory:
    def test_add_and_size(self):
        mem = ShortTermMemory(window_size=10)
        mem.add("test", role="user")
        assert mem.size == 1

    def test_window_limit(self):
        mem = ShortTermMemory(window_size=3)
        for i in range(5):
            mem.add(f"msg {i}")
        assert mem.size == 3

    def test_add_user_message(self):
        mem = ShortTermMemory()
        mem.add_user_message("hello")
        msgs = mem.to_messages()
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "hello"

    def test_add_agent_response(self):
        mem = ShortTermMemory()
        mem.add_agent_response("I'll help")
        msgs = mem.to_messages()
        assert msgs[-1]["role"] == "assistant"

    def test_add_tool_result(self):
        mem = ShortTermMemory()
        mem.add_tool_result("shell", "exit code 0")
        msgs = mem.to_messages()
        assert "shell" in msgs[-1]["content"]
        assert "exit code 0" in msgs[-1]["content"]

    def test_to_context_string(self):
        mem = ShortTermMemory()
        mem.add_user_message("Build API")
        mem.add_agent_response("Planning...")
        ctx = mem.to_context_string()
        assert "User" in ctx
        assert "Agent" in ctx

    def test_get_recent(self):
        mem = ShortTermMemory()
        for i in range(10):
            mem.add(f"msg {i}")
        recent = mem.get_recent(3)
        assert len(recent) == 3
        assert recent[-1].content == "msg 9"

    def test_clear(self):
        mem = ShortTermMemory()
        mem.add("test")
        mem.clear()
        assert mem.size == 0

    def test_total_chars(self):
        mem = ShortTermMemory()
        mem.add("hello")
        mem.add("world")
        assert mem.total_chars == 10

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "memory.json")
        mem = ShortTermMemory()
        mem.add_user_message("saved msg")
        mem.save(path)

        mem2 = ShortTermMemory()
        mem2.load(path)
        assert mem2.size == 1
        assert mem2.to_messages()[-1]["content"] == "saved msg"

    def test_load_missing_file(self, tmp_path):
        mem = ShortTermMemory()
        mem.load(str(tmp_path / "nonexistent.json"))
        assert mem.size == 0
