"""Cognitive fitness scoring — multi-metric evaluation of agent strategies.

Measures agent performance across multiple dimensions:
- Code quality (test pass rate, lint score)
- Efficiency (execution time, token usage)
- Robustness (error rate, recovery success)
- Learning (improvement over time)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FitnessMetrics:
    """Multi-dimensional fitness metrics for an agent."""
    # Code quality
    test_pass_rate: float = 0.0  # 0-1
    lint_score: float = 0.0  # 0-1
    code_complexity_penalty: float = 0.0  # 0-1 (lower is better)

    # Efficiency
    execution_time: float = 0.0  # seconds
    token_usage: float = 0.0  # number of tokens
    steps_taken: int = 0

    # Robustness
    error_rate: float = 0.0  # 0-1 (lower is better)
    recovery_success: float = 0.0  # 0-1
    consecutive_failures: int = 0

    # Learning
    improvement_rate: float = 0.0  # improvement over previous attempts
    knowledge_reuse: float = 0.0  # 0-1 (how well past knowledge is applied)

    # Overall
    weighted_score: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "test_pass_rate": self.test_pass_rate,
            "lint_score": self.lint_score,
            "code_complexity_penalty": self.code_complexity_penalty,
            "execution_time": self.execution_time,
            "token_usage": self.token_usage,
            "steps_taken": float(self.steps_taken),
            "error_rate": self.error_rate,
            "recovery_success": self.recovery_success,
            "consecutive_failures": float(self.consecutive_failures),
            "improvement_rate": self.improvement_rate,
            "knowledge_reuse": self.knowledge_reuse,
            "weighted_score": self.weighted_score,
        }


class CognitiveFitness:
    """Calculates and tracks fitness scores for agent genomes.

    Uses a weighted multi-metric approach:
    - Quality: 40% (test pass rate, lint, complexity)
    - Efficiency: 25% (time, tokens, steps)
    - Robustness: 20% (error rate, recovery)
    - Learning: 15% (improvement, knowledge reuse)
    """

    def __init__(
        self,
        quality_weight: float = 0.40,
        efficiency_weight: float = 0.25,
        robustness_weight: float = 0.20,
        learning_weight: float = 0.15,
        max_execution_time: float = 300.0,
        max_token_usage: float = 50000.0,
        max_steps: int = 50,
    ):
        self.quality_weight = quality_weight
        self.efficiency_weight = efficiency_weight
        self.robustness_weight = robustness_weight
        self.learning_weight = learning_weight
        self.max_execution_time = max_execution_time
        self.max_token_usage = max_token_usage
        self.max_steps = max_steps
        self._history: Dict[str, List[FitnessMetrics]] = {}

    def calculate(
        self,
        agent_id: str,
        test_results: Optional[Dict[str, Any]] = None,
        execution_stats: Optional[Dict[str, Any]] = None,
        error_stats: Optional[Dict[str, Any]] = None,
        learning_stats: Optional[Dict[str, Any]] = None,
    ) -> FitnessMetrics:
        """Calculate fitness metrics for an agent's performance.

        Args:
            agent_id: The agent's genome ID.
            test_results: Dict with tests_passed, tests_total, lint_score.
            execution_stats: Dict with time_seconds, tokens_used, steps.
            error_stats: Dict with errors, total_attempts, recoveries.
            learning_stats: Dict with previous_score, knowledge_hits.

        Returns:
            FitnessMetrics with individual scores and weighted total.
        """
        metrics = FitnessMetrics()

        # Quality metrics
        if test_results:
            total = test_results.get("tests_total", 1)
            passed = test_results.get("tests_passed", 0)
            metrics.test_pass_rate = min(passed / max(total, 1), 1.0)
            metrics.lint_score = test_results.get("lint_score", 0.5)
            metrics.code_complexity_penalty = min(
                test_results.get("complexity", 0) / 10.0, 1.0,
            )

        # Efficiency metrics
        if execution_stats:
            metrics.execution_time = execution_stats.get("time_seconds", 0)
            metrics.token_usage = execution_stats.get("tokens_used", 0)
            metrics.steps_taken = execution_stats.get("steps", 0)

        # Robustness metrics
        if error_stats:
            total_attempts = error_stats.get("total_attempts", 1)
            errors = error_stats.get("errors", 0)
            metrics.error_rate = min(errors / max(total_attempts, 1), 1.0)
            recoveries = error_stats.get("recoveries", 0)
            metrics.recovery_success = min(
                recoveries / max(errors, 1), 1.0,
            ) if errors > 0 else 1.0
            metrics.consecutive_failures = error_stats.get(
                "consecutive_failures", 0,
            )

        # Learning metrics
        if learning_stats:
            metrics.improvement_rate = learning_stats.get("improvement", 0.0)
            metrics.knowledge_reuse = learning_stats.get(
                "knowledge_hits", 0.0,
            )

        # Calculate weighted score
        metrics.weighted_score = self._compute_weighted_score(metrics)

        # Store in history
        self._history.setdefault(agent_id, []).append(metrics)

        logger.debug(
            "Fitness for %s: %.3f (quality=%.2f, eff=%.2f, robust=%.2f, learn=%.2f)",
            agent_id,
            metrics.weighted_score,
            self._quality_score(metrics),
            self._efficiency_score(metrics),
            self._robustness_score(metrics),
            self._learning_score(metrics),
        )

        return metrics

    def get_improvement(self, agent_id: str) -> float:
        """Calculate how much an agent has improved over its history."""
        history = self._history.get(agent_id, [])
        if len(history) < 2:
            return 0.0
        return history[-1].weighted_score - history[0].weighted_score

    def get_agent_history(self, agent_id: str) -> List[FitnessMetrics]:
        """Get the fitness history for an agent."""
        return list(self._history.get(agent_id, []))

    def _compute_weighted_score(self, metrics: FitnessMetrics) -> float:
        """Compute the weighted fitness score."""
        quality = self._quality_score(metrics)
        efficiency = self._efficiency_score(metrics)
        robustness = self._robustness_score(metrics)
        learning = self._learning_score(metrics)

        return (
            self.quality_weight * quality
            + self.efficiency_weight * efficiency
            + self.robustness_weight * robustness
            + self.learning_weight * learning
        )

    def _quality_score(self, m: FitnessMetrics) -> float:
        """Calculate quality sub-score (0-1)."""
        test_component = m.test_pass_rate * 0.5
        lint_component = m.lint_score * 0.3
        complexity_component = (1.0 - m.code_complexity_penalty) * 0.2
        return test_component + lint_component + complexity_component

    def _efficiency_score(self, m: FitnessMetrics) -> float:
        """Calculate efficiency sub-score (0-1)."""
        if m.execution_time == 0 and m.token_usage == 0:
            return 0.5  # Neutral if no data

        time_score = max(0, 1.0 - (m.execution_time / self.max_execution_time))
        token_score = max(0, 1.0 - (m.token_usage / self.max_token_usage))
        steps_score = max(0, 1.0 - (m.steps_taken / self.max_steps))

        return (time_score * 0.3 + token_score * 0.4 + steps_score * 0.3)

    def _robustness_score(self, m: FitnessMetrics) -> float:
        """Calculate robustness sub-score (0-1)."""
        error_component = (1.0 - m.error_rate) * 0.5
        recovery_component = m.recovery_success * 0.3
        failure_penalty = max(0, 1.0 - (m.consecutive_failures * 0.2)) * 0.2
        return error_component + recovery_component + failure_penalty

    def _learning_score(self, m: FitnessMetrics) -> float:
        """Calculate learning sub-score (0-1)."""
        improvement_component = max(0, min(1.0, (m.improvement_rate + 1.0) / 2.0))
        knowledge_component = m.knowledge_reuse
        return improvement_component * 0.6 + knowledge_component * 0.4

    def get_stats(self) -> Dict[str, Any]:
        """Get overall fitness statistics."""
        all_scores = []
        for history in self._history.values():
            all_scores.extend(m.weighted_score for m in history)

        if not all_scores:
            return {"total_evaluations": 0}

        return {
            "total_evaluations": len(all_scores),
            "avg_fitness": sum(all_scores) / len(all_scores),
            "best_fitness": max(all_scores),
            "worst_fitness": min(all_scores),
            "agents_tracked": len(self._history),
        }
