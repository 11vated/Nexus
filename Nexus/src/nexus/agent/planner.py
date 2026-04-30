"""LLM-based planning for the Nexus agent.

Replaces the keyword-matching planner with actual LLM reasoning.
The planner takes a goal and current context, and produces a structured
list of tasks for the executor.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from nexus.agent.llm import OllamaClient, extract_json
from nexus.agent.models import AgentConfig, AgentRole, Step, Task

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You are Nexus, an autonomous coding agent that plans and executes software tasks.

You receive a goal and must break it into concrete, actionable steps.
Each step should be something you can execute with your available tools.

Available tools:
{tool_descriptions}

Rules:
1. Break complex goals into small, testable steps
2. Always verify your work (run code, check output, run tests)
3. If something fails, diagnose and fix rather than moving on
4. Prefer simple, working code over clever, complex code
5. Create tests when building new functionality

CRITICAL: The "action" field must contain a SPECIFIC, ACTIONABLE description of what to do.
NEVER use placeholder text like "description", "step description", or "describe action here".
Example: "action": "Create app.py with Flask application and /health endpoint"

Respond with a JSON array of steps. Each step has:
{{
  "action": "SPECIFIC actionable description of what to do (NEVER use generic placeholder text)",
  "tool": "tool_name",
  "args": {{"arg1": "value1"}},
  "reasoning": "why this step"
}}
"""

# Fallback if no tool descriptions provided
DEFAULT_TOOL_DESCRIPTIONS = """\
- shell: Run shell commands (install packages, check files, run builds)
    command (str): The shell command to execute
- file_read: Read a file's contents
    path (str): Path to the file to read
- file_write: Write content to a file (creates directories if needed)
    path (str): Path to write to
    content (str): File content
- file_list: List files in a directory
    path (str): Directory path
- code_run: Execute a Python/JS/etc script and capture output
    code (str): Code to execute
    language (str): python, node, or bash
- test_run: Run pytest/npm test and get results
    command (str): Test command (e.g. "pytest tests/")
- search: Search codebase with grep/ripgrep
    pattern (str): Search pattern
    path (str): Directory to search
- git: Git operations (status, diff, add, commit)
    command (str): Git subcommand (status, diff, add, commit, log)"""

REPLAN_PROMPT = """\
The previous step had an issue. Based on the execution history below, \
decide what to do next.

Goal: {goal}

Execution history:
{history}

Last step result: {last_result}
Success: {success}

CRITICAL: The "action" field must contain a SPECIFIC, ACTIONABLE description.
NEVER use placeholder text like "description" or generic terms.

What should the next step be? Respond with a single step as JSON:
{{
  "action": "SPECIFIC actionable description (NEVER use generic placeholder text)",
  "tool": "tool_name",
  "args": {{}},
  "reasoning": "why"
}}

If the goal is complete, respond with:
{{"action": "done", "tool": "none", "args": {{}}, "reasoning": "goal achieved because..."}}
"""


class Planner:
    """Plans task execution using LLM reasoning.

    The planner operates in two modes:
    1. Initial planning: Break a goal into a sequence of steps
    2. Adaptive replanning: Decide next step based on execution history
    """

    def __init__(
        self,
        llm: OllamaClient,
        config: Optional[AgentConfig] = None,
    ):
        self.llm = llm
        self.config = config or AgentConfig()

    def _build_system_prompt(self, tool_descriptions: str = "") -> str:
        """Build the system prompt with dynamic tool descriptions."""
        tools = tool_descriptions or DEFAULT_TOOL_DESCRIPTIONS
        return SYSTEM_PROMPT_TEMPLATE.format(tool_descriptions=tools)

    def _validate_plan(self, plan: List[Dict[str, Any]], goal: str) -> List[Dict[str, Any]]:
        """Validate and fix steps with generic placeholder text in action field."""
        generic_actions = {"description", "step description", "describe action here",
                          "action description", "description of what to do"}
        for i, step in enumerate(plan):
            if not isinstance(step, dict):
                continue
            action = step.get("action", "").strip().lower()
            if action in generic_actions or not action:
                # Generate a meaningful action from the goal and step index
                step["action"] = f"Step {i+1}: Work on {goal[:60]}"
                logger.warning("Fixed generic action in step %d", i)
        return plan

    async def create_plan(
        self,
        goal: str,
        context: str = "",
        workspace_info: str = "",
        tool_descriptions: str = "",
    ) -> List[Dict[str, Any]]:
        """Create an initial execution plan for a goal.

        Args:
            goal: The high-level goal to accomplish.
            context: Additional context (file contents, prior work, etc).
            workspace_info: Description of current workspace state.
            tool_descriptions: Formatted tool descriptions from the registry.

        Returns:
            List of step dicts with action, tool, args, reasoning.
        """
        prompt = f"Goal: {goal}\n"
        if workspace_info:
            prompt += f"\nWorkspace:\n{workspace_info}\n"
        if context:
            prompt += f"\nContext:\n{context}\n"
        prompt += (
            "\nCreate a step-by-step plan to accomplish this goal. "
            "Respond with a JSON array of steps."
        )

        system_prompt = self._build_system_prompt(tool_descriptions)

        response = await self.llm.generate(
            prompt=prompt,
            model=self.config.planning_model,
            system=system_prompt,
            temperature=0.3,
        )

        plan = extract_json(response)
        if isinstance(plan, list):
            # Validate and fix any steps with generic placeholder text
            plan = self._validate_plan(plan, goal)
            logger.info("Created plan with %d steps", len(plan))
            return plan

        # If we got a single step dict, wrap it
        if isinstance(plan, dict):
            plan = self._validate_plan([plan], goal)
            return plan

        # Fallback: couldn't parse plan, create a single exploratory step
        logger.warning("Could not parse plan from LLM response, using fallback")
        return [
            {
                "action": f"Explore and work on: {goal}",
                "tool": "shell",
                "args": {"command": "ls -la"},
                "reasoning": "Starting by exploring the workspace",
            }
        ]

    async def next_step(
        self,
        goal: str,
        history: List[Step],
        last_result: str = "",
        success: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Decide the next step based on execution history.

        This is called after each step execution to adaptively plan.

        Args:
            goal: The original goal.
            history: Execution history (completed steps).
            last_result: Output from the last executed step.
            success: Whether the last step succeeded.

        Returns:
            Next step dict, or None if the goal is complete.
        """
        history_str = "\n".join(
            step.to_context() for step in history[-10:]  # Last 10 steps for context
        )

        prompt = REPLAN_PROMPT.format(
            goal=goal,
            history=history_str,
            last_result=last_result[:1000],
            success=success,
        )

        response = await self.llm.generate(
            prompt=prompt,
            model=self.config.planning_model,
            system="You are a planning assistant. Respond with valid JSON only.",
            temperature=0.2,  # Lower temp for more focused replanning
        )

        step = extract_json(response)
        if isinstance(step, dict):
            if step.get("action") == "done" or step.get("tool") == "none":
                logger.info("Planner determined goal is complete")
                return None
            return step

        return None

    async def decompose_to_tasks(
        self,
        goal: str,
        context: str = "",
    ) -> List[Task]:
        """Decompose a goal into Task objects with assigned roles.

        Higher-level than create_plan — produces Task objects for
        multi-agent orchestration.
        """
        prompt = f"""Break this goal into tasks and assign each to a role.

Goal: {goal}
{f"Context: {context}" if context else ""}

Roles: architect (design), developer (implement), reviewer (check quality), tester (verify)

Respond with a JSON array:
[
  {{"description": "task description", "role": "developer"}},
  ...
]
"""
        response = await self.llm.generate(
            prompt=prompt,
            model=self.config.planning_model,
            temperature=0.3,
        )

        parsed = extract_json(response)
        if not isinstance(parsed, list):
            # Fallback: single developer task
            return [Task(description=goal, role=AgentRole.DEVELOPER)]

        role_map = {
            "architect": AgentRole.ARCHITECT,
            "developer": AgentRole.DEVELOPER,
            "reviewer": AgentRole.REVIEWER,
            "tester": AgentRole.TESTER,
            "planner": AgentRole.PLANNER,
        }

        tasks = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            desc = item.get("description", "")
            if not desc:
                continue
            role_str = item.get("role", "developer").lower()
            tasks.append(
                Task(
                    description=desc,
                    role=role_map.get(role_str, AgentRole.DEVELOPER),
                )
            )

        return tasks if tasks else [Task(description=goal, role=AgentRole.DEVELOPER)]
