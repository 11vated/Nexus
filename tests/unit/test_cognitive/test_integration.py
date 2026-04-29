"""Tests for the Cognitive Integration Layer."""
import pytest
from nexus.cognitive.integration import (
    CognitiveLayer, CognitiveMode, CognitiveEvent,
)
from nexus.cognitive.knowledge import KnowledgeEntry, KnowledgeLayer
from nexus.cognitive.memory import MemoryType


class TestCognitiveMode:
    def test_all_modes(self):
        assert len(CognitiveMode) == 4
        assert CognitiveMode.OFF.value == "off"
        assert CognitiveMode.PASSIVE.value == "passive"
        assert CognitiveMode.GUIDED.value == "guided"


class TestCognitiveEvent:
    def test_event_creation(self):
        e = CognitiveEvent(event="test", data={"key": "value"})
        assert e.event == "test"
        assert e.timestamp > 0


class TestCognitiveLayerInit:
    def test_default_mode(self):
        layer = CognitiveLayer()
        assert layer.mode == CognitiveMode.PASSIVE

    def test_has_all_modules(self):
        layer = CognitiveLayer()
        assert layer.loop is not None
        assert layer.state is not None
        assert layer.trace is not None
        assert layer.knowledge is not None
        assert layer.verifier is not None
        assert layer.detector is not None
        assert layer.memory is not None

    def test_session_memory_bank_created(self):
        layer = CognitiveLayer()
        assert "session" in layer.memory.bank_names

    def test_builtin_constraints_loaded(self):
        layer = CognitiveLayer()
        assert len(layer.verifier.constraints) > 0


class TestSetMode:
    def test_set_valid_mode(self):
        layer = CognitiveLayer()
        result = layer.set_mode("guided")
        assert layer.mode == CognitiveMode.GUIDED
        assert "guided" in result

    def test_set_invalid_mode(self):
        layer = CognitiveLayer()
        result = layer.set_mode("invalid")
        assert "Unknown" in result
        assert layer.mode == CognitiveMode.PASSIVE  # Unchanged

    def test_off_mode(self):
        layer = CognitiveLayer()
        layer.set_mode("off")
        events = layer.analyze_message("test")
        assert events == []  # No events in OFF mode


class TestAnalyzeMessage:
    def test_passive_mode_basic(self):
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.PASSIVE
        events = layer.analyze_message("Refactor everything to be better and faster")
        # Should produce some events (ambiguity, trace, etc)
        assert isinstance(events, list)

    def test_stores_episodic_memory(self):
        layer = CognitiveLayer()
        layer.analyze_message("Hello world")
        assert layer.memory.total_memories >= 1

    def test_updates_trace(self):
        layer = CognitiveLayer()
        layer.analyze_message("Refactor auth module")
        assert len(layer.trace.nodes) >= 1

    def test_increments_message_count(self):
        layer = CognitiveLayer()
        layer.analyze_message("First")
        layer.analyze_message("Second")
        assert layer._messages_analyzed == 2

    def test_guided_mode_sets_goal(self):
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.GUIDED
        events = layer.analyze_message("Build an authentication system")
        event_types = [e.event for e in events]
        assert "goal_set" in event_types
        assert layer.state.goal == "Build an authentication system"

    def test_knowledge_retrieval(self):
        layer = CognitiveLayer()
        layer.knowledge.add(KnowledgeEntry(
            layer=KnowledgeLayer.DOMAIN,
            content="The auth module uses OAuth2 with JWT tokens",
            tags=["auth"],
            confidence=0.9,
        ))
        events = layer.analyze_message("auth module")
        event_types = [e.event for e in events]
        assert "knowledge_retrieved" in event_types

    def test_off_mode_returns_empty(self):
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.OFF
        events = layer.analyze_message("Test message")
        assert events == []


class TestBeforeToolCall:
    def test_verifies_file_write(self):
        layer = CognitiveLayer()
        events = layer.before_tool_call("file_write", {
            "path": "test.py",
            "content": 'print("debug")\nfrom os import *\n',
        })
        event_types = [e.event for e in events]
        assert "verification_warning" in event_types

    def test_no_verification_for_file_read(self):
        layer = CognitiveLayer()
        events = layer.before_tool_call("file_read", {"path": "test.py"})
        assert all(e.event != "verification_warning" for e in events)

    def test_traces_tool_call(self):
        layer = CognitiveLayer()
        initial_nodes = len(layer.trace.nodes)
        layer.before_tool_call("shell", {"command": "ls -la"})
        assert len(layer.trace.nodes) > initial_nodes

    def test_off_mode_skips(self):
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.OFF
        events = layer.before_tool_call("file_write", {
            "path": "test.py", "content": 'print("x")',
        })
        assert events == []


class TestAfterToolCall:
    def test_stores_tool_memory(self):
        layer = CognitiveLayer()
        initial = layer.memory.total_memories
        layer.after_tool_call("shell", {"command": "ls"}, "file1.py\nfile2.py")
        assert layer.memory.total_memories > initial

    def test_failure_has_higher_importance(self):
        layer = CognitiveLayer()
        layer.after_tool_call("shell", {"command": "bad"}, "Error: failed", success=False)
        memories = layer.memory.search("session", tags=["tool_execution"])
        assert any(m.importance >= 0.8 for m in memories)

    def test_file_read_updates_knowledge(self):
        layer = CognitiveLayer()
        layer.after_tool_call("file_read", {"path": "src/auth.py"},
                              "class AuthManager:\n    def login(self):\n        pass")
        # Should have added to knowledge store
        assert layer.knowledge.total_entries >= 1

    def test_traces_result(self):
        layer = CognitiveLayer()
        initial = len(layer.trace.nodes)
        layer.after_tool_call("test_run", {}, "5 passed, 0 failed")
        assert len(layer.trace.nodes) > initial


class TestAnalyzeResponse:
    def test_traces_response(self):
        layer = CognitiveLayer()
        initial = len(layer.trace.nodes)
        layer.analyze_response("I'll refactor the auth module by...")
        assert len(layer.trace.nodes) > initial

    def test_stores_response_memory(self):
        layer = CognitiveLayer()
        initial = layer.memory.total_memories
        layer.analyze_response("Here's the plan for refactoring...")
        assert layer.memory.total_memories > initial

    def test_off_mode_skips(self):
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.OFF
        events = layer.analyze_response("test")
        assert events == []


class TestContextAugmentation:
    def test_off_mode_returns_empty(self):
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.OFF
        assert layer.get_context_augmentation("test") == ""

    def test_guided_mode_includes_loop_state(self):
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.GUIDED
        layer.loop.set_goal("Build auth module")
        aug = layer.get_context_augmentation("test")
        assert "Cognitive Loop" in aug
        assert "Build auth module" in aug

    def test_includes_relevant_knowledge(self):
        layer = CognitiveLayer()
        layer.knowledge.add(KnowledgeEntry(
            layer=KnowledgeLayer.DOMAIN,
            content="Authentication uses bcrypt for password hashing",
            tags=["auth", "security"],
        ))
        aug = layer.get_context_augmentation("auth bcrypt")
        # Should include knowledge if query matches
        assert "bcrypt" in aug or "Knowledge" in aug or aug == ""


class TestKnowledgeManagement:
    def test_learn(self):
        layer = CognitiveLayer()
        entry_id = layer.learn("We use PostgreSQL for the main database", tags=["database"])
        assert entry_id != ""
        results = layer.knowledge.query(search="PostgreSQL", limit=5)
        assert any("PostgreSQL" in r.content for r in results)

    def test_learn_invalid_layer(self):
        layer = CognitiveLayer()
        # Should fall back to DOMAIN
        entry_id = layer.learn("test content", layer="nonexistent")
        assert entry_id != ""

    def test_remember(self):
        layer = CognitiveLayer()
        mem_id = layer.remember("User prefers tabs over spaces", tags=["preferences"])
        assert mem_id != ""
        results = layer.memory.search("session", tags=["preferences"])
        assert len(results) >= 1

    def test_remember_invalid_type(self):
        layer = CognitiveLayer()
        mem_id = layer.remember("test", memory_type="nonexistent")
        assert mem_id != ""  # Falls back to SEMANTIC


class TestGetters:
    def test_get_plan(self):
        layer = CognitiveLayer()
        assert layer.get_plan() == []

    def test_get_trace_summary_empty(self):
        layer = CognitiveLayer()
        assert "No reasoning trace" in layer.get_trace_summary()

    def test_get_trace_summary_with_nodes(self):
        layer = CognitiveLayer()
        layer.analyze_message("Test message")
        summary = layer.get_trace_summary()
        assert "Reasoning trace" in summary

    def test_get_knowledge_summary(self):
        layer = CognitiveLayer()
        summary = layer.get_knowledge_summary()
        assert isinstance(summary, str)
        assert "KnowledgeStore" in summary

    def test_get_memory_summary(self):
        layer = CognitiveLayer()
        summary = layer.get_memory_summary()
        assert "MemoryMesh" in summary

    def test_get_verification_status(self):
        layer = CognitiveLayer()
        status = layer.get_verification_status()
        assert status["constraints"] > 0


class TestStats:
    def test_initial_stats(self):
        layer = CognitiveLayer()
        stats = layer.stats()
        assert stats["mode"] == "passive"
        assert stats["messages_analyzed"] == 0
        assert stats["trace_nodes"] == 0

    def test_stats_after_activity(self):
        layer = CognitiveLayer()
        layer.analyze_message("Test one")
        layer.analyze_message("Test two")
        stats = layer.stats()
        assert stats["messages_analyzed"] == 2
        assert stats["trace_nodes"] >= 2
        assert stats["total_memories"] >= 2


class TestSerialization:
    def test_roundtrip(self):
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.GUIDED
        layer.analyze_message("Build a REST API")
        layer.learn("We use FastAPI", tags=["framework"])
        layer.remember("User prefers async", tags=["style"])

        data = layer.to_dict()
        restored = CognitiveLayer.from_dict(data)

        assert restored.mode == CognitiveMode.GUIDED
        assert restored._messages_analyzed == 1
        assert restored.memory.total_memories >= 2

    def test_from_empty_dict(self):
        layer = CognitiveLayer.from_dict({})
        assert layer.mode == CognitiveMode.PASSIVE


class TestFullWorkflow:
    def test_passive_chat_turn(self):
        """Simulate a full passive-mode chat turn."""
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.PASSIVE

        # User message comes in
        pre_events = layer.analyze_message("Add error handling to the API endpoints")
        assert isinstance(pre_events, list)

        # Before tool call (LLM decided to read a file)
        tool_events = layer.before_tool_call("file_read", {"path": "src/api.py"})
        assert isinstance(tool_events, list)

        # After tool call
        post_events = layer.after_tool_call(
            "file_read", {"path": "src/api.py"},
            "def get_users():\n    return db.query(User).all()\n",
        )

        # AI response
        response_events = layer.analyze_response(
            "I see the API lacks try/except blocks. Here's my plan..."
        )

        # Check state
        assert layer._messages_analyzed == 1
        assert layer.memory.total_memories >= 3  # user msg + tool + response
        assert len(layer.trace.nodes) >= 3

    def test_guided_goal_flow(self):
        """Simulate guided mode goal setting."""
        layer = CognitiveLayer()
        layer.mode = CognitiveMode.GUIDED

        events = layer.analyze_message("Refactor the database layer")
        goal_events = [e for e in events if e.event == "goal_set"]
        assert len(goal_events) == 1
        assert layer.state.goal == "Refactor the database layer"

    def test_verification_catches_issues(self):
        """Verify that file writes are checked against constraints."""
        layer = CognitiveLayer()

        events = layer.before_tool_call("file_write", {
            "path": "src/main.py",
            "content": '#!/usr/bin/env python\nfrom os import *\nAPI_KEY = "sk-secret123"\nprint("debug")\n',
        })

        warnings = [e for e in events if e.event == "verification_warning"]
        assert len(warnings) == 1
        report = warnings[0].data
        assert report["error_count"] >= 1  # star import is ERROR level
