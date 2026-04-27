#!/usr/bin/env python3
"""
EVOLUTIONARY TOOLS FOR NEXUS
============================

Core genetic algorithm tools for code evolution.
"""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from random import Random
from copy import deepcopy


# ============================================
# LLM CODE GENERATOR
# ============================================

class LLMCodeGenerator:
    """Generate code using Ollama."""
    
    def __init__(self, model: str = "qwen2.5-coder:14b"):
        self.model = model
        self._check_model()
    
    def _check_model(self):
        """Check if model is available."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                timeout=10,
                text=True
            )
            available = self.model in result.stdout
            if not available:
                print("Pulling " + self.model + "...")
                subprocess.run(
                    ["ollama", "pull", self.model],
                    capture_output=True,
                    timeout=300
                )
        except Exception as e:
            print("WARN: Ollama not available: " + str(e))
            self.model = None
    
    async def generate(self, intent: str, variation_hint: str = "", language: str = "python") -> Dict[str, str]:
        """Generate code for the given intent."""
        if not self.model:
            return {"main.py": "# Ollama not available\n# Intent: " + intent + "\n"}
        
        prompt = "Write " + language + " code for: " + intent
        
        try:
            code = await self._call_ollama(prompt)
            return self._parse_code(code, language)
        except Exception as e:
            print("ERR: LLM generation failed: " + str(e))
            return {"main.py": "# Generation failed: " + str(e) + "\n"}
    
    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama to generate code."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=120
            )
            
            if proc.returncode != 0:
                raise Exception(stderr.decode())
            
            return stdout.decode()
        except asyncio.TimeoutError:
            raise Exception("Timeout")
    
    def _parse_code(self, code: str, language: str) -> Dict[str, str]:
        """Parse code output into files."""
        files = {}
        lines = code.split('\n')
        current_file = "main.py"
        current_content = []
        
        for line in lines:
            file_match = re.match(r'# \*\*(\w+\.\w+)\*\*', line)
            if file_match:
                if current_content:
                    files[current_file] = '\n'.join(current_content)
                current_file = file_match.group(1)
                current_content = []
            else:
                current_content.append(line)
        
        if current_content:
            files[current_file] = '\n'.join(current_content)
        
        if not files:
            ext = ".py" if language == "python" else ".js"
            files["main" + ext] = code
        
        return files
    
    async def mutate(self, parent_code: Dict[str, str], mutation_type: str = "variation", language: str = "python") -> Dict[str, str]:
        """Generate a variation of parent code."""
        code_summary = '\n\n'.join([
            "# " + fname + "\n" + '\n'.join(content.split('\n')[:20])
            for fname, content in parent_code.items()
        ])
        
        prompts = {
            "variation": "Create a variation with different approach",
            "fix_bug": "Fix potential bugs and improve error handling",
            "improve": "Improve code quality and structure",
            "extend": "Extend functionality"
        }
        
        prompt = prompts.get(mutation_type, "Create variation") + "\n\nOriginal code:\n" + code_summary
        
        try:
            result = await self._call_ollama(prompt)
            return self._parse_code(result, language)
        except:
            return parent_code
    
    async def crossover(self, parent_a_code: Dict[str, str], parent_b_code: Dict[str, str], strategy: str = "merge") -> Dict[str, str]:
        """Combine code from two parents."""
        if strategy == "merge":
            result = {}
            result.update(parent_a_code)
            result.update(parent_b_code)
            return result
        
        prompt = "Combine these two codebases:\n\nCode A:\n" + json.dumps(parent_a_code) + "\n\nCode B:\n" + json.dumps(parent_b_code)
        
        try:
            result = await self._call_ollama(prompt)
            return self._parse_code(result, "python")
        except:
            result = {}
            result.update(parent_a_code)
            result.update(parent_b_code)
            return result


# ============================================
# EVOLUTION MEMORY
# ============================================

@dataclass
class EvolutionMemory:
    """Track evolution history and lineage."""
    intent: str
    started_at: float = field(default_factory=lambda: time.time())
    generations: List[Dict] = field(default_factory=list)
    best_solutions: List = field(default_factory=list)
    lineage: List = field(default_factory=list)
    
    def record_generation(self, generation: int, population: List, best):
        """Record a generation."""
        fitnesses = [s.total_fitness for s in population]
        
        self.generations.append({
            "generation": generation,
            "best_fitness": best.total_fitness,
            "avg_fitness": sum(fitnesses) / len(fitnesses),
            "timestamp": time.time()
        })
        
        self.best_solutions.append(best)
        for sol in population:
            for parent_id in sol.lineage:
                self.lineage.append((parent_id, sol.id))
    
    def get_best_ever(self):
        """Get the best solution across all generations."""
        if not self.best_solutions:
            return None
        return max(self.best_solutions, key=lambda s: s.total_fitness)


# ============================================
# SOLUTION SEED
# ============================================

@dataclass
class SolutionSeed:
    """A solution as a genetic blueprint."""
    id: str
    intent: str
    code: Dict[str, str]
    lineage: List[str] = field(default_factory=list)
    fitness: Dict[str, float] = field(default_factory=dict)
    total_fitness: float = 0.0
    created_at: float = field(default_factory=lambda: __import__('time').time())


# ============================================
# FITNESS SCORER
# ============================================

class FitnessScorer:
    """Multi-metric scoring."""
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "tests": 0.40,
            "lint": 0.15,
            "typecheck": 0.15,
            "coverage": 0.15,
            "complexity": 0.10,
            "duplicate": 0.05
        }
    
    async def score(self, solution: SolutionSeed, workspace: str = ".") -> Dict[str, float]:
        """Score a solution across all metrics."""
        scores = {}
        total = 0.0
        
        test_score = await self._score_tests_safe(solution.code)
        scores["tests"] = test_score
        total += test_score * self.weights["tests"]
        
        syntax_score = self._score_syntax(solution)
        scores["lint"] = syntax_score
        total += syntax_score * self.weights["lint"]
        
        type_score = self._score_type_safety(solution)
        scores["typecheck"] = type_score
        total += type_score * self.weights["typecheck"]
        
        cov_score = self._score_structure(solution)
        scores["coverage"] = cov_score
        total += cov_score * self.weights["coverage"]
        
        comp_score = self._score_complexity(solution)
        scores["complexity"] = comp_score
        total += comp_score * self.weights["complexity"]
        
        dup_score = self._score_duplicates(solution)
        scores["duplicate"] = dup_score
        total += dup_score * self.weights["duplicate"]
        
        return {"scores": scores, "total": total}
    
    async def _score_tests_safe(self, code: Dict[str, str]) -> float:
        """Check for test patterns in code."""
        total = 0.0
        for filepath, content in code.items():
            content_lower = content.lower()
            if 'test' in filepath.lower():
                total += 0.5
            if 'def test' in content_lower or 'class test' in content_lower:
                total += 0.3
            if 'assert' in content_lower or 'unittest' in content_lower:
                total += 0.2
        return min(1.0, total)
    
    def _score_syntax(self, solution: SolutionSeed) -> float:
        """Check basic Python syntax."""
        all_code = '\n'.join(solution.code.values())
        try:
            compile(all_code, '<string>', 'exec')
            return 1.0
        except SyntaxError:
            return 0.5
    
    def _score_type_safety(self, solution: SolutionSeed) -> float:
        """Check for type hints."""
        code = '\n'.join(solution.code.values())
        has_type_hints = ': int' in code or ': str' in code or ': float' in code
        has_annotations = '->' in code
        if has_type_hints and has_annotations:
            return 1.0
        elif has_type_hints or has_annotations:
            return 0.5
        return 0.2
    
    def _score_structure(self, solution: SolutionSeed) -> float:
        """Check code structure."""
        score = 0.0
        for filepath, content in solution.code.items():
            funcs = len([l for l in content.split('\n') if l.strip().startswith('def ') or l.strip().startswith('class ')])
            score += min(1.0, funcs * 0.2)
        return min(1.0, score)
    
    def _score_complexity(self, solution: SolutionSeed) -> float:
        """Score complexity - lower is better."""
        total_complexity = 0
        total_lines = 0
        
        for content in solution.code.values():
            branches = len(re.findall(r'\bif\b|\bfor\b|\bwhile\b|\band\b|\bor\b', content))
            total_complexity += branches
            total_lines += len(content.split('\n'))
        
        if total_lines == 0:
            return 0.0
        
        ratio = total_complexity / (total_lines / 100)
        return max(0.0, 1.0 - (ratio * 0.1))
    
    def _score_duplicates(self, solution: SolutionSeed) -> float:
        """Score duplicates - less is better."""
        all_content = '\n'.join(solution.code.values())
        lines = [l.strip() for l in all_content.split('\n') if l.strip()]
        
        if len(lines) < 10:
            return 1.0
        
        unique_lines = len(set(lines))
        dup_ratio = 1.0 - (unique_lines / len(lines))
        
        return max(0.0, 1.0 - dup_ratio)


# ============================================
# CODE CROSSOVER
# ============================================

class CodeCrossover:
    """Combine code from two solutions."""
    
    def crossover(self, parent_a: SolutionSeed, parent_b: SolutionSeed, strategy: str = "union", rng: Optional[Random] = None) -> SolutionSeed:
        """Breed two solutions to create a child."""
        if rng is None:
            rng = Random()
        
        child_id = "child_" + parent_a.id[:8] + "_" + parent_b.id[:8] + "_" + str(int(rng.random() * 10000))
        
        if strategy == "union":
            code = {}
            code.update(parent_a.code)
            code.update(parent_b.code)
        else:
            code = parent_a.code.copy()
        
        return SolutionSeed(
            id=child_id,
            intent=parent_a.intent,
            code=code,
            lineage=[parent_a.id, parent_b.id],
            fitness={},
            total_fitness=0.0
        )


# ============================================
# SOLUTION POPULATION
# ============================================

class SolutionPopulation:
    """Maintain N solution variants, evolve over generations."""
    
    def __init__(
        self,
        population_size: int = 20,
        elitism_count: int = 2,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        tournament_size: int = 3,
        max_generations: int = 100,
        convergence_threshold: float = 0.95,
        llm_model: str = "qwen2.5-coder:14b"
    ):
        self.population_size = population_size
        self.elitism_count = elitism_count
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.tournament_size = tournament_size
        self.max_generations = max_generations
        self.convergence_threshold = convergence_threshold
        
        self.scorer = FitnessScorer()
        self.crossover = CodeCrossover()
        self.rng = Random()
        self.llm = LLMCodeGenerator(llm_model)
        self.memory = None
        self.population = []
        self.generation = 0
        self.best_solution = None
        self.history = []
    
    async def evolve(self, intent: str, initial_code: Optional[Dict[str, str]] = None, workspace: str = ".") -> SolutionSeed:
        """Run LLM-powered evolution."""
        print()
        print("="*60)
        print("EVOLUTION STARTING (LLM-POWERED)")
        print("Intent: " + intent)
        print("Population: " + str(self.population_size))
        print("Max generations: " + str(self.max_generations))
        print("LLM: " + self.llm.model)
        print("="*60)
        print()
        
        self.memory = EvolutionMemory(intent)
        await self._init_population_llm(intent, initial_code)
        
        for gen in range(self.max_generations):
            self.generation = gen
            await self._evaluate_population(workspace)
            self.population.sort(key=lambda s: s.total_fitness, reverse=True)
            
            if self.population:
                self.best_solution = self.population[0]
                print("[Gen " + str(gen) + "] Best fitness: " + str(self.best_solution.total_fitness))
            
            if self.memory:
                self.memory.record_generation(gen, self.population, self.best_solution)
            
            if self.best_solution and self.best_solution.total_fitness >= self.convergence_threshold:
                print()
                print("="*60)
                print("CONVERGED at generation " + str(gen))
                print("Best solution: " + self.best_solution.id)
                print("Fitness: " + str(self.best_solution.total_fitness))
                print("="*60)
                break
            
            await self._next_generation_llm()
            
            self.history.append({
                "generation": gen,
                "best_fitness": self.best_solution.total_fitness if self.best_solution else 0
            })
        
        return self.best_solution or self.population[0] if self.population else None
    
    async def _init_population_llm(self, intent: str, initial_code: Optional[Dict[str, str]]):
        """Initialize population using LLM."""
        self.population = []
        
        print("Generating initial population...")
        
        base_code = initial_code or {"main.py": "# Solution for: " + intent + "\n"}
        
        for i in range(self.population_size):
            variation_hint = "Variation " + str(i+1) + "/" + str(self.population_size)
            
            try:
                code = await self.llm.generate(intent, variation_hint)
            except Exception as e:
                print("WARN: LLM failed: " + str(e))
                code = self._mutate_code(deepcopy(base_code), self.rng)
            
            solution = SolutionSeed(
                id="gen0_" + str(i).zfill(3),
                intent=intent,
                code=code,
                lineage=[],
                fitness={},
                total_fitness=0.0
            )
            self.population.append(solution)
            print("  Created variant " + str(i+1) + "/" + str(self.population_size))
    
    async def _next_generation_llm(self):
        """Create next generation using LLM."""
        new_pop = []
        
        self.population.sort(key=lambda s: s.total_fitness, reverse=True)
        new_pop.extend(self.population[:self.elitism_count])
        
        while len(new_pop) < self.population_size:
            tournament = self.rng.sample(
                self.population,
                min(self.tournament_size, len(self.population))
            )
            tournament.sort(key=lambda s: s.total_fitness, reverse=True)
            parent_a = tournament[0]
            
            if self.rng.random() < self.crossover_rate and len(self.population) > 1:
                tournament = self.rng.sample(
                    self.population,
                    min(self.tournament_size, len(self.population))
                )
                tournament.sort(key=lambda s: s.total_fitness, reverse=True)
                parent_b = tournament[0]
                
                try:
                    child_code = await self.llm.crossover(parent_a.code, parent_b.code, strategy="blend")
                    child_id = "gen" + str(self.generation+1) + "_x_" + parent_a.id[:8] + "_" + parent_b.id[:8]
                except:
                    child = self.crossover.crossover(parent_a, parent_b, rng=self.rng)
                    child_code = child.code
                    child_id = child.id
            else:
                mutation_types = ["variation", "fix_bug", "improve", "extend"]
                mutation = self.rng.choice(mutation_types)
                
                try:
                    child_code = await self.llm.mutate(parent_a.code, mutation_type=mutation)
                    child_id = "gen" + str(self.generation+1) + "_m_" + parent_a.id[:8]
                except:
                    child = self._mutate(parent_a)
                    child_code = child.code
                    child_id = child.id
            
            new_pop.append(SolutionSeed(
                id=child_id,
                intent=parent_a.intent,
                code=child_code,
                lineage=[parent_a.id],
                fitness={},
                total_fitness=0.0
            ))
        
        self.population = new_pop
    
    def _mutate_code(self, code: Dict[str, str], rng: Random) -> Dict[str, str]:
        """Mutate code with small variations."""
        result = {}
        
        for filepath, content in code.items():
            lines = content.split('\n')
            mutated = []
            
            for line in lines:
                if rng.random() < self.mutation_rate:
                    mutation_type = rng.randint(0, 3)
                    if mutation_type == 0:
                        mutated.append("# Variant mutation")
                    elif mutation_type == 1:
                        line = line.replace('if ', 'if not ')
                mutated.append(line)
            
            result[filepath] = '\n'.join(mutated)
        
        return result
    
    async def _evaluate_population(self, workspace: str):
        """Score all solutions."""
        for solution in self.population:
            if not solution.fitness:
                scores = await self.scorer.score(solution, workspace)
                solution.fitness = scores["scores"]
                solution.total_fitness = scores["total"]
    
    def _mutate(self, solution: SolutionSeed) -> SolutionSeed:
        """Mutate a single solution."""
        mutated_code = self._mutate_code(deepcopy(solution.code), self.rng)
        
        return SolutionSeed(
            id="gen" + str(self.generation + 1) + "_" + solution.id[:8] + "_" + str(self.rng.randint(0, 9999)),
            intent=solution.intent,
            code=mutated_code,
            lineage=[solution.id],
            fitness={},
            total_fitness=0.0
        )


# ============================================
# HELPER FUNCTIONS
# ============================================

def create_seed(intent: str, code: Dict[str, str], parent_ids: Optional[List[str]] = None) -> SolutionSeed:
    """Helper to create a solution seed."""
    content = json.dumps(code, sort_keys=True)
    seed_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    
    return SolutionSeed(
        id="seed_" + seed_hash,
        intent=intent,
        code=code,
        lineage=parent_ids or [],
        fitness={},
        total_fitness=0.0
    )


async def quick_fitness(code: Dict[str, str], intent: str = "", workspace: str = ".") -> float:
    """Quick single-solution fitness check."""
    seed = create_seed(intent, code)
    scorer = FitnessScorer()
    scores = await scorer.score(seed, workspace)
    return scores["total"]


# ============================================
# CLI ENTRY POINT
# ============================================

async def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python evolutionary_tools.py <intent> [code_file]")
        sys.exit(1)

    intent = sys.argv[1]

    initial_code = {}
    if len(sys.argv) > 2:
        code_path = Path(sys.argv[2])
        if code_path.is_file():
            initial_code = {code_path.name: code_path.read_text()}

    pop = SolutionPopulation(population_size=10, max_generations=20)
    best = await pop.evolve(intent, initial_code)

    if best:
        print()
        print("="*60)
        print("EVOLUTION COMPLETE")
        print("Best solution: " + best.id)
        print("Fitness: " + str(best.total_fitness))
        print("Scores: " + str(best.fitness))
        print()
        print("Code:")
        for filepath, content in best.code.items():
            print()
            print("--- " + filepath + " ---")
            print(content[:500])
        print("="*60)


if __name__ == "__main__":
    asyncio.run(main())