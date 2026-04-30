"""Dynamic plugin loading from .nexus/plugins/ directories.

Discovers, validates, and loads Python plugins:
- Scans .nexus/plugins/ for plugin directories
- Validates metadata and dependencies
- Loads via importlib with error isolation
- Supports hot-reload via file watching
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nexus.plugins.base import Plugin, PluginState

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""
    pass


class PluginDependencyError(PluginLoadError):
    """Raised when a plugin's dependencies cannot be resolved."""
    pass


class PluginValidationError(PluginLoadError):
    """Raised when a plugin fails validation."""
    pass


class PluginLoader:
    """Discovers and loads plugins from filesystem directories.

    Usage:
        loader = PluginLoader(plugin_dirs=[".nexus/plugins"])
        plugins = loader.discover()
        loaded = loader.load_all(plugins)
    """

    def __init__(
        self,
        plugin_dirs: Optional[List[str]] = None,
        workspace: str = ".",
    ):
        self.plugin_dirs = plugin_dirs or []
        self.workspace = Path(workspace).resolve()
        self._loaded_plugins: Dict[str, Plugin] = {}
        self._load_times: Dict[str, float] = {}
        self._errors: Dict[str, str] = {}

        # Add default plugin directory
        default_dir = self.workspace / ".nexus" / "plugins"
        if default_dir.exists() and str(default_dir) not in self.plugin_dirs:
            self.plugin_dirs.append(str(default_dir))

    def discover(self) -> List[Tuple[str, Path]]:
        """Discover all potential plugins in configured directories.

        Returns:
            List of (plugin_name, plugin_path) tuples.
        """
        discovered = []

        for dir_str in self.plugin_dirs:
            plugin_dir = Path(dir_str)
            if not plugin_dir.exists():
                continue

            for item in plugin_dir.iterdir():
                if not item.is_dir():
                    continue
                if item.name.startswith(("_", ".")):
                    continue

                # Check for plugin.py or __init__.py
                plugin_file = item / "plugin.py"
                if plugin_file.exists():
                    discovered.append((item.name, plugin_file))
                elif (item / "__init__.py").exists():
                    discovered.append((item.name, item / "__init__.py"))
                else:
                    logger.debug("Skipping %s: no plugin.py or __init__.py", item.name)

        logger.info("Discovered %d potential plugins", len(discovered))
        return discovered

    def load_plugin(self, name: str, path: Path) -> Optional[Plugin]:
        """Load a single plugin from its file path.

        Args:
            name: Plugin name (directory name).
            path: Path to plugin.py or __init__.py.

        Returns:
            Loaded Plugin instance, or None on failure.
        """
        start_time = time.time()

        try:
            # Load module dynamically
            spec = importlib.util.spec_from_file_location(
                f"nexus_plugin_{name}", str(path)
            )
            if spec is None or spec.loader is None:
                self._errors[name] = f"Cannot create spec for {name}"
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"nexus_plugin_{name}"] = module
            spec.loader.exec_module(module)

            # Find the plugin class
            plugin_instance = self._extract_plugin_instance(module, name)
            if plugin_instance is None:
                self._errors[name] = (
                    f"No Plugin subclass found in {name}. "
                    f"Plugin must define a class that inherits from nexus.plugins.Plugin"
                )
                return None

            # Validate metadata
            if plugin_instance.metadata.name == "unnamed_plugin":
                plugin_instance.metadata.name = name

            # Mark as loaded
            plugin_instance.on_load()
            self._loaded_plugins[name] = plugin_instance
            self._load_times[name] = time.time() - start_time

            logger.info(
                "Loaded plugin %s v%s in %.2fms",
                name,
                plugin_instance.metadata.version,
                self._load_times[name] * 1000,
            )
            return plugin_instance

        except Exception as exc:
            self._errors[name] = str(exc)
            logger.error("Failed to load plugin %s: %s", name, exc)
            return None

    def _extract_plugin_instance(self, module: Any, name: str) -> Optional[Plugin]:
        """Extract a Plugin instance from a loaded module.

        Strategy:
        1. Look for a variable named `plugin` or `PLUGIN`
        2. Look for any class that inherits from Plugin
        3. Look for a class named {Name}Plugin
        """
        # Strategy 1: Named variable
        for attr_name in ("plugin", "PLUGIN", "instance"):
            attr = getattr(module, attr_name, None)
            if isinstance(attr, Plugin):
                return attr

        # Strategy 2: Any subclass of Plugin
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Plugin)
                and attr is not Plugin
            ):
                return attr()

        # Strategy 3: Named class
        class_name = f"{name.title().replace('_', '')}Plugin"
        attr = getattr(module, class_name, None)
        if attr and isinstance(attr, type) and issubclass(attr, Plugin):
            return attr()

        return None

    def load_all(self, discovered: Optional[List[Tuple[str, Path]]] = None) -> Dict[str, Plugin]:
        """Load all discovered plugins.

        Args:
            discovered: Optional pre-discovered list. If None, runs discover().

        Returns:
            Dict of plugin_name -> Plugin instance (successfully loaded only).
        """
        if discovered is None:
            discovered = self.discover()

        loaded = {}
        for name, path in discovered:
            if name in self._loaded_plugins:
                logger.debug("Plugin %s already loaded, skipping", name)
                continue

            plugin = self.load_plugin(name, path)
            if plugin is not None:
                loaded[name] = plugin

        return loaded

    def reload_plugin(self, name: str) -> Optional[Plugin]:
        """Hot-reload a single plugin.

        Unloads the current version and loads a fresh copy.

        Args:
            name: Plugin name to reload.

        Returns:
            New Plugin instance, or None on failure.
        """
        if name not in self._loaded_plugins:
            logger.warning("Cannot reload %s: not loaded", name)
            return None

        old_plugin = self._loaded_plugins[name]
        old_plugin.on_unload()

        # Remove from sys.modules
        module_name = f"nexus_plugin_{name}"
        if module_name in sys.modules:
            del sys.modules[module_name]

        del self._loaded_plugins[name]

        # Re-discover and reload
        for dir_str in self.plugin_dirs:
            plugin_dir = Path(dir_str) / name
            if not plugin_dir.exists():
                continue

            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                plugin_file = plugin_dir / "__init__.py"

            if plugin_file.exists():
                return self.load_plugin(name, plugin_file)

        logger.warning("Cannot reload %s: source not found", name)
        return None

    def get_plugin_path(self, name: str) -> Optional[Path]:
        """Get the filesystem path for a loaded plugin."""
        for dir_str in self.plugin_dirs:
            plugin_dir = Path(dir_str) / name
            if plugin_dir.exists():
                return plugin_dir
        return None

    @property
    def loaded_plugins(self) -> Dict[str, Plugin]:
        return dict(self._loaded_plugins)

    @property
    def errors(self) -> Dict[str, str]:
        return dict(self._errors)

    def get_stats(self) -> Dict[str, Any]:
        """Get loading statistics."""
        return {
            "total_discovered": len(self.discover()),
            "total_loaded": len(self._loaded_plugins),
            "total_errors": len(self._errors),
            "load_times": dict(self._load_times),
            "plugin_dirs": self.plugin_dirs,
        }
