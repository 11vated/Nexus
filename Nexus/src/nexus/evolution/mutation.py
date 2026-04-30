"""Mutation engine — introduces variation into agent genomes.

Applies controlled random changes to genomes:
- Gaussian mutation for continuous parameters
- Random reset for discrete parameters
- Adaptive mutation rate (decreases as fitness improves)
- Catastrophic mutation (random restart for stuck populations)
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

from nexus.evolution.agent_population import AgentGenome

logger = logging.getLogger(__name__)


# Mutation ranges for continuous parameters
MUTATION_RANGES = {
    "temperature": (-0.2, 0.2),
    "context_window_ratio": (-0.15, 0.15),
    "memory_recall_depth": (-2, 2),
}

# Possible values for discrete parameters
DISCRETE_OPTIONS = {
    "model": [
        "qwen2.5-coder:14b",
        "qwen2.5-coder:7b",
        "deepseek-r1:7b",
        "codellama:13b",
    ],
    "planning_style": ["sequential", "parallel", "adaptive"],
    "reflection_depth": [0, 1, 2],
    "max_retries": [1, 2, 3, 5],
    "max_tokens": [2048, 4096, 8192],
    "retry_on_failure": [True, False],
}


class MutationEngine:
    """Applies mutations to agent genomes.

    Adaptive mutation rate:
    - High rate early in evolution (exploration)
    - Low rate as population converges (exploitation)
    - Catastrophic mutation if population is stuck
    """

    def __init__(
        self,
        base_rate: float = 0.15,
        min_rate: float = 0.02,
        max_rate: float = 0.50,
        adaptive: bool = True,
    ):
        self.base_rate = base_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.adaptive = adaptive
        self._current_rate = base_rate
        self._mutation_count = 0
        self._no_improvement_generations = 0

    def mutate(self, genome: AgentGenome) -> AgentGenome:
        """Apply mutation to a genome.

        Args:
            genome: The genome to mutate.

        Returns:
            New mutated genome (original is not modified).
        """
        child = genome.copy()
        mutated_params = []

        # Mutate continuous parameters
        for param, (low, high) in MUTATION_RANGES.items():
            if random.random() < self._current_rate:
                current = getattr(child, param)
                delta = random.uniform(low, high)
                new_value = current + delta

                # Clamp to valid range
                if param == "temperature":
                    new_value = max(0.05, min(1.0, new_value))
                elif param == "context_window_ratio":
                    new_value = max(0.3, min(0.95, new_value))
                elif param == "memory_recall_depth":
                    new_value = max(1, min(10, int(new_value)))

                setattr(child, param, new_value)
                mutated_params.append(param)

        # Mutate discrete parameters
        for param, options in DISCRETE_OPTIONS.items():
            if random.random() < self._current_rate * 0.5:  # Lower rate for discrete
                setattr(child, param, random.choice(options))
                mutated_params.append(param)

        # Mutate tool weights
        for tool in child.tool_weights:
            if random.random() < self._current_rate:
                child.tool_weights[tool] *= random.uniform(0.7, 1.3)
                child.tool_weights[tool] = max(0.1, min(2.0, child.tool_weights[tool]))
                mutated_params.append(f"weight:{tool}")

        if mutated_params:
            self._mutation_count += 1
            logger.debug(
                "Mutated %s: %d params changed (%s)",
                child.id, len(mutated_params), ", ".join(mutated_params[:5]),
            )

        return child

    def catastrophic_mutation(self, genome: AgentGenome) -> AgentGenome:
        """Apply extreme mutation — essentially a random restart.

        Used when the population is stuck in a local optimum.
        """
        child = genome.copy()

        # Randomize all continuous parameters
        for param in MUTATION_RANGES:
            low, high = MUTATION_RANGES[param]
            mid = (low + high) / 2
            current = getattr(child, param)
            child.__dict__[param] = current + random.uniform(-high * 2, high * 2)

        # Clamp
        child.temperature = max(0.05, min(1.0, child.temperature))
        child.context_window_ratio = max(0.3, min(0.95, child.context_window_ratio))
        child.memory_recall_depth = max(1, min(10, int(child.memory_recall_depth)))

        # Randomize discrete parameters
        for param, options in DISCRETE_OPTIONS.items():
            child.__dict__[param] = random.choice(options)

        # Randomize tool weights
        for tool in child.tool_weights:
            child.tool_weights[tool] = random.uniform(0.3, 2.0)

        self._mutation_count += 1
        logger.info("Catastrophic mutation applied to %s", child.id)
        return child

    def update_rate(
        self,
        best_fitness: float,
        prev_best: float,
        generation: int,
        total_generations: int,
    ) -> None:
        """Adaptively adjust the mutation rate.

        Args:
            best_fitness: Current best fitness.
            prev_best: Previous generation's best fitness.
            generation: Current generation number.
            total_generations: Total planned generations.
        """
        if not self.adaptive:
            return

        # Track improvement
        if best_fitness <= prev_best:
            self._no_improvement_generations += 1
        else:
            self._no_improvement_generations = 0

        # Increase rate if stuck (exploration)
        if self._no_improvement_generations > 5:
            self._current_rate = min(
                self.max_rate,
                self._current_rate * 1.2,
            )
            logger.info(
                "No improvement for %d generations, increasing mutation rate to %.3f",
                self._no_improvement_generations, self._current_rate,
            )

        # Decrease rate as we progress (exploitation)
        else:
            progress = generation / max(total_generations, 1)
            target_rate = self.max_rate - (self.max_rate - self.min_rate) * progress
            self._current_rate = self._current_rate * 0.9 + target_rate * 0.1

    def should_catastrophic_mutate(
        self,
        fitness_history: List[float],
        threshold_generations: int = 10,
    ) -> bool:
        """Check if the population is stuck and needs catastrophic mutation."""
        if len(fitness_history) < threshold_generations:
            return False

        recent = fitness_history[-threshold_generations:]
        improvement = recent[-1] - recent[0]
        return improvement < 0.01  # Less than 1% improvement

    @property
    def current_rate(self) -> float:
        return self._current_rate

    @property
    def mutation_count(self) -> int:
        return self._mutation_count

    def get_stats(self) -> Dict[str, Any]:
        return {
            "current_rate": self._current_rate,
            "total_mutations": self._mutation_count,
            "no_improvement_generations": self._no_improvement_generations,
            "adaptive": self.adaptive,
        }
