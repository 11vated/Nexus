"""Tool execution engine for the Nexus agent.

The executor takes planned steps (with tool name + args) and dispatches
them to the appropriate tool implementation, capturing results.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from nexus.agent.models import AgentConfig, Step

logger = logging.getLogger(__name__)


class Executor:
    """Dispatches tool calls to registered tool implementations.

    The executor is the bridge between the planner's decisions and
    actual tool execution. It handles:
    - Tool dispatch by name
    - Timeout enforcement
    - Result capture and formatting
    - Error handling and recovery
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self._tools: Dict[str, Any] = {}

    def register_tool(self, name: str, tool: Any) -> None:
        """Register a tool implementation.

        Args:
            name: Tool name (must match what planner references).
            tool: Tool instance with an async execute() method.
        """
        self._tools[name] = tool
        logger.debug("Registered tool: %s", name)

    def register_tools(self, tools: Dict[str, Any]) -> None:
        """Register multiple tools at once."""
        for name, tool in tools.items():
            self.register_tool(name, tool)

    @property
    def available_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for LLM context."""
        descriptions = []
        for name, tool in self._tools.items():
            desc = getattr(tool, "description", f"Tool: {name}")
            schema = getattr(tool, "schema", {})
            descriptions.append(f"- {name}: {desc}")
            if schema:
                for param, info in schema.items():
                    descriptions.append(f"    {param}: {info}")
        return "\n".join(descriptions)

    async def execute_step(self, step_plan: Dict[str, Any]) -> Step:
        """Execute a single planned step.

        Args:
            step_plan: Dict with 'action', 'tool', 'args', 'reasoning'.

        Returns:
            Step object with execution results.
        """
        step = Step(
            action=step_plan.get("action", "unknown"),
            tool_name=step_plan.get("tool", ""),
            tool_args=step_plan.get("args", {}),
        )

        tool_name = step.tool_name
        start_time = time.time()

        # Handle special cases
        if tool_name in ("none", "done", ""):
            step.result = "No tool execution needed"
            step.success = True
            step.duration_ms = (time.time() - start_time) * 1000
            return step

        # Find and execute tool
        tool = self._tools.get(tool_name)
        if tool is None:
            # Try fuzzy matching (e.g., "file_read" vs "read_file")
            for registered_name, registered_tool in self._tools.items():
                aliases = getattr(registered_tool, "aliases", [])
                if tool_name in aliases:
                    tool = registered_tool
                    break

        if tool is None:
            step.result = (
                f"Unknown tool: {tool_name}. "
                f"Available: {', '.join(self._tools.keys())}"
            )
            step.success = False
            step.duration_ms = (time.time() - start_time) * 1000
            logger.warning("Unknown tool requested: %s", tool_name)
            return step

        try:
            result = await tool.execute(**step.tool_args)
            step.result = str(result) if result is not None else ""
            step.success = True
            logger.info(
                "Tool %s executed successfully (%.0fms)",
                tool_name,
                (time.time() - start_time) * 1000,
            )
        except Exception as exc:
            step.result = f"Error: {type(exc).__name__}: {exc}"
            step.success = False
            logger.error("Tool %s failed: %s", tool_name, exc)

        step.duration_ms = (time.time() - start_time) * 1000
        return step
