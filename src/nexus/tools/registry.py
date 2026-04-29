"""Tool registry and base tool class.

All tools inherit from BaseTool and are registered with the ToolRegistry.
The registry provides tool discovery and LLM-formatted descriptions.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Base class for all Nexus tools.

    Each tool must define:
    - name: Unique identifier used by the LLM
    - description: What the tool does (shown to LLM)
    - schema: Parameter schema (shown to LLM)
    - execute(): The actual implementation
    """

    name: str = "base"
    description: str = "Base tool"
    aliases: List[str] = []
    schema: Dict[str, str] = {}

    def __init__(self, workspace: str = "."):
        self.workspace = workspace

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool with given arguments.

        Returns:
            String result of the tool execution.
        """
        ...

    def to_prompt_description(self) -> str:
        """Format tool for inclusion in LLM system prompt."""
        parts = [f"- {self.name}: {self.description}"]
        if self.schema:
            for param, desc in self.schema.items():
                parts.append(f"    {param}: {desc}")
        return "\n".join(parts)


class ToolRegistry:
    """Registry for tool discovery and management.

    Tools are registered by name and can be retrieved for use by the
    executor, or formatted as descriptions for the LLM planner.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool
        for alias in tool.aliases:
            self._tools[alias] = tool
        logger.debug("Registered tool: %s", tool.name)

    def register_class(self, tool_class: Type[BaseTool], **kwargs: Any) -> None:
        """Register a tool by class (instantiates it)."""
        tool = tool_class(**kwargs)
        self.register(tool)

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name or alias."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names (excluding aliases)."""
        seen = set()
        names = []
        for name, tool in self._tools.items():
            if id(tool) not in seen:
                seen.add(id(tool))
                names.append(tool.name)
        return names

    def as_dict(self) -> Dict[str, BaseTool]:
        """Get tools as a dict (for executor.register_tools)."""
        seen = set()
        result = {}
        for name, tool in self._tools.items():
            if id(tool) not in seen:
                seen.add(id(tool))
                result[tool.name] = tool
        return result

    def get_prompt_descriptions(self) -> str:
        """Get all tool descriptions formatted for LLM system prompt."""
        seen = set()
        descriptions = []
        for tool in self._tools.values():
            if id(tool) not in seen:
                seen.add(id(tool))
                descriptions.append(tool.to_prompt_description())
        return "\n".join(descriptions)
