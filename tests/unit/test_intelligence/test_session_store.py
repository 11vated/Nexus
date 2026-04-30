"""Tests for session persistence."""

import json
import time
import pytest
from pathlib import Path

from nexus.intelligence.session_store import SessionStore, SessionSnapshot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    return SessionStore(str(tmp_path))


@pytest.fixture
def sample_messages():
    return [
        {"role": "user", "content": "Write a hello world function"},
        {"role": "assistant", "content": "Here's a simple hello world:\n```python\ndef hello():\n    print('Hello, World!')\n```"},
        {"role": "user", "content": "Add a parameter for the name"},
        {"role": "assistant", "content": "```python\ndef hello(name='World'):\n    print(f'Hello, {name}!')\n```"},
    ]


# ---------------------------------------------------------------------------
# Save tests
# ---------------------------------------------------------------------------

class TestSave:
    """Tests for saving sessions."""

    def test_save_returns_session_id(self, store, sample_messages):
        sid = store.save(messages=sample_messages)
        assert sid is not None
        assert len(sid) > 0

    def test_save_creates_file(self, store, sample_messages):
        sid = store.save(messages=sample_messages)
        path = store.sessions_dir / f"{sid}.json"
        assert path.exists()

    def test_save_with_title(self, store, sample_messages):
        sid = store.save(messages=sample_messages, title="Hello World Session")
        snapshot = store.load(sid)
        assert snapshot.title == "Hello World Session"

    def test_save_auto_title(self, store, sample_messages):
        sid = store.save(messages=sample_messages)
        snapshot = store.load(sid)
        assert snapshot.title == "Write a hello world function"

    def test_save_with_metadata(self, store, sample_messages):
        metadata = {"stance": "pair_programmer", "model": "qwen2.5-coder:14b"}
        sid = store.save(messages=sample_messages, metadata=metadata)
        snapshot = store.load(sid)
        assert snapshot.metadata["stance"] == "pair_programmer"
        assert snapshot.metadata["model"] == "qwen2.5-coder:14b"

    def test_save_with_project_context(self, store, sample_messages):
        ctx = {"type": "fastapi_app", "files": 42}
        sid = store.save(messages=sample_messages, project_context=ctx)
        snapshot = store.load(sid)
        assert snapshot.project_context["type"] == "fastapi_app"

    def test_save_with_tags(self, store, sample_messages):
        sid = store.save(messages=sample_messages, tags=["tutorial", "python"])
        snapshot = store.load(sid)
        assert "tutorial" in snapshot.tags

    def test_save_with_explicit_id(self, store, sample_messages):
        sid = store.save(messages=sample_messages, session_id="my-custom-id")
        assert sid == "my-custom-id"
        snapshot = store.load("my-custom-id")
        assert snapshot is not None

    def test_save_updates_existing(self, store, sample_messages):
        sid = store.save(messages=sample_messages[:2], session_id="update-test")
        original = store.load(sid)
        original_created = original.created_at

        # Update with more messages
        time.sleep(0.01)
        store.save(messages=sample_messages, session_id="update-test")
        updated = store.load(sid)

        assert updated.message_count == 4
        assert updated.created_at == original_created  # Preserves original creation time
        assert updated.updated_at >= original_created


# ---------------------------------------------------------------------------
# Load tests
# ---------------------------------------------------------------------------

class TestLoad:
    """Tests for loading sessions."""

    def test_load_existing(self, store, sample_messages):
        sid = store.save(messages=sample_messages)
        snapshot = store.load(sid)
        assert snapshot is not None
        assert snapshot.session_id == sid
        assert len(snapshot.messages) == 4

    def test_load_nonexistent_returns_none(self, store):
        assert store.load("nonexistent-id") is None

    def test_load_corrupted_returns_none(self, store):
        # Write invalid JSON
        bad_path = store.sessions_dir / "bad.json"
        bad_path.write_text("not json {{{")
        assert store.load("bad") is None

    def test_load_preserves_message_content(self, store, sample_messages):
        sid = store.save(messages=sample_messages)
        snapshot = store.load(sid)
        assert snapshot.messages[0]["content"] == "Write a hello world function"
        assert snapshot.messages[1]["role"] == "assistant"


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

class TestListSessions:
    """Tests for listing sessions."""

    def test_list_empty(self, store):
        sessions = store.list_sessions()
        assert sessions == []

    def test_list_after_saves(self, store, sample_messages):
        store.save(messages=sample_messages, session_id="s1", title="Session 1")
        store.save(messages=sample_messages, session_id="s2", title="Session 2")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_list_ordered_by_recent(self, store, sample_messages):
        store.save(messages=sample_messages, session_id="old", title="Old")
        time.sleep(0.01)
        store.save(messages=sample_messages, session_id="new", title="New")
        sessions = store.list_sessions()
        assert sessions[0].session_id == "new"  # Most recent first

    def test_list_respects_limit(self, store, sample_messages):
        for i in range(5):
            store.save(messages=sample_messages, session_id=f"s{i}")
        sessions = store.list_sessions(limit=3)
        assert len(sessions) == 3


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------

class TestDelete:
    """Tests for deleting sessions."""

    def test_delete_existing(self, store, sample_messages):
        sid = store.save(messages=sample_messages)
        assert store.delete(sid) is True
        assert store.load(sid) is None

    def test_delete_nonexistent(self, store):
        assert store.delete("nonexistent") is False


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------

class TestSearch:
    """Tests for searching sessions."""

    def test_search_by_title(self, store, sample_messages):
        store.save(messages=sample_messages, title="Building an API")
        store.save(messages=sample_messages, title="Fixing a bug")
        results = store.search("API")
        assert len(results) == 1
        assert results[0].title == "Building an API"

    def test_search_by_content(self, store, sample_messages):
        results = store.search("hello world")
        # Nothing saved yet
        assert len(results) == 0

        store.save(messages=sample_messages, session_id="hw")
        results = store.search("hello world")
        assert len(results) == 1

    def test_search_by_tag(self, store, sample_messages):
        store.save(messages=sample_messages, tags=["python", "beginner"])
        results = store.search("python")
        assert len(results) == 1

    def test_search_case_insensitive(self, store, sample_messages):
        store.save(messages=sample_messages, title="Building an API")
        results = store.search("api")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# SessionSnapshot properties
# ---------------------------------------------------------------------------

class TestSessionSnapshot:
    """Tests for SessionSnapshot dataclass."""

    def test_message_count(self, store, sample_messages):
        sid = store.save(messages=sample_messages)
        snapshot = store.load(sid)
        assert snapshot.message_count == 4

    def test_duration_display_minutes(self, store, sample_messages):
        sid = store.save(messages=sample_messages)
        snapshot = store.load(sid)
        # Just created — should be "0m ago"
        assert "m ago" in snapshot.duration_display

    def test_count_property(self, store, sample_messages):
        assert store.count == 0
        store.save(messages=sample_messages)
        assert store.count == 1
        store.save(messages=sample_messages)
        assert store.count == 2


# ---------------------------------------------------------------------------
# Auto title generation
# ---------------------------------------------------------------------------

class TestAutoTitle:
    """Tests for automatic title generation."""

    def test_auto_title_from_first_user_message(self, store):
        messages = [
            {"role": "user", "content": "Help me build an authentication system"},
            {"role": "assistant", "content": "Sure!"},
        ]
        sid = store.save(messages=messages)
        snapshot = store.load(sid)
        assert snapshot.title == "Help me build an authentication system"

    def test_auto_title_truncates_long_messages(self, store):
        messages = [
            {"role": "user", "content": "x" * 100},
            {"role": "assistant", "content": "ok"},
        ]
        sid = store.save(messages=messages)
        snapshot = store.load(sid)
        assert len(snapshot.title) <= 63  # 57 + "..."
        assert snapshot.title.endswith("...")

    def test_auto_title_empty_messages(self, store):
        sid = store.save(messages=[])
        snapshot = store.load(sid)
        assert snapshot.title == "Untitled Session"
