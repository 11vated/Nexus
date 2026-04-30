"""Tests for Temporal Intelligence module."""

import time
from unittest.mock import patch

import pytest

from nexus.cognitive.temporal import (
    CodeAge,
    CommitInfo,
    GitAnalyzer,
    TemporalIndex,
    TemporalMemory,
    VelocityEntry,
    VelocityTracker,
)


class TestCommitInfo:
    def test_to_dict(self):
        c = CommitInfo(
            hash="abc123",
            author="dev",
            date=1000.0,
            message="fix bug",
            files_changed=["a.py"],
            additions=10,
            deletions=5,
        )
        d = c.to_dict()
        assert d["hash"] == "abc123"
        assert d["additions"] == 10

    def test_from_dict_roundtrip(self):
        c = CommitInfo(
            hash="def456",
            author="dev2",
            date=2000.0,
            message="feat: add login",
            category="feature",
        )
        d = c.to_dict()
        restored = CommitInfo.from_dict(d)
        assert restored.hash == c.hash
        assert restored.category == c.category


class TestCodeAge:
    def test_age_days(self):
        now = time.time()
        age = CodeAge(
            entity="foo",
            file_path="a.py",
            created_at=now - 86400 * 5,
            last_modified=now,
        )
        assert age.age_days == pytest.approx(5, abs=0.1)

    def test_days_since_modified(self):
        now = time.time()
        age = CodeAge(
            entity="foo",
            file_path="a.py",
            created_at=now - 86400 * 10,
            last_modified=now - 86400 * 2,
        )
        assert age.days_since_modified == pytest.approx(2, abs=0.1)

    def test_to_dict(self):
        age = CodeAge(
            entity="bar",
            file_path="b.py",
            created_at=1000.0,
            last_modified=2000.0,
            churn_count=5,
        )
        d = age.to_dict()
        assert d["entity"] == "bar"
        assert d["churn_count"] == 5

    def test_from_dict_roundtrip(self):
        age = CodeAge(
            entity="baz",
            file_path="c.py",
            created_at=100.0,
            last_modified=200.0,
            last_author="dev",
            churn_count=3,
        )
        d = age.to_dict()
        restored = CodeAge.from_dict(d)
        assert restored.entity == age.entity
        assert restored.churn_count == age.churn_count


class TestVelocityEntry:
    def test_duration(self):
        entry = VelocityEntry(
            task_description="test",
            start_time=1000.0,
            end_time=1060.0,
            success=True,
        )
        assert entry.duration_seconds == 60.0
        assert entry.duration_minutes == 1.0

    def test_to_dict(self):
        entry = VelocityEntry(
            task_description="feat",
            start_time=1000.0,
            end_time=1100.0,
            success=True,
            task_type="code",
            complexity="moderate",
        )
        d = entry.to_dict()
        assert d["task_type"] == "code"

    def test_from_dict_roundtrip(self):
        entry = VelocityEntry(
            task_description="test",
            start_time=1000.0,
            end_time=1200.0,
            success=False,
            task_type="test",
            complexity="simple",
        )
        d = entry.to_dict()
        restored = VelocityEntry.from_dict(d)
        assert restored.task_description == entry.task_description
        assert restored.success == entry.success


class TestTemporalIndex:
    def test_record_change_new(self):
        idx = TemporalIndex()
        idx.record_change("foo", "a.py", "abc123", "dev", 1000.0)
        age = idx.get_entity_age("a.py", "foo")
        assert age is not None
        assert age.churn_count == 1

    def test_record_change_existing(self):
        idx = TemporalIndex()
        idx.record_change("foo", "a.py", "abc123", "dev1", 1000.0)
        idx.record_change("foo", "a.py", "def456", "dev2", 2000.0)
        age = idx.get_entity_age("a.py", "foo")
        assert age.churn_count == 2
        assert age.last_author == "dev2"

    def test_get_most_churned(self):
        idx = TemporalIndex()
        idx.record_change("foo", "a.py", "h1", "dev", 1000.0)
        idx.record_change("foo", "a.py", "h2", "dev", 1100.0)
        idx.record_change("foo", "a.py", "h3", "dev", 1200.0)
        idx.record_change("bar", "b.py", "h4", "dev", 1000.0)

        most = idx.get_most_churned(limit=1)
        assert len(most) == 1
        assert most[0].entity == "foo"

    def test_get_stale_entities(self):
        idx = TemporalIndex()
        now = time.time()
        idx.record_change("old", "a.py", "h1", "dev", now - 86400 * 100)
        idx.record_change("new", "b.py", "h2", "dev", now)

        stale = idx.get_stale_entities(days=90)
        assert len(stale) == 1
        assert stale[0].entity == "old"

    def test_serialization_roundtrip(self):
        idx = TemporalIndex()
        idx.record_change("foo", "a.py", "h1", "dev", 1000.0)
        idx.record_change("bar", "b.py", "h2", "dev", 2000.0)

        data = idx.to_dict()
        restored = TemporalIndex.from_dict(data)

        assert len(restored.entities) == 2


class TestGitAnalyzer:
    def test_categorize_feature(self):
        analyzer = GitAnalyzer()
        assert analyzer._categorize_message("feat: add login") == "feature"
        assert analyzer._categorize_message("add new endpoint") == "feature"

    def test_categorize_fix(self):
        analyzer = GitAnalyzer()
        assert analyzer._categorize_message("fix: null pointer") == "fix"
        assert analyzer._categorize_message("bug in auth") == "fix"

    def test_categorize_refactor(self):
        analyzer = GitAnalyzer()
        assert analyzer._categorize_message("refactor: clean up") == "refactor"

    def test_categorize_test(self):
        analyzer = GitAnalyzer()
        assert analyzer._categorize_message("test: add unit tests") == "test"

    def test_categorize_docs(self):
        analyzer = GitAnalyzer()
        assert analyzer._categorize_message("doc: update readme") == "docs"

    def test_categorize_chore(self):
        analyzer = GitAnalyzer()
        assert analyzer._categorize_message("chore: update deps") == "chore"

    def test_categorize_performance(self):
        analyzer = GitAnalyzer()
        assert analyzer._categorize_message("perf: optimize query") == "performance"

    def test_categorize_unknown(self):
        analyzer = GitAnalyzer()
        assert analyzer._categorize_message("random message") == "other"

    def test_categorize_commits(self):
        analyzer = GitAnalyzer()
        commits = [
            CommitInfo(hash="1", author="a", date=1.0, message="feat: add x"),
            CommitInfo(hash="2", author="a", date=2.0, message="fix: bug y"),
        ]
        categorized = analyzer.categorize_commits(commits)
        assert categorized[0].category == "feature"
        assert categorized[1].category == "fix"

    def test_analyze_patterns_empty(self):
        analyzer = GitAnalyzer()
        patterns = analyzer.analyze_patterns([])
        assert patterns == {}

    def test_analyze_patterns(self):
        analyzer = GitAnalyzer()
        commits = [
            CommitInfo(hash="1", author="dev", date=1000.0, message="feat: add a", category="feature", files_changed=["a.py"], additions=10, deletions=5),
            CommitInfo(hash="2", author="dev", date=2000.0, message="fix: b", category="fix", files_changed=["b.py"], additions=5, deletions=2),
        ]
        patterns = analyzer.analyze_patterns(commits)
        assert patterns["total_commits"] == 2
        assert patterns["categories"]["feature"] == 1
        assert patterns["total_additions"] == 15

    def test_get_commits_no_repo(self):
        analyzer = GitAnalyzer(repo_path="/nonexistent/path")
        commits = analyzer.get_commits()
        assert commits == []


class TestVelocityTracker:
    def test_record_task(self):
        tracker = VelocityTracker()
        entry = tracker.record_task(
            "test task",
            start_time=1000.0,
            end_time=1060.0,
            success=True,
        )
        assert entry.duration_minutes == 1.0
        assert len(tracker.entries) == 1

    def test_estimate_time_no_data(self):
        tracker = VelocityTracker()
        assert tracker.estimate_time("code", "complex") is None

    def test_estimate_time(self):
        tracker = VelocityTracker()
        tracker.record_task("task1", 1000.0, 1060.0, True, "code", "simple")
        tracker.record_task("task2", 2000.0, 2070.0, True, "code", "simple")
        tracker.record_task("task3", 3000.0, 3120.0, True, "code", "simple")

        estimate = tracker.estimate_time("code", "simple")
        assert estimate == pytest.approx(1.4, abs=0.1)

    def test_get_average_velocity_no_data(self):
        tracker = VelocityTracker()
        stats = tracker.get_average_velocity()
        assert stats["tasks_completed"] == 0

    def test_get_average_velocity(self):
        tracker = VelocityTracker()
        now = time.time()
        tracker.record_task("task1", now - 3600, now - 3000, True, "code")
        tracker.record_task("task2", now - 1800, now - 1200, True, "code")
        tracker.record_task("task3", now - 600, now - 300, False, "code")

        stats = tracker.get_average_velocity(days=1)
        assert stats["tasks_completed"] == 2
        assert stats["success_rate"] == pytest.approx(0.67, abs=0.01)

    def test_is_unusually_slow_no_data(self):
        tracker = VelocityTracker()
        assert tracker.is_unusually_slow(60.0, "code") is False

    def test_is_unusually_slow(self):
        tracker = VelocityTracker()
        tracker.record_task("t1", 1000.0, 1060.0, True, "code")
        tracker.record_task("t2", 2000.0, 2060.0, True, "code")
        tracker.record_task("t3", 3000.0, 3060.0, True, "code")
        tracker.record_task("t4", 4000.0, 4500.0, True, "code")

        assert tracker.is_unusually_slow(8.3, "code", threshold=2.0) is True

    def test_serialization_roundtrip(self):
        tracker = VelocityTracker()
        tracker.record_task("test", 1000.0, 1100.0, True, "code", "simple")

        data = tracker.to_dict()
        restored = VelocityTracker.from_dict(data)

        assert len(restored.entries) == 1
        assert restored.entries[0].task_description == "test"


class TestTemporalMemory:
    def test_store_and_get(self):
        tm = TemporalMemory()
        tm.store("key1", "value1")
        assert tm.get("key1") == "value1"

    def test_get_nonexistent(self):
        tm = TemporalMemory()
        assert tm.get("missing") is None

    def test_get_at_time(self):
        tm = TemporalMemory()
        tm.store("key", "old_value", timestamp=1000.0)
        assert tm.get_at_time("key", 1500.0) == "old_value"
        assert tm.get_at_time("key", 500.0) is None

    def test_get_since(self):
        tm = TemporalMemory()
        tm.store("a", 1, timestamp=1000.0)
        tm.store("b", 2, timestamp=2000.0)
        tm.store("c", 3, timestamp=3000.0)

        since = tm.get_since(1500.0)
        assert "b" in since
        assert "c" in since
        assert "a" not in since

    def test_get_between(self):
        tm = TemporalMemory()
        tm.store("a", 1, timestamp=1000.0)
        tm.store("b", 2, timestamp=2000.0)
        tm.store("c", 3, timestamp=3000.0)
        tm.store("d", 4, timestamp=4000.0)

        between = tm.get_between(1500.0, 3500.0)
        assert "b" in between
        assert "c" in between
        assert "a" not in between
        assert "d" not in between

    def test_delete(self):
        tm = TemporalMemory()
        tm.store("key", "value")
        tm.delete("key")
        assert tm.get("key") is None

    def test_clear_before(self):
        tm = TemporalMemory()
        tm.store("a", 1, timestamp=1000.0)
        tm.store("b", 2, timestamp=2000.0)
        tm.store("c", 3, timestamp=3000.0)

        removed = tm.clear_before(2500.0)
        assert removed == 2
        assert tm.get("a") is None
        assert tm.get("b") is None
        assert tm.get("c") == 3

    def test_serialization_roundtrip(self):
        tm = TemporalMemory()
        tm.store("key1", "value1", timestamp=1000.0)
        tm.store("key2", {"nested": True}, timestamp=2000.0)

        data = tm.to_dict()
        restored = TemporalMemory.from_dict(data)

        assert restored.get("key1") == "value1"
        assert restored.get("key2") == {"nested": True}

    def test_from_dict_empty(self):
        restored = TemporalMemory.from_dict({})
        assert restored.entries == {}
