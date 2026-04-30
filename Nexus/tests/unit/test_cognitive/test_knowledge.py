"""Tests for the Stratified Knowledge Architecture."""
import time
import pytest
from nexus.cognitive.knowledge import (
    KnowledgeStore, KnowledgeEntry, KnowledgeLayer,
    MembraneRule, LAYER_DESCRIPTIONS,
)


class TestKnowledgeLayer:
    def test_all_layers_exist(self):
        assert len(KnowledgeLayer) == 5
        assert KnowledgeLayer.SYNTAX == 0
        assert KnowledgeLayer.INTENT == 4

    def test_ordering(self):
        assert KnowledgeLayer.SYNTAX < KnowledgeLayer.FLOW
        assert KnowledgeLayer.FLOW < KnowledgeLayer.PATTERNS
        assert KnowledgeLayer.PATTERNS < KnowledgeLayer.DOMAIN
        assert KnowledgeLayer.DOMAIN < KnowledgeLayer.INTENT

    def test_descriptions_complete(self):
        for layer in KnowledgeLayer:
            assert layer in LAYER_DESCRIPTIONS


class TestKnowledgeEntry:
    def test_default_entry(self):
        entry = KnowledgeEntry(id="test", content="hello")
        assert entry.layer == KnowledgeLayer.SYNTAX
        assert entry.confidence == 1.0
        assert entry.access_count == 0

    def test_serialization_roundtrip(self):
        entry = KnowledgeEntry(
            id="fn-main", layer=KnowledgeLayer.FLOW,
            content="main() calls parse() then execute()",
            source="analysis", confidence=0.9,
            tags=["function", "flow"], references=["fn-parse"],
            metadata={"complexity": "medium"},
        )
        data = entry.to_dict()
        restored = KnowledgeEntry.from_dict(data)
        assert restored.id == "fn-main"
        assert restored.layer == KnowledgeLayer.FLOW
        assert restored.confidence == 0.9
        assert "function" in restored.tags
        assert "fn-parse" in restored.references


class TestMembraneRule:
    def test_allows_all_by_default(self):
        rule = MembraneRule(name="test")
        entry = KnowledgeEntry(id="e1", tags=["any"])
        assert rule.allows(entry)

    def test_blocks_when_disabled(self):
        rule = MembraneRule(name="test", enabled=False)
        entry = KnowledgeEntry(id="e1")
        assert not rule.allows(entry)

    def test_allowed_tags_filter(self):
        rule = MembraneRule(name="test", allowed_tags=["public"])
        assert rule.allows(KnowledgeEntry(id="e1", tags=["public"]))
        assert not rule.allows(KnowledgeEntry(id="e2", tags=["private"]))
        assert not rule.allows(KnowledgeEntry(id="e3", tags=[]))

    def test_blocked_tags_filter(self):
        rule = MembraneRule(name="test", blocked_tags=["secret"])
        assert rule.allows(KnowledgeEntry(id="e1", tags=["public"]))
        assert not rule.allows(KnowledgeEntry(id="e2", tags=["secret"]))

    def test_blocked_takes_priority(self):
        rule = MembraneRule(
            name="test",
            allowed_tags=["data"],
            blocked_tags=["secret"],
        )
        assert not rule.allows(KnowledgeEntry(id="e1", tags=["data", "secret"]))


class TestKnowledgeStore:
    def test_empty_store(self):
        store = KnowledgeStore()
        assert store.total_entries == 0

    def test_add_and_get(self):
        store = KnowledgeStore()
        entry = store.add(KnowledgeEntry(
            id="fn-foo", layer=KnowledgeLayer.SYNTAX,
            content="def foo(): pass",
        ))
        assert store.total_entries == 1
        retrieved = store.get("fn-foo")
        assert retrieved is not None
        assert retrieved.content == "def foo(): pass"
        assert retrieved.access_count == 1

    def test_auto_id(self):
        store = KnowledgeStore()
        entry = store.add(KnowledgeEntry(content="auto id test"))
        assert entry.id != ""
        assert store.get(entry.id) is not None

    def test_remove(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="e1", content="test"))
        removed = store.remove("e1")
        assert removed is not None
        assert store.total_entries == 0
        assert store.get("e1") is None

    def test_remove_nonexistent(self):
        store = KnowledgeStore()
        assert store.remove("nope") is None

    def test_update(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="e1", content="old", confidence=0.5))
        updated = store.update("e1", content="new", confidence=0.9)
        assert updated.content == "new"
        assert updated.confidence == 0.9

    def test_update_nonexistent(self):
        store = KnowledgeStore()
        assert store.update("nope", content="x") is None

    def test_query_by_layer(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="s1", layer=KnowledgeLayer.SYNTAX, content="syntax"))
        store.add(KnowledgeEntry(id="f1", layer=KnowledgeLayer.FLOW, content="flow"))
        store.add(KnowledgeEntry(id="s2", layer=KnowledgeLayer.SYNTAX, content="syntax2"))
        results = store.query(layer=KnowledgeLayer.SYNTAX)
        assert len(results) == 2

    def test_query_by_tags(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="e1", tags=["parser", "function"]))
        store.add(KnowledgeEntry(id="e2", tags=["database"]))
        store.add(KnowledgeEntry(id="e3", tags=["parser", "class"]))
        results = store.query(tags=["parser"])
        assert len(results) == 2

    def test_query_by_source(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="e1", source="auth.py"))
        store.add(KnowledgeEntry(id="e2", source="cache.py"))
        results = store.query(source="auth.py")
        assert len(results) == 1

    def test_query_by_confidence(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="e1", confidence=0.9))
        store.add(KnowledgeEntry(id="e2", confidence=0.3))
        results = store.query(min_confidence=0.5)
        assert len(results) == 1

    def test_query_text_search(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="e1", content="Cache eviction policy"))
        store.add(KnowledgeEntry(id="e2", content="Authentication handler"))
        results = store.query(search="cache")
        assert len(results) == 1

    def test_query_limit(self):
        store = KnowledgeStore()
        for i in range(20):
            store.add(KnowledgeEntry(id=f"e{i}", content=f"entry {i}"))
        results = store.query(limit=5)
        assert len(results) == 5

    def test_query_combined_filters(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(
            id="e1", layer=KnowledgeLayer.PATTERNS,
            tags=["factory"], confidence=0.9, content="Config factory",
        ))
        store.add(KnowledgeEntry(
            id="e2", layer=KnowledgeLayer.PATTERNS,
            tags=["factory"], confidence=0.3, content="Old factory",
        ))
        store.add(KnowledgeEntry(
            id="e3", layer=KnowledgeLayer.SYNTAX,
            tags=["factory"], confidence=0.9, content="factory function",
        ))
        results = store.query(
            layer=KnowledgeLayer.PATTERNS,
            tags=["factory"],
            min_confidence=0.5,
        )
        assert len(results) == 1
        assert results[0].id == "e1"

    def test_cross_layer_query_via_references(self):
        store = KnowledgeStore()
        syntax = store.add(KnowledgeEntry(
            id="fn-cache", layer=KnowledgeLayer.SYNTAX,
            content="def cache_get(key)", tags=["cache", "function"],
            references=["pattern-caching"],
        ))
        pattern = store.add(KnowledgeEntry(
            id="pattern-caching", layer=KnowledgeLayer.PATTERNS,
            content="LRU caching pattern with TTL", tags=["cache", "pattern"],
        ))
        results = store.query_cross_layer("fn-cache", KnowledgeLayer.PATTERNS)
        assert any(r.id == "pattern-caching" for r in results)

    def test_cross_layer_query_via_tags(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(
            id="fn-auth", layer=KnowledgeLayer.SYNTAX,
            content="def authenticate()", tags=["auth"],
        ))
        store.add(KnowledgeEntry(
            id="domain-auth", layer=KnowledgeLayer.DOMAIN,
            content="Authentication uses OAuth2", tags=["auth"],
        ))
        results = store.query_cross_layer("fn-auth", KnowledgeLayer.DOMAIN)
        assert any(r.id == "domain-auth" for r in results)

    def test_cross_layer_blocked_by_membrane(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(
            id="secret-key", layer=KnowledgeLayer.SYNTAX,
            content="API_KEY = ...", tags=["secret"],
        ))
        store.add(KnowledgeEntry(
            id="pattern-config", layer=KnowledgeLayer.PATTERNS,
            content="Config management", tags=["config"],
        ))
        # Add blocking membrane
        store.add_membrane(MembraneRule(
            name="block-secrets-up",
            from_layer=KnowledgeLayer.SYNTAX,
            to_layer=KnowledgeLayer.PATTERNS,
            direction="up",
            blocked_tags=["secret"],
        ))
        results = store.query_cross_layer("secret-key", KnowledgeLayer.PATTERNS)
        assert len(results) == 0

    def test_cross_layer_nonexistent_entry(self):
        store = KnowledgeStore()
        assert store.query_cross_layer("nope", KnowledgeLayer.SYNTAX) == []

    def test_layer_summary(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(
            id="e1", layer=KnowledgeLayer.SYNTAX,
            content="x", tags=["func"], source="a.py",
        ))
        store.add(KnowledgeEntry(
            id="e2", layer=KnowledgeLayer.SYNTAX,
            content="y", tags=["func"], source="b.py",
        ))
        summary = store.layer_summary(layers=[KnowledgeLayer.SYNTAX])
        assert "SYNTAX" in summary
        assert summary["SYNTAX"]["count"] == 2
        assert "func" in summary["SYNTAX"]["top_tags"]

    def test_layer_summary_all(self):
        store = KnowledgeStore()
        summary = store.layer_summary()
        assert len(summary) == 5

    def test_developer_view_vs_architect_view(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="s1", layer=KnowledgeLayer.SYNTAX))
        store.add(KnowledgeEntry(id="f1", layer=KnowledgeLayer.FLOW))
        store.add(KnowledgeEntry(id="p1", layer=KnowledgeLayer.PATTERNS))
        store.add(KnowledgeEntry(id="d1", layer=KnowledgeLayer.DOMAIN))
        store.add(KnowledgeEntry(id="i1", layer=KnowledgeLayer.INTENT))

        dev = store.layer_summary([KnowledgeLayer.SYNTAX, KnowledgeLayer.FLOW, KnowledgeLayer.PATTERNS])
        arch = store.layer_summary([KnowledgeLayer.PATTERNS, KnowledgeLayer.DOMAIN, KnowledgeLayer.INTENT])
        assert "SYNTAX" in dev and "SYNTAX" not in arch
        assert "INTENT" in arch and "INTENT" not in dev
        assert "PATTERNS" in dev and "PATTERNS" in arch  # Shared layer

    def test_default_membranes(self):
        store = KnowledgeStore()
        membranes = store.get_membranes()
        # 4 adjacent pairs × 2 directions = 8 default membranes
        assert len(membranes) == 8

    def test_disable_enable_membrane(self):
        store = KnowledgeStore()
        membranes = store.get_membranes()
        name = membranes[0].name
        assert store.disable_membrane(name)
        assert not membranes[0].enabled
        assert store.enable_membrane(name)
        assert membranes[0].enabled
        assert not store.disable_membrane("nonexistent")

    def test_layer_counts(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="e1", layer=KnowledgeLayer.SYNTAX))
        store.add(KnowledgeEntry(id="e2", layer=KnowledgeLayer.SYNTAX))
        store.add(KnowledgeEntry(id="e3", layer=KnowledgeLayer.DOMAIN))
        counts = store.layer_counts()
        assert counts["SYNTAX"] == 2
        assert counts["DOMAIN"] == 1
        assert counts["FLOW"] == 0

    def test_prune_stale_entries(self):
        store = KnowledgeStore()
        old = KnowledgeEntry(id="old", content="stale")
        old.last_accessed = time.time() - 100000  # Very old
        old.access_count = 0
        store.add(old)

        fresh = KnowledgeEntry(id="fresh", content="new")
        store.add(fresh)

        removed = store.prune(max_age_s=1000, min_access_count=0)
        assert removed == 1
        assert store.get("old") is None
        assert store.get("fresh") is not None

    def test_prune_respects_access_count(self):
        store = KnowledgeStore()
        old_but_used = KnowledgeEntry(id="used", content="used")
        old_but_used.last_accessed = time.time() - 100000
        old_but_used.access_count = 5
        store.add(old_but_used)

        removed = store.prune(max_age_s=1000, min_access_count=3)
        assert removed == 0  # access_count > min

    def test_serialization_roundtrip(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(
            id="e1", layer=KnowledgeLayer.PATTERNS,
            content="Factory pattern", tags=["pattern"],
        ))
        store.add(KnowledgeEntry(
            id="e2", layer=KnowledgeLayer.INTENT,
            content="Prioritize readability", tags=["principle"],
        ))
        store.add_membrane(MembraneRule(
            name="custom", from_layer=KnowledgeLayer.SYNTAX,
            to_layer=KnowledgeLayer.FLOW, blocked_tags=["secret"],
        ))

        data = store.to_dict()
        restored = KnowledgeStore.from_dict(data)
        assert restored.total_entries == 2
        assert restored.get("e1").content == "Factory pattern"
        # from_dict restores only the serialized membranes (8 defaults + 1 custom)
        custom = [m for m in restored.get_membranes() if m.name == "custom"]
        assert len(custom) == 1
        assert custom[0].blocked_tags == ["secret"]

    def test_summary(self):
        store = KnowledgeStore()
        store.add(KnowledgeEntry(id="e1", layer=KnowledgeLayer.SYNTAX))
        store.add(KnowledgeEntry(id="e2", layer=KnowledgeLayer.INTENT))
        s = store.summary()
        assert "2 entries" in s
        assert "SYNTAX" in s
        assert "INTENT" in s
