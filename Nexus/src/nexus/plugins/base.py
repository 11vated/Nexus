"""Plugin base classes and NexusAPI interface.

Every plugin must inherit from Plugin and implement register().
The NexusAPI gives plugins safe access to Nexus internals.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class PluginState(Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginMetadata:
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    license: str = "MIT"
    min_nexus_version: str = "0.1.0"
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    homepage: str = ""


class NexusAPI:
    """Safe interface exposed to plugins.

    Plugins receive an instance of this to register components,
    access memory, execute tools, and interact with the agent system.
    They do NOT get direct access to internal state.
    """

    def __init__(self, nexus_instance: Optional[Any] = None):
        self._nexus = nexus_instance
        self._registered_tools: Dict[str, Any] = {}
        self._registered_hooks: List[Dict[str, Any]] = []
        self._registered_stances: List[Dict[str, Any]] = []
        self._registered_commands: List[Dict[str, Any]] = []
        self._registered_panels: List[Dict[str, Any]] = []

    # -- Tool Registration ------------------------------------------------

    def register_tool(self, name: str, tool_class: Type[Any], description: str = "") -> None:
        """Register a new tool that the agent can use.

        Args:
            name: Tool name (must be unique).
            tool_class: Class implementing execute(**args) -> str.
            description: Human-readable description.
        """
        self._registered_tools[name] = {
            "class": tool_class,
            "description": description,
        }
        logger.info("Plugin registered tool: %s", name)

    def get_registered_tools(self) -> Dict[str, Any]:
        return dict(self._registered_tools)

    # -- Hook Registration ------------------------------------------------

    def register_hook(
        self,
        event: str,
        callback: Callable[..., Any],
        priority: int = 50,
    ) -> None:
        """Register a hook that fires on specific events.

        Events: "pre_tool_call", "post_tool_call", "pre_llm_call",
                "post_llm_call", "on_session_start", "on_session_end",
                "on_goal_complete", "on_error"

        Args:
            event: Event name to hook into.
            callback: Async or sync function(event_data) -> result.
            priority: Lower = earlier execution (0-100).
        """
        self._registered_hooks.append({
            "event": event,
            "callback": callback,
            "priority": priority,
        })
        logger.info("Plugin registered hook: %s (priority %d)", event, priority)

    def get_registered_hooks(self) -> List[Dict[str, Any]]:
        return list(self._registered_hooks)

    # -- Stance Registration ----------------------------------------------

    def register_stance(
        self,
        name: str,
        system_prompt_modifier: str,
        model_override: Optional[str] = None,
        temperature_override: Optional[float] = None,
    ) -> None:
        """Register a new conversation stance.

        Args:
            name: Stance identifier (e.g., "security_auditor").
            system_prompt_modifier: Text appended to system prompt.
            model_override: Optional model to use when this stance is active.
            temperature_override: Optional temperature override.
        """
        self._registered_stances.append({
            "name": name,
            "system_prompt_modifier": system_prompt_modifier,
            "model_override": model_override,
            "temperature_override": temperature_override,
        })
        logger.info("Plugin registered stance: %s", name)

    def get_registered_stances(self) -> List[Dict[str, Any]]:
        return list(self._registered_stances)

    # -- CLI Command Registration -----------------------------------------

    def register_command(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
        aliases: Optional[List[str]] = None,
    ) -> None:
        """Register a CLI/TUI command available to the user.

        Args:
            name: Command name (e.g., "analyze").
            handler: Function(name, args) -> str response.
            description: Help text.
            aliases: Alternative command names.
        """
        self._registered_commands.append({
            "name": name,
            "handler": handler,
            "description": description,
            "aliases": aliases or [],
        })
        logger.info("Plugin registered command: %s", name)

    def get_registered_commands(self) -> List[Dict[str, Any]]:
        return list(self._registered_commands)

    # -- UI Panel Registration --------------------------------------------

    def register_panel(
        self,
        name: str,
        title: str,
        renderer: Callable[..., str],
        position: str = "bottom",
    ) -> None:
        """Register a TUI dashboard panel.

        Args:
            name: Panel identifier.
            title: Display title.
            renderer: Function() -> str content.
            position: "top", "bottom", "left", "right".
        """
        self._registered_panels.append({
            "name": name,
            "title": title,
            "renderer": renderer,
            "position": position,
        })
        logger.info("Plugin registered panel: %s", name)

    def get_registered_panels(self) -> List[Dict[str, Any]]:
        return list(self._registered_panels)

    # -- Accessor Methods (read-only) -------------------------------------

    def get_workspace(self) -> str:
        """Get the current workspace path."""
        if self._nexus and hasattr(self._nexus, "workspace"):
            return self._nexus.workspace
        return "."

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        if self._nexus and hasattr(self._nexus, "config"):
            return getattr(self._nexus.config, key, default)
        return default

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a registered tool by name."""
        if self._nexus and hasattr(self._nexus, "executor"):
            return await self._nexus.executor.execute_step({
                "action": f"Execute {tool_name}",
                "tool": tool_name,
                "args": kwargs,
            })
        raise RuntimeError("Executor not available")

    def get_memory(self) -> Optional[Any]:
        """Get access to memory systems (read-only)."""
        if self._nexus:
            if hasattr(self._nexus, "long_term"):
                return self._nexus.long_term
            if hasattr(self._nexus, "memory"):
                return self._nexus.memory
        return None


class Plugin(ABC):
    """Base class for all Nexus plugins.

    Every plugin must:
    1. Inherit from Plugin
    2. Implement register(api: NexusAPI)
    3. Optionally implement lifecycle methods (on_enable, on_disable, etc.)
    """

    metadata = PluginMetadata(name="unnamed_plugin")

    def __init__(self):
        self._state = PluginState.DISCOVERED
        self._api: Optional[NexusAPI] = None

    @property
    def state(self) -> PluginState:
        return self._state

    @abstractmethod
    def register(self, api: NexusAPI) -> None:
        """Register plugin components with Nexus.

        This is the main entry point. Use the api to register tools,
        hooks, stances, commands, and panels.

        Args:
            api: NexusAPI instance for safe registration.
        """
        raise NotImplementedError

    # -- Lifecycle Hooks (override as needed) -----------------------------

    def on_enable(self) -> None:
        """Called when the plugin is enabled."""
        self._state = PluginState.ENABLED
        logger.info("Plugin enabled: %s", self.metadata.name)

    def on_disable(self) -> None:
        """Called when the plugin is disabled."""
        self._state = PluginState.DISABLED
        logger.info("Plugin disabled: %s", self.metadata.name)

    def on_load(self) -> None:
        """Called after successful loading."""
        self._state = PluginState.LOADED
        logger.info("Plugin loaded: %s", self.metadata.name)

    def on_unload(self) -> None:
        """Called when the plugin is being unloaded."""
        self._state = PluginState.DISCOVERED
        logger.info("Plugin unloaded: %s", self.metadata.name)

    def on_error(self, error: Exception) -> None:
        """Called when an error occurs in the plugin."""
        self._state = PluginState.ERROR
        logger.error("Plugin error: %s — %s", self.metadata.name, error)

    def __repr__(self) -> str:
        return (
            f"<Plugin {self.metadata.name} v{self.metadata.version} "
            f"state={self._state.value}>"
        )
