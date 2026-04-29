"""Hooks & Watchers — the reactive nervous system of Nexus.

Hooks run automatically before/after tool executions.
Watchers monitor files and trigger actions on changes.

This is what makes Nexus feel alive — it reacts to your project.
"""

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

__all__ = [
    "Hook",
    "HookEngine",
    "HookPhase",
    "HookResult",
    "Watcher",
    "WatcherEngine",
    "WatchEvent",
    "WatchEventType",
]
