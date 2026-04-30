"""Tests for Concurrent Tool Execution."""
import asyncio

import pytest

from nexus.tools.concurrent import (
    BatchResult,
    CircuitBreaker,
    DependencyGraph,
    QueuedTask,
    TaskPriority,
    TaskQueue,
    TaskResult,
    ToolBatchExecutor,
)


class TestCircuitBreaker:
    def test_initially_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        assert not cb.is_open("tool")

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        for _ in range(3):
            cb.record_failure("tool")
        assert cb.is_open("tool")

    def test_success_resets(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        cb.record_failure("tool")
        cb.record_failure("tool")
        cb.record_success("tool")
        cb.record_failure("tool")
        assert not cb.is_open("tool")

    def test_recovery_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure("tool")
        cb.record_failure("tool")
        assert cb.is_open("tool")

        # Wait for recovery
        import time
        time.sleep(0.02)
        assert not cb.is_open("tool")

    def test_get_stats(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        cb.record_failure("tool_a")
        stats = cb.get_stats()
        assert stats["failure_counts"]["tool_a"] == 1


class TestDependencyGraph:
    def test_no_deps_all_ready(self):
        g = DependencyGraph()
        ready = g.get_ready_tasks({"a", "b", "c"}, set())
        assert ready == {"a", "b", "c"}

    def test_deps_not_ready(self):
        g = DependencyGraph()
        g.add_dependency("b", {"a"})
        ready = g.get_ready_tasks({"a", "b"}, set())
        assert ready == {"a"}

    def test_deps_ready(self):
        g = DependencyGraph()
        g.add_dependency("b", {"a"})
        ready = g.get_ready_tasks({"a", "b"}, {"a"})
        assert ready == {"b"}

    def test_independent_groups(self):
        g = DependencyGraph()
        g.add_dependency("c", {"a", "b"})
        groups = g.find_independent_groups({"a", "b", "c"})
        # First group should be {a, b}, second {c}
        assert len(groups) == 2
        first = groups[0]
        second = groups[1]
        assert "a" in first
        assert "b" in first
        assert "c" in second

    def test_empty(self):
        g = DependencyGraph()
        assert g.find_independent_groups(set()) == []


class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_execute_empty(self):
        q = TaskQueue()
        result = await q.execute_all({})
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_execute_single(self):
        q = TaskQueue()
        mock_tool = _MockTool("file_read", "file contents")
        q.add("t1", "file_read", {"path": "test.py"})
        result = await q.execute_all({"file_read": mock_tool})

        assert len(result.results) == 1
        assert result.results[0].success
        assert result.results[0].result == "file contents"

    @pytest.mark.asyncio
    async def test_execute_multiple_concurrent(self):
        q = TaskQueue(max_concurrency=3)
        results_log = []

        class SlowTool:
            name = "slow"
            async def execute(self, **kwargs):
                results_log.append("start")
                await asyncio.sleep(0.05)
                results_log.append("end")
                return "done"

        slow = SlowTool()
        q.add("t1", "slow", {})
        q.add("t2", "slow", {})
        q.add("t3", "slow", {})

        result = await q.execute_all({"slow": slow})
        assert result.success_count == 3

        # With concurrency=3, all starts should happen before any ends
        start_indices = [i for i, v in enumerate(results_log) if v == "start"]
        end_indices = [i for i, v in enumerate(results_log) if v == "end"]
        assert max(start_indices) < min(end_indices)

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        q = TaskQueue()
        q.add("t1", "missing_tool", {})
        result = await q.execute_all({})
        assert len(result.results) == 1
        assert not result.results[0].success

    @pytest.mark.asyncio
    async def test_tool_error(self):
        q = TaskQueue()
        mock_tool = _MockTool("file_write", "Error: Disk full")
        q.add("t1", "file_write", {"path": "test.txt", "content": "hello"})
        result = await q.execute_all({"file_write": mock_tool})
        assert result.failure_count == 1

    def test_circuit_breaker_access(self):
        q = TaskQueue()
        assert q.circuit_breaker is not None

    def test_dependency_graph_access(self):
        q = TaskQueue()
        assert q.dependency_graph is not None

    def test_get_stats(self):
        q = TaskQueue(max_concurrency=5)
        stats = q.get_stats()
        assert stats["max_concurrency"] == 5

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks(self):
        q = TaskQueue(max_concurrency=1)
        # Open the circuit breaker using time.time (same as the breaker uses)
        import time
        q.circuit_breaker._open_until["blocked_tool"] = time.time() + 60

        mock_tool = _MockTool("blocked_tool", "should not reach")
        q.add("t1", "blocked_tool", {})

        result = await q.execute_all({"blocked_tool": mock_tool})
        assert result.failure_count == 1
        assert result.results[0].error == "Circuit breaker open"


class TestBatchResult:
    def test_all_succeeded_empty(self):
        b = BatchResult()
        assert not b.all_succeeded

    def test_all_succeeded_true(self):
        b = BatchResult(
            results=[TaskResult(task_id="a", tool_name="x", success=True, result="ok")],
            success_count=1,
        )
        assert b.all_succeeded

    def test_all_succeeded_false(self):
        b = BatchResult(
            results=[
                TaskResult(task_id="a", tool_name="x", success=True, result="ok"),
                TaskResult(task_id="b", tool_name="x", success=False, error="fail"),
            ],
            success_count=1, failure_count=1,
        )
        assert not b.all_succeeded


class TestToolBatchExecutor:
    def test_create_with_defaults(self):
        ex = ToolBatchExecutor()
        assert ex.queue is not None
        assert ex.validation_manager is not None
        assert ex.fallback_manager is not None

    def test_create_without_extras(self):
        ex = ToolBatchExecutor(validate_results=False, use_fallbacks=False)
        assert ex.validation_manager is None
        assert ex.fallback_manager is None

    def test_add_call(self):
        ex = ToolBatchExecutor()
        ex.add_call("t1", "file_read", {"path": "test.py"})
        assert len(ex.queue._queue) == 1

    @pytest.mark.asyncio
    async def test_execute(self):
        ex = ToolBatchExecutor()
        ex.add_call("t1", "file_read", {"path": "test.py"})
        mock_tool = _MockTool("file_read", "file contents")
        result = await ex.execute({"file_read": mock_tool})
        assert result.success_count == 1

    def test_get_stats(self):
        ex = ToolBatchExecutor()
        stats = ex.get_stats()
        assert "queue" in stats
        assert "validation" in stats
        assert "fallbacks" in stats


class _MockTool:
    """Simple mock tool for testing."""
    def __init__(self, name: str, result: str):
        self.name = name
        self._result = result

    async def execute(self, **kwargs):
        return self._result
