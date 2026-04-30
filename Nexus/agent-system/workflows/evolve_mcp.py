import json
import subprocess
import os
import random
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class Individual:
    genes: Dict
    fitness: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class EvolveMCP:
    def __init__(self, 
                 model: str = "ollama/qwen2.5-coder:14b",
                 population_size: int = 5,
                 mutation_rate: float = 0.1):
        self.model = model
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.population: List[Individual] = []
        self.best_genome = None
        self.generation = 0
        self.history = []
    
    def initialize(self, base_prompts: List[Dict]) -> List[Individual]:
        for genes in base_prompts:
            individual = Individual(genes=genes)
            self.population.append(individual)
        
        return self.population
    
    def mutate(self, genes: Dict) -> Dict:
        mutation_types = ["temperature", "system_prompt", "tool_order", "max_retries", "context_window"]
        
        mutated = genes.copy()
        
        if random.random() < self.mutation_rate:
            key = random.choice(list(genes.keys()))
            
            if key in ["temperature", "max_retries", "context_window"]:
                if isinstance(genes[key], (int, float)):
                    mutated[key] = max(0.0, genes[key] + random.uniform(-0.1, 0.1))
            else:
                mutated[key] = f"{genes[key]}_mutated_{self.generation}"
        
        return mutated
    
    def crossover(self, parent1: Dict, parent2: Dict) -> Dict:
        child = {}
        all_keys = list(set(list(parent1.keys()) + list(parent2.keys())))
        
        for key in all_keys:
            if random.random() < 0.5:
                child[key] = parent1.get(key, parent2.get(key))
            else:
                child[key] = parent2.get(key, parent1.get(key))
        
        return child
    
    def evaluate(self, individual: Individual, test_task: str, test_cases: List[str]) -> float:
        prompt = f"""Evaluate this prompt configuration for a coding task.

Task: {test_task}
Config: {json.dumps(individual.genes)}

Test cases to pass:
{chr(10).join(f"- {tc}" for tc in test_cases)}

Rate the config from 0-1 based on how well it would handle this task.
Output ONLY a JSON object: {{"score": 0.0-1.0, "reason": "brief explanation"}}
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            output = result.stdout.strip()
            data = json.loads(output.strip("`").strip("json"))
            return data.get("score", 0.5)
        except:
            return 0.5
    
    def evolve(self, test_task: str, test_cases: List[str], generations: int = 3) -> Dict:
        if not self.population:
            self.initialize([{"temperature": 0.3, "max_retries": 3}])
        
        for gen in range(generations):
            self.generation = gen
            print(f"\n[EVO] Generation {gen+1}/{generations}")
            
            scores = []
            for i, individual in enumerate(self.population):
                fitness = self.evaluate(individual, test_task, test_cases)
                individual.fitness = fitness
                scores.append(fitness)
                print(f"  [{i}] fitness: {fitness:.2f}")
            
            best_idx = max(range(len(scores)), key=lambda i: scores[i])
            self.best_genome = self.population[best_idx].genes
            
            new_population = []
            
            parents = sorted(self.population, key=lambda x: x.fitness, reverse=True)[:2]
            
            for i in range(self.population_size):
                if i < len(parents):
                    new_population.append(parents[i])
                else:
                    child_genes = self.mutate(random.choice(parents).genes)
                    new_population.append(Individual(genes=child_genes))
            
            self.population = new_population
            
            self.history.append({
                "generation": gen,
                "best_fitness": max(scores),
                "avg_fitness": sum(scores) / len(scores),
                "best_genes": self.best_genome
            })
        
        return {
            "best_genome": self.best_genome,
            "generations": generations,
            "history": self.history
        }
    
    def get_fitness_explanation(self, genome: Dict) -> str:
        return f"Optimized genome from {self.generation} generations"


class SelfImprovingAgent:
    def __init__(self, model: str = "ollama/qwen2.5-coder:14b"):
        self.model = model
        self.evolver = EvolveMCP(model=model)
        self.performance_history = []
        self.improvements = []
    
    def analyze_failure(self, task: str, error: str) -> Dict:
        prompt = f"""Analyze this failure to suggest improvements.

Task: {task}
Error: {error}

What specifically went wrong and how would you fix the agent's configuration?
Output JSON: {{"root_cause": "...", "fix_suggestion": "...", "config_change": {{}}}}"
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return json.loads(result.stdout.strip("`").strip("json"))
        except:
            return {"root_cause": "unknown", "fix_suggestion": "review logs", "config_change": {}}
    
    def improve_from_feedback(self, task: str, result: Dict) -> Dict:
        if result.get("status") == "success":
            return {"action": "none", "improvement": "already working"}
        
        error = result.get("error", "unknown error")
        analysis = self.analyze_failure(task, error)
        
        self.improvements.append({
            "task": task,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "action": "config_update",
            "changes": analysis.get("config_change", {}),
            "reason": analysis.get("root_cause", "")
        }
    
    def learn_from_success(self, task: str, result: Dict) -> Dict:
        prompt = f"""Analyze this successful task and extract lessons.

Task: {task}
Result: {result}

What worked well? How could the agent be improved for future similar tasks?
Output JSON: {{"lessons": [...], "improvements": [...]}}
"""
        
        try:
            result_text = subprocess.run(
                f'ollama run {self.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return json.loads(result_text.stdout.strip("`").strip("json"))
        except:
            return {"lessons": [], "improvements": []}
    
    def run_evolution_cycle(self, test_tasks: List[Dict], test_cases: List[List[str]]) -> Dict:
        results = []
        
        for task_data, cases in zip(test_tasks, test_cases):
            result = self.evolver.evolve(
                test_task=task_data.get("task", ""),
                test_cases=cases,
                generations=2
            )
            results.append(result)
        
        best = max(results, key=lambda x: x.get("history", [{}])[0].get("best_fitness", 0))
        
        return {
            "evolved_config": best.get("best_genome"),
            "results": results
        }


class PromptOptimizer:
    def __init__(self, model: str = "ollama/qwen2.5-coder:14b"):
        self.model = model
    
    def optimize(self, base_prompt: str, examples: List[Dict]) -> str:
        examples_text = json.dumps(examples[:3], indent=2)
        
        prompt = f"""Optimize this system prompt based on real conversation history.

Current prompt:
{base_prompt}

Examples from history:
{examples_text}

Provide an improved version that would:
1. Be more specific about tool usage
2. Handle edge cases better
3. Reduce token waste
4. Improve success rate

Output ONLY the optimized prompt, no explanations.
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return result.stdout.strip()
        except:
            return base_prompt
    
    def analyze_prompt_weaknesses(self, prompt: str) -> List[str]:
        prompt_analysis = f"""Analyze this prompt for weaknesses.

{prompt}

List specific weaknesses as JSON array.
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.model} "{prompt_analysis}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return json.loads(result.stdout.strip("`").strip("json"))
        except:
            return []


def create_evolver(model: str = "ollama/qwen2.5-coder:14b") -> EvolveMCP:
    return EvolveMCP(model=model)


def create_self_improving_agent(model: str = "ollama/qwen2.5-coder:14b") -> SelfImprovingAgent:
    return SelfImprovingAgent(model=model)