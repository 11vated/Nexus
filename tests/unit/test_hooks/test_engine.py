"""Tests for Hooks & Watchers engine."""

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

from nexus.hooks.engine import (
    Hook,
    HookEngine,
    HookPhase,
    HookResult,
    Watcher,
    WatcherEngine,
    WatchEvent,
    WatchEventType,
)


# ============================================================================
# Hook Engine Tests
# ============================================================================

@pytest.fixture
def hook_engine():
    return HookEngine()


class TestHookRegistration:
    """Test registering and managing hooks."""

    def test_register_hook(self, hook_engine):
        hook = Hook(
            name="test-hook",
            phase=HookPhase.PRE,
            tools=["file_write"],
            action=lambda ctx: True,
        )
        hook_engine.register(hook)
        hooks = hook_engine.list_hooks()
        assert len(hooks) == 1
        assert hooks[0]["name"] == "test-hook"

    def test_unregister_hook(self, hook_engine):
        hook = Hook(
            name="removable",
            phase=HookPhase.POST,
            tools=["*"],
            action=lambda ctx: None,
        )
        hook_engine.register(hook)
        assert hook_engine.unregister("removable") is True
        assert len(hook_engine.list_hooks()) == 0

    def test_unregister_nonexistent(self, hook_engine):
        assert hook_engine.unregister("nope") is False

    def test_priority_ordering(self, hook_engine):
        hook_engine.register(Hook(
            name="low-priority",
            phase=HookPhase.PRE,
            tools=["*"],
            action=lambda ctx: True,
            priority=200,
        ))
        hook_engine.register(Hook(
            name="high-priority",
            phase=HookPhase.PRE,
            tools=["*"],
            action=lambda ctx: True,
            priority=50,
        ))

        hooks = hook_engine.list_hooks()
        assert hooks[0]["name"] == "high-priority"
        assert hooks[1]["name"] == "low-priority"


class TestHookMatching:
    """Test hook tool matching."""

    def test_specific_tool_match(self):
        hook = Hook(name="t", phase=HookPhase.PRE, tools=["file_write"], action=lambda c: True)
        assert hook.matches("file_write") is True
        assert hook.matches("file_read") is False

    def test_wildcard_match(self):
        hook = Hook(name="t", phase=HookPhase.PRE, tools=["*"], action=lambda c: True)
        assert hook.matches("file_write") is True
        assert hook.matches("shell") is True

    def test_multiple_tools(self):
        hook = Hook(
            name="t",
            phase=HookPhase.PRE,
            tools=["file_write", "file_read"],
            action=lambda c: True,
        )
        assert hook.matches("file_write") is True
        assert hook.matches("file_read") is True
        assert hook.matches("shell") is False

    def test_disabled_hook_no_match(self):
        hook = Hook(
            name="t",
            phase=HookPhase.PRE,
            tools=["*"],
            action=lambda c: True,
            enabled=False,
        )
        assert hook.matches("file_write") is False


class TestPreHooks:
    """Test PRE hook firing."""

    @pytest.mark.asyncio
    async def test_fire_pre_allows(self, hook_engine):
        hook_engine.register(Hook(
            name="allow-all",
            phase=HookPhase.PRE,
            tools=["*"],
            action=lambda ctx: True,
        ))

        results = await hook_engine.fire_pre("file_write", {"path": "test.py"})
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].blocked is False

    @pytest.mark.asyncio
    async def test_fire_pre_blocks(self, hook_engine):
        hook_engine.register(Hook(
            name="blocker",
            phase=HookPhase.PRE,
            tools=["shell"],
            action=lambda ctx: False,
        ))

        results = await hook_engine.fire_pre("shell", {"command": "rm -rf /"})
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].blocked is True

    @pytest.mark.asyncio
    async def test_pre_hook_modifies_args(self, hook_engine):
        def modifier(ctx):
            return {"allow": True, "args": {"path": "modified.py"}}

        hook_engine.register(Hook(
            name="modifier",
            phase=HookPhase.PRE,
            tools=["file_write"],
            action=modifier,
        ))

        results = await hook_engine.fire_pre("file_write", {"path": "original.py"})
        assert results[0].modified_args == {"path": "modified.py"}

    @pytest.mark.asyncio
    async def test_pre_hook_error_handling(self, hook_engine):
        def failing_hook(ctx):
            raise RuntimeError("Hook crashed")

        hook_engine.register(Hook(
            name="crasher",
            phase=HookPhase.PRE,
            tools=["*"],
            action=failing_hook,
        ))

        results = await hook_engine.fire_pre("file_write", {})
        assert len(results) == 1
        assert results[0].success is False
        assert "Hook error" in results[0].message

    @pytest.mark.asyncio
    async def test_pre_hooks_stop_on_block(self, hook_engine):
        calls = []

        hook_engine.register(Hook(
            name="blocker",
            phase=HookPhase.PRE,
            tools=["*"],
            action=lambda ctx: False,
            priority=10,
        ))
        hook_engine.register(Hook(
            name="never-reached",
            phase=HookPhase.PRE,
            tools=["*"],
            action=lambda ctx: calls.append("reached"),
            priority=20,
        ))

        await hook_engine.fire_pre("shell", {})
        assert len(calls) == 0  # Second hook never fired

    @pytest.mark.asyncio
    async def test_async_hook(self, hook_engine):
        async def async_check(ctx):
            return True

        hook_engine.register(Hook(
            name="async-hook",
            phase=HookPhase.PRE,
            tools=["*"],
            action=async_check,
        ))

        results = await hook_engine.fire_pre("file_write", {})
        assert results[0].success is True


class TestPostHooks:
    """Test POST hook firing."""

    @pytest.mark.asyncio
    async def test_fire_post(self, hook_engine):
        captured = {}

        def logger(ctx):
            captured.update(ctx)

        hook_engine.register(Hook(
            name="logger",
            phase=HookPhase.POST,
            tools=["file_write"],
            action=logger,
        ))

        await hook_engine.fire_post(
            "file_write",
            {"path": "test.py"},
            result="Written 100 chars",
            success=True,
        )

        assert captured["tool"] == "file_write"
        assert captured["success"] is True
        assert captured["result"] == "Written 100 chars"

    @pytest.mark.asyncio
    async def test_post_hook_doesnt_fire_for_pre(self, hook_engine):
        hook_engine.register(Hook(
            name="post-only",
            phase=HookPhase.POST,
            tools=["*"],
            action=lambda ctx: None,
        ))

        results = await hook_engine.fire_pre("file_write", {})
        assert len(results) == 0  # POST hooks don't fire in PRE

    @pytest.mark.asyncio
    async def test_post_hook_error_handling(self, hook_engine):
        hook_engine.register(Hook(
            name="crasher",
            phase=HookPhase.POST,
            tools=["*"],
            action=lambda ctx: 1 / 0,
        ))

        results = await hook_engine.fire_post("file_write", {})
        assert len(results) == 1
        assert results[0].success is False


class TestHookHistory:
    """Test hook execution history."""

    @pytest.mark.asyncio
    async def test_history_recorded(self, hook_engine):
        hook_engine.register(Hook(
            name="tracked",
            phase=HookPhase.PRE,
            tools=["*"],
            action=lambda ctx: True,
        ))

        await hook_engine.fire_pre("shell", {})
        assert len(hook_engine.history) == 1

    @pytest.mark.asyncio
    async def test_clear_history(self, hook_engine):
        hook_engine.register(Hook(
            name="t",
            phase=HookPhase.PRE,
            tools=["*"],
            action=lambda ctx: True,
        ))
        await hook_engine.fire_pre("shell", {})
        hook_engine.clear_history()
        assert len(hook_engine.history) == 0


# ============================================================================
# Watcher Engine Tests
# ============================================================================

@pytest.fixture
def watch_workspace(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_it(): pass\n")
    return str(tmp_path)


@pytest.fixture
def watcher_engine(watch_workspace):
    return WatcherEngine(workspace=watch_workspace)


class TestWatcherRegistration:
    """Test registering watchers."""

    def test_register_watcher(self, watcher_engine):
        watcher_engine.register(Watcher(
            name="test-watcher",
            patterns=["*.py"],
            on_change=lambda e: None,
        ))
        watchers = watcher_engine.list_watchers()
        assert len(watchers) == 1
        assert watchers[0]["name"] == "test-watcher"

    def test_unregister(self, watcher_engine):
        watcher_engine.register(Watcher(
            name="removable",
            patterns=["*"],
            on_change=lambda e: None,
        ))
        assert watcher_engine.unregister("removable") is True
        assert len(watcher_engine.list_watchers()) == 0


class TestWatcherMatching:
    """Test watcher pattern matching."""

    def test_glob_match(self):
        w = Watcher(name="t", patterns=["*.py"], on_change=lambda e: None)
        assert w.matches("main.py") is True
        assert w.matches("main.js") is False

    def test_directory_match(self):
        w = Watcher(name="t", patterns=["tests/*"], on_change=lambda e: None)
        assert w.matches("tests/test_main.py") is True
        assert w.matches("src/main.py") is False

    def test_disabled_no_match(self):
        w = Watcher(name="t", patterns=["*"], on_change=lambda e: None, enabled=False)
        assert w.matches("anything.py") is False

    def test_multiple_patterns(self):
        w = Watcher(name="t", patterns=["*.py", "*.js"], on_change=lambda e: None)
        assert w.matches("main.py") is True
        assert w.matches("app.js") is True
        assert w.matches("style.css") is False


class TestFileScanning:
    """Test file change detection."""

    def test_initial_scan(self, watcher_engine, watch_workspace):
        events = watcher_engine.scan()
        # First scan detects all files as "created"
        assert len(events) > 0
        assert all(e.event_type == WatchEventType.CREATED for e in events)

    def test_no_changes(self, watcher_engine, watch_workspace):
        watcher_engine.scan()  # Initial snapshot
        events = watcher_engine.scan()  # Second scan — no changes
        assert len(events) == 0

    def test_detect_modification(self, watcher_engine, watch_workspace):
        watcher_engine.scan()  # Initial snapshot

        # Modify a file
        (Path(watch_workspace) / "src" / "main.py").write_text("print('changed')\n")
        events = watcher_engine.scan()

        modified = [e for e in events if e.event_type == WatchEventType.MODIFIED]
        assert len(modified) >= 1

    def test_detect_creation(self, watcher_engine, watch_workspace):
        watcher_engine.scan()

        (Path(watch_workspace) / "src" / "new.py").write_text("new file\n")
        events = watcher_engine.scan()

        created = [e for e in events if e.event_type == WatchEventType.CREATED]
        assert len(created) >= 1

    def test_detect_deletion(self, watcher_engine, watch_workspace):
        watcher_engine.scan()

        (Path(watch_workspace) / "src" / "main.py").unlink()
        events = watcher_engine.scan()

        deleted = [e for e in events if e.event_type == WatchEventType.DELETED]
        assert len(deleted) >= 1


class TestWatcherCallbacks:
    """Test watcher callbacks fire on changes."""

    def test_callback_fires(self, watcher_engine, watch_workspace):
        events_received = []

        watcher_engine.register(Watcher(
            name="spy",
            patterns=["src/*"],
            on_change=lambda e: events_received.append(e),
            debounce_ms=0,
        ))

        watcher_engine.scan()  # Initial
        (Path(watch_workspace) / "src" / "main.py").write_text("changed\n")
        watcher_engine.scan()

        assert len(events_received) >= 1

    def test_callback_not_fired_for_unmatched(self, watcher_engine, watch_workspace):
        # Take initial snapshot WITHOUT a watcher
        watcher_engine.scan()

        events_received = []
        watcher_engine.register(Watcher(
            name="src-only",
            patterns=["src/*"],
            on_change=lambda e: events_received.append(e),
            debounce_ms=0,
        ))

        # Change a tests/ file — should NOT trigger src-only watcher
        (Path(watch_workspace) / "tests" / "test_main.py").write_text("changed\n")
        watcher_engine.scan()

        # The watcher only watches src/*, so tests/ changes shouldn't fire
        assert len(events_received) == 0


class TestSnapshot:
    """Test snapshot operations."""

    def test_take_snapshot(self, watcher_engine, watch_workspace):
        snapshot = watcher_engine.take_snapshot()
        assert len(snapshot) > 0
        # Should have relative paths
        assert any("main.py" in k for k in snapshot)

    def test_recent_events(self, watcher_engine, watch_workspace):
        watcher_engine.scan()
        events = watcher_engine.recent_events
        assert isinstance(events, list)

    def test_clear_events(self, watcher_engine, watch_workspace):
        watcher_engine.scan()
        watcher_engine.clear_events()
        assert len(watcher_engine.recent_events) == 0


class TestWatchEvent:
    """Test WatchEvent dataclass."""

    def test_create(self):
        event = WatchEvent(
            event_type=WatchEventType.MODIFIED,
            path="src/main.py",
            old_hash="abc",
            new_hash="def",
        )
        assert event.event_type == WatchEventType.MODIFIED
        assert event.path == "src/main.py"
        assert event.timestamp > 0


class TestHookResult:
    """Test HookResult properties."""

    def test_blocked_only_for_pre(self):
        pre_fail = HookResult(
            hook_name="test",
            phase=HookPhase.PRE,
            success=False,
        )
        assert pre_fail.blocked is True

        post_fail = HookResult(
            hook_name="test",
            phase=HookPhase.POST,
            success=False,
        )
        assert post_fail.blocked is False

    def test_not_blocked_on_success(self):
        result = HookResult(
            hook_name="test",
            phase=HookPhase.PRE,
            success=True,
        )
        assert result.blocked is False
