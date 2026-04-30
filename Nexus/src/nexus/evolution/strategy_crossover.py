"""Strategy crossover — genetic recombination of agent genomes.

Combines two parent genomes to produce offspring with mixed traits:
- Single-point crossover
- Multi-point crossover
- Uniform crossover
- Blend crossover (for continuous parameters)
"""

from __future__ import annotations

import copy
import logging
import random
import uuid
from typing import Any, Dict, List, Tuple

from nexus.evolution.agent_population import AgentGenome

logger = logging.getLogger(__name__)

# Continuous parameters that should be blended, not swapped
CONTINUOUS_PARAMS = {
    "temperature",
    "context_window_ratio",
    "memory_recall_depth",
}

# Discrete parameters that should be swapped
DISCRETE_PARAMS = {
    "model",
    "planning_style",
    "reflection_depth",
    "retry_on_failure",
    "max_retries",
    "max_tokens",
}


class StrategyCrossover:
    """Combines parent genomes to produce offspring.

    Supports multiple crossover strategies:
    - single_point: Split genome at a random point
    - multi_point: Split at multiple points
    - uniform: Randomly select from each parent per gene
    - blend: Average continuous parameters, swap discrete ones
    """

    def __init__(self, method: str = "blend"):
        self.method = method

    def crossover(
        self,
        parent1: AgentGenome,
        parent2: AgentGenome,
        num_offspring: int = 2,
    ) -> List[AgentGenome]:
        """Produce offspring from two parents.

        Args:
            parent1: First parent genome.
            parent2: Second parent genome.
            num_offspring: Number of children to produce.

        Returns:
            List of new offspring genomes.
        """
        offspring = []
        for _ in range(num_offspring):
            if self.method == "single_point":
                child = self._single_point_crossover(parent1, parent2)
            elif self.method == "multi_point":
                child = self._multi_point_crossover(parent1, parent2)
            elif self.method == "uniform":
                child = self._uniform_crossover(parent1, parent2)
            elif self.method == "blend":
                child = self._blend_crossover(parent1, parent2)
            else:
                child = self._blend_crossover(parent1, parent2)

            child.id = str(uuid.uuid4())[:8]
            child.generation = max(parent1.generation, parent2.generation) + 1
            child.fitness_score = 0.0
            child.task_history = []
            child.age = 0
            offspring.append(child)

        logger.info(
            "Crossover (%s): %s + %s → %d offspring",
            self.method, parent1.id, parent2.id, len(offspring),
        )
        return offspring

    def _single_point_crossover(
        self, p1: AgentGenome, p2: AgentGenome,
    ) -> AgentGenome:
        """Single-point crossover: split parameter list at random point."""
        all_params = list(CONTINUOUS_PARAMS | DISCRETE_PARAMS)
        split_point = random.randint(1, len(all_params) - 1)

        child = p1.copy()
        for i, param in enumerate(all_params):
            if i >= split_point:
                setattr(child, param, getattr(p2, param))

        # Blend tool weights
        child.tool_weights = self._blend_weights(
            p1.tool_weights, p2.tool_weights,
        )
        return child

    def _multi_point_crossover(
        self, p1: AgentGenome, p2: AgentGenome,
    ) -> AgentGenome:
        """Multi-point crossover: 3 random crossover points."""
        all_params = list(CONTINUOUS_PARAMS | DISCRETE_PARAMS)
        num_points = min(3, len(all_params) - 1)
        points = sorted(random.sample(range(1, len(all_params)), num_points))
        points = [0] + points + [len(all_params)]

        child = p1.copy()
        for segment in range(len(points) - 1):
            start, end = points[segment], points[segment + 1]
            if segment % 2 == 1:
                for i in range(start, end):
                    setattr(child, all_params[i], getattr(p2, all_params[i]))

        child.tool_weights = self._blend_weights(
            p1.tool_weights, p2.tool_weights, alpha=random.random(),
        )
        return child

    def _uniform_crossover(
        self, p1: AgentGenome, p2: AgentGenome,
    ) -> AgentGenome:
        """Uniform crossover: randomly select each gene from either parent."""
        all_params = CONTINUOUS_PARAMS | DISCRETE_PARAMS
        child = p1.copy()

        for param in all_params:
            if random.random() < 0.5:
                setattr(child, param, getattr(p2, param))

        child.tool_weights = self._blend_weights(
            p1.tool_weights, p2.tool_weights, alpha=random.random(),
        )
        return child

    def _blend_crossover(
        self, p1: AgentGenome, p2: AgentGenome,
    ) -> AgentGenome:
        """Blend crossover: average continuous params, swap discrete ones.

        This is the recommended method for agent genomes because:
        - Continuous params (temperature) benefit from averaging
        - Discrete params (model, planning_style) need clear choices
        """
        child = AgentGenome()

        # Blend continuous parameters
        for param in CONTINUOUS_PARAMS:
            v1 = getattr(p1, param)
            v2 = getattr(p2, param)
            alpha = random.random()
            blended = v1 * alpha + v2 * (1 - alpha)

            # Type preservation
            if isinstance(v1, int):
                blended = round(blended)
            setattr(child, param, blended)

        # Swap discrete parameters
        for param in DISCRETE_PARAMS:
            if random.random() < 0.5:
                setattr(child, param, getattr(p1, param))
            else:
                setattr(child, param, getattr(p2, param))

        # Blend tool weights
        child.tool_weights = self._blend_weights(
            p1.tool_weights, p2.tool_weights, alpha=random.random(),
        )

        return child

    @staticmethod
    def _blend_weights(
        w1: Dict[str, float],
        w2: Dict[str, float],
        alpha: float = 0.5,
    ) -> Dict[str, float]:
        """Blend two weight dictionaries."""
        all_keys = set(w1.keys()) | set(w2.keys())
        blended = {}
        for key in all_keys:
            v1 = w1.get(key, 1.0)
            v2 = w2.get(key, 1.0)
            blended[key] = v1 * alpha + v2 * (1 - alpha)
        return blended
