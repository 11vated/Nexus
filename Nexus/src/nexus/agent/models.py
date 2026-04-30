"""Data models for the Nexus agent system."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentState(Enum):
    """Current state of the agent loop."""
    IDLE = "idle"
    PLANNING = "planning"
    ACTING = "acting"
    OBSERVING = "observing"
    REFLECTING = "reflecting"
    CORRECTING = "correcting"
    DONE = "done"
    ERROR = "error"


class AgentRole(Enum):
    """Roles in the multi-agent hierarchy."""
    PLANNER = "planner"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    TESTER = "tester"
    ARCHITECT = "architect"


class TaskStatus(Enum):
    """Status of a task in the execution pipeline."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    DONE = "done"
    FAILED = "failed"


class QualityLevel(Enum):
    """Quality assessment levels for generated output."""
    REJECTED = 0
    POOR = 1
    FAIR = 2
    GOOD = 3
    EXCELLENT = 4


@dataclass
class Task:
    """A task to be executed by the agent."""
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: AgentRole = AgentRole.DEVELOPER
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: float = field(default_factory=time.time)

    def mark_in_progress(self) -> None:
        self.status = TaskStatus.IN_PROGRESS
        self.attempts += 1

    def mark_done(self, result: str) -> None:
        self.status = TaskStatus.DONE
        self.result = result

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error = error

    @property
    def can_retry(self) -> bool:
        return self.attempts < self.max_attempts


@dataclass
class Step:
    """A single step in the agent's execution trace."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    action: str = ""
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    result: str = ""
    success: bool = False
    quality_score: float = 0.0
    reflection: str = ""
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    def to_context(self) -> str:
        """Format step for inclusion in LLM context."""
        status = "✓" if self.success else "✗"
        parts = [f"[{status}] {self.action}"]
        if self.tool_name:
            parts.append(f"  Tool: {self.tool_name}({self.tool_args})")
        if self.result:
            # Truncate long results for context window
            result_preview = self.result[:500]
            if len(self.result) > 500:
                result_preview += "... [truncated]"
            parts.append(f"  Result: {result_preview}")
        if self.reflection:
            parts.append(f"  Reflection: {self.reflection}")
        return "\n".join(parts)


@dataclass
class ToolCall:
    """A parsed tool call from LLM output."""
    name: str
    arguments: Dict[str, Any]
    raw: str = ""


@dataclass
class AgentConfig:
    """Configuration for the agent loop."""
    # Model selection
    planning_model: str = "deepseek-r1:7b"
    coding_model: str = "qwen2.5-coder:14b"
    review_model: str = "deepseek-r1:7b"
    fast_model: str = "qwen2.5-coder:7b"

    # Loop control
    max_iterations: int = 25
    max_retries: int = 3
    quality_threshold: float = 3.5

    # Timeouts
    llm_timeout: int = 120
    tool_timeout: int = 60

    # Ollama settings
    ollama_url: str = "http://localhost:11434"
    temperature: float = 0.3
    max_tokens: int = 4096

    # Workspace
    workspace_path: str = "."

    # Features
    reflection_enabled: bool = True
    memory_enabled: bool = True
    sandbox_enabled: bool = False

    # Context compaction
    compaction_enabled: bool = True
    compaction_model: str = "qwen2.5-coder:7b"
