"""AgentBus — async message passing between specialized agents.

Provides pub/sub communication, conflict detection, and result merging
for multi-agent coordination.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    ARCHITECT = "architect"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    ORCHESTRATOR = "orchestrator"


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass
class AgentMessage:
    """Message passed between agents."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    sender: str = ""
    content: Any = None
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "sender": self.sender,
            "content": self.content,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            topic=data.get("topic", ""),
            sender=data.get("sender", ""),
            content=data.get("content"),
            priority=MessagePriority(data.get("priority", 1)),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentTask:
    """A task assigned to an agent."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_role: AgentRole = AgentRole.CODER
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    files_touched: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_role": self.agent_role.value,
            "description": self.description,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "files_touched": self.files_touched,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTask":
        task = cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            agent_role=AgentRole(data.get("agent_role", "coder")),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            files_touched=data.get("files_touched", []),
            created_at=data.get("created_at", time.time()),
            completed_at=data.get("completed_at"),
        )
        return task


@dataclass
class AgentConflict:
    """Conflict between two agents."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_a: str = ""
    agent_b: str = ""
    resource: str = ""
    description: str = ""
    resolution: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "resource": self.resource,
            "description": self.description,
            "resolution": self.resolution,
            "timestamp": self.timestamp,
        }


Handler = Callable[[AgentMessage], Awaitable[None]]


class AgentBus:
    """Async message bus for inter-agent communication.

    Topics:
    - task.new: New task assigned
    - task.complete: Task completed
    - task.failed: Task failed
    - conflict.detected: Resource conflict
    - review.requested: Code review needed
    - decision.needed: Human decision required
    - ai.suggest: AI-initiated suggestion
    - ai.concern: AI-initiated concern
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Handler]] = {}
        self._message_log: List[AgentMessage] = []
        self._max_log_size = 5000

    def subscribe(self, topic: str, handler: Handler) -> None:
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        if topic in self._subscribers:
            self._subscribers[topic] = [
                h for h in self._subscribers[topic] if h != handler
            ]

    async def publish(self, topic: str, message: AgentMessage) -> None:
        message.topic = topic
        self._message_log.append(message)
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size:]

        handlers = self._subscribers.get(topic, [])
        if handlers:
            await asyncio.gather(
                *[h(message) for h in handlers],
                return_exceptions=True,
            )

    async def publish_simple(
        self,
        topic: str,
        sender: str,
        content: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> None:
        message = AgentMessage(
            topic=topic,
            sender=sender,
            content=content,
            priority=priority,
        )
        await self.publish(topic, message)

    def get_messages(self, topic: Optional[str] = None, limit: int = 50) -> List[AgentMessage]:
        messages = self._message_log
        if topic:
            messages = [m for m in messages if m.topic == topic]
        return messages[-limit:]

    def stats(self) -> Dict[str, Any]:
        topics: Dict[str, int] = {}
        for m in self._message_log:
            topics[m.topic] = topics.get(m.topic, 0) + 1
        return {
            "total_messages": len(self._message_log),
            "topics": topics,
            "subscriber_count": sum(len(h) for h in self._subscribers.values()),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages": [m.to_dict() for m in self._message_log[-1000:]],
            "max_log_size": self._max_log_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentBus":
        bus = cls()
        bus._max_log_size = data.get("max_log_size", 5000)
        for mdata in data.get("messages", []):
            bus._message_log.append(AgentMessage.from_dict(mdata))
        return bus


class ConflictDetector:
    """Detects when multiple agents modify the same resource."""

    def __init__(self) -> None:
        self._resource_owners: Dict[str, Set[str]] = {}
        self.conflicts: List[AgentConflict] = []

    def register_access(self, agent_id: str, resource: str) -> Optional[AgentConflict]:
        """Register that an agent is accessing a resource. Returns conflict if any."""
        if resource not in self._resource_owners:
            self._resource_owners[resource] = set()

        owners = self._resource_owners[resource]
        if owners and agent_id not in owners:
            conflict = AgentConflict(
                agent_a=agent_id,
                agent_b=next(iter(owners)),
                resource=resource,
                description=f"Both {agent_id} and {next(iter(owners))} are modifying {resource}",
            )
            self.conflicts.append(conflict)
            return conflict

        owners.add(agent_id)
        return None

    def release_access(self, agent_id: str, resource: str) -> None:
        if resource in self._resource_owners:
            self._resource_owners[resource].discard(agent_id)

    def resolve_conflict(self, conflict_id: str, resolution: str) -> None:
        for conflict in self.conflicts:
            if conflict.id == conflict_id:
                conflict.resolution = resolution
                break

    def get_unresolved(self) -> List[AgentConflict]:
        return [c for c in self.conflicts if c.resolution is None]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflicts": [c.to_dict() for c in self.conflicts],
            "resource_owners": {k: list(v) for k, v in self._resource_owners.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConflictDetector":
        detector = cls()
        for cdata in data.get("conflicts", []):
            conflict = AgentConflict(
                id=cdata["id"],
                agent_a=cdata["agent_a"],
                agent_b=cdata["agent_b"],
                resource=cdata["resource"],
                description=cdata["description"],
                resolution=cdata.get("resolution"),
                timestamp=cdata.get("timestamp", time.time()),
            )
            detector.conflicts.append(conflict)
        for resource, owners in data.get("resource_owners", {}).items():
            detector._resource_owners[resource] = set(owners)
        return detector


class AgentOrchestrator:
    """Decomposes goals into parallel-safe sub-tasks and manages agents."""

    def __init__(
        self,
        bus: Optional[AgentBus] = None,
        conflict_detector: Optional[ConflictDetector] = None,
    ) -> None:
        self.bus = bus or AgentBus()
        self.conflict_detector = conflict_detector or ConflictDetector()
        self.tasks: Dict[str, AgentTask] = {}
        self.results: Dict[str, str] = {}

    def decompose_goal(self, goal: str) -> List[AgentTask]:
        """Heuristic decomposition of a goal into agent tasks."""
        tasks = []
        lower = goal.lower()

        has_design = any(k in lower for k in ["design", "architect", "plan", "structure"])
        has_code = any(k in lower for k in ["create", "implement", "build", "write", "add", "fix"])
        has_test = any(k in lower for k in ["test", "verify", "validate"])
        has_review = any(k in lower for k in ["review", "audit", "check quality"])

        if has_design:
            tasks.append(AgentTask(
                agent_role=AgentRole.ARCHITECT,
                description=f"Design architecture for: {goal}",
            ))
        if has_code:
            tasks.append(AgentTask(
                agent_role=AgentRole.CODER,
                description=f"Implement: {goal}",
            ))
        if has_test:
            tasks.append(AgentTask(
                agent_role=AgentRole.TESTER,
                description=f"Create and run tests for: {goal}",
            ))
        if has_review:
            tasks.append(AgentTask(
                agent_role=AgentRole.REVIEWER,
                description=f"Review implementation of: {goal}",
            ))

        if not tasks:
            tasks.append(AgentTask(
                agent_role=AgentRole.CODER,
                description=goal,
            ))

        for task in tasks:
            self.tasks[task.id] = task

        return tasks

    async def execute_task(
        self,
        task_id: str,
        executor: Callable[[str], Awaitable[str]],
    ) -> Optional[str]:
        """Execute a single task with an executor function."""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        task.status = TaskStatus.RUNNING

        await self.bus.publish_simple(
            "task.running",
            sender="orchestrator",
            content=f"Starting task {task_id}: {task.description}",
        )

        try:
            result = await executor(task.description)
            task.result = result
            task.status = TaskStatus.COMPLETE
            task.completed_at = time.time()
            self.results[task_id] = result

            await self.bus.publish_simple(
                "task.complete",
                sender=f"agent_{task.agent_role.value}",
                content=f"Task {task_id} completed",
            )
            return result
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()

            await self.bus.publish_simple(
                "task.failed",
                sender=f"agent_{task.agent_role.value}",
                content=f"Task {task_id} failed: {e}",
            )
            return None

    async def execute_parallel(
        self,
        task_ids: List[str],
        executors: Dict[str, Callable[[str], Awaitable[str]]],
    ) -> Dict[str, Optional[str]]:
        """Execute multiple tasks in parallel."""
        coroutines = []
        for task_id in task_ids:
            if task_id in executors:
                coroutines.append(self.execute_task(task_id, executors[task_id]))

        results = await asyncio.gather(*coroutines, return_exceptions=True)
        output: Dict[str, Optional[str]] = {}
        for i, task_id in enumerate(task_ids):
            r = results[i]
            output[task_id] = r if not isinstance(r, Exception) else None
        return output

    def merge_results(self) -> str:
        """Merge all task results into a summary."""
        parts = []
        for task_id, task in self.tasks.items():
            status = task.status.value
            result = task.result or task.error or ""
            parts.append(f"[{task.agent_role.value}] {status}: {result[:200]}")
        return "\n".join(parts)

    def get_tasks_by_role(self, role: AgentRole) -> List[AgentTask]:
        return [t for t in self.tasks.values() if t.agent_role == role]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "results": self.results,
            "bus": self.bus.to_dict(),
            "conflict_detector": self.conflict_detector.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        bus: Optional[AgentBus] = None,
        conflict_detector: Optional[ConflictDetector] = None,
    ) -> "AgentOrchestrator":
        orch = cls(bus=bus, conflict_detector=conflict_detector)
        for tid, tdata in data.get("tasks", {}).items():
            orch.tasks[tid] = AgentTask.from_dict(tdata)
        orch.results = data.get("results", {})
        return orch
