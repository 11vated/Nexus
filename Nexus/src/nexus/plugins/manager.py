"""Plugin Manager — lifecycle, dependencies, and state management.

Manages the full plugin lifecycle:
- Dependency resolution with topological sort
- Enable/disable with cascading effects
- Health monitoring and error recovery
- Configuration persistence
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from nexus.plugins.base import NexusAPI, Plugin, PluginState
from nexus.plugins.loader import PluginLoader, PluginDependencyError, PluginLoadError

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages plugin lifecycle, dependencies, and integration with Nexus.

    Usage:
        manager = PluginManager(workspace="/path/to/project")
        manager.initialize(nexus_instance)
        manager.enable_plugin("code_analyzer")
    """

    def __init__(
        self,
        workspace: str = ".",
        plugin_dirs: Optional[List[str]] = None,
        state_file: Optional[str] = None,
    ):
        self.workspace = Path(workspace).resolve()
        self.loader = PluginLoader(plugin_dirs=plugin_dirs, workspace=workspace)
        self._nexus: Optional[Any] = None
        self._api: Optional[NexusAPI] = None
        self._state_file = Path(state_file) if state_file else self.workspace / ".nexus" / "plugins" / ".plugin_state.json"
        self._enabled_plugins: Set[str] = set()
        self._plugin_registry: Dict[str, Plugin] = {}
        self._dependency_graph: Dict[str, List[str]] = {}

    def initialize(self, nexus_instance: Any) -> None:
        """Initialize the plugin manager with a Nexus instance.

        Discovers and loads all plugins, then enables previously
        enabled ones (from persistent state).

        Args:
            nexus_instance: The Nexus ChatSession or AgentLoop instance.
        """
        self._nexus = nexus_instance
        self._api = NexusAPI(nexus_instance)

        # Load saved state
        self._load_state()

        # Discover and load all plugins
        discovered = self.loader.discover()
        loaded = self.loader.load_all(discovered)

        self._plugin_registry.update(loaded)
        self._build_dependency_graph()

        # Enable previously enabled plugins
        for name in list(self._enabled_plugins):
            if name in self._plugin_registry:
                try:
                    self._enable_plugin(name)
                except Exception as exc:
                    logger.error("Failed to enable plugin %s: %s", name, exc)
                    self._enabled_plugins.discard(name)

        logger.info(
            "Plugin manager initialized: %d loaded, %d enabled",
            len(self._plugin_registry),
            len(self._enabled_plugins),
        )

    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all discovered plugins with their state."""
        result = []
        for name, plugin in self._plugin_registry.items():
            result.append({
                "name": name,
                "version": plugin.metadata.version,
                "description": plugin.metadata.description,
                "author": plugin.metadata.author,
                "state": plugin.state.value,
                "enabled": name in self._enabled_plugins,
                "dependencies": plugin.metadata.dependencies,
                "tags": plugin.metadata.tags,
            })
        return result

    def enable_plugin(self, name: str) -> Dict[str, Any]:
        """Enable a plugin and its dependencies.

        Args:
            name: Plugin name to enable.

        Returns:
            Dict with success status and details.
        """
        if name not in self._plugin_registry:
            return {"success": False, "error": f"Plugin '{name}' not found"}

        if name in self._enabled_plugins:
            return {"success": False, "error": f"Plugin '{name}' is already enabled"}

        # Check dependencies
        deps = self._dependency_graph.get(name, [])
        missing_deps = [d for d in deps if d not in self._enabled_plugins]
        if missing_deps:
            # Auto-enable dependencies
            for dep in missing_deps:
                if dep in self._plugin_registry:
                    self.enable_plugin(dep)
                else:
                    return {
                        "success": False,
                        "error": f"Missing dependency '{dep}' for plugin '{name}'",
                    }

        try:
            self._enable_plugin(name)
            self._enabled_plugins.add(name)
            self._save_state()

            plugin = self._plugin_registry[name]
            return {
                "success": True,
                "plugin": name,
                "version": plugin.metadata.version,
                "tools_registered": len(plugin._api.get_registered_tools()) if plugin._api else 0,
                "hooks_registered": len(plugin._api.get_registered_hooks()) if plugin._api else 0,
                "stances_registered": len(plugin._api.get_registered_stances()) if plugin._api else 0,
            }
        except Exception as exc:
            logger.error("Failed to enable plugin %s: %s", name, exc)
            return {"success": False, "error": str(exc)}

    def _enable_plugin(self, name: str) -> None:
        """Internal: enable a single plugin and register its components."""
        plugin = self._plugin_registry[name]

        # Create fresh API instance for this plugin
        plugin._api = NexusAPI(self._nexus)

        # Call register
        plugin.register(plugin._api)

        # Call on_enable lifecycle hook
        plugin.on_enable()

        # Register components with Nexus
        self._register_plugin_components(name, plugin)

        logger.info("Plugin enabled and registered: %s", name)

    def disable_plugin(self, name: str) -> Dict[str, Any]:
        """Disable a plugin and any plugins that depend on it.

        Args:
            name: Plugin name to disable.

        Returns:
            Dict with success status and details.
        """
        if name not in self._plugin_registry:
            return {"success": False, "error": f"Plugin '{name}' not found"}

        if name not in self._enabled_plugins:
            return {"success": False, "error": f"Plugin '{name}' is not enabled"}

        # Find dependents
        dependents = self._get_dependents(name)
        disabled = [name]

        # Disable dependents first (reverse order)
        for dep in reversed(dependents):
            if dep in self._enabled_plugins:
                self._disable_plugin(dep)
                self._enabled_plugins.discard(dep)
                disabled.append(dep)

        # Disable the target plugin
        self._disable_plugin(name)
        self._enabled_plugins.discard(name)
        self._save_state()

        return {
            "success": True,
            "disabled": disabled,
        }

    def _disable_plugin(self, name: str) -> None:
        """Internal: disable a single plugin and unregister its components."""
        plugin = self._plugin_registry[name]

        # Call on_disable lifecycle hook
        plugin.on_disable()

        # Unregister components from Nexus
        self._unregister_plugin_components(name)

        logger.info("Plugin disabled: %s", name)

    def reload_plugin(self, name: str) -> Dict[str, Any]:
        """Hot-reload a plugin.

        Args:
            name: Plugin name to reload.

        Returns:
            Dict with success status.
        """
        was_enabled = name in self._enabled_plugins

        if was_enabled:
            self.disable_plugin(name)

        # Reload via loader
        new_plugin = self.loader.reload_plugin(name)
        if new_plugin is None:
            return {"success": False, "error": f"Failed to reload '{name}'"}

        self._plugin_registry[name] = new_plugin

        if was_enabled:
            return self.enable_plugin(name)

        return {"success": True, "plugin": name, "reloaded": True}

    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about a specific plugin."""
        if name not in self._plugin_registry:
            return None

        plugin = self._plugin_registry[name]
        return {
            "name": plugin.metadata.name,
            "version": plugin.metadata.version,
            "description": plugin.metadata.description,
            "author": plugin.metadata.author,
            "license": plugin.metadata.license,
            "min_nexus_version": plugin.metadata.min_nexus_version,
            "dependencies": plugin.metadata.dependencies,
            "tags": plugin.metadata.tags,
            "homepage": plugin.metadata.homepage,
            "state": plugin.state.value,
            "enabled": name in self._enabled_plugins,
            "tools": list(plugin._api.get_registered_tools().keys()) if plugin._api else [],
            "hooks": [h["event"] for h in plugin._api.get_registered_hooks()] if plugin._api else [],
            "stances": [s["name"] for s in plugin._api.get_registered_stances()] if plugin._api else [],
            "commands": [c["name"] for c in plugin._api.get_registered_commands()] if plugin._api else [],
        }

    def get_enabled_components(self) -> Dict[str, Any]:
        """Get all components registered by enabled plugins."""
        tools = {}
        hooks = []
        stances = []
        commands = []
        panels = []

        for name in self._enabled_plugins:
            plugin = self._plugin_registry[name]
            if plugin._api:
                tools.update(plugin._api.get_registered_tools())
                hooks.extend(plugin._api.get_registered_hooks())
                stances.extend(plugin._api.get_registered_stances())
                commands.extend(plugin._api.get_registered_commands())
                panels.extend(plugin._api.get_registered_panels())

        return {
            "tools": tools,
            "hooks": hooks,
            "stances": stances,
            "commands": commands,
            "panels": panels,
        }

    # -- Internal Helpers -------------------------------------------------

    def _build_dependency_graph(self) -> None:
        """Build a dependency graph from plugin metadata."""
        self._dependency_graph = {}
        for name, plugin in self._plugin_registry.items():
            self._dependency_graph[name] = list(plugin.metadata.dependencies)

    def _get_dependents(self, name: str) -> List[str]:
        """Find all plugins that depend on the given plugin."""
        dependents = []
        for plugin_name, deps in self._dependency_graph.items():
            if name in deps:
                dependents.append(plugin_name)
        return dependents

    def _register_plugin_components(self, name: str, plugin: Plugin) -> None:
        """Register plugin's components with the Nexus instance."""
        if self._nexus is None or plugin._api is None:
            return

        # Register tools with executor
        if hasattr(self._nexus, "executor"):
            for tool_name, tool_info in plugin._api.get_registered_tools().items():
                tool_class = tool_info["class"]
                self._nexus.executor.register_tool(tool_name, tool_class())

        # Register hooks with hook engine
        if hasattr(self._nexus, "_hooks") and self._nexus._hooks:
            for hook in plugin._api.get_registered_hooks():
                self._nexus._hooks.register(
                    event=hook["event"],
                    callback=hook["callback"],
                    priority=hook["priority"],
                )

        # Register stances with stance manager
        if hasattr(self._nexus, "_stances") and self._nexus._stances:
            for stance in plugin._api.get_registered_stances():
                # Add to stance registry
                pass  # StanceManager needs a register method

    def _unregister_plugin_components(self, name: str) -> None:
        """Unregister plugin's components from the Nexus instance."""
        if self._nexus is None:
            return

        plugin = self._plugin_registry.get(name)
        if plugin is None or plugin._api is None:
            return

        # Remove tools from executor
        if hasattr(self._nexus, "executor"):
            for tool_name in plugin._api.get_registered_tools():
                if tool_name in self._nexus.executor._tools:
                    del self._nexus.executor._tools[tool_name]

    def _save_state(self) -> None:
        """Persist enabled plugins to disk."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(
                json.dumps({"enabled": list(self._enabled_plugins)}, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to save plugin state: %s", exc)

    def _load_state(self) -> None:
        """Load enabled plugins from disk."""
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                self._enabled_plugins = set(data.get("enabled", []))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load plugin state: %s", exc)
                self._enabled_plugins = set()

    @property
    def enabled_count(self) -> int:
        return len(self._enabled_plugins)

    @property
    def total_count(self) -> int:
        return len(self._plugin_registry)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive plugin statistics."""
        return {
            "total_plugins": self.total_count,
            "enabled_plugins": self.enabled_count,
            "disabled_plugins": self.total_count - self.enabled_count,
            "loader_stats": self.loader.get_stats(),
            "enabled_list": list(self._enabled_plugins),
        }
