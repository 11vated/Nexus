"""Tests for nexus.memory.long_term — persistent memory (JSON fallback)."""
import pytest
from nexus.memory.long_term import LongTermMemory


@pytest.fixture
def memory(tmp_path):
    """Create a LongTermMemory with JSON fallback."""
    return LongTermMemory(persist_dir=str(tmp_path / "memory"))


class TestLongTermMemory:
    def test_store_and_count(self, memory):
        memory.store("Test document", metadata={"type": "test"})
        assert memory.count == 1

    def test_store_with_explicit_id(self, memory):
        doc_id = memory.store("Hello", doc_id="doc1")
        assert doc_id == "doc1"
        assert memory.count == 1

    def test_store_auto_id(self, memory):
        doc_id = memory.store("Auto ID document")
        assert len(doc_id) == 16  # SHA256 truncated

    def test_upsert_same_id(self, memory):
        memory.store("Version 1", doc_id="doc1")
        memory.store("Version 2", doc_id="doc1")
        assert memory.count == 1  # Updated, not duplicated

    def test_search_keyword(self, memory):
        memory.store("Python Flask API development", doc_id="d1")
        memory.store("React frontend components", doc_id="d2")
        memory.store("Django REST framework", doc_id="d3")

        results = memory.search("Flask API")
        assert len(results) > 0
        # Flask doc should be first (most keyword matches)
        assert results[0][0] == "d1"

    def test_search_no_results(self, memory):
        memory.store("Unrelated content", doc_id="d1")
        results = memory.search("xyznonexistent")
        assert len(results) == 0

    def test_search_empty_store(self, memory):
        results = memory.search("anything")
        assert len(results) == 0

    def test_delete(self, memory):
        memory.store("To delete", doc_id="del1")
        assert memory.count == 1
        deleted = memory.delete("del1")
        assert deleted is True
        assert memory.count == 0

    def test_delete_nonexistent(self, memory):
        deleted = memory.delete("nonexistent")
        assert deleted is False

    def test_persistence(self, tmp_path):
        persist_dir = str(tmp_path / "persist")
        mem1 = LongTermMemory(persist_dir=persist_dir)
        mem1.store("Persistent data", doc_id="p1")
        assert mem1.count == 1

        # Create new instance pointing to same dir
        mem2 = LongTermMemory(persist_dir=persist_dir)
        assert mem2.count == 1

    def test_search_returns_tuples(self, memory):
        memory.store("Test document for search", doc_id="s1")
        results = memory.search("Test document")
        assert len(results) == 1
        doc_id, content, score = results[0]
        assert doc_id == "s1"
        assert "Test document" in content
        assert 0.0 < score <= 1.0

    def test_n_results_limit(self, memory):
        for i in range(10):
            memory.store(f"Document about topic {i}", doc_id=f"d{i}")
        results = memory.search("Document topic", n_results=3)
        assert len(results) <= 3
