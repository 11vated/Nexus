"""Tests for PersistenceManager and ConversationArchive."""
import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nexus.cognitive.persistence import (
    ConversationArchive,
    PersistenceManager,
    PersistenceStats,
)


class TestPersistenceStats:
    def test_default_values(self):
        stats = PersistenceStats()
        assert stats.last_save_time == 0.0
        assert stats.last_load_time == 0.0
        assert stats.save_count == 0
        assert stats.load_count == 0
        assert stats.errors == []

    def test_to_dict(self):
        stats = PersistenceStats(
            last_save_time=100.0,
            last_load_time=200.0,
            save_count=3,
            load_count=5,
            errors=["e1", "e2", "e3", "e4", "e5", "e6"],
        )
        d = stats.to_dict()
        assert d["last_save"] == 100.0
        assert d["last_load"] == 200.0
        assert d["saves"] == 3
        assert d["loads"] == 5
        # Only last 5 errors kept
        assert len(d["errors"]) == 5
        assert "e2" in d["errors"]
        assert "e1" not in d["errors"]


class TestConversationArchive:
    @pytest.fixture
    def archive(self, tmp_path):
        return ConversationArchive(tmp_path / "conv")

    def test_archive_and_load(self, archive):
        messages = [{"role": "user", "content": "Build a todo app"}]
        meta = {"model": "gpt-4", "tokens": 500}

        path = archive.archive("s1", messages, meta)
        assert Path(path).exists()

        data = archive.load_archive("s1")
        assert data is not None
        assert data["session_id"] == "s1"
        assert data["message_count"] == 1
        assert data["metadata"]["model"] == "gpt-4"

    def test_list_archives(self, archive):
        archive.archive("s1", [{"role": "user", "content": "msg1"}])
        archive.archive("s2", [{"role": "user", "content": "msg2"}])

        entries = archive.list_archives()
        assert len(entries) == 2
        ids = {e["session_id"] for e in entries}
        assert ids == {"s1", "s2"}

    def test_search_by_summary(self, archive):
        archive.archive("s1", [{"role": "user", "content": "Implement authentication"}])
        archive.archive("s2", [{"role": "user", "content": "Fix CSS layout"}])

        results = archive.search_archives("authentication")
        assert len(results) == 1
        assert results[0]["session_id"] == "s1"

    def test_search_by_tag(self, archive):
        archive.archive("s1", [
            {"role": "user", "content": "Run tests"},
            {"role": "assistant", "content": "All tests pass"},
        ])
        results = archive.search_archives("testing")
        assert len(results) == 1

    def test_delete_archive(self, archive):
        archive.archive("s1", [{"role": "user", "content": "test"}])
        assert archive.delete_archive("s1") is True
        assert archive.load_archive("s1") is None
        assert len(archive.list_archives()) == 0

    def test_delete_nonexistent(self, archive):
        assert archive.delete_archive("nonexistent") is False

    def test_extract_summary_truncation(self):
        long_content = "A" * 300
        summary = ConversationArchive._extract_summary([{"role": "user", "content": long_content}])
        assert len(summary) <= 203  # 200 + "..."

    def test_extract_tags(self):
        msgs = [
            {"role": "user", "content": "Use file_write to update config"},
            {"role": "assistant", "content": "Tests fail with error"},
        ]
        tags = ConversationArchive._extract_tags(msgs)
        assert "file_modification" in tags
        assert "error_handling" in tags
        assert "testing" in tags


class TestPersistenceManager:
    @pytest.fixture
    def manager(self, tmp_path):
        return PersistenceManager(str(tmp_path))

    def test_init_creates_nexus_dir(self, tmp_path, manager):
        assert manager.nexus_dir.exists()

    def test_save_and_load_knowledge(self, manager):
        data = {"entries": [{"id": "k1", "content": "project uses FastAPI"}]}
        assert manager.save_knowledge(data) is True

        loaded = manager.load_knowledge()
        assert loaded is not None
        assert loaded["entries"][0]["id"] == "k1"

    def test_load_knowledge_when_missing(self, manager):
        assert manager.load_knowledge() is None

    def test_save_and_load_memory(self, manager):
        data = {
            "banks": {
                "episodic": [{"id": "e1", "text": "user asked for login"}],
                "procedural": [{"id": "p1", "text": "how to deploy"}],
            }
        }
        assert manager.save_memory(data) is True
        loaded = manager.load_memory()
        assert loaded is not None
        assert "episodic" in loaded["banks"]

    def test_load_memory_when_missing(self, manager):
        assert manager.load_memory() is None

    def test_save_and_load_cognitive(self, manager):
        data = {"state": "EXECUTE", "loop_count": 3}
        assert manager.save_cognitive(data) is True
        loaded = manager.load_cognitive()
        assert loaded is not None
        assert loaded["state"] == "EXECUTE"

    def test_load_cognitive_when_missing(self, manager):
        assert manager.load_cognitive() is None

    def test_save_all(self, manager):
        results = manager.save_all(
            knowledge={"entries": []},
            memory={"banks": {}},
            cognitive={"state": "UNDERSTAND"},
        )
        assert results["knowledge"] is True
        assert results["memory"] is True
        assert results["cognitive"] is True
        assert manager.stats.save_count == 1

    def test_load_all(self, manager):
        manager.save_all(
            knowledge={"entries": []},
            memory={"banks": {}},
            cognitive={"state": "PROPOSE"},
        )
        loaded = manager.load_all()
        assert loaded["knowledge"] is not None
        assert loaded["memory"] is not None
        assert loaded["cognitive"] is not None
        assert manager.stats.load_count == 1

    def test_load_all_empty(self, manager):
        loaded = manager.load_all()
        assert all(v is None for v in loaded.values())

    def test_save_partial(self, manager):
        results = manager.save_all(knowledge={"entries": []})
        assert "knowledge" in results
        assert "memory" not in results
        assert "cognitive" not in results

    def test_archive_conversation(self, manager):
        msgs = [{"role": "user", "content": "Help me refactor"}]
        path = manager.archive_conversation("s1", msgs)
        assert Path(path).exists()

    def test_search_conversations(self, manager):
        manager.archive_conversation("s1", [{"role": "user", "content": "Build auth module"}])
        manager.archive_conversation("s2", [{"role": "user", "content": "Fix CSS"}])
        results = manager.search_conversations("auth")
        assert len(results) == 1
        assert results[0]["session_id"] == "s1"

    def test_list_conversations(self, manager):
        manager.archive_conversation("s1", [{"role": "user", "content": "msg"}])
        manager.archive_conversation("s2", [{"role": "user", "content": "msg"}])
        assert len(manager.list_conversations()) == 2

    def test_should_autosave(self, manager):
        # Initially should not autosave (just created)
        assert not manager.should_autosave()

        # Fake old autosave time
        manager._last_autosave = time.time() - 600
        assert manager.should_autosave()

    def test_record_autosave(self, manager):
        manager._last_autosave = time.time() - 600
        manager.record_autosave()
        assert not manager.should_autosave()

    def test_cleanup_old_archives(self, manager):
        # Create archive with old timestamp
        msgs = [{"role": "user", "content": "old session"}]
        manager.archive_conversation("old", msgs)

        # Manipulate index to have old timestamp
        archive = manager.conversation_archive
        for entry in archive._index:
            if entry["session_id"] == "old":
                entry["archived_at"] = time.time() - (60 * 86400)  # 60 days ago
        archive._save_index()

        deleted = manager.cleanup_old_archives(max_age_days=30)
        assert deleted == 1
        assert manager.load_conversation("old") is None

    def test_get_stats(self, manager):
        manager.save_knowledge({"entries": []})
        stats = manager.get_stats()
        assert "nexus_dir" in stats
        assert "archived_conversations" in stats
        assert "knowledge.json_size" in stats
