"""Nexus Plugin System.

Extensible plugin architecture for Nexus:
- Dynamic loading from .nexus/plugins/
- Hot-reload support
- Plugin API for tools, hooks, stances, and UI
- Dependency resolution and lifecycle management
"""

from nexus.plugins.base import Plugin, NexusAPI
from nexus.plugins.loader import PluginLoader
from nexus.plugins.manager import PluginManager

__all__ = ["Plugin", "NexusAPI", "PluginLoader", "PluginManager"]
