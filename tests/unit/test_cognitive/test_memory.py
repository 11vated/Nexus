"""Tests for the Multi-Memory Architecture."""
import time
import pytest
from nexus.cognitive.memory import (
    MemoryMesh, MemoryBank, MemoryEntry, MemoryLineage,
    MemoryType, MemoryScope,
)


class TestMemoryLineage:
    def test_defaults(self):
        l = MemoryLineage()
        assert l.version == 1
        assert l.derived_from == []

    def test_roundtrip(self):
        l = MemoryLineage(
            created_by="dev", derived_from=["m1"],
            propagated_to=["shared:m2"], version=2,
            modified_by=["architect"],
        )
        data = l.to_dict()
        restored = MemoryLineage.from_dict(data)
        assert restored.created_by == "dev"
        assert restored.version == 2
        assert "m1" in restored.derived_from


class TestMemoryEntry:
    def test_defaults(self):
        e = MemoryEntry(id="m1", content="test")
        assert e.type == MemoryType.WORKING
        assert e.scope == MemoryScope.PRIVATE
        assert e.access_count == 0

    def test_touch(self):
        e = MemoryEntry(id="m1")
        old_time = e.last_accessed
        time.sleep(0.01)
        e.touch()
        assert e.access_count == 1
        assert e.last_accessed >= old_time

    def test_roundtrip(self):
        e = MemoryEntry(
            id="m1", type=MemoryType.SEMANTIC,
            scope=MemoryScope.SHARED,
            content="Auth uses OAuth2",
            tags=["auth"], relevance=0.9, importance=0.8,
        )
        data = e.to_dict()
        restored = MemoryEntry.from_dict(data)
        assert restored.type == MemoryType.SEMANTIC
        assert restored.scope == MemoryScope.SHARED
        assert restored.relevance == 0.9


class TestMemoryBank:
    def test_store_and_recall(self):
        bank = MemoryBank(owner="dev")
        entry = bank.store(MemoryEntry(content="test"))
        assert entry.id != ""
        assert bank.size == 1
        recalled = bank.recall(entry.id)
        assert recalled.content == "test"
        assert recalled.access_count == 1

    def test_auto_owner(self):
        bank = MemoryBank(owner="dev")
        entry = bank.store(MemoryEntry(content="test"))
        assert entry.lineage.created_by == "dev"

    def test_forget(self):
        bank = MemoryBank(owner="dev")
        entry = bank.store(MemoryEntry(id="m1", content="test"))
        removed = bank.forget("m1")
        assert removed is not None
        assert bank.size == 0
        assert bank.forget("m1") is None

    def test_search_by_query(self):
        bank = MemoryBank(owner="dev")
        bank.store(MemoryEntry(id="m1", content="Auth uses OAuth2"))
        bank.store(MemoryEntry(id="m2", content="Cache uses LRU"))
        results = bank.search(query="auth")
        assert len(results) == 1
        assert results[0].id == "m1"

    def test_search_by_tags(self):
        bank = MemoryBank(owner="dev")
        bank.store(MemoryEntry(id="m1", tags=["auth"]))
        bank.store(MemoryEntry(id="m2", tags=["cache"]))
        results = bank.search(tags=["auth"])
        assert len(results) == 1

    def test_search_by_type(self):
        bank = MemoryBank(owner="dev")
        bank.store(MemoryEntry(id="m1", type=MemoryType.EPISODIC))
        bank.store(MemoryEntry(id="m2", type=MemoryType.SEMANTIC))
        results = bank.search(memory_type=MemoryType.SEMANTIC)
        assert len(results) == 1

    def test_search_by_relevance(self):
        bank = MemoryBank(owner="dev")
        bank.store(MemoryEntry(id="m1", relevance=0.9))
        bank.store(MemoryEntry(id="m2", relevance=0.1))
        results = bank.search(min_relevance=0.5)
        assert len(results) == 1

    def test_search_by_importance(self):
        bank = MemoryBank(owner="dev")
        bank.store(MemoryEntry(id="m1", importance=0.9))
        bank.store(MemoryEntry(id="m2", importance=0.1))
        results = bank.search(min_importance=0.5)
        assert len(results) == 1

    def test_search_sorted_by_relevance_importance(self):
        bank = MemoryBank(owner="dev")
        bank.store(MemoryEntry(id="low", relevance=0.3, importance=0.3))
        bank.store(MemoryEntry(id="high", relevance=0.9, importance=0.9))
        bank.store(MemoryEntry(id="mid", relevance=0.5, importance=0.5))
        results = bank.search()
        assert results[0].id == "high"
        assert results[-1].id == "low"

    def test_search_limit(self):
        bank = MemoryBank(owner="dev")
        for i in range(10):
            bank.store(MemoryEntry(id=f"m{i}"))
        results = bank.search(limit=3)
        assert len(results) == 3

    def test_decay(self):
        bank = MemoryBank(owner="dev")
        bank.store(MemoryEntry(id="m1", relevance=0.5))
        bank.store(MemoryEntry(id="m2", relevance=0.05))
        bank.store(MemoryEntry(id="proc", relevance=0.5, type=MemoryType.PROCEDURAL))
        below = bank.decay(rate=0.1)
        assert bank.recall("m1").relevance == 0.4
        assert bank.recall("proc").relevance == 0.5  # Procedural doesn't decay
        assert below >= 1  # m2 is below 0.1

    def test_consolidate(self):
        bank = MemoryBank(owner="dev")
        bank.store(MemoryEntry(id="fresh", relevance=0.9, importance=0.3))
        bank.store(MemoryEntry(id="stale", relevance=0.05, importance=0.3))
        bank.store(MemoryEntry(id="important", relevance=0.05, importance=0.8))
        removed = bank.consolidate(min_relevance=0.1)
        assert len(removed) == 1  # Only "stale" (low relevance + low importance)
        assert removed[0].id == "stale"
        assert bank.size == 2

    def test_roundtrip(self):
        bank = MemoryBank(owner="dev", scope=MemoryScope.PRIVATE)
        bank.store(MemoryEntry(id="m1", content="test"))
        data = bank.to_dict()
        restored = MemoryBank.from_dict(data)
        assert restored.owner == "dev"
        assert restored.size == 1


class TestMemoryMesh:
    def test_default_has_shared(self):
        mesh = MemoryMesh()
        assert "shared" in mesh.bank_names
        assert mesh.get_bank("shared") is not None

    def test_create_bank(self):
        mesh = MemoryMesh()
        bank = mesh.create_bank("developer", scope=MemoryScope.PRIVATE)
        assert bank.owner == "developer"
        assert "developer" in mesh.bank_names

    def test_remove_bank(self):
        mesh = MemoryMesh()
        mesh.create_bank("temp")
        assert mesh.remove_bank("temp")
        assert "temp" not in mesh.bank_names

    def test_cannot_remove_shared(self):
        mesh = MemoryMesh()
        assert not mesh.remove_bank("shared")

    def test_store_and_recall(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        entry = mesh.store("dev", MemoryEntry(content="test"))
        assert entry is not None
        recalled = mesh.recall("dev", entry.id)
        assert recalled.content == "test"

    def test_store_nonexistent_bank(self):
        mesh = MemoryMesh()
        assert mesh.store("nope", MemoryEntry()) is None

    def test_recall_nonexistent_bank(self):
        mesh = MemoryMesh()
        assert mesh.recall("nope", "m1") is None

    def test_propagate(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        original = mesh.store("dev", MemoryEntry(
            content="Found OAuth2 issue",
            tags=["auth"], importance=0.8,
        ))
        copy = mesh.propagate("dev", original.id, "shared")
        assert copy is not None
        assert copy.content == "Found OAuth2 issue"
        assert copy.id != original.id
        assert original.id in copy.lineage.derived_from
        assert copy.lineage.version == 2
        # Original tracks propagation
        assert any("shared" in p for p in original.lineage.propagated_to)

    def test_propagate_nonexistent(self):
        mesh = MemoryMesh()
        assert mesh.propagate("nope", "m1", "shared") is None

    def test_search_private_only(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        mesh.store("dev", MemoryEntry(id="private", content="dev note", tags=["auth"]))
        mesh.store("shared", MemoryEntry(id="public", content="shared auth note", tags=["auth"]))

        # Search from dev's perspective (includes shared)
        results = mesh.search("dev", tags=["auth"])
        assert len(results) == 2

        # Search excluding shared
        results = mesh.search("dev", tags=["auth"], include_shared=False)
        assert len(results) == 1
        assert results[0].id == "private"

    def test_search_deduplicates(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        entry = mesh.store("dev", MemoryEntry(content="test", tags=["x"]))
        # Won't actually duplicate since same ID won't be in two banks
        results = mesh.search("dev", tags=["x"])
        seen_ids = [r.id for r in results]
        assert len(seen_ids) == len(set(seen_ids))

    def test_search_sorted_by_combined_score(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        mesh.store("dev", MemoryEntry(id="low", relevance=0.2, importance=0.2))
        mesh.store("dev", MemoryEntry(id="high", relevance=0.9, importance=0.9))
        results = mesh.search("dev")
        assert results[0].id == "high"

    def test_decay_all(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        mesh.store("dev", MemoryEntry(id="m1", relevance=0.5))
        mesh.store("shared", MemoryEntry(id="m2", relevance=0.5))
        stats = mesh.decay_all(rate=0.1)
        assert isinstance(stats, dict)
        assert "dev" in stats

    def test_consolidate_all(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        mesh.store("dev", MemoryEntry(relevance=0.01, importance=0.1))
        mesh.store("dev", MemoryEntry(relevance=0.9, importance=0.9))
        removed = mesh.consolidate_all(min_relevance=0.1)
        assert removed == 1

    def test_total_memories(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        mesh.store("dev", MemoryEntry(content="a"))
        mesh.store("dev", MemoryEntry(content="b"))
        mesh.store("shared", MemoryEntry(content="c"))
        assert mesh.total_memories == 3

    def test_stats(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        mesh.store("dev", MemoryEntry(content="a"))
        stats = mesh.stats()
        assert stats["banks"] == 2
        assert stats["total_memories"] == 1
        assert "dev" in stats["per_bank"]

    def test_summary(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev")
        s = mesh.summary()
        assert "MemoryMesh" in s
        assert "dev" in s

    def test_serialization_roundtrip(self):
        mesh = MemoryMesh()
        mesh.create_bank("dev", scope=MemoryScope.PRIVATE)
        mesh.store("dev", MemoryEntry(id="m1", content="private note"))
        mesh.store("shared", MemoryEntry(id="m2", content="shared note"))

        data = mesh.to_dict()
        restored = MemoryMesh.from_dict(data)
        assert restored.total_memories == 2
        assert restored.recall("dev", "m1").content == "private note"
        assert restored.recall("shared", "m2").content == "shared note"

    def test_multi_agent_scenario(self):
        """Simulate two agents with private banks + shared communication."""
        mesh = MemoryMesh()
        mesh.create_bank("developer", scope=MemoryScope.PRIVATE)
        mesh.create_bank("architect", scope=MemoryScope.PRIVATE)

        # Developer discovers something
        finding = mesh.store("developer", MemoryEntry(
            type=MemoryType.EPISODIC,
            content="auth.py has circular import with cache.py",
            tags=["auth", "circular-import"],
            importance=0.9,
        ))

        # Developer shares it
        shared = mesh.propagate("developer", finding.id, "shared")
        assert shared is not None

        # Architect searches and finds it
        results = mesh.search("architect", tags=["auth"])
        assert any("circular import" in r.content for r in results)

        # Architect creates their own analysis
        mesh.store("architect", MemoryEntry(
            type=MemoryType.SEMANTIC,
            content="Circular dependency violates layered architecture",
            tags=["auth", "architecture"],
            importance=0.9,
            lineage=MemoryLineage(derived_from=[shared.id]),
        ))

        # Both agents can see shared knowledge
        dev_results = mesh.search("developer", tags=["auth"])
        arch_results = mesh.search("architect", tags=["auth"])
        assert len(dev_results) >= 2  # own + shared
        assert len(arch_results) >= 2  # own + shared
