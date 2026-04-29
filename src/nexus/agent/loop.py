"""The Nexus agent loop — Plan → Act → Observe → Reflect.

This is the main entry point for autonomous task execution.
It orchestrates the planner, executor, reflector, and memory
into a coherent loop that can accomplish coding tasks.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from nexus.agent.context import ContextManager
from nexus.agent.executor import Executor
from nexus.agent.llm import OllamaClient
from nexus.agent.models import AgentConfig, AgentState, QualityLevel, Step
from nexus.agent.planner import Planner
from nexus.agent.reflector import Reflector
from nexus.memory.short_term import ShortTermMemory
from nexus.memory.long_term import LongTermMemory

logger = logging.getLogger(__name__)


class AgentLoop:
    """The autonomous agent execution loop.

    Implements Plan → Act → Observe → Reflect cycle:
    1. PLAN:    LLM creates/updates execution plan
    2. ACT:     Execute the next tool call
    3. OBSERVE: Capture and store results
    4. REFLECT: Assess quality, decide to continue/retry/stop

    Memory integration:
    - Short-term: tracks conversation within the current session
    - Long-term:  persists learnings across sessions (task patterns, fixes)
    - Context:    manages the LLM prompt window budget

    Usage:
        config = AgentConfig(workspace_path="/path/to/project")
        agent = AgentLoop(config)
        agent.register_default_tools()
        result = await agent.run("Build a Flask API with /health endpoint")
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.llm = OllamaClient(self.config)
        self.planner = Planner(self.llm, self.config)
        self.executor = Executor(self.config)
        self.reflector = Reflector(self.llm, self.config)
        self.context = ContextManager()

        # Memory systems
        self.short_term = ShortTermMemory(window_size=30)
        self.long_term: Optional[LongTermMemory] = None
        if self.config.memory_enabled:
            memory_dir = os.path.join(self.config.workspace_path, ".nexus_memory")
            self.long_term = LongTermMemory(persist_dir=memory_dir)

        self.state = AgentState.IDLE
        self.history: List[Step] = []
        self._on_step: Optional[Callable[[Step, AgentState], None]] = None
        self._on_state_change: Optional[Callable[[AgentState], None]] = None

    # ------------------------------------------------------------------
    # Callbacks (for TUI / live display)
    # ------------------------------------------------------------------

    def on_step(self, callback: Callable[[Step, AgentState], None]) -> None:
        """Register a callback for step completion (for TUI updates)."""
        self._on_step = callback

    def on_state_change(self, callback: Callable[[AgentState], None]) -> None:
        """Register a callback for state changes (for TUI updates)."""
        self._on_state_change = callback

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tool(self, name: str, tool: Any) -> None:
        """Register a tool with the executor."""
        self.executor.register_tool(name, tool)

    def register_tools(self, tools: Dict[str, Any]) -> None:
        """Register multiple tools."""
        self.executor.register_tools(tools)

    def _set_state(self, state: AgentState) -> None:
        self.state = state
        if self._on_state_change:
            self._on_state_change(state)

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def _recall_relevant(self, goal: str) -> str:
        """Search long-term memory for anything relevant to this goal."""
        if not self.long_term or self.long_term.count == 0:
            return ""
        results = self.long_term.search(goal, n_results=3)
        if not results:
            return ""
        parts = ["Relevant memories from past sessions:"]
        for doc_id, content, score in results:
            if score > 0.15:  # Only include somewhat-relevant matches
                parts.append(f"  [{score:.0%}] {content[:300]}")
        return "\n".join(parts) if len(parts) > 1 else ""

    def _remember_session(self, goal: str, result: Dict[str, Any]) -> None:
        """Store a summary of this session in long-term memory."""
        if not self.long_term:
            return
        successful_steps = [s for s in self.history if s.success]
        if not successful_steps:
            return
        summary_parts = [f"Goal: {goal}", f"Result: {'success' if result.get('success') else 'failed'}"]
        for s in successful_steps[-5:]:  # Last 5 successful steps
            summary_parts.append(f"  - {s.action} ({s.tool_name})")
        summary = "\n".join(summary_parts)
        self.long_term.store(
            content=summary,
            metadata={"type": "session", "goal": goal[:200], "success": result.get("success", False)},
        )

    # ------------------------------------------------------------------
    # Dynamic tool descriptions for planner
    # ------------------------------------------------------------------

    def _get_tool_descriptions(self) -> str:
        """Get tool descriptions from the executor for dynamic planner prompts."""
        return self.executor.get_tool_descriptions()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, goal: str) -> Dict[str, Any]:
        """Execute a goal autonomously.

        This is the main entry point. It:
        1. Recalls relevant long-term memories
        2. Creates an initial plan (with dynamic tool list)
        3. Executes steps one by one
        4. Reflects after each step
        5. Replans when needed
        6. Stores session summary for future recall

        Args:
            goal: High-level goal description.

        Returns:
            Dict with success, steps, final_result, stats.
        """
        start_time = time.time()
        self.history.clear()
        self.context.clear()
        self.context.goal = goal
        self.short_term.clear()

        # Record the goal in short-term memory
        self.short_term.add_user_message(goal)

        # Gather workspace info
        workspace = Path(self.config.workspace_path)
        if workspace.exists():
            try:
                files = list(workspace.rglob("*"))[:50]
                self.context.workspace_info = (
                    f"Path: {workspace}\n"
                    f"Files: {len(files)} (showing first 50)\n"
                    + "\n".join(str(f.relative_to(workspace)) for f in files[:20])
                )
            except OSError:
                self.context.workspace_info = f"Path: {workspace}"

        # Recall relevant long-term memories
        memories = self._recall_relevant(goal)
        if memories:
            self.context.pin(memories, source="long_term_memory")
            logger.info("Recalled %d relevant memories", memories.count("["))

        logger.info("Starting agent loop for goal: %s", goal[:100])
        self._set_state(AgentState.PLANNING)

        # Phase 1: Create initial plan (with dynamic tool list)
        tool_descriptions = self._get_tool_descriptions()
        plan = await self.planner.create_plan(
            goal=goal,
            context=self.context.build_prompt_context(),
            workspace_info=self.context.workspace_info,
            tool_descriptions=tool_descriptions,
        )

        logger.info("Initial plan: %d steps", len(plan))
        self.short_term.add_agent_response(
            f"Plan created with {len(plan)} steps"
        )

        # Phase 2: Execute loop
        iteration = 0
        plan_index = 0
        consecutive_failures = 0

        while iteration < self.config.max_iterations:
            iteration += 1

            # Get next step: from plan or from replanning
            if plan_index < len(plan):
                step_plan = plan[plan_index]
                plan_index += 1
            else:
                # Plan exhausted — ask planner for next step
                self._set_state(AgentState.PLANNING)
                last_step = self.history[-1] if self.history else None
                step_plan = await self.planner.next_step(
                    goal=goal,
                    history=self.history,
                    last_result=last_step.result if last_step else "",
                    success=last_step.success if last_step else True,
                )
                if step_plan is None:
                    logger.info("Planner says goal is complete at iteration %d", iteration)
                    break

            # Execute the step
            self._set_state(AgentState.ACTING)
            logger.info(
                "Step %d/%d: %s",
                iteration,
                self.config.max_iterations,
                step_plan.get("action", "unknown")[:80],
            )

            step = await self.executor.execute_step(step_plan)
            self.history.append(step)
            self.context.add_step(step)

            # Record in short-term memory
            self.short_term.add_tool_result(
                step.tool_name or "action",
                f"{'✓' if step.success else '✗'} {step.action}: {step.result[:200]}",
            )

            # Notify listeners
            if self._on_step:
                self._on_step(step, self.state)

            # Observe
            self._set_state(AgentState.OBSERVING)

            if not step.success:
                consecutive_failures += 1
                logger.warning(
                    "Step failed (consecutive: %d): %s",
                    consecutive_failures,
                    step.result[:200],
                )
            else:
                consecutive_failures = 0

            # Circuit breaker: too many consecutive failures
            if consecutive_failures >= 3:
                logger.error("3 consecutive failures — stopping")
                self._set_state(AgentState.ERROR)
                break

            # Reflect (if enabled)
            if self.config.reflection_enabled:
                self._set_state(AgentState.REFLECTING)
                reflection = await self.reflector.reflect_on_step(
                    step=step,
                    goal=goal,
                    history=self.history,
                )

                if reflection.get("goal_complete"):
                    logger.info("Reflector confirms goal complete")
                    break

                if reflection.get("should_retry") and getattr(step, "can_retry", False):
                    self._set_state(AgentState.CORRECTING)
                    plan_index -= 1
                    continue

        # Wrap up
        total_time = time.time() - start_time
        successful_steps = sum(1 for s in self.history if s.success)
        self._set_state(AgentState.DONE)

        await self.llm.close()

        result = {
            "success": consecutive_failures < 3 and successful_steps > 0,
            "goal": goal,
            "steps_total": len(self.history),
            "steps_successful": successful_steps,
            "iterations": iteration,
            "duration_seconds": round(total_time, 1),
            "final_state": self.state.value,
            "history": [
                {
                    "action": s.action,
                    "tool": s.tool_name,
                    "success": s.success,
                    "quality": s.quality_score,
                    "duration_ms": s.duration_ms,
                }
                for s in self.history
            ],
        }

        # Store session in long-term memory
        self._remember_session(goal, result)

        logger.info(
            "Agent loop complete: %d/%d steps succeeded in %.1fs",
            successful_steps,
            len(self.history),
            total_time,
        )

        return result

    async def run_interactive(self, goal: str) -> Dict[str, Any]:
        """Run with step-by-step confirmation (for debugging).

        Same as run() but pauses after each step for user input.
        Useful during development to observe agent behavior.
        """
        # TODO: Implement interactive stepping mode
        # For now, delegate to the standard loop
        return await self.run(goal)
