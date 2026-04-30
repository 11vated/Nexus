"""Evolution Engine — orchestrates the full evolutionary cycle.

Coordinates:
1. Population management
2. Fitness evaluation
3. Selection, crossover, and mutation
4. Knowledge transfer
5. Generational replacement
6. Convergence detection
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

from nexus.evolution.agent_population import AgentGenome, AgentPopulation
from nexus.evolution.cognitive_fitness import CognitiveFitness, FitnessMetrics
from nexus.evolution.knowledge_transfer import KnowledgeTransfer
from nexus.evolution.mutation import MutationEngine
from nexus.evolution.strategy_crossover import StrategyCrossover

logger = logging.getLogger(__name__)


@dataclass
class EvolutionConfig:
    population_size: int = 20
    elite_count: int = 2
    max_generations: int = 50
    crossover_method: str = "blend"
    base_mutation_rate: float = 0.15
    knowledge_transfer: bool = True
    early_stop_threshold: float = 0.95  # Stop if fitness exceeds this
    early_stop_patience: int = 10  # Generations with no improvement
    evaluation_timeout: float = 300.0  # Max seconds per agent evaluation


@dataclass
class GenerationResult:
    generation: int
    best_fitness: float
    avg_fitness: float
    best_genome: AgentGenome
    improvements: List[str] = field(default_factory=list)


class EvolutionEngine:
    """Main evolution orchestrator.

    Runs a generational evolutionary loop:
    1. Evaluate each agent's fitness on coding tasks
    2. Select parents using tournament selection
    3. Breed offspring via crossover
    4. Apply mutations
    5. Transfer knowledge from top performers
    6. Replace generation with elites + offspring
    7. Check convergence criteria

    Usage:
        engine = EvolutionEngine(config)
        results = await engine.run(evaluate_fn)
    """

    def __init__(self, config: Optional[EvolutionConfig] = None):
        self.config = config or EvolutionConfig()
        self.population = AgentPopulation(
            population_size=self.config.population_size,
            elite_count=self.config.elite_count,
        )
        self.fitness = CognitiveFitness()
        self.crossover = StrategyCrossover(method=self.config.crossover_method)
        self.mutation = MutationEngine(base_rate=self.config.base_mutation_rate)
        self.knowledge = KnowledgeTransfer()

        self._results: List[GenerationResult] = []
        self._is_running = False
        self._start_time: float = 0

    async def run(
        self,
        evaluate_fn: Callable[[AgentGenome], Coroutine[Any, Any, Dict[str, Any]]],
        callback: Optional[Callable[[GenerationResult], None]] = None,
    ) -> List[GenerationResult]:
        """Run the full evolutionary process.

        Args:
            evaluate_fn: Async function that evaluates an agent genome.
                Takes AgentGenome, returns dict with test_results, execution_stats, etc.
            callback: Optional function called after each generation.

        Returns:
            List of GenerationResult for each generation.
        """
        self._is_running = True
        self._start_time = time.time()

        # Initialize population
        self.population.initialize()
        logger.info(
            "Starting evolution: %d agents, %d generations max",
            self.config.population_size, self.config.max_generations,
        )

        for gen in range(self.config.max_generations):
            if not self._is_running:
                logger.info("Evolution stopped by user")
                break

            # Phase 1: Evaluate all agents
            logger.info("=== Generation %d / %d ===", gen + 1, self.config.max_generations)
            await self._evaluate_population(evaluate_fn)

            # Phase 2: Extract knowledge from top performers
            if self.config.knowledge_transfer:
                top_agents = self.population.get_top_n(3)
                for agent in top_agents:
                    if agent.task_history:
                        self.knowledge.extract_knowledge(
                            agent_id=agent.id,
                            task_history=agent.task_history,
                            fitness=agent.fitness_score,
                        )

            # Phase 3: Selection and breeding
            offspring = []
            num_offspring = self.config.population_size - self.config.elite_count
            for _ in range((num_offspring + 1) // 2):
                parent1, parent2 = self.population.select_parents()
                children = self.crossover.crossover(parent1, parent2)
                offspring.extend(children)

            # Phase 4: Mutation
            mutated_offspring = [self.mutation.mutate(child) for child in offspring]

            # Phase 5: Knowledge transfer to offspring
            if self.config.knowledge_transfer:
                for child in mutated_offspring:
                    transferred = self.knowledge.transfer_knowledge(
                        target_agent_id=child.id,
                        target_fitness=0.0,  # New agent, no fitness yet
                    )
                    if transferred:
                        child.task_history.append({
                            "knowledge_transferred": [e.id for e in transferred],
                        })

            # Phase 6: Elitism and replacement
            elites = self.population.apply_elitism()
            self.population.replace_generation(mutated_offspring, elites)

            # Phase 7: Update mutation rate
            prev_best = self._results[-1].best_fitness if self._results else 0
            self.mutation.update_rate(
                best_fitness=self.population.best_fitness,
                prev_best=prev_best,
                generation=gen + 1,
                total_generations=self.config.max_generations,
            )

            # Phase 8: Check catastrophic mutation
            if self.mutation.should_catastrophic_mutate(
                self.population.fitness_history,
            ):
                logger.info("Population stuck — applying catastrophic mutation")
                worst = min(
                    self.population.genomes, key=lambda g: g.fitness_score,
                )
                idx = self.population.genomes.index(worst)
                self.population._population[idx] = self.mutation.catastrophic_mutation(
                    worst,
                )

            # Build generation result
            best = self.population.get_best()
            result = GenerationResult(
                generation=gen + 1,
                best_fitness=self.population.best_fitness,
                avg_fitness=sum(
                    g.fitness_score for g in self.population.genomes
                ) / len(self.population.genomes),
                best_genome=best.copy() if best else None,
                improvements=self._get_improvements(gen),
            )
            self._results.append(result)

            if callback:
                callback(result)

            logger.info(
                "Gen %d: best=%.3f, avg=%.3f, mutations=%d",
                gen + 1, result.best_fitness, result.avg_fitness,
                self.mutation.mutation_count,
            )

            # Early stopping
            if result.best_fitness >= self.config.early_stop_threshold:
                logger.info(
                    "Early stop: fitness %.3f >= %.3f",
                    result.best_fitness, self.config.early_stop_threshold,
                )
                break

            if self._check_convergence():
                logger.info("Early stop: population converged")
                break

        self._is_running = False
        elapsed = time.time() - self._start_time
        logger.info(
            "Evolution complete: %d generations in %.1fs, best fitness: %.3f",
            len(self._results), elapsed, self.population.best_fitness,
        )

        # Prune ineffective knowledge
        self.knowledge.prune_ineffective()

        return self._results

    def stop(self) -> None:
        """Stop the evolutionary process."""
        self._is_running = False

    async def _evaluate_population(
        self,
        evaluate_fn: Callable[[AgentGenome], Coroutine[Any, Any, Dict[str, Any]]],
    ) -> None:
        """Evaluate all agents in the population."""
        for genome in self.population.genomes:
            try:
                results = await asyncio.wait_for(
                    evaluate_fn(genome),
                    timeout=self.config.evaluation_timeout,
                )

                metrics = self.fitness.calculate(
                    agent_id=genome.id,
                    test_results=results.get("test_results"),
                    execution_stats=results.get("execution_stats"),
                    error_stats=results.get("error_stats"),
                    learning_stats=results.get("learning_stats"),
                )

                genome.fitness_score = metrics.weighted_score
                if results.get("task"):
                    genome.task_history.append(results["task"])

            except asyncio.TimeoutError:
                logger.warning("Evaluation timeout for agent %s", genome.id)
                genome.fitness_score = 0.0
            except Exception as exc:
                logger.error("Evaluation error for agent %s: %s", genome.id, exc)
                genome.fitness_score = 0.0

    def _get_improvements(self, gen: int) -> List[str]:
        """Get improvements from the previous generation."""
        if gen == 0:
            return []

        prev = self._results[-1] if self._results else None
        if not prev:
            return []

        current_best = self.population.best_fitness
        if current_best > prev.best_fitness:
            return [
                f"Best fitness: {prev.best_fitness:.3f} → {current_best:.3f}"
            ]
        return []

    def _check_convergence(self) -> bool:
        """Check if the population has converged."""
        if len(self.population.fitness_history) < self.config.early_stop_patience:
            return False

        recent = self.population.fitness_history[-self.config.early_stop_patience:]
        variance = sum((x - recent[-1]) ** 2 for x in recent) / len(recent)
        return variance < 0.0001  # Very low variance = converged

    @property
    def results(self) -> List[GenerationResult]:
        return list(self._results)

    @property
    def best_genome(self) -> Optional[AgentGenome]:
        return self.population.get_best()

    def get_full_stats(self) -> Dict[str, Any]:
        """Get comprehensive evolution statistics."""
        return {
            "population_stats": self.population.get_stats(),
            "fitness_stats": self.fitness.get_stats(),
            "mutation_stats": self.mutation.get_stats(),
            "knowledge_stats": self.knowledge.get_knowledge_summary(),
            "generations_completed": len(self._results),
            "best_genome": (
                self.population.get_best().to_dict()
                if self.population.get_best()
                else None
            ),
            "elapsed_seconds": time.time() - self._start_time if self._start_time else 0,
        }
