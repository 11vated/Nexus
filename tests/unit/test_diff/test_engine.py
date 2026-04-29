"""Tests for the Diff Engine — live diff preview."""

import os
import tempfile
from pathlib import Path

import pytest

from nexus.diff.engine import Changeset, DiffEngine, DiffHunk, DiffResult, DiffType


@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace with some files."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def hello():\n    print('hello')\n")
    (tmp_path / "src" / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "README.md").write_text("# My Project\n")
    return str(tmp_path)


@pytest.fixture
def engine(workspace):
    return DiffEngine(workspace=workspace)


class TestDiffGeneration:
    """Test diff generation for various scenarios."""

    def test_simple_modification(self, engine, workspace):
        new_content = "def hello():\n    print('hello world')\n"
        result = engine.diff("src/main.py", new_content)

        assert result.diff_type == DiffType.MODIFICATION
        assert result.additions > 0
        assert result.deletions > 0
        assert len(result.hunks) >= 1
        assert "hello world" in result.unified

    def test_new_file(self, engine, workspace):
        new_content = "class Config:\n    pass\n"
        result = engine.diff("src/config.py", new_content)

        assert result.diff_type == DiffType.NEW_FILE
        assert result.additions > 0
        assert result.deletions == 0

    def test_delete_file(self, engine, workspace):
        result = engine.diff("src/main.py", "")

        assert result.diff_type == DiffType.DELETE_FILE
        assert result.deletions > 0

    def test_no_changes(self, engine, workspace):
        original = Path(workspace) / "src" / "main.py"
        content = original.read_text()
        result = engine.diff("src/main.py", content)

        assert result.is_empty

    def test_stats(self, engine, workspace):
        new_content = "def hello():\n    print('hi')\n    return True\n"
        result = engine.diff("src/main.py", new_content)

        stats = result.stats
        assert "additions" in stats
        assert "deletions" in stats
        assert "hunks" in stats
        assert "net" in stats

    def test_path_traversal_blocked(self, engine):
        with pytest.raises(ValueError, match="traversal"):
            engine.diff("../../etc/passwd", "malicious")


class TestHunkOperations:
    """Test hunk accept/reject functionality."""

    def test_accept_all(self, engine, workspace):
        new_content = "def hello():\n    print('changed')\n    return 42\n"
        result = engine.diff("src/main.py", new_content)
        result.accept_all()

        assert all(h.accepted is True for h in result.hunks)
        assert len(result.accepted_hunks) == len(result.hunks)

    def test_reject_all(self, engine, workspace):
        new_content = "def hello():\n    print('changed')\n"
        result = engine.diff("src/main.py", new_content)
        result.reject_all()

        assert all(h.accepted is False for h in result.hunks)
        assert len(result.accepted_hunks) == 0

    def test_accept_specific_hunk(self, engine, workspace):
        new_content = "def hello():\n    print('changed')\n"
        result = engine.diff("src/main.py", new_content)

        if result.hunks:
            assert result.accept_hunk(0) is True
            assert result.hunks[0].accepted is True

    def test_reject_specific_hunk(self, engine, workspace):
        new_content = "def hello():\n    print('changed')\n"
        result = engine.diff("src/main.py", new_content)

        if result.hunks:
            assert result.reject_hunk(0) is True
            assert result.hunks[0].accepted is False

    def test_accept_nonexistent_hunk(self, engine, workspace):
        new_content = "def hello():\n    print('changed')\n"
        result = engine.diff("src/main.py", new_content)

        assert result.accept_hunk(999) is False

    def test_pending_hunks(self, engine, workspace):
        new_content = "def hello():\n    print('changed')\n"
        result = engine.diff("src/main.py", new_content)

        # All hunks start as pending
        assert len(result.pending_hunks) == len(result.hunks)

    def test_hunk_properties(self, engine, workspace):
        new_content = "def hello():\n    print('changed')\n    return True\n"
        result = engine.diff("src/main.py", new_content)

        for hunk in result.hunks:
            assert hunk.additions >= 0
            assert hunk.deletions >= 0
            assert hunk.context_lines >= 0


class TestDiffApplication:
    """Test applying diffs to files."""

    def test_apply_full_diff(self, engine, workspace):
        new_content = "def hello():\n    print('applied!')\n"
        diff = engine.diff("src/main.py", new_content)

        result = engine.apply(diff)
        assert len(result["applied"]) == 1
        assert len(result["errors"]) == 0

        # Verify file was written
        content = (Path(workspace) / "src" / "main.py").read_text()
        assert "applied!" in content

    def test_apply_new_file(self, engine, workspace):
        new_content = "# New module\nclass Foo:\n    pass\n"
        diff = engine.diff("src/new_module.py", new_content)

        result = engine.apply(diff)
        assert len(result["applied"]) == 1

        target = Path(workspace) / "src" / "new_module.py"
        assert target.exists()
        assert "Foo" in target.read_text()

    def test_apply_creates_directories(self, engine, workspace):
        new_content = "# Deep file\n"
        diff = engine.diff("src/deep/nested/file.py", new_content)

        result = engine.apply(diff)
        assert len(result["applied"]) == 1
        assert (Path(workspace) / "src" / "deep" / "nested" / "file.py").exists()

    def test_conflict_detection(self, engine, workspace):
        diff = engine.diff("src/main.py", "new content\n")

        # Modify the file behind the engine's back
        (Path(workspace) / "src" / "main.py").write_text("sneaky change\n")

        result = engine.apply(diff)
        assert len(result["errors"]) == 1
        assert "conflict" in result["errors"][0]["reason"]

    def test_reject_skips_application(self, engine, workspace):
        diff = engine.diff("src/main.py", "rejected content\n")
        diff.reject_all()

        result = engine.apply(diff)
        assert len(result["skipped"]) == 1

        # Original file unchanged
        content = (Path(workspace) / "src" / "main.py").read_text()
        assert "rejected content" not in content

    def test_undo_last(self, engine, workspace):
        original = (Path(workspace) / "src" / "main.py").read_text()
        diff = engine.diff("src/main.py", "overwritten\n")
        engine.apply(diff)

        # Undo
        undo_result = engine.undo_last()
        assert undo_result is not None
        assert undo_result["restored"] is True

        # File restored
        content = (Path(workspace) / "src" / "main.py").read_text()
        assert content == original

    def test_undo_empty_history(self, engine):
        assert engine.undo_last() is None


class TestChangeset:
    """Test multi-file changesets."""

    def test_create_changeset(self, engine, workspace):
        cs = engine.changeset([
            ("src/main.py", "def hello():\n    return 'changed'\n"),
            ("src/utils.py", "def add(a, b):\n    return a + b + 0\n"),
        ], description="Fix both files")

        assert cs.file_count == 2
        assert "Fix both files" in cs.description
        assert cs.total_additions >= 0

    def test_apply_changeset(self, engine, workspace):
        cs = engine.changeset([
            ("src/main.py", "# changed main\n"),
            ("src/utils.py", "# changed utils\n"),
        ])

        result = engine.apply(cs)
        assert len(result["applied"]) == 2
        assert cs.applied is True

    def test_changeset_stats(self, engine, workspace):
        cs = engine.changeset([
            ("src/main.py", "new\n"),
            ("src/new.py", "brand new\n"),
        ])

        stats = cs.stats
        assert stats["files"] == 2
        assert "additions" in stats
        assert "deletions" in stats


class TestEngineState:
    """Test engine state and metadata."""

    def test_pending_count(self, engine, workspace):
        assert engine.pending_count == 0
        engine.diff("src/main.py", "new\n")
        assert engine.pending_count == 1

    def test_pending_diffs(self, engine, workspace):
        engine.diff("src/main.py", "new\n")
        engine.diff("src/utils.py", "new\n")
        assert len(engine.pending_diffs) == 2

    def test_history_after_apply(self, engine, workspace):
        assert engine.history_count == 0
        diff = engine.diff("src/main.py", "new\n")
        engine.apply(diff)
        assert engine.history_count == 1

    def test_reject_clears_pending(self, engine, workspace):
        diff = engine.diff("src/main.py", "new\n")
        engine.reject(diff)
        assert engine.pending_count == 0

    def test_hash_content(self):
        h1 = DiffEngine._hash_content("hello")
        h2 = DiffEngine._hash_content("hello")
        h3 = DiffEngine._hash_content("world")

        assert h1 == h2
        assert h1 != h3
