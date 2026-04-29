"""Tests for TUI slash command handling.

Validates all slash commands in the chat TUI return expected
responses without requiring Ollama or a live terminal.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nexus.agent.chat import ChatSession
from nexus.agent.models import AgentConfig
from nexus.tui.chat_ui import _handle_command


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text('print("hello")\n')
    return str(tmp_path)


@pytest.fixture
def session(workspace):
    """Create a ChatSession for command testing."""
    config = AgentConfig(workspace_path=workspace)
    return ChatSession(workspace=workspace, config=config)


@pytest.fixture
def console():
    """Mock console for command handling."""
    return MagicMock()


def run_cmd(cmd: str, session, console) -> str:
    """Helper to run a slash command synchronously."""
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_handle_command(cmd, session, console))
    finally:
        loop.close()
    return result


# ===================================================================
# Basic commands
# ===================================================================

class TestBasicCommands:
    """Tests for basic session management commands."""

    def test_help(self, session, console):
        result = run_cmd("/help", session, console)
        assert "Nexus Chat Commands" in result
        assert "/quit" in result
        assert "/diff" in result
        assert "/branch" in result
        assert "/trust" in result

    def test_quit(self, session, console):
        result = run_cmd("/quit", session, console)
        assert result is None  # Quit signal

    def test_exit(self, session, console):
        result = run_cmd("/exit", session, console)
        assert result is None

    def test_q(self, session, console):
        result = run_cmd("/q", session, console)
        assert result is None

    def test_clear(self, session, console):
        session.history.append({"role": "user", "content": "test"})
        result = run_cmd("/clear", session, console)
        assert "cleared" in result.lower()
        assert len(session.history) == 0

    def test_tools(self, session, console):
        result = run_cmd("/tools", session, console)
        assert "Available tools" in result

    def test_plan_no_arg(self, session, console):
        result = run_cmd("/plan", session, console)
        assert "Usage" in result

    def test_plan_with_arg(self, session, console):
        result = run_cmd("/plan build an API", session, console)
        assert result.startswith("SEND:")

    def test_unknown_command(self, session, console):
        result = run_cmd("/foobar", session, console)
        assert "Unknown command" in result

    def test_stats(self, session, console):
        result = run_cmd("/stats", session, console)
        assert "Turns" in result
        assert "Messages" in result
        assert "Tool calls" in result


# ===================================================================
# Intelligence commands
# ===================================================================

class TestIntelligenceCommands:

    def test_stance_list(self, session, console):
        result = run_cmd("/stance", session, console)
        # Should list stances or say not available
        assert "stance" in result.lower() or "Stances" in result

    def test_stance_set(self, session, console):
        result = run_cmd("/stance architect", session, console)
        # Either sets it or says not found
        assert "Stance" in result or "Unknown" in result or "stance" in result.lower()

    def test_project(self, session, console):
        result = run_cmd("/project", session, console)
        # Should show project info or "not available"
        assert isinstance(result, str)

    def test_route(self, session, console):
        result = run_cmd("/route", session, console)
        assert isinstance(result, str)


# ===================================================================
# Diff commands
# ===================================================================

class TestDiffCommands:

    def test_diff_no_pending(self, session, console):
        result = run_cmd("/diff", session, console)
        assert "No pending diffs" in result

    def test_diff_with_pending(self, session, console, workspace):
        """Generate a diff then check /diff output."""
        session._diff_engine.diff("src/main.py", "new content\n")
        result = run_cmd("/diff", session, console)
        assert "pending" in result.lower()
        assert "src/main.py" in result

    def test_diff_summary_mode(self, session, console, workspace):
        session._diff_engine.diff("src/main.py", "new content\n")
        result = run_cmd("/diff summary", session, console)
        assert "src/main.py" in result

    def test_accept_no_pending(self, session, console):
        result = run_cmd("/accept", session, console)
        assert "No pending" in result or "Nothing" in result

    def test_accept_with_pending(self, session, console, workspace):
        session._diff_engine.diff("src/main.py", "accepted content\n")
        result = run_cmd("/accept", session, console)
        assert "Applied" in result or "applied" in result.lower()

    def test_accept_specific_path(self, session, console, workspace):
        session._diff_engine.diff("src/main.py", "specific\n")
        result = run_cmd("/accept src/main.py", session, console)
        assert "Applied" in result or "applied" in result.lower()

    def test_reject_no_pending(self, session, console):
        result = run_cmd("/reject", session, console)
        assert "No pending" in result or "Nothing" in result

    def test_reject_with_pending(self, session, console, workspace):
        session._diff_engine.diff("src/main.py", "to reject\n")
        result = run_cmd("/reject", session, console)
        assert "Rejected" in result or "rejected" in result.lower()

    def test_undo_nothing(self, session, console):
        result = run_cmd("/undo", session, console)
        assert "Nothing to undo" in result or "undo" in result.lower()

    def test_undo_after_apply(self, session, console, workspace):
        diff = session._diff_engine.diff("src/main.py", "undo test\n")
        diff.accept_all()
        session._diff_engine.apply(diff)

        result = run_cmd("/undo", session, console)
        assert "Undone" in result or "restored" in result.lower()


# ===================================================================
# Branch commands
# ===================================================================

class TestBranchCommands:

    def test_branch_no_arg(self, session, console):
        result = run_cmd("/branch", session, console)
        assert "Usage" in result

    def test_branch_create(self, session, console):
        result = run_cmd("/branch feature-x", session, console)
        assert "feature-x" in result
        assert "Created" in result or "created" in result.lower()

    def test_branch_create_with_description(self, session, console):
        result = run_cmd("/branch feature-y trying new approach", session, console)
        assert "feature-y" in result

    def test_branches_list(self, session, console):
        session.create_branch("list-test")
        result = run_cmd("/branches", session, console)
        assert "main" in result
        assert "list-test" in result

    def test_switch_no_arg(self, session, console):
        result = run_cmd("/switch", session, console)
        assert "Usage" in result

    def test_switch_branch(self, session, console):
        session.create_branch("switch-target", switch=False)
        # Switch back to main first
        result = run_cmd("/switch main", session, console)
        assert "main" in result

    def test_switch_nonexistent(self, session, console):
        result = run_cmd("/switch nonexistent", session, console)
        assert "Error" in result or "not found" in result.lower()

    def test_compare_no_args(self, session, console):
        result = run_cmd("/compare", session, console)
        assert "Usage" in result

    def test_compare_one_arg(self, session, console):
        result = run_cmd("/compare main", session, console)
        assert "Usage" in result

    def test_compare_branches(self, session, console):
        session.create_branch("cmp-branch")
        result = run_cmd("/compare main cmp-branch", session, console)
        assert "main" in result
        assert "cmp-branch" in result

    def test_merge_no_arg(self, session, console):
        result = run_cmd("/merge", session, console)
        assert "Usage" in result

    def test_merge_branch(self, session, console):
        if session._branch_tree:
            session._branch_tree.add_message("user", "test")
        session.create_branch("merge-src")
        if session._branch_tree:
            session._branch_tree.add_message("user", "branch msg")
        session.switch_branch("main")
        result = run_cmd("/merge merge-src", session, console)
        assert "Merged" in result or "merged" in result.lower()

    def test_tree(self, session, console):
        session.create_branch("tree-branch")
        result = run_cmd("/tree", session, console)
        assert "main" in result
        assert "tree-branch" in result


# ===================================================================
# Safety commands
# ===================================================================

class TestSafetyCommands:

    def test_trust_show(self, session, console):
        result = run_cmd("/trust", session, console)
        assert "WRITE" in result
        assert "trust level" in result.lower()

    def test_trust_set(self, session, console):
        result = run_cmd("/trust execute", session, console)
        assert "EXECUTE" in result

    def test_trust_invalid(self, session, console):
        result = run_cmd("/trust superpower", session, console)
        assert "Unknown" in result

    def test_audit_empty(self, session, console):
        result = run_cmd("/audit", session, console)
        # Should show audit info even if empty
        assert "audit" in result.lower() or "Audit" in result

    def test_audit_after_checks(self, session, console):
        session._permissions.check("file_read", {"path": "x"})
        session._permissions.check("shell", {"command": "ls"})
        result = run_cmd("/audit", session, console)
        assert "file_read" in result or "Audit" in result

    def test_audit_with_limit(self, session, console):
        result = run_cmd("/audit 5", session, console)
        assert isinstance(result, str)


# ===================================================================
# Hook & watcher commands
# ===================================================================

class TestHookWatcherCommands:

    def test_hooks_empty(self, session, console):
        result = run_cmd("/hooks", session, console)
        assert "No hooks" in result

    def test_hooks_with_registered(self, session, console):
        from nexus.hooks.engine import Hook, HookPhase

        hook = Hook(
            name="test-display",
            phase=HookPhase.PRE,
            tools=["file_write"],
            action=lambda ctx: True,
            description="Displayed in /hooks",
        )
        session._hooks.register(hook)

        result = run_cmd("/hooks", session, console)
        assert "test-display" in result
        assert "file_write" in result

    def test_watch_status(self, session, console):
        result = run_cmd("/watch", session, console)
        assert "watcher" in result.lower() or "Watcher" in result

    def test_watch_with_registered(self, session, console):
        from nexus.hooks.engine import Watcher

        watcher = Watcher(
            name="py-watcher",
            patterns=["*.py"],
            on_change=lambda e: None,
            description="Watch Python files",
        )
        session._watcher.register(watcher)

        result = run_cmd("/watch", session, console)
        assert "py-watcher" in result


# ===================================================================
# Session commands
# ===================================================================

class TestSessionCommands:

    def test_save(self, session, console):
        result = run_cmd("/save", session, console)
        # Either saves or fails gracefully
        assert "saved" in result.lower() or "failed" in result.lower()

    def test_save_with_title(self, session, console):
        result = run_cmd("/save My Test Session", session, console)
        assert isinstance(result, str)

    def test_load_no_sessions(self, session, console):
        result = run_cmd("/load", session, console)
        # Either lists sessions or says none
        assert isinstance(result, str)
