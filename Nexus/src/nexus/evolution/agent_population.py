"""Agent genome and population management.

Each agent variant is represented as a genome — a set of configurable
parameters that determine its behavior. The population manages selection,
survival, and breeding.
"""

from __future__ import annotations

import copy
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AgentGenome:
    """A single agent's configurable parameters.

    The genome encodes:
    - LLM parameters (temperature, model, max_tokens)
    - Strategy parameters (reflection depth, planning style)
    - Tool preferences (which tools to prioritize)
    - Memory parameters (context window size, recall depth)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    generation: int = 0

    # LLM parameters
    model: str = "qwen2.5-coder:14b"
    temperature: float = 0.3
    max_tokens: int = 4096

    # Strategy parameters
    reflection_depth: int = 1  # 0=none, 1=single, 2=multi-level
    planning_style: str = "sequential"  # sequential, parallel, adaptive
    retry_on_failure: bool = True
    max_retries: int = 3

    # Tool preferences
    tool_weights: Dict[str, float] = field(default_factory=dict)

    # Memory parameters
    context_window_ratio: float = 0.7  # How much of context to use
    memory_recall_depth: int = 3  # How many past memories to recall

    # Fitness tracking
    fitness_score: float = 0.0
    task_history: List[Dict[str, Any]] = field(default_factory=list)
    age: int = 0  # Number of generations survived

    def to_config(self) -> Dict[str, Any]:
        """Convert genome to AgentConfig-compatible dict."""
        return {
            "coding_model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "reflection_enabled": self.reflection_depth > 0,
            "max_retries": self.max_retries,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert genome to a full dictionary."""
        return {
            "id": self.id,
            "generation": self.generation,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "reflection_depth": self.reflection_depth,
            "planning_style": self.planning_style,
            "retry_on_failure": self.retry_on_failure,
            "max_retries": self.max_retries,
            "tool_weights": self.tool_weights,
            "context_window_ratio": self.context_window_ratio,
            "memory_recall_depth": self.memory_recall_depth,
            "fitness_score": self.fitness_score,
            "age": self.age,
        }

    def copy(self) -> "AgentGenome":
        """Create a deep copy of this genome."""
        return copy.deepcopy(self)

    def __repr__(self) -> str:
        return (
            f"<AgentGenome {self.id} gen={self.generation} "
            f"fitness={self.fitness_score:.3f} age={self.age}>"
        )


class AgentPopulation:
    """Manages a population of agent genomes.

    Handles:
    - Population initialization with diverse genomes
    - Selection (tournament, roulette, elitism)
    - Survival of the fittest
    - Generational replacement
    """

    def __init__(
        self,
        population_size: int = 20,
        elite_count: int = 2,
        model_pool: Optional[List[str]] = None,
    ):
        self.population_size = population_size
        self.elite_count = elite_count
        self.model_pool = model_pool or [
            "qwen2.5-coder:14b",
            "qwen2.5-coder:7b",
            "deepseek-r1:7b",
        ]
        self._population: List[AgentGenome] = []
        self._generation = 0
        self._best_fitness = 0.0
        self._fitness_history: List[float] = []

    def initialize(self) -> List[AgentGenome]:
        """Create an initial diverse population.

        Returns:
            List of randomly initialized genomes.
        """
        self._population = []
        for _ in range(self.population_size):
            genome = self._create_random_genome()
            self._population.append(genome)

        logger.info(
            "Initialized population: %d agents, %d models",
            len(self._population), len(self.model_pool),
        )
        return self._population

    def select_parents(
        self,
        method: str = "tournament",
        tournament_size: int = 3,
    ) -> Tuple[AgentGenome, AgentGenome]:
        """Select two parents for breeding.

        Args:
            method: Selection method ('tournament', 'roulette', 'rank').
            tournament_size: Number of candidates for tournament selection.

        Returns:
            Two parent genomes.
        """
        parent1 = self._select_one(method, tournament_size)
        parent2 = self._select_one(method, tournament_size)
        while parent2.id == parent1.id and len(self._population) > 1:
            parent2 = self._select_one(method, tournament_size)
        return parent1, parent2

    def _select_one(self, method: str, tournament_size: int) -> AgentGenome:
        """Select a single individual."""
        if method == "tournament":
            candidates = random.sample(
                self._population,
                min(tournament_size, len(self._population)),
            )
            return max(candidates, key=lambda g: g.fitness_score)

        elif method == "roulette":
            total_fitness = sum(g.fitness_score for g in self._population)
            if total_fitness <= 0:
                return random.choice(self._population)
            threshold = random.uniform(0, total_fitness)
            cumulative = 0.0
            for genome in self._population:
                cumulative += genome.fitness_score
                if cumulative >= threshold:
                    return genome
            return self._population[-1]

        elif method == "rank":
            sorted_pop = sorted(self._population, key=lambda g: g.fitness_score)
            # Linear rank selection
            n = len(sorted_pop)
            rank_weights = [(i + 1) / (n * (n + 1) / 2) for i in range(n)]
            chosen = random.choices(sorted_pop, weights=rank_weights, k=1)[0]
            return chosen

        return random.choice(self._population)

    def apply_elitism(self) -> List[AgentGenome]:
        """Select the elite genomes to survive to the next generation.

        Returns:
            List of elite genomes.
        """
        sorted_pop = sorted(
            self._population, key=lambda g: g.fitness_score, reverse=True,
        )
        elites = sorted_pop[:self.elite_count]

        # Increment age for elites
        for elite in elites:
            elite.age += 1

        return elites

    def replace_generation(
        self,
        offspring: List[AgentGenome],
        elites: Optional[List[AgentGenome]] = None,
    ) -> List[AgentGenome]:
        """Replace the current generation with offspring + elites.

        Args:
            offspring: New genomes from breeding.
            elites: Genomes to preserve from current generation.

        Returns:
            New population.
        """
        self._generation += 1

        new_population = []

        # Add elites first
        if elites:
            new_population.extend(elites)

        # Fill remaining slots with offspring
        for child in offspring:
            child.generation = self._generation
            new_population.append(child)
            if len(new_population) >= self.population_size:
                break

        # Trim to population size
        self._population = new_population[:self.population_size]

        # Update best fitness
        if self._population:
            current_best = max(g.fitness_score for g in self._population)
            self._best_fitness = max(self._best_fitness, current_best)
            self._fitness_history.append(self._best_fitness)

        logger.info(
            "Generation %d: %d agents, best fitness: %.3f",
            self._generation, len(self._population), self._best_fitness,
        )
        return self._population

    def get_best(self) -> Optional[AgentGenome]:
        """Get the highest-fitness genome in the population."""
        if not self._population:
            return None
        return max(self._population, key=lambda g: g.fitness_score)

    def get_top_n(self, n: int = 5) -> List[AgentGenome]:
        """Get the top N genomes by fitness."""
        sorted_pop = sorted(
            self._population, key=lambda g: g.fitness_score, reverse=True,
        )
        return sorted_pop[:n]

    def _create_random_genome(self) -> AgentGenome:
        """Create a genome with randomized parameters."""
        return AgentGenome(
            generation=self._generation,
            model=random.choice(self.model_pool),
            temperature=random.uniform(0.1, 0.8),
            max_tokens=random.choice([2048, 4096, 8192]),
            reflection_depth=random.randint(0, 2),
            planning_style=random.choice(["sequential", "parallel", "adaptive"]),
            retry_on_failure=random.choice([True, False]),
            max_retries=random.randint(1, 5),
            context_window_ratio=random.uniform(0.5, 0.9),
            memory_recall_depth=random.randint(1, 5),
            tool_weights={
                "file_write": random.uniform(0.5, 1.5),
                "shell": random.uniform(0.5, 1.5),
                "test_run": random.uniform(0.5, 1.5),
            },
        )

    @property
    def genomes(self) -> List[AgentGenome]:
        return list(self._population)

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def best_fitness(self) -> float:
        return self._best_fitness

    @property
    def fitness_history(self) -> List[float]:
        return list(self._fitness_history)

    def get_stats(self) -> Dict[str, Any]:
        """Get population statistics."""
        if not self._population:
            return {"population_size": 0}

        scores = [g.fitness_score for g in self._population]
        ages = [g.age for g in self._population]
        models = {}
        for g in self._population:
            models[g.model] = models.get(g.model, 0) + 1

        return {
            "population_size": len(self._population),
            "generation": self._generation,
            "best_fitness": self._best_fitness,
            "avg_fitness": sum(scores) / len(scores),
            "min_fitness": min(scores),
            "max_fitness": max(scores),
            "avg_age": sum(ages) / len(ages),
            "model_distribution": models,
            "fitness_history_length": len(self._fitness_history),
        }
