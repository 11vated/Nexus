"""Advisor Federation — cheap executor + expensive reviewer pattern.

Uses a fast model for generation and a slower/deeper model for review,
revising the solution when the advisor finds issues. Also provides
consensus routing for critical decisions and cost tracking.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from nexus.agent.llm import OllamaClient
from nexus.agent.models import AgentConfig

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"


@dataclass
class CostEntry:
    """Single cost/performance observation."""
    model: str
    task_type: str
    complexity: str
    tokens_in: int
    tokens_out: int
    duration_ms: float
    quality_score: float = 0.0  # 0-1, set by reflector/feedback
    timestamp: float = field(default_factory=time.time)


@dataclass
class AdvisorReview:
    """Result of an advisor review pass."""
    has_issues: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: str = "info"  # info, warning, critical
    confidence: float = 0.5
    raw_response: str = ""


@dataclass
class Solution:
    """A generated solution with metadata."""
    content: str
    model_used: str
    complexity: TaskComplexity
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: float = 0.0
    review: Optional[AdvisorReview] = None
    revision_count: int = 0


@dataclass
class ModelProfile:
    """Learned performance profile for a model."""
    model: str
    total_tasks: int = 0
    avg_duration_ms: float = 0.0
    avg_quality: float = 0.5
    avg_tokens_out: int = 0
    complexity_scores: Dict[str, float] = field(default_factory=dict)
    task_type_scores: Dict[str, float] = field(default_factory=dict)
    _complexity_counts: Dict[str, int] = field(default_factory=dict)
    _task_type_counts: Dict[str, int] = field(default_factory=dict)

    def update(self, entry: CostEntry) -> None:
        self.total_tasks += 1
        n = self.total_tasks
        self.avg_duration_ms = (self.avg_duration_ms * (n - 1) + entry.duration_ms) / n
        self.avg_quality = (self.avg_quality * (n - 1) + entry.quality_score) / n
        self.avg_tokens_out = (self.avg_tokens_out * (n - 1) + entry.tokens_out) / n

        c = entry.complexity
        c_count = self._complexity_counts.get(c, 0)
        c_count += 1
        self._complexity_counts[c] = c_count
        old_c = self.complexity_scores.get(c, 0.0)
        self.complexity_scores[c] = (old_c * (c_count - 1) + entry.quality_score) / c_count

        t = entry.task_type
        t_count = self._task_type_counts.get(t, 0)
        t_count += 1
        self._task_type_counts[t] = t_count
        old_t = self.task_type_scores.get(t, 0.0)
        self.task_type_scores[t] = (old_t * (t_count - 1) + entry.quality_score) / t_count


class CostTracker:
    """Track cost and performance per model per task type."""

    def __init__(self) -> None:
        self.log: List[CostEntry] = []
        self.profiles: Dict[str, ModelProfile] = {}

    def record(
        self,
        model: str,
        task_type: str,
        complexity: TaskComplexity,
        tokens_in: int,
        tokens_out: int,
        duration_ms: float,
        quality_score: float = 0.0,
    ) -> None:
        entry = CostEntry(
            model=model,
            task_type=task_type,
            complexity=complexity.value,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            quality_score=quality_score,
        )
        self.log.append(entry)

        if model not in self.profiles:
            self.profiles[model] = ModelProfile(model=model)
        self.profiles[model].update(entry)

    def get_best_model(
        self,
        task_type: Optional[str] = None,
        complexity: Optional[TaskComplexity] = None,
    ) -> Optional[str]:
        """Return the model with highest avg quality for the given filters."""
        candidates = self.profiles
        if not candidates:
            return None

        def score(name: str) -> float:
            p = candidates[name]
            s = p.avg_quality
            if task_type and task_type in p.task_type_scores:
                s = s * 0.6 + p.task_type_scores[task_type] * 0.4
            if complexity and complexity.value in p.complexity_scores:
                s = s * 0.5 + p.complexity_scores[complexity.value] * 0.5
            return s

        return max(candidates, key=score)

    def summary(self) -> Dict[str, Any]:
        return {
            model: {
                "total_tasks": p.total_tasks,
                "avg_duration_ms": round(p.avg_duration_ms, 1),
                "avg_quality": round(p.avg_quality, 3),
                "avg_tokens_out": p.avg_tokens_out,
            }
            for model, p in self.profiles.items()
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log": [
                {
                    "model": e.model,
                    "task_type": e.task_type,
                    "complexity": e.complexity,
                    "tokens_in": e.tokens_in,
                    "tokens_out": e.tokens_out,
                    "duration_ms": e.duration_ms,
                    "quality_score": e.quality_score,
                    "timestamp": e.timestamp,
                }
                for e in self.log[-500:]
            ],
            "profiles": {
                m: {
                    "total_tasks": p.total_tasks,
                    "avg_duration_ms": p.avg_duration_ms,
                    "avg_quality": p.avg_quality,
                    "avg_tokens_out": p.avg_tokens_out,
                    "complexity_scores": p.complexity_scores,
                    "task_type_scores": p.task_type_scores,
                    "_complexity_counts": p._complexity_counts,
                    "_task_type_counts": p._task_type_counts,
                }
                for m, p in self.profiles.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CostTracker":
        tracker = cls()
        for entry_data in data.get("log", []):
            entry = CostEntry(
                model=entry_data["model"],
                task_type=entry_data["task_type"],
                complexity=entry_data["complexity"],
                tokens_in=entry_data["tokens_in"],
                tokens_out=entry_data["tokens_out"],
                duration_ms=entry_data["duration_ms"],
                quality_score=entry_data.get("quality_score", 0.0),
                timestamp=entry_data.get("timestamp", time.time()),
            )
            tracker.log.append(entry)
        for model, pdata in data.get("profiles", {}).items():
            profile = ModelProfile(
                model=model,
                total_tasks=pdata["total_tasks"],
                avg_duration_ms=pdata["avg_duration_ms"],
                avg_quality=pdata["avg_quality"],
                avg_tokens_out=pdata["avg_tokens_out"],
                complexity_scores=pdata.get("complexity_scores", {}),
                task_type_scores=pdata.get("task_type_scores", {}),
                _complexity_counts=pdata.get("_complexity_counts", {}),
                _task_type_counts=pdata.get("_task_type_counts", {}),
            )
            tracker.profiles[model] = profile
        return tracker


def classify_complexity(
    task: str,
    context_length: int = 0,
    has_risk: bool = False,
) -> TaskComplexity:
    """Heuristic complexity classifier."""
    lower = task.lower()

    keywords_critical = [
        "security", "deploy to production", "database migration",
        "schema change", "schema",
    ]
    keywords_complex = ["architect", "design", "migrate", "rewrite", "optimize"]
    keywords_moderate = ["create", "add", "modify", "refactor", "implement", "fix"]
    keywords_simple = ["read", "list", "show", "print", "explain"]

    if has_risk:
        return TaskComplexity.CRITICAL
    if any(k in lower for k in keywords_critical):
        return TaskComplexity.CRITICAL
    if any(k in lower for k in keywords_complex):
        return TaskComplexity.COMPLEX
    if any(k in lower for k in keywords_moderate):
        return TaskComplexity.MODERATE
    if any(k in lower for k in keywords_simple):
        return TaskComplexity.SIMPLE

    if context_length > 50000:
        return TaskComplexity.COMPLEX
    if context_length > 10000:
        return TaskComplexity.MODERATE

    return TaskComplexity.TRIVIAL


class AdvisorFederation:
    """Executor + Advisor tandem with cost tracking.

    Pattern:
    1. Executor (cheap/fast model) generates solution
    2. Advisor (expensive/deep model) reviews for non-trivial tasks
    3. Executor revises based on advisor feedback
    4. Result is returned with review metadata
    """

    REVIEW_THRESHOLD = TaskComplexity.MODERATE

    def __init__(
        self,
        config: AgentConfig,
        executor: Optional[OllamaClient] = None,
        advisor: Optional[OllamaClient] = None,
    ) -> None:
        self.config = config
        self.executor = executor or OllamaClient(config)
        self.advisor = advisor or OllamaClient(config)
        self.cost_tracker = CostTracker()
        self._review_prompt_template = (
            "Review the following solution for correctness, completeness, "
            "efficiency, and potential issues.\n\n"
            "Original task: {task}\n\n"
            "Proposed solution:\n{solution}\n\n"
            "Respond with a structured review:\n"
            "- ISSUES: list any bugs, errors, or problems\n"
            "- SUGGESTIONS: list improvements\n"
            "- SEVERITY: one of info/warning/critical\n"
            "- CONFIDENCE: 0.0 to 1.0\n\n"
            "If there are no issues, say 'NO ISSUES FOUND'."
        )
        self._revision_prompt_template = (
            "Revise your solution based on this review feedback.\n\n"
            "Original task: {task}\n\n"
            "Your previous solution:\n{solution}\n\n"
            "Review feedback:\n{review}\n\n"
            "Provide the revised solution."
        )

    async def execute_with_review(
        self,
        task: str,
        system: Optional[str] = None,
        task_type: str = "general",
        max_revisions: int = 1,
    ) -> Solution:
        """Execute with advisor review for non-trivial tasks."""
        complexity = classify_complexity(task)
        start = time.monotonic()

        solution = await self._execute(task, system, complexity)
        solution.complexity = complexity

        if complexity.value in (TaskComplexity.TRIVIAL.value, TaskComplexity.SIMPLE.value):
            self.cost_tracker.record(
                model=solution.model_used,
                task_type=task_type,
                complexity=complexity,
                tokens_in=solution.tokens_in,
                tokens_out=solution.tokens_out,
                duration_ms=solution.duration_ms,
            )
            return solution

        for revision_i in range(max_revisions + 1):
            review = await self._review(task, solution.content)
            solution.review = review

            if not review.has_issues:
                break

            if review.severity == "critical" and revision_i < max_revisions:
                revised = await self._revise(task, solution.content, review.raw_response)
                solution.content = revised
                solution.revision_count += 1

        solution.duration_ms = (time.monotonic() - start) * 1000

        self.cost_tracker.record(
            model=solution.model_used,
            task_type=task_type,
            complexity=complexity,
            tokens_in=solution.tokens_in,
            tokens_out=solution.tokens_out,
            duration_ms=solution.duration_ms,
        )

        return solution

    async def _execute(
        self,
        task: str,
        system: Optional[str] = None,
        complexity: TaskComplexity = TaskComplexity.SIMPLE,
    ) -> Solution:
        """Execute task with executor model."""
        start = time.monotonic()
        response = await self.executor.generate(task, system=system)
        duration = (time.monotonic() - start) * 1000
        return Solution(
            content=response,
            model_used=self.config.fast_model,
            complexity=complexity,
            tokens_in=len(task),
            tokens_out=len(response),
            duration_ms=duration,
        )

    async def _review(self, task: str, solution: str) -> AdvisorReview:
        """Have advisor review the solution."""
        prompt = self._review_prompt_template.format(task=task, solution=solution)
        response = await self.advisor.generate(prompt, model=self.config.planning_model)

        has_issues = "NO ISSUES FOUND" not in response.upper()
        issues = []
        suggestions = []
        severity = "info"
        confidence = 0.5

        lines = response.strip().split("\n")
        current_section = None
        for line in lines:
            upper = line.upper().strip()
            if upper.startswith("ISSUES:"):
                current_section = "issues"
                content = line.split(":", 1)[1].strip()
                if content:
                    issues.append(content)
            elif upper.startswith("SUGGESTIONS:"):
                current_section = "suggestions"
                content = line.split(":", 1)[1].strip()
                if content:
                    suggestions.append(content)
            elif upper.startswith("SEVERITY:"):
                severity = line.split(":", 1)[1].strip().lower()
                current_section = None
            elif upper.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    confidence = 0.5
                current_section = None
            elif current_section == "issues" and line.strip().startswith("- "):
                issues.append(line.strip()[2:])
            elif current_section == "suggestions" and line.strip().startswith("- "):
                suggestions.append(line.strip()[2:])

        return AdvisorReview(
            has_issues=has_issues,
            issues=issues,
            suggestions=suggestions,
            severity=severity,
            confidence=confidence,
            raw_response=response,
        )

    async def _revise(self, task: str, solution: str, review: str) -> str:
        """Revise solution based on review."""
        prompt = self._revision_prompt_template.format(
            task=task,
            solution=solution,
            review=review,
        )
        return await self.executor.generate(prompt)

    async def consensus_route(
        self,
        task: str,
        models: Optional[List[str]] = None,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ask multiple models and compare answers for critical decisions."""
        if models is None:
            models = [self.config.fast_model, self.config.coding_model, self.config.planning_model]

        async def _ask(model: str) -> Dict[str, str]:
            start = time.monotonic()
            client = OllamaClient(self.config)
            resp = await client.generate(task, model=model, system=system)
            return {"model": model, "response": resp, "duration_ms": (time.monotonic() - start) * 1000}

        results = await asyncio.gather(*[_ask(m) for m in models], return_exceptions=True)
        valid = [r for r in results if not isinstance(r, Exception)]

        disagreements = []
        for i in range(len(valid)):
            for j in range(i + 1, len(valid)):
                if valid[i]["response"].strip() != valid[j]["response"].strip():
                    disagreements.append({
                        "models": [valid[i]["model"], valid[j]["model"]],
                        "response_a": valid[i]["response"][:200],
                        "response_b": valid[j]["response"][:200],
                    })

        return {
            "results": valid,
            "disagreements": disagreements,
            "consensus": len(disagreements) == 0,
            "model_count": len(valid),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost_tracker": self.cost_tracker.to_dict(),
            "review_threshold": self.REVIEW_THRESHOLD.value,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        config: AgentConfig,
        executor: Optional[OllamaClient] = None,
        advisor: Optional[OllamaClient] = None,
    ) -> "AdvisorFederation":
        fed = cls(config=config, executor=executor, advisor=advisor)
        if "cost_tracker" in data:
            fed.cost_tracker = CostTracker.from_dict(data["cost_tracker"])
        return fed
