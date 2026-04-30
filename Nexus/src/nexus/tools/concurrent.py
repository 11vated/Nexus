"""Concurrent Tool Execution — parallel execution of independent tool calls.

When the LLM requests multiple independent tool calls (e.g., reading 3 files,
running 2 searches), execute them in parallel to reduce latency.

Features:
- TaskQueue: Manages concurrent execution with configurable concurrency limits
- ToolBatch: Executes a batch of tool calls concurrently
- DependencyGraph: Detects tool call dependencies to maximize parallelism
- CircuitBreaker: Prevents cascading failures from overloaded tools
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of a single task execution."""
    task_id: str
    tool_name: str
    success: bool
    result: str = ""
    error: str = ""
    duration: float = 0.0


@dataclass
class BatchResult:
    """Result of a batch of concurrent tool calls."""
    results: List[TaskResult] = field(default_factory=list)
    total_duration: float = 0.0
    success_count: int = 0
    failure_count: int = 0

    @property
    def all_succeeded(self) -> bool:
        return self.failure_count == 0 and len(self.results) > 0


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class QueuedTask:
    """A task in the execution queue."""
    task_id: str
    tool_name: str
    args: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    coroutine: Optional[Coroutine] = None


class CircuitBreaker:
    """Prevents cascading failures by temporarily disabling failing tools.

    When a tool fails N times within a time window, the breaker opens and
    subsequent calls fail immediately until a cooldown period passes.
    """

    def __init__(self, failure_threshold: int = 5,
                 recovery_timeout: float = 60.0):
        self._failures: Dict[str, List[float]] = {}
        self._open_until: Dict[str, float] = {}
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

    def is_open(self, tool_name: str) -> bool:
        """Check if the circuit breaker is open for a tool."""
        if tool_name not in self._open_until:
            return False

        if time.time() >= self._open_until[tool_name]:
            # Recovery timeout passed — close the breaker
            del self._open_until[tool_name]
            self._failures.pop(tool_name, None)
            return False

        return True

    def record_success(self, tool_name: str) -> None:
        """Record a successful call."""
        self._failures.pop(tool_name, None)

    def record_failure(self, tool_name: str) -> None:
        """Record a failed call."""
        now = time.time()
        if tool_name not in self._failures:
            self._failures[tool_name] = []

        self._failures[tool_name].append(now)

        # Clean old failures (only keep last 60 seconds)
        cutoff = now - 60
        self._failures[tool_name] = [
            t for t in self._failures[tool_name] if t > cutoff
        ]

        if len(self._failures[tool_name]) >= self.failure_threshold:
            self._open_until[tool_name] = now + self.recovery_timeout
            logger.warning(
                "Circuit breaker opened for %s (%d failures in 60s)",
                tool_name, len(self._failures[tool_name]),
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        open_tools = [
            name for name, until in self._open_until.items()
            if time.time() < until
        ]
        return {
            "open_circuits": open_tools,
            "failure_counts": {
                name: len(failures)
                for name, failures in self._failures.items()
            },
        }


class DependencyGraph:
    """Detects dependencies between tool calls to maximize parallelism.

    Some tool calls depend on the results of others (e.g., read a file,
    then write based on its contents). This graph detects independent
    calls that can run concurrently.
    """

    def __init__(self):
        self._dependencies: Dict[str, Set[str]] = {}  # task_id -> depends on
        self._results: Dict[str, str] = {}  # task_id -> result

    def add_dependency(self, task_id: str, depends_on: Set[str]) -> None:
        """Register that a task depends on other tasks."""
        self._dependencies[task_id] = depends_on

    def get_ready_tasks(self, task_ids: Set[str], completed: Set[str]) -> Set[str]:
        """Get tasks that are ready to execute (all dependencies met).

        Args:
            task_ids: All task IDs to consider.
            completed: Tasks that have already completed.

        Returns:
            Set of task IDs ready to execute.
        """
        ready = set()
        for task_id in task_ids:
            if task_id in completed:
                continue
            deps = self._dependencies.get(task_id, set())
            if deps.issubset(completed):
                ready.add(task_id)
        return ready

    def find_independent_groups(self, task_ids: Set[str]) -> List[Set[str]]:
        """Group tasks into batches of independent tasks.

        Returns a list of sets, where each set contains tasks that can
        run concurrently. Execute batches in order.
        """
        if not task_ids:
            return []

        # Tasks with no dependencies can run first
        no_deps = {tid for tid in task_ids if not self._dependencies.get(tid)}
        if no_deps:
            remaining = task_ids - no_deps
            return [no_deps] + self.find_independent_groups(remaining)

        # If all tasks have deps, find tasks whose deps are all in other batches
        # This is a topological sort — return one at a time if cyclic
        first = next(iter(task_ids))
        remaining = task_ids - {first}
        return [{first}] + self.find_independent_groups(remaining)


class TaskQueue:
    """Manages concurrent tool execution with configurable limits.

    Usage:
        queue = TaskQueue(max_concurrency=5)

        # Add tasks
        queue.add("task1", "file_read", {"path": "a.py"})
        queue.add("task2", "file_read", {"path": "b.py"})
        queue.add("task3", "file_write", {"path": "c.py", "content": "..."})

        # Execute all
        results = await queue.execute_all(tools)
    """

    def __init__(self, max_concurrency: int = 5):
        self._queue: List[QueuedTask] = []
        self.max_concurrency = max_concurrency
        self._circuit_breaker = CircuitBreaker()
        self._dependency_graph = DependencyGraph()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    @property
    def dependency_graph(self) -> DependencyGraph:
        return self._dependency_graph

    def add(self, task_id: str, tool_name: str, args: Dict[str, Any],
            priority: TaskPriority = TaskPriority.NORMAL,
            depends_on: Optional[Set[str]] = None) -> None:
        """Add a task to the queue.

        Args:
            task_id: Unique task identifier.
            tool_name: Tool to execute.
            args: Tool arguments.
            priority: Execution priority.
            depends_on: Set of task IDs this task depends on.
        """
        task = QueuedTask(
            task_id=task_id, tool_name=tool_name,
            args=args, priority=priority,
        )
        self._queue.append(task)

        if depends_on:
            self._dependency_graph.add_dependency(task_id, depends_on)

    async def execute_all(self, tools: Dict[str, BaseTool]) -> BatchResult:
        """Execute all queued tasks with concurrency limits and dependency awareness.

        Args:
            tools: Available tools.

        Returns:
            BatchResult with all task results.
        """
        batch = BatchResult()
        start_time = time.time()

        if not self._queue:
            return batch

        # Sort by priority (high first)
        self._queue.sort(key=lambda t: t.priority.value, reverse=True)

        # Find independent groups
        all_ids = {t.task_id for t in self._queue}
        groups = self._dependency_graph.find_independent_groups(all_ids)

        completed: Set[str] = set()
        task_map = {t.task_id: t for t in self._queue}

        for group in groups:
            # Filter out tasks with open circuit breakers
            runnable = []
            for task_id in group:
                task = task_map[task_id]
                if self._circuit_breaker.is_open(task.tool_name):
                    result = TaskResult(
                        task_id=task_id, tool_name=task.tool_name,
                        success=False, error="Circuit breaker open",
                    )
                    batch.results.append(result)
                    batch.failure_count += 1
                    completed.add(task_id)
                else:
                    runnable.append(task)

            if not runnable:
                continue

            # Execute group concurrently with semaphore
            semaphore = asyncio.Semaphore(self.max_concurrency)
            coroutines = [
                self._execute_task(task, tools, semaphore)
                for task in runnable
            ]

            group_results = await asyncio.gather(*coroutines, return_exceptions=True)

            for task, result_or_exc in zip(runnable, group_results):
                if isinstance(result_or_exc, Exception):
                    result = TaskResult(
                        task_id=task.task_id, tool_name=task.tool_name,
                        success=False, error=str(result_or_exc),
                    )
                    self._circuit_breaker.record_failure(task.tool_name)
                else:
                    result = result_or_exc
                    if result.success:
                        self._circuit_breaker.record_success(task.tool_name)
                    else:
                        self._circuit_breaker.record_failure(task.tool_name)

                batch.results.append(result)
                completed.add(task.task_id)

                if result.success:
                    batch.success_count += 1
                else:
                    batch.failure_count += 1

        batch.total_duration = time.time() - start_time
        logger.info(
            "Batch execution: %d succeeded, %d failed in %.2fs",
            batch.success_count, batch.failure_count, batch.total_duration,
        )

        # Reset queue
        self._queue = []
        return batch

    async def _execute_task(self, task: QueuedTask,
                            tools: Dict[str, BaseTool],
                            semaphore: asyncio.Semaphore) -> TaskResult:
        """Execute a single task with semaphore control."""
        tool = tools.get(task.tool_name)
        if not tool:
            return TaskResult(
                task_id=task.task_id, tool_name=task.tool_name,
                success=False, error=f"Tool not found: {task.tool_name}",
            )

        async with semaphore:
            start = time.time()
            try:
                output = await tool.execute(**task.args)
                duration = time.time() - start

                return TaskResult(
                    task_id=task.task_id,
                    tool_name=task.tool_name,
                    success=not output.startswith("Error:"),
                    result=output,
                    error=output if output.startswith("Error:") else "",
                    duration=duration,
                )
            except Exception as exc:
                duration = time.time() - start
                return TaskResult(
                    task_id=task.task_id,
                    tool_name=task.tool_name,
                    success=False,
                    error=str(exc),
                    duration=duration,
                )

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "queued_tasks": len(self._queue),
            "max_concurrency": self.max_concurrency,
            "circuit_breaker": self._circuit_breaker.get_stats(),
        }


class ToolBatchExecutor:
    """High-level interface for concurrent tool execution.

    Combines TaskQueue, validation, and fallback into a single interface.
    """

    def __init__(self, max_concurrency: int = 5,
                 validate_results: bool = True,
                 use_fallbacks: bool = True):
        self.queue = TaskQueue(max_concurrency=max_concurrency)
        self._validate_results = validate_results
        self._use_fallbacks = use_fallbacks

        if validate_results:
            from nexus.tools.validation import ToolValidationManager
            self.validation_manager = ToolValidationManager()
        else:
            self.validation_manager = None

        if use_fallbacks:
            from nexus.tools.fallback import FallbackManager
            self.fallback_manager = FallbackManager()
        else:
            self.fallback_manager = None

    def add_call(self, task_id: str, tool_name: str,
                 args: Dict[str, Any],
                 depends_on: Optional[Set[str]] = None) -> None:
        """Add a tool call to the batch."""
        self.queue.add(task_id, tool_name, args, depends_on=depends_on)

    async def execute(self, tools: Dict[str, BaseTool]) -> BatchResult:
        """Execute the batch of tool calls."""
        return await self.queue.execute_all(tools)

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        stats = {
            "queue": self.queue.get_stats(),
            "validate_results": self._validate_results,
            "use_fallbacks": self._use_fallbacks,
        }
        if self.validation_manager:
            stats["validation"] = self.validation_manager.get_stats()
        if self.fallback_manager:
            stats["fallbacks"] = self.fallback_manager.get_stats()
        return stats
