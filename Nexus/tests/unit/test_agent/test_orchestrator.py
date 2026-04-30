"""Tests for Agent Orchestrator module."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from nexus.agent.orchestrator import (
    AgentBus,
    AgentConflict,
    AgentMessage,
    AgentOrchestrator,
    AgentRole,
    AgentTask,
    ConflictDetector,
    MessagePriority,
    TaskStatus,
)


class TestAgentMessage:
    def test_defaults(self):
        msg = AgentMessage()
        assert len(msg.id) == 8
        assert msg.priority == MessagePriority.NORMAL

    def test_to_dict(self):
        msg = AgentMessage(topic="test", sender="agent1", content="hello")
        d = msg.to_dict()
        assert d["topic"] == "test"
        assert d["sender"] == "agent1"

    def test_from_dict_roundtrip(self):
        msg = AgentMessage(
            topic="task.complete",
            sender="coder",
            content="done",
            priority=MessagePriority.HIGH,
            metadata={"key": "value"},
        )
        d = msg.to_dict()
        restored = AgentMessage.from_dict(d)
        assert restored.topic == msg.topic
        assert restored.priority == msg.priority
        assert restored.metadata == msg.metadata


class TestAgentTask:
    def test_defaults(self):
        task = AgentTask(description="test")
        assert task.status == TaskStatus.PENDING
        assert task.files_touched == []

    def test_to_dict(self):
        task = AgentTask(
            agent_role=AgentRole.CODER,
            description="implement feature",
            files_touched=["a.py", "b.py"],
        )
        d = task.to_dict()
        assert d["agent_role"] == "coder"
        assert d["files_touched"] == ["a.py", "b.py"]

    def test_from_dict_roundtrip(self):
        task = AgentTask(
            id="t1",
            agent_role=AgentRole.TESTER,
            description="test auth",
            status=TaskStatus.COMPLETE,
            result="all pass",
            files_touched=["test_auth.py"],
        )
        d = task.to_dict()
        restored = AgentTask.from_dict(d)
        assert restored.id == task.id
        assert restored.status == task.status
        assert restored.result == task.result


class TestAgentConflict:
    def test_defaults(self):
        c = AgentConflict(agent_a="A", agent_b="B", resource="file.py")
        assert c.resolution is None

    def test_to_dict(self):
        c = AgentConflict(
            agent_a="coder",
            agent_b="reviewer",
            resource="auth.py",
            description="both editing",
        )
        d = c.to_dict()
        assert d["agent_a"] == "coder"
        assert d["resource"] == "auth.py"


class TestAgentBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = AgentBus()
        received = []

        async def handler(msg: AgentMessage) -> None:
            received.append(msg)

        bus.subscribe("test", handler)
        await bus.publish_simple("test", "sender", "content")

        assert len(received) == 1
        assert received[0].content == "content"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = AgentBus()
        received_a = []
        received_b = []

        async def handler_a(msg: AgentMessage) -> None:
            received_a.append(msg)

        async def handler_b(msg: AgentMessage) -> None:
            received_b.append(msg)

        bus.subscribe("topic", handler_a)
        bus.subscribe("topic", handler_b)
        await bus.publish_simple("topic", "sender", "data")

        assert len(received_a) == 1
        assert len(received_b) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = AgentBus()
        received = []

        async def handler(msg: AgentMessage) -> None:
            received.append(msg)

        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        await bus.publish_simple("test", "sender", "data")

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_different_topics(self):
        bus = AgentBus()
        received_a = []
        received_b = []

        async def handler_a(msg: AgentMessage) -> None:
            received_a.append(msg)

        async def handler_b(msg: AgentMessage) -> None:
            received_b.append(msg)

        bus.subscribe("topic_a", handler_a)
        bus.subscribe("topic_b", handler_b)

        await bus.publish_simple("topic_a", "sender", "data_a")
        await bus.publish_simple("topic_b", "sender", "data_b")

        assert len(received_a) == 1
        assert received_a[0].content == "data_a"
        assert len(received_b) == 1

    @pytest.mark.asyncio
    async def test_message_log(self):
        bus = AgentBus()
        for i in range(10):
            await bus.publish_simple(f"topic_{i}", "sender", f"data_{i}")

        messages = bus.get_messages()
        assert len(messages) == 10

        messages_topic_5 = bus.get_messages(topic="topic_5")
        assert len(messages_topic_5) == 1

    @pytest.mark.asyncio
    async def test_message_log_limit(self):
        bus = AgentBus()
        bus._max_log_size = 5
        for i in range(10):
            await bus.publish_simple("topic", "sender", f"data_{i}")

        messages = bus.get_messages()
        assert len(messages) == 5
        assert messages[0].content == "data_5"

    def test_stats(self):
        bus = AgentBus()
        bus._message_log = [
            AgentMessage(topic="task.new", sender="orch"),
            AgentMessage(topic="task.new", sender="orch"),
            AgentMessage(topic="task.complete", sender="coder"),
        ]

        stats = bus.stats()
        assert stats["total_messages"] == 3
        assert stats["topics"]["task.new"] == 2

    def test_serialization_roundtrip(self):
        bus = AgentBus()
        bus._message_log = [
            AgentMessage(topic="test", sender="a", content="hello"),
            AgentMessage(topic="test", sender="b", content="world"),
        ]

        data = bus.to_dict()
        restored = AgentBus.from_dict(data)

        assert len(restored._message_log) == 2


class TestConflictDetector:
    def test_no_conflict_single_agent(self):
        detector = ConflictDetector()
        result = detector.register_access("agent_a", "file.py")
        assert result is None

    def test_conflict_two_agents(self):
        detector = ConflictDetector()
        detector.register_access("agent_a", "file.py")
        conflict = detector.register_access("agent_b", "file.py")

        assert conflict is not None
        assert conflict.agent_a == "agent_b"
        assert conflict.agent_b == "agent_a"

    def test_no_conflict_same_agent(self):
        detector = ConflictDetector()
        detector.register_access("agent_a", "file.py")
        conflict = detector.register_access("agent_a", "file.py")
        assert conflict is None

    def test_release_access(self):
        detector = ConflictDetector()
        detector.register_access("agent_a", "file.py")
        detector.release_access("agent_a", "file.py")
        conflict = detector.register_access("agent_b", "file.py")
        assert conflict is None

    def test_resolve_conflict(self):
        detector = ConflictDetector()
        detector.register_access("agent_a", "file.py")
        conflict = detector.register_access("agent_b", "file.py")

        detector.resolve_conflict(conflict.id, "agent_a wins")
        assert conflict.resolution == "agent_a wins"

    def test_get_unresolved(self):
        detector = ConflictDetector()
        detector.register_access("agent_a", "file_a.py")
        c1 = detector.register_access("agent_b", "file_a.py")
        detector.register_access("agent_a", "file_b.py")
        c2 = detector.register_access("agent_b", "file_b.py")
        detector.resolve_conflict(c1.id, "resolved")

        unresolved = detector.get_unresolved()
        assert len(unresolved) == 1
        assert unresolved[0].id == c2.id

    def test_serialization_roundtrip(self):
        detector = ConflictDetector()
        detector.register_access("agent_a", "file.py")
        conflict = detector.register_access("agent_b", "file.py")

        data = detector.to_dict()
        restored = ConflictDetector.from_dict(data)

        assert len(restored.conflicts) == 1


class TestAgentOrchestratorDecompose:
    def test_decompose_design_goal(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Design a new API architecture")

        roles = [t.agent_role for t in tasks]
        assert AgentRole.ARCHITECT in roles

    def test_decompose_code_goal(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Create a user authentication module")

        roles = [t.agent_role for t in tasks]
        assert AgentRole.CODER in roles

    def test_decompose_test_goal(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Write tests for payment processing")

        roles = [t.agent_role for t in tasks]
        assert AgentRole.TESTER in roles

    def test_decompose_review_goal(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Review the code quality")

        roles = [t.agent_role for t in tasks]
        assert AgentRole.REVIEWER in roles

    def test_decompose_generic_goal(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Hello world")

        assert len(tasks) == 1
        assert tasks[0].agent_role == AgentRole.CODER

    def test_decompose_complex_goal(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal(
            "Design and implement a user system with tests and review"
        )

        roles = [t.agent_role for t in tasks]
        assert len(roles) == 4
        assert AgentRole.ARCHITECT in roles
        assert AgentRole.CODER in roles
        assert AgentRole.TESTER in roles
        assert AgentRole.REVIEWER in roles


class TestAgentOrchestratorExecute:
    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Create a feature")
        task_id = tasks[0].id

        async def mock_executor(desc: str) -> str:
            return f"Result for: {desc}"

        result = await orch.execute_task(task_id, mock_executor)

        assert result is not None
        assert orch.tasks[task_id].status == TaskStatus.COMPLETE
        assert orch.tasks[task_id].result is not None

    @pytest.mark.asyncio
    async def test_execute_task_failure(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Create a feature")
        task_id = tasks[0].id

        async def mock_executor(desc: str) -> str:
            raise ValueError("Something went wrong")

        result = await orch.execute_task(task_id, mock_executor)

        assert result is None
        assert orch.tasks[task_id].status == TaskStatus.FAILED
        assert orch.tasks[task_id].error is not None

    @pytest.mark.asyncio
    async def test_execute_nonexistent_task(self):
        orch = AgentOrchestrator()

        async def mock_executor(desc: str) -> str:
            return "result"

        result = await orch.execute_task("nonexistent", mock_executor)
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_parallel(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Design and implement a feature")
        task_ids = [t.id for t in tasks]

        async def mock_executor(desc: str) -> str:
            await asyncio.sleep(0.01)
            return f"Done: {desc[:30]}"

        executors = {tid: mock_executor for tid in task_ids}
        results = await orch.execute_parallel(task_ids, executors)

        assert len(results) == len(task_ids)
        for tid, result in results.items():
            assert result is not None

    @pytest.mark.asyncio
    async def test_execute_parallel_partial_failure(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("Design and implement")
        task_ids = [t.id for t in tasks]

        async def success_executor(desc: str) -> str:
            return "success"

        async def fail_executor(desc: str) -> str:
            raise RuntimeError("fail")

        executors = {}
        for i, tid in enumerate(task_ids):
            executors[tid] = success_executor if i == 0 else fail_executor

        results = await orch.execute_parallel(task_ids, executors)

        success_count = sum(1 for r in results.values() if r is not None)
        fail_count = sum(1 for r in results.values() if r is None)
        assert success_count >= 1
        assert fail_count >= 1


class TestAgentOrchestratorMerge:
    def test_merge_results(self):
        orch = AgentOrchestrator()
        orch.decompose_goal("Design and implement a feature")

        for task in orch.tasks.values():
            task.status = TaskStatus.COMPLETE
            task.result = f"Result from {task.agent_role.value}"

        merged = orch.merge_results()
        assert len(merged) > 0
        assert "coder" in merged.lower() or "architect" in merged.lower()

    def test_get_tasks_by_role(self):
        orch = AgentOrchestrator()
        orch.decompose_goal("Design and implement and test")

        coder_tasks = orch.get_tasks_by_role(AgentRole.CODER)
        assert len(coder_tasks) >= 1


class TestAgentOrchestratorSerialization:
    def test_to_dict(self):
        orch = AgentOrchestrator()
        orch.decompose_goal("Create feature")

        data = orch.to_dict()
        assert "tasks" in data
        assert "bus" in data
        assert "conflict_detector" in data

    def test_from_dict_roundtrip(self):
        orch = AgentOrchestrator()
        orch.decompose_goal("Design and implement")

        for task in orch.tasks.values():
            task.status = TaskStatus.COMPLETE
            task.result = "done"

        data = orch.to_dict()
        restored = AgentOrchestrator.from_dict(data)

        assert len(restored.tasks) == len(orch.tasks)
        assert len(restored.results) == len(orch.results)

    def test_from_dict_empty(self):
        restored = AgentOrchestrator.from_dict({})
        assert len(restored.tasks) == 0
        assert len(restored.results) == 0


class TestAgentOrchestratorEdgeCases:
    def test_decompose_empty_goal(self):
        orch = AgentOrchestrator()
        tasks = orch.decompose_goal("")
        assert len(tasks) == 1

    def test_merge_no_results(self):
        orch = AgentOrchestrator()
        merged = orch.merge_results()
        assert merged == ""

    def test_bus_stats_after_execution(self):
        orch = AgentOrchestrator()
        assert orch.bus.stats()["total_messages"] == 0
