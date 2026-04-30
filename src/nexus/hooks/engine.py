"""Hook & Watcher Engine — automatic reactions to events.

## Hooks — before/after tool execution

Hooks fire automatically around tool calls:
  - pre_write: lint check before writing files
  - post_write: auto-format after writing files
  - pre_shell: safety check before shell commands
  - post_test: analyze test results

Think of hooks like git hooks but for AI tool calls.

## Watchers — background file monitoring

Watchers detect file changes and trigger notifications or actions:
  - "test file changed → run tests"
  - "config file changed → reload"
  - "new file created → add to project map"

This is what makes Nexus a living part of your workflow — it notices
things and tells you proactively.

Usage:
    hooks = HookEngine()

    # Register a hook
    hooks.register(Hook(
        name="auto-format",
        phase=HookPhase.POST,
        tools=["file_write"],
        action=lambda ctx: format_file(ctx["path"]),
    ))

    # Fire hooks around a tool call
    await hooks.fire_pre("file_write", {"path": "src/api.py"})
    result = await tool.execute(...)
    await hooks.fire_post("file_write", {"path": "src/api.py", "result": result})

    # Set up a watcher
    watchers = WatcherEngine(workspace="/path/to/project")
    watchers.register(Watcher(
        name="test-watcher",
        patterns=["tests/**/*.py"],
        on_change=lambda event: run_tests(),
    ))
"""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ============================================================================
# Hooks
# ============================================================================

class HookPhase(Enum):
    """When a hook fires relative to tool execution."""
    PRE = "pre"      # Before the tool runs
    POST = "post"    # After the tool completes


@dataclass
class HookResult:
    """Result of firing a hook."""
    hook_name: str
    phase: HookPhase
    success: bool
    message: str = ""
    modified_args: Optional[Dict[str, Any]] = None  # PRE hooks can modify args
    duration_ms: float = 0.0

    @property
    def blocked(self) -> bool:
        """PRE hooks can block execution by returning success=False."""
        return self.phase == HookPhase.PRE and not self.success


@dataclass
class Hook:
    """A hook that fires before or after tool execution.

    Hooks can:
      - Validate/modify tool arguments (PRE hooks)
      - Block tool execution (PRE hooks returning False)
      - React to tool results (POST hooks)
      - Log, format, lint, test, etc.
    """
    name: str
    phase: HookPhase
    tools: List[str]                    # Tool names to hook into ("*" = all)
    action: Callable[..., Any]          # Sync or async callable
    enabled: bool = True
    priority: int = 100                 # Lower = runs first
    description: str = ""

    def matches(self, tool_name: str) -> bool:
        """Check if this hook should fire for a given tool."""
        if not self.enabled:
            return False
        return "*" in self.tools or tool_name in self.tools


class HookEngine:
    """Manages and fires hooks around tool execution."""

    def __init__(self) -> None:
        self._hooks: List[Hook] = []
        self._history: List[HookResult] = []

    def register(self, hook: Hook) -> None:
        """Register a hook."""
        self._hooks.append(hook)
        self._hooks.sort(key=lambda h: h.priority)
        logger.info("Registered hook: %s (%s)", hook.name, hook.phase.value)

    def unregister(self, name: str) -> bool:
        """Unregister a hook by name."""
        before = len(self._hooks)
        self._hooks = [h for h in self._hooks if h.name != name]
        return len(self._hooks) < before

    async def fire_pre(
        self,
        tool_name: str,
        args: Dict[str, Any],
    ) -> List[HookResult]:
        """Fire all PRE hooks for a tool.

        Returns list of results. If any hook blocks, the tool should NOT execute.
        PRE hooks can also modify args (returned in HookResult.modified_args).
        """
        results = []
        for hook in self._hooks:
            if hook.phase != HookPhase.PRE or not hook.matches(tool_name):
                continue

            start = time.time()
            try:
                context = {"tool": tool_name, "args": args, "phase": "pre"}
                result = hook.action(context)
                if asyncio.iscoroutine(result):
                    result = await result

                # Interpret result
                if isinstance(result, dict):
                    # Hook returned modified args or control signals
                    success = result.get("allow", True)
                    message = result.get("message", "")
                    modified = result.get("args")
                elif isinstance(result, bool):
                    success = result
                    message = "" if result else f"Blocked by {hook.name}"
                    modified = None
                else:
                    success = True
                    message = str(result) if result else ""
                    modified = None

                hr = HookResult(
                    hook_name=hook.name,
                    phase=HookPhase.PRE,
                    success=success,
                    message=message,
                    modified_args=modified,
                    duration_ms=(time.time() - start) * 1000,
                )

            except Exception as exc:
                hr = HookResult(
                    hook_name=hook.name,
                    phase=HookPhase.PRE,
                    success=False,
                    message=f"Hook error: {exc}",
                    duration_ms=(time.time() - start) * 1000,
                )

            results.append(hr)
            self._history.append(hr)

            # Stop if a hook blocks
            if hr.blocked:
                break

        return results

    async def fire_post(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: str = "",
        success: bool = True,
    ) -> List[HookResult]:
        """Fire all POST hooks for a tool.

        POST hooks receive the tool's result and can react to it
        (format files, run tests, log, etc.)
        """
        results = []
        for hook in self._hooks:
            if hook.phase != HookPhase.POST or not hook.matches(tool_name):
                continue

            start = time.time()
            try:
                context = {
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                    "success": success,
                    "phase": "post",
                }
                hook_result = hook.action(context)
                if asyncio.iscoroutine(hook_result):
                    hook_result = await hook_result

                hr = HookResult(
                    hook_name=hook.name,
                    phase=HookPhase.POST,
                    success=True,
                    message=str(hook_result) if hook_result else "",
                    duration_ms=(time.time() - start) * 1000,
                )

            except Exception as exc:
                hr = HookResult(
                    hook_name=hook.name,
                    phase=HookPhase.POST,
                    success=False,
                    message=f"Hook error: {exc}",
                    duration_ms=(time.time() - start) * 1000,
                )

            results.append(hr)
            self._history.append(hr)

        return results

    def list_hooks(self) -> List[Dict[str, Any]]:
        """List all registered hooks."""
        return [
            {
                "name": h.name,
                "phase": h.phase.value,
                "tools": h.tools,
                "enabled": h.enabled,
                "priority": h.priority,
                "description": h.description,
            }
            for h in self._hooks
        ]

    @property
    def history(self) -> List[HookResult]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()


# ============================================================================
# Watchers
# ============================================================================

class WatchEventType(Enum):
    """Types of file system events."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class WatchEvent:
    """A detected file change event."""
    event_type: WatchEventType
    path: str                           # Relative to workspace
    timestamp: float = field(default_factory=time.time)
    old_hash: str = ""
    new_hash: str = ""


@dataclass
class Watcher:
    """A file watcher that monitors patterns and triggers callbacks.

    Patterns use glob syntax (e.g., "tests/**/*.py", "*.json").
    """
    name: str
    patterns: List[str]                 # Glob patterns to match
    on_change: Callable[[WatchEvent], Any]  # Callback
    enabled: bool = True
    debounce_ms: int = 500              # Minimum ms between triggers
    description: str = ""
    _last_trigger: float = 0.0

    def matches(self, path: str) -> bool:
        """Check if a path matches this watcher's patterns."""
        if not self.enabled:
            return False
        return any(fnmatch.fnmatch(path, p) for p in self.patterns)

    @property
    def can_trigger(self) -> bool:
        """Check debounce — enough time since last trigger?"""
        return (time.time() - self._last_trigger) * 1000 >= self.debounce_ms


class WatcherEngine:
    """Monitors workspace files and fires watchers on changes.

    Uses polling-based detection (no OS dependencies) — scans the
    workspace periodically and compares file hashes.
    """

    def __init__(self, workspace: str = "."):
        self.workspace = str(Path(workspace).resolve())
        self._watchers: List[Watcher] = []
        self._snapshots: Dict[str, str] = {}  # path → hash
        self._events: List[WatchEvent] = []
        self._running = False

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Quick hash of a file's content."""
        try:
            content = path.read_bytes()
            return hashlib.md5(content).hexdigest()[:12]
        except (OSError, PermissionError):
            return ""

    def register(self, watcher: Watcher) -> None:
        """Register a file watcher."""
        self._watchers.append(watcher)
        logger.info("Registered watcher: %s (patterns: %s)", watcher.name, watcher.patterns)

    def unregister(self, name: str) -> bool:
        """Unregister a watcher by name."""
        before = len(self._watchers)
        self._watchers = [w for w in self._watchers if w.name != name]
        return len(self._watchers) < before

    def scan(self) -> List[WatchEvent]:
        """Scan workspace for changes since last scan.

        Returns list of detected events.
        """
        events = []
        ws = Path(self.workspace)

        # Collect current file hashes
        current: Dict[str, str] = {}
        for path in ws.rglob("*"):
            if path.is_file():
                # Skip hidden dirs and common noise
                rel = str(path.relative_to(ws))
                parts = path.relative_to(ws).parts
                if any(p.startswith(".") for p in parts):
                    continue
                if any(p in ("node_modules", "__pycache__", ".git", "venv") for p in parts):
                    continue

                file_hash = self._hash_file(path)
                current[rel] = file_hash

        # Detect changes
        # New files
        for path, file_hash in current.items():
            if path not in self._snapshots:
                events.append(WatchEvent(
                    event_type=WatchEventType.CREATED,
                    path=path,
                    new_hash=file_hash,
                ))

        # Modified files
        for path, file_hash in current.items():
            if path in self._snapshots and self._snapshots[path] != file_hash:
                events.append(WatchEvent(
                    event_type=WatchEventType.MODIFIED,
                    path=path,
                    old_hash=self._snapshots[path],
                    new_hash=file_hash,
                ))

        # Deleted files
        for path in self._snapshots:
            if path not in current:
                events.append(WatchEvent(
                    event_type=WatchEventType.DELETED,
                    path=path,
                    old_hash=self._snapshots[path],
                ))

        # Update snapshots
        self._snapshots = current

        # Fire matching watchers
        for event in events:
            for watcher in self._watchers:
                if watcher.matches(event.path) and watcher.can_trigger:
                    try:
                        watcher.on_change(event)
                        watcher._last_trigger = time.time()
                    except Exception as exc:
                        logger.error("Watcher %s failed: %s", watcher.name, exc)

        self._events.extend(events)
        return events

    async def watch_loop(self, interval_seconds: float = 2.0) -> None:
        """Start a continuous watch loop (run in background).

        Scans every `interval_seconds` and fires watchers on changes.
        """
        self._running = True
        # Take initial snapshot
        self.scan()
        logger.info("Watcher loop started (interval: %.1fs)", interval_seconds)

        while self._running:
            await asyncio.sleep(interval_seconds)
            events = self.scan()
            if events:
                logger.info("Detected %d file changes", len(events))

    def stop(self) -> None:
        """Stop the watch loop."""
        self._running = False

    def take_snapshot(self) -> Dict[str, str]:
        """Take a snapshot of current file hashes (no change detection)."""
        ws = Path(self.workspace)
        snapshot: Dict[str, str] = {}
        for path in ws.rglob("*"):
            if path.is_file():
                rel = str(path.relative_to(ws))
                parts = path.relative_to(ws).parts
                if any(p.startswith(".") for p in parts):
                    continue
                if any(p in ("node_modules", "__pycache__", ".git", "venv") for p in parts):
                    continue
                snapshot[rel] = self._hash_file(path)
        self._snapshots = snapshot
        return snapshot

    def list_watchers(self) -> List[Dict[str, Any]]:
        """List all registered watchers."""
        return [
            {
                "name": w.name,
                "patterns": w.patterns,
                "enabled": w.enabled,
                "debounce_ms": w.debounce_ms,
                "description": w.description,
            }
            for w in self._watchers
        ]

    @property
    def recent_events(self) -> List[WatchEvent]:
        """Get recent events (last 50)."""
        return self._events[-50:]

    def clear_events(self) -> None:
        self._events.clear()
