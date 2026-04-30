"""Plugin hook system — extends the core HookEngine for plugin integration.

Provides a bridge between plugin-registered hooks and the core HookEngine:
- Event routing and filtering
- Hook chaining with priority ordering
- Error isolation (one plugin's hook failure doesn't break others)
- Async/sync hook support
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class HookEvent:
    """Data passed to hook callbacks."""
    event_name: str
    data: Dict[str, Any]
    source: str = ""  # Plugin name that triggered
    result: Any = None
    cancelled: bool = False

    def cancel(self, reason: str = "") -> None:
        """Cancel the event (prevent further processing)."""
        self.cancelled = True
        if reason:
            self.data["cancel_reason"] = reason


@dataclass
class HookRegistration:
    """Internal hook registration info."""
    plugin_name: str
    event: str
    callback: Callable[..., Any]
    priority: int
    is_async: bool


class PluginHookEngine:
    """Manages hooks registered by plugins.

    Integrates with the core HookEngine to provide plugin-safe
    event handling. Plugins can hook into Nexus events without
    direct access to internal state.

    Events available to plugins:
    - pre_tool_call: Before any tool executes
    - post_tool_call: After tool execution (with result)
    - pre_llm_call: Before LLM request
    - post_llm_call: After LLM response
    - on_session_start: When a new session begins
    - on_session_end: When a session ends
    - on_goal_complete: When an autonomous goal finishes
    - on_error: When an error occurs anywhere
    - on_message_received: When user sends a message
    - on_message_sent: When assistant sends a response
    """

    def __init__(self):
        self._hooks: List[HookRegistration] = []
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 100

    def register(
        self,
        plugin_name: str,
        event: str,
        callback: Callable[..., Any],
        priority: int = 50,
    ) -> None:
        """Register a plugin hook.

        Args:
            plugin_name: Name of the registering plugin.
            event: Event name to hook into.
            callback: Function(event: HookEvent) -> Any.
            priority: Lower = earlier execution (0-100).
        """
        is_async = inspect.iscoroutinefunction(callback)
        self._hooks.append(HookRegistration(
            plugin_name=plugin_name,
            event=event,
            callback=callback,
            priority=priority,
            is_async=is_async,
        ))
        logger.debug(
            "Plugin %s registered hook: %s (priority %d, async=%s)",
            plugin_name, event, priority, is_async,
        )

    def register_from_api(
        self,
        plugin_name: str,
        event: str,
        callback: Callable[..., Any],
        priority: int = 50,
    ) -> None:
        """Register a hook via the NexusAPI interface."""
        self.register(plugin_name, event, callback, priority)

    async def fire(
        self,
        event_name: str,
        data: Optional[Dict[str, Any]] = None,
        source: str = "core",
    ) -> HookEvent:
        """Fire an event and execute all registered hooks.

        Hooks execute in priority order (lowest first).
        If any hook cancels the event, remaining hooks are skipped.

        Args:
            event_name: Event name.
            data: Event data dict.
            source: Source of the event.

        Returns:
            HookEvent with final state.
        """
        event = HookEvent(
            event_name=event_name,
            data=data or {},
            source=source,
        )

        # Get matching hooks sorted by priority
        matching_hooks = [
            h for h in self._hooks if h.event == event_name
        ]
        matching_hooks.sort(key=lambda h: h.priority)

        for hook in matching_hooks:
            if event.cancelled:
                logger.debug(
                    "Event %s cancelled, skipping hook from %s",
                    event_name, hook.plugin_name,
                )
                break

            try:
                if hook.is_async:
                    result = await hook.callback(event)
                else:
                    result = hook.callback(event)

                if result is not None:
                    event.result = result

            except Exception as exc:
                logger.error(
                    "Hook error in plugin %s for event %s: %s",
                    hook.plugin_name, event_name, exc,
                )
                event.data.setdefault("hook_errors", []).append({
                    "plugin": hook.plugin_name,
                    "error": str(exc),
                })

        # Record in history
        self._record_event(event)

        return event

    def get_hooks_for_event(self, event_name: str) -> List[Dict[str, Any]]:
        """Get all hooks registered for a specific event."""
        return [
            {
                "plugin": h.plugin_name,
                "priority": h.priority,
                "async": h.is_async,
            }
            for h in self._hooks
            if h.event == event_name
        ]

    def get_registered_events(self) -> Set[str]:
        """Get all event names that have registered hooks."""
        return {h.event for h in self._hooks}

    def clear_plugin_hooks(self, plugin_name: str) -> int:
        """Remove all hooks registered by a plugin.

        Args:
            plugin_name: Plugin whose hooks to remove.

        Returns:
            Number of hooks removed.
        """
        before = len(self._hooks)
        self._hooks = [h for h in self._hooks if h.plugin_name != plugin_name]
        removed = before - len(self._hooks)
        logger.info("Removed %d hooks for plugin %s", removed, plugin_name)
        return removed

    def _record_event(self, event: HookEvent) -> None:
        """Record event in history (bounded)."""
        self._event_history.append({
            "event": event.event_name,
            "source": event.source,
            "cancelled": event.cancelled,
            "timestamp": __import__("time").time(),
        })
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

    @property
    def total_hooks(self) -> int:
        return len(self._hooks)

    def get_stats(self) -> Dict[str, Any]:
        """Get hook engine statistics."""
        events = {}
        for h in self._hooks:
            events.setdefault(h.event, []).append(h.plugin_name)

        return {
            "total_hooks": self.total_hooks,
            "events": {event: len(plugins) for event, plugins in events.items()},
            "event_history_size": len(self._event_history),
            "unique_plugins": len(set(h.plugin_name for h in self._hooks)),
        }
