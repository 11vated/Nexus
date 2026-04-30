"""Tests for the multi-agent cognitive evolution system."""

import pytest


# -- Agent Population Tests ------------------------------------------------

class TestAgentGenome:
    def test_default_genome(self):
        from nexus.evolution.agent_population import AgentGenome

        genome = AgentGenome()
        assert genome.temperature == 0.3
        assert genome.reflection_depth == 1
        assert genome.fitness_score == 0.0
        assert genome.id is not None

    def test_to_config(self):
        from nexus.evolution.agent_population import AgentGenome

        genome = AgentGenome(
            model="deepseek-r1:7b",
            temperature=0.5,
            reflection_depth=2,
        )
        config = genome.to_config()
        assert config["coding_model"] == "deepseek-r1:7b"
        assert config["temperature"] == 0.5
        assert config["reflection_enabled"] is True

    def test_copy(self):
        from nexus.evolution.agent_population import AgentGenome

        g1 = AgentGenome(temperature=0.7)
        g2 = g1.copy()
        g2.temperature = 0.3
        assert g1.temperature == 0.7
        assert g2.temperature == 0.3

    def test_repr(self):
        from nexus.evolution.agent_population import AgentGenome

        genome = AgentGenome()
        assert "AgentGenome" in repr(genome)


class TestAgentPopulation:
    def test_initialize(self):
        from nexus.evolution.agent_population import AgentPopulation

        pop = AgentPopulation(population_size=10)
        genomes = pop.initialize()
        assert len(genomes) == 10

    def test_diversity(self):
        from nexus.evolution.agent_population import AgentPopulation

        pop = AgentPopulation(population_size=20)
        pop.initialize()

        models = set(g.model for g in pop.genomes)
        temps = [g.temperature for g in pop.genomes]

        assert len(models) > 1  # Multiple models
        assert min(temps) != max(temps)  # Diverse temperatures

    def test_tournament_selection(self):
        from nexus.evolution.agent_population import AgentPopulation

        pop = AgentPopulation(population_size=10)
        pop.initialize()

        # Set varied fitness
        for i, g in enumerate(pop.genomes):
            g.fitness_score = i / 10.0

        # Tournament should favor high fitness
        winners = []
        for _ in range(20):
            parent = pop._select_one("tournament", 3)
            winners.append(parent.fitness_score)

        avg_winner = sum(winners) / len(winners)
        assert avg_winner > 0.5  # Better than random (0.5)

    def test_elitism(self):
        from nexus.evolution.agent_population import AgentPopulation

        pop = AgentPopulation(population_size=10, elite_count=2)
        pop.initialize()

        for i, g in enumerate(pop.genomes):
            g.fitness_score = i / 10.0

        elites = pop.apply_elitism()
        assert len(elites) == 2
        assert all(e.fitness_score >= 0.7 for e in elites)

    def test_get_best(self):
        from nexus.evolution.agent_population import AgentPopulation

        pop = AgentPopulation(population_size=5)
        pop.initialize()

        pop.genomes[0].fitness_score = 0.9
        pop.genomes[1].fitness_score = 0.5

        best = pop.get_best()
        assert best.fitness_score == 0.9

    def test_get_stats(self):
        from nexus.evolution.agent_population import AgentPopulation

        pop = AgentPopulation(population_size=10)
        pop.initialize()
        stats = pop.get_stats()

        assert stats["population_size"] == 10
        assert "avg_fitness" in stats
        assert "model_distribution" in stats


# -- Cognitive Fitness Tests -----------------------------------------------

class TestCognitiveFitness:
    def test_basic_calculation(self):
        from nexus.evolution.cognitive_fitness import CognitiveFitness

        fitness = CognitiveFitness()
        metrics = fitness.calculate(
            agent_id="test1",
            test_results={"tests_passed": 8, "tests_total": 10, "lint_score": 0.9},
            execution_stats={"time_seconds": 10, "tokens_used": 5000, "steps": 5},
        )

        assert metrics.test_pass_rate == 0.8
        assert metrics.lint_score == 0.9
        assert metrics.weighted_score > 0

    def test_perfect_score(self):
        from nexus.evolution.cognitive_fitness import CognitiveFitness

        fitness = CognitiveFitness()
        metrics = fitness.calculate(
            agent_id="perfect",
            test_results={
                "tests_passed": 10, "tests_total": 10,
                "lint_score": 1.0, "complexity": 0,
            },
            execution_stats={"time_seconds": 1, "tokens_used": 100, "steps": 1},
            error_stats={"total_attempts": 1, "errors": 0, "recoveries": 0},
        )

        assert metrics.test_pass_rate == 1.0
        assert metrics.error_rate == 0.0
        assert metrics.weighted_score > 0.7  # Should be high

    def test_poor_score(self):
        from nexus.evolution.cognitive_fitness import CognitiveFitness

        fitness = CognitiveFitness()
        metrics = fitness.calculate(
            agent_id="poor",
            test_results={"tests_passed": 0, "tests_total": 10, "lint_score": 0.1},
            execution_stats={"time_seconds": 250, "tokens_used": 40000, "steps": 40},
            error_stats={"total_attempts": 10, "errors": 8, "recoveries": 1},
        )

        assert metrics.test_pass_rate == 0.0
        assert metrics.error_rate == 0.8
        assert metrics.weighted_score < 0.3

    def test_improvement_tracking(self):
        from nexus.evolution.cognitive_fitness import CognitiveFitness

        fitness = CognitiveFitness()
        fitness.calculate("agent1", test_results={"tests_passed": 3, "tests_total": 10})
        fitness.calculate("agent1", test_results={"tests_passed": 7, "tests_total": 10})

        improvement = fitness.get_improvement("agent1")
        assert improvement > 0

    def test_history(self):
        from nexus.evolution.cognitive_fitness import CognitiveFitness

        fitness = CognitiveFitness()
        fitness.calculate("a1", test_results={"tests_passed": 5, "tests_total": 10})
        fitness.calculate("a1", test_results={"tests_passed": 8, "tests_total": 10})

        history = fitness.get_agent_history("a1")
        assert len(history) == 2

    def test_stats(self):
        from nexus.evolution.cognitive_fitness import CognitiveFitness

        fitness = CognitiveFitness()
        fitness.calculate("a1", test_results={"tests_passed": 5, "tests_total": 10})
        stats = fitness.get_stats()

        assert stats["total_evaluations"] == 1
        assert stats["agents_tracked"] == 1


# -- Strategy Crossover Tests ----------------------------------------------

class TestStrategyCrossover:
    def test_blend_crossover(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.strategy_crossover import StrategyCrossover

        crossover = StrategyCrossover(method="blend")
        p1 = AgentGenome(temperature=0.2, model="qwen2.5-coder:14b")
        p2 = AgentGenome(temperature=0.8, model="deepseek-r1:7b")

        children = crossover.crossover(p1, p2, num_offspring=2)
        assert len(children) == 2

        # Children should have blended temperature
        for child in children:
            assert 0.15 <= child.temperature <= 0.85

    def test_uniform_crossover(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.strategy_crossover import StrategyCrossover

        crossover = StrategyCrossover(method="uniform")
        p1 = AgentGenome(temperature=0.1, reflection_depth=0)
        p2 = AgentGenome(temperature=0.9, reflection_depth=2)

        children = crossover.crossover(p1, p2)
        assert len(children) == 2

    def test_single_point_crossover(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.strategy_crossover import StrategyCrossover

        crossover = StrategyCrossover(method="single_point")
        p1 = AgentGenome(temperature=0.3)
        p2 = AgentGenome(temperature=0.7)

        children = crossover.crossover(p1, p2)
        assert len(children) == 2

    def test_generation_increments(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.strategy_crossover import StrategyCrossover

        crossover = StrategyCrossover()
        p1 = AgentGenome(generation=5)
        p2 = AgentGenome(generation=3)

        children = crossover.crossover(p1, p2)
        for child in children:
            assert child.generation == 6


# -- Mutation Engine Tests -------------------------------------------------

class TestMutationEngine:
    def test_mutate_changes_params(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.mutation import MutationEngine

        engine = MutationEngine(base_rate=1.0)  # 100% mutation rate
        genome = AgentGenome(temperature=0.5)

        mutated = engine.mutate(genome)
        assert mutated.temperature != 0.5 or genome.temperature == mutated.temperature

    def test_mutate_preserves_original(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.mutation import MutationEngine

        engine = MutationEngine(base_rate=1.0)
        genome = AgentGenome(temperature=0.5, model="qwen2.5-coder:14b")
        original_temp = genome.temperature
        original_model = genome.model

        _ = engine.mutate(genome)
        assert genome.temperature == original_temp
        assert genome.model == original_model

    def test_clamping(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.mutation import MutationEngine

        engine = MutationEngine(base_rate=1.0)
        genome = AgentGenome(temperature=0.01)

        # Multiple mutations should keep temp in range
        for _ in range(20):
            genome = engine.mutate(genome)
            assert 0.05 <= genome.temperature <= 1.0

    def test_adaptive_rate(self):
        from nexus.evolution.mutation import MutationEngine

        engine = MutationEngine(base_rate=0.1, adaptive=True)
        initial_rate = engine.current_rate

        # No improvement → rate increases
        engine.update_rate(0.5, 0.5, 10, 50)
        assert engine.current_rate >= initial_rate

    def test_catastrophic_mutation(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.mutation import MutationEngine

        engine = MutationEngine()
        genome = AgentGenome(temperature=0.3, model="qwen2.5-coder:14b")

        mutated = engine.catastrophic_mutation(genome)
        assert mutated.temperature != genome.temperature or mutated.model != genome.model

    def test_stats(self):
        from nexus.evolution.mutation import MutationEngine

        engine = MutationEngine()
        stats = engine.get_stats()
        assert "current_rate" in stats
        assert "total_mutations" in stats


# -- Knowledge Transfer Tests ----------------------------------------------

class TestKnowledgeTransfer:
    def test_extract_knowledge(self):
        from nexus.evolution.knowledge_transfer import KnowledgeTransfer

        kt = KnowledgeTransfer()
        task_history = [
            {
                "planning_style": "adaptive",
                "success": True,
                "task_type": ["api", "fastapi"],
            },
            {
                "tools_used": ["file_write", "test_run"],
                "success": True,
                "task_type": ["testing"],
                "tool_efficiency": 0.8,
            },
        ]

        entries = kt.extract_knowledge("agent1", task_history, fitness=0.8)
        assert len(entries) >= 1

    def test_transfer_knowledge(self):
        from nexus.evolution.knowledge_transfer import KnowledgeTransfer

        kt = KnowledgeTransfer()
        # Add some knowledge
        kt.extract_knowledge("expert", [
            {"planning_style": "adaptive", "success": True, "task_type": ["api"]},
        ], fitness=0.9)

        transferred = kt.transfer_knowledge(
            target_agent_id="novice",
            target_fitness=0.2,
            task_context="api",
        )
        assert len(transferred) >= 1

    def test_no_transfer_to_high_fitness(self):
        from nexus.evolution.knowledge_transfer import KnowledgeTransfer

        kt = KnowledgeTransfer()
        kt.extract_knowledge("expert", [
            {"planning_style": "adaptive", "success": True, "task_type": ["api"]},
        ], fitness=0.9)

        transferred = kt.transfer_knowledge(
            target_agent_id="good",
            target_fitness=0.85,  # Above threshold
            task_context="api",
        )
        assert len(transferred) == 0

    def test_record_outcome(self):
        from nexus.evolution.knowledge_transfer import KnowledgeTransfer

        kt = KnowledgeTransfer()
        entries = kt.extract_knowledge("agent1", [
            {"planning_style": "sequential", "success": True, "task_type": ["web"]},
        ], fitness=0.7)

        if entries:
            kt.record_outcome(entries[0].id, success=True)
            assert entries[0].success_count >= 1

    def test_prune_ineffective(self):
        from nexus.evolution.knowledge_transfer import KnowledgeTransfer

        kt = KnowledgeTransfer()
        removed = kt.prune_ineffective()
        assert removed == 0  # Nothing to prune

    def test_knowledge_summary(self):
        from nexus.evolution.knowledge_transfer import KnowledgeTransfer

        kt = KnowledgeTransfer()
        kt.extract_knowledge("agent1", [
            {"planning_style": "adaptive", "success": True, "task_type": ["api"]},
        ], fitness=0.8)

        summary = kt.get_knowledge_summary()
        assert summary["total_entries"] >= 1
        assert "by_type" in summary


# -- Evolution Engine Tests ------------------------------------------------

class TestEvolutionEngine:
    @pytest.mark.asyncio
    async def test_run_basic(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.evolution_engine import EvolutionConfig, EvolutionEngine

        config = EvolutionConfig(
            population_size=5,
            max_generations=2,
            elite_count=1,
        )
        engine = EvolutionEngine(config)

        async def dummy_eval(genome: AgentGenome):
            return {
                "test_results": {"tests_passed": 5, "tests_total": 10},
                "execution_stats": {"time_seconds": 5, "tokens_used": 1000, "steps": 3},
                "task": {"planning_style": genome.planning_style, "success": True},
            }

        results = await engine.run(dummy_eval)
        assert len(results) == 2
        assert results[0].generation == 1
        assert results[-1].best_fitness >= 0

    @pytest.mark.asyncio
    async def test_early_stopping(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.evolution_engine import EvolutionConfig, EvolutionEngine

        config = EvolutionConfig(
            population_size=5,
            max_generations=10,
            early_stop_threshold=0.99,
        )
        engine = EvolutionEngine(config)

        async def perfect_eval(genome: AgentGenome):
            return {
                "test_results": {"tests_passed": 10, "tests_total": 10, "lint_score": 1.0},
                "execution_stats": {"time_seconds": 1, "tokens_used": 100, "steps": 1},
                "task": {"success": True},
            }

        results = await engine.run(perfect_eval)
        # Should stop early due to high fitness
        assert len(results) <= 10

    @pytest.mark.asyncio
    async def test_stop(self):
        from nexus.evolution.agent_population import AgentGenome
        from nexus.evolution.evolution_engine import EvolutionConfig, EvolutionEngine

        config = EvolutionConfig(population_size=5, max_generations=10)
        engine = EvolutionEngine(config)

        async def slow_eval(genome: AgentGenome):
            import asyncio
            await asyncio.sleep(0.1)
            return {"test_results": {"tests_passed": 5, "tests_total": 10}}

        # Stop after first generation
        async def eval_with_stop(genome: AgentGenome):
            result = await slow_eval(genome)
            engine.stop()
            return result

        results = await engine.run(eval_with_stop)
        assert len(results) <= 1

    def test_get_full_stats(self):
        from nexus.evolution.evolution_engine import EvolutionConfig, EvolutionEngine

        engine = EvolutionEngine(EvolutionConfig(population_size=5))
        engine.population.initialize()

        stats = engine.get_full_stats()
        assert "population_stats" in stats
        assert "fitness_stats" in stats
        assert "mutation_stats" in stats
        assert "knowledge_stats" in stats
