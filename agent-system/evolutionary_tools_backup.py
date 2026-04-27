"""
#!/usr/bin/env python3
"""
EVOLUTIONARY TOOLS FOR NEXUS
=========================

Core genetic algorithm tools inspired by Paradigm GSPL:

1. SolutionPopulation - Maintain N solution variants in parallel
2. FitnessScorer - Multi-metric scoring
3. CodeCrossover - Combine code from solutions
4. LLMCodeGenerator - Generate code using Ollama
5. EvolutionMemory - Track history and lineage

These transform the feedback loop from:
    TRY -> FAIL -> TRY AGAIN
Into:
    EVOLVE -> SELECT -> BREED (LLM-powered)

Models supported: All Ollama models (see model_registry.py)
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
# ALL AVAILABLE MODELS (for full capabilities)
# ============================================

ALL_MODELS = [
    # Code generation
    "qwen2.5-coder:14b",
    "qwen2.5-coder:7b", 
    "codellama",
    "deepseek-r1:7b",
    "deepseek-r1:1.5b",
    
    # User requested
    "gpt-5-nano",
    "minimax-max-m2.5-free",
    "bigpickle",
    "ling-2.6-flash-free",
    "hy3-preview-free",
    "nemotron-super-3b",
    "bartowski/llama-3.2-1b-instruct-q4_k_m",
    
    # Vision
    "llava",
    "moondream",
    "dolphin-mistral",
]


# ============================================
# LLM CODE GENERATOR
# ============================================

class LLMCodeGenerator:
    """
    Generate code using Ollama.
    
    Uses local Ollama models to generate code variations.
    Supports ALL available models.
    """
    
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
                # Try to pull
                print(f"Pulling {self.model}...")
                subprocess.run(
                    ["ollama", "pull", self.model],
                    capture_output=True,
                    timeout=300
                )
        except Exception as e:
            print(f"WARN: Ollama not available: {e}")
            self.model = None
    
    async def generate(
        self, 
        intent: str, 
        variation_hint: str = "",
        language: str = "python"
    ) -> Dict[str, str]:
        """
        Generate code for the given intent.
        
        Args:
            intent: What the code should do
            variation_hint: How this should differ from parent
            language: Programming language
        
        Returns:
            {filename: code}
        """
        if not self.model:
            return {"main.py": f"# Ollama not available\n# Intent: {intent}\n"}
        
        # Build prompt
        prompt = self._build_prompt(intent, variation_hint, language)
        
        try:
            code = await self._call_ollama(prompt)
            return self._parse_code(code, language)
        except Exception as e:
            print(f"ERR: LLM generation failed: {e}")
            return {"main.py": f"# Generation failed: {e}\n"}
    
    def _build_prompt(self, intent: str, variation_hint: str, language: str) -> str:
        """Build the prompt for code generation."""
        if variation_hint:
            hint = f"\nVariation hint: {variation_hint}"
        else:
            hint = ""
        
        return f"""Write {language} code for: {intent}{hint}

Requirements:
- Clean, well-structured code
- Include type hints
- Handle errors gracefully
- Return ONLY the code, no explanations
- Use standard naming conventions

Code:"""
    
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
        
        # Try to detect file boundaries
        # Look for filename comments or common patterns
        lines = code.split('\n')
        current_file = "main.py"
        current_content = []
        
        for line in lines:
            # Detect file header
            file_match = re.match(r'# (?:\*\*)?(\w+\.\w+)(?:\*\*)?', line)
            if file_match:
                # Save previous file
                if current_content:
                    files[current_file] = '\n'.join(current_content)
                current_file = file_match.group(1)
                current_content = []
            else:
                current_content.append(line)
        
        # Save last file
        if current_content:
            files[current_file] = '\n'.join(current_content)
        
        # If no files detected, use default
        if not files:
            ext = ".py" if language == "python" else ".js"
            files["main" + ext] = code
        
        return files
    
    async def mutate(
        self, 
        parent_code: Dict[str, str], 
        mutation_type: str = "variation",
        language: str = "python"
    ) -> Dict[str, str]:
        """
        Generate a variation of parent code.
        
        mutation_type: "variation", "fix_bug", "improve", "extend"
        """
        # Build code summary
        file_summaries = []
        for fname, content in parent_code.items():
            lines = content.split('\n')
            summary = f"# {fname}\n" + '\n'.join(lines[:20])
            if len(lines) > 20:
                summary += f"\n# ... ({len(lines)} lines total)"
            file_summaries.append(summary)
        
        code_summary = '\n\n'.join(file_summaries)
        
        mutation_prompts = {
            "variation": "Create a variation with different approach",
            "fix_bug": "Fix potential bugs and improve error handling",
            "improve": "Improve code quality and structure",
            "extend": "Extend functionality"
        }
        
        prompt = f"""{mutation_prompts.get(mutation_type, 'Create variation')}

Original code:
{code_summary}

Requirements:
- {mutation_type} the code while keeping core functionality
- Keep same file structure
- Clean, well-structured code

Code:"""
        
        try:
            result = await self._call_ollama(prompt)
            return self._parse_code(result, language)
        except:
            return parent_code  # Fallback to parent
    
    async def crossover(
        self,
        parent_a_code: Dict[str, str],
        parent_b_code: Dict[str, str],
        strategy: str = "merge"
    ) -> Dict[str, str]:
        """
        Combine code from two parents.
        
        strategy: "merge" (take all files), "blend" (combine shared files)
        """
        if strategy == "merge":
            result = {}
            result.update(parent_a_code)
            result.update(parent_b_code)
            return result
        
        # For blend, we need LLM to intelligently combine
        prompt = f"""Combine these two codebases into one working solution:

Code A:
{json.dumps(parent_a_code, indent=2)}

Code B:
{json.dumps(parent_b_code, indent=2)}

Merge strategy: Take best functions from both, resolve conflicts.
Keep both files if they have different purposes.
Return ONLY the merged code, no explanations.

Merged code:"""
        
        try:
            result = await self._call_ollama(prompt)
            return self._parse_code(result, "python")
        except:
            # Fallback to merge
            result = {}
            result.update(parent_a_code)
            result.update(parent_b_code)
            return result


# ============================================
# EVOLUTION MEMORY (NEW)
# ============================================

@dataclass
class EvolutionMemory:
    """
    Track evolution history and lineage.
    
    Stores:
    - generations: fitness per generation
    - best_solutions: archived best per generation
    - lineage: parent-child relationships
    """
    intent: str
    started_at: float = field(default_factory=lambda: time.time())
    generations: List[Dict] = field(default_factory=list)
    best_solutions: List[SolutionSeed] = field(default_factory=list)
    lineage: List[Tuple[str, str]] = field(default_factory=list)  # (parent, child)
    
    def record_generation(
        self, 
        generation: int, 
        population: List[SolutionSeed],
        best: SolutionSeed
    ):
        """Record a generation."""
        fitnesses = [s.total_fitness for s in population]
        
        self.generations.append({
            "generation": generation,
            "best_fitness": best.total_fitness,
            "avg_fitness": sum(fitnesses) / len(fitnesses),
            "min_fitness": min(fitnesses),
            "max_fitness": max(fitnesses),
            "population_size": len(population),
            "timestamp": time.time()
        })
        
        self.best_solutions.append(best)
        
        # Record lineage
        for sol in population:
            for parent_id in sol.lineage:
                self.lineage.append((parent_id, sol.id))
    
    def get_best_ever(self) -> Optional[SolutionSeed]:
        """Get the best solution across all generations."""
        if not self.best_solutions:
            return None
        return max(self.best_solutions, key=lambda s: s.total_fitness)
    
    def get_stats(self) -> Dict:
        """Get evolution statistics."""
        if not self.generations:
            return {"status": "no data"}
        
        return {
            "intents": self.intent,
            "total_generations": len(self.generations),
            "best_fitness_ever": max(g["best_fitness"] for g in self.generations),
            "avg_fitness_final": self.generations[-1]["avg_fitness"],
            "converged": any(g["best_fitness"] >= 0.95 for g in self.generations),
            "duration_seconds": time.time() - self.started_at
        }
    
    def save(self, path: str):
        """Save memory to file."""
        data = {
            "intent": self.intent,
            "started_at": self.started_at,
            "generations": self.generations,
            "best_solutions": [
                {"id": s.id, "fitness": s.total_fitness, "lineage": s.lineage}
                for s in self.best_solutions
            ],
            "lineage": self.lineage
        }
        Path(path).write_text(json.dumps(data, indent=2))
    
    def load(self, path: str):
        """Load memory from file."""
        data = json.loads(Path(path).read_text())
        self.intent = data.get("intent", "")
        self.started_at = data.get("started_at", time.time())
        self.generations = data.get("generations", [])
        self.lineage = data.get("lineage", [])


# ============================================
# SOLUTION SEED
# ============================================

@dataclass
class SolutionSeed:
    """
    A solution as a genetic blueprint.
    
    Instead of file contains code - it is solution HAS genes:
    - intent: what we are solving
    - code: filepath -> content 
    - lineage: parent solution IDs
    - fitness: scores per metric
    """
    id: str
    intent: str
    code: Dict[str, str]  # filepath -> content
    lineage: List[str] = field(default_factory=list)
    fitness: Dict[str, float] = field(default_factory=dict)
    total_fitness: float = 0.0
    created_at: float = field(default_factory=lambda: __import__('time').time())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "intent": self.intent,
            "code": self.code,
            "lineage": self.lineage,
            "fitness": self.fitness,
            "total_fitness": self.total_fitness,
            "created_at": self.created_at
        }


# ============================================
# FITNESS SCORER
# ============================================

class FitnessScorer:
    """
    Multi-metric scoring beyond pass/fail.
    
    Metrics:
    - tests: test pass rate (0-1)
    - lint: lint passes (0-1)
    - typecheck: typecheck passes (0-1)
    - coverage: code coverage (0-1)
    - complexity: lower is better (0-1, penalty)
    - duplicate: less dupes = better (0-1)
    
    Weighted combination: total = sum(weight * score)
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "tests": 0.40,      # 40% - tests are primary
            "lint": 0.15,       # 15% - code quality
            "typecheck": 0.15,  # 15% - type safety
            "coverage": 0.15,   # 15% - coverage
            "complexity": 0.10, # 10% - penalty for complexity
            "duplicate": 0.05   # 5% - penalty for dupes
        }
    
    async def score(self, solution: SolutionSeed, workspace: str = ".") -> Dict[str, float]:
        """
        Score a solution across all metrics.
        Returns dict of per-metric scores and total fitness.
        
        Falls back to syntactic scoring if external tools not available.
        """
        scores = {}
        total = 0.0
        
        # 1. Test score (fallback: check for test patterns in code)
        test_score = await self._score_tests_safe(solution.code)
        scores["tests"] = test_score
        total += test_score * self.weights["tests"]
        
        # 2. Syntax score (instead of lint)
        syntax_score = self._score_syntax(solution)
        scores["lint"] = syntax_score
        total += syntax_score * self.weights["lint"]
        
        # 3. Type safety (fallback)
        type_score = self._score_type_safety(solution)
        scores["typecheck"] = type_score
        total += type_score * self.weights["typecheck"]
        
        # 4. Coverage (fallback to structure check)
        cov_score = self._score_structure(solution)
        scores["coverage"] = cov_score
        total += cov_score * self.weights["coverage"]
        
        # 5. Complexity penalty
        comp_score = self._score_complexity(solution)
        scores["complexity"] = comp_score
        total += comp_score * self.weights["complexity"]
        
        # 6. Duplicate penalty
        dup_score = self._score_duplicates(solution)
        scores["duplicate"] = dup_score
        total += dup_score * self.weights["duplicate"]
        
        return {"scores": scores, "total": total}
    
    async def _score_tests_safe(self, code: Dict[str, str]) -> float:
        """Check for test patterns in code (no external tools)."""
        total = 0.0
        for filepath, content in code.items():
            content_lower = content.lower()
            # Check for test patterns
            if 'test' in filepath.lower():
                total += 0.5
            if 'def test' in content_lower or 'class test' in content_lower:
                total += 0.3
            if 'assert' in content_lower or 'unittest' in content_lower:
                total += 0.2
        return min(1.0, total)
    
    def _score_syntax(self, solution: SolutionSeed) -> float:
        """Check basic Python/JS syntax."""
        all_code = '\n'.join(solution.code.values())
        try:
            compile(all_code, '<string>', 'exec')
            return 1.0
        except SyntaxError:
            # Count error lines
            error_lines = len([l for l in all_code.split('\n') if '>>>' in l or '<<<' in l])
            if error_lines > 0:
                return max(0.0, 1.0 - error_lines * 0.1)
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
            # Has functions/classes
            funcs = len([l for l in content.split('\n') if l.strip().startswith('def ') or l.strip().startswith('class ')])
            score += min(1.0, funcs * 0.2)
        return min(1.0, score)
        # Write solution files first
        for filepath, content in solution.code.items():
            path = Path(workspace) / filepath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        
        # Try to run tests
        for test_cmd in [["pytest"], ["npm", "test"], ["npm", "run", "test:unit"], ["python", "-m", "pytest"]]:
            try:
                result = subprocess.run(
                    test_cmd,
                    cwd=workspace,
                    capture_output=True,
                    timeout=120,
                    text=True
                )
                if result.returncode == 0:
                    return 1.0
                # Parse output for pass/fail ratio
                output = result.stdout + result.stderr
                passed = len(re.findall(r'PASSED|passed|[OK]', output))
                failed = len(re.findall(r'FAILED|failed|[FAIL]', output))
                total = passed + failed
                if total > 0:
                    return passed / total
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        return 0.0
    
    async def _score_lint(self, solution: SolutionSeed, workspace: str) -> float:
        """Run linter."""
        for filepath in solution.code.keys():
            if not filepath.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
                continue
            
            path = Path(workspace) / filepath
            if not path.exists():
                continue
            
            for lint_cmd in [["pylint", str(path)], ["eslint", str(path)], ["tsc", "--noEmit"]]:
                try:
                    result = subprocess.run(
                        lint_cmd[:1] + lint_cmd[1:],
                        cwd=workspace,
                        capture_output=True,
                        timeout=60,
                        text=True
                    )
                    if result.returncode == 0:
                        return 1.0
                    errors = len(re.findall(r'error\b', result.stderr + result.stdout))
                    warnings = len(re.findall(r'warning\b', result.stderr + result.stdout))
                    if errors + warnings == 0:
                        return 1.0
                    # Penalize by severity
                    return max(0.0, 1.0 - (errors * 0.1) - (warnings * 0.02))
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
        
        return 0.0
    
    async def _score_typecheck(self, solution: SolutionSeed, workspace: str) -> float:
        """Run type checker."""
        for filepath in solution.code.keys():
            if not filepath.endswith(('.py', '.ts', '.tsx')):
                continue
                
            for type_cmd in [["mypy", filepath], ["tsc", "--noEmit", filepath]]:
                try:
                    result = subprocess.run(
                        type_cmd,
                        cwd=workspace,
                        capture_output=True,
                        timeout=60,
                        text=True
                    )
                    if result.returncode == 0:
                        return 1.0
                    errors = len(re.findall(r'error:', result.stderr))
                    if errors == 0:
                        return 1.0
                    return max(0.0, 1.0 - errors * 0.1)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
        
        return 0.0
    
    async def _score_coverage(self, solution: SolutionSeed, workspace: str) -> float:
        """Run coverage."""
        for cov_cmd in [["pytest", "--cov", ".", "--cov-report=term"], ["npm", "run", "test:coverage"]]:
            try:
                result = subprocess.run(
                    cov_cmd,
                    cwd=workspace,
                    capture_output=True,
                    timeout=120,
                    text=True
                )
                # Parse coverage percentage
                match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', result.stdout + result.stderr)
                if match:
                    return int(match.group(1)) / 100.0
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        return 0.0
    
    def _score_complexity(self, solution: SolutionSeed) -> float:
        """Score complexity - lower is better (penalty style)."""
        total_complexity = 0
        total_lines = 0
        
        for content in solution.code.values():
            # Simple cyclomatic complexity proxy: count branches
            branches = len(re.findall(r'\bif\b|\bfor\b|\bwhile\b|\band\b|\bor\b', content))
            total_complexity += branches
            total_lines += len(content.split('\n'))
        
        if total_lines == 0:
            return 0.0
        
        # Normalize: aim for <10 complexity per 100 lines
        ratio = total_complexity / (total_lines / 100)
        return max(0.0, 1.0 - (ratio * 0.1))
    
    def _score_duplicates(self, solution: SolutionSeed) -> float:
        """Score duplicates - less is better (penalty style)."""
        all_content = '\n'.join(solution.code.values())
        lines = [l.strip() for l in all_content.split('\n') if l.strip()]
        
        if len(lines) < 10:
            return 1.0
        
        # Simple duplicate detection
        unique_lines = len(set(lines))
        dup_ratio = 1.0 - (unique_lines / len(lines))
        
        return max(0.0, 1.0 - dup_ratio)


# ============================================
# CODE CROSSOVER
# ============================================

class CodeCrossover:
    """
    Combine code from two solutions.
    
    Strategies:
    -.one_point: take file structure from one parent, content from others
    - blend: line-by-line blending for shared files
    - union: keep all files from both
    """
    
    def crossover(
        self, 
        parent_a: SolutionSeed, 
        parent_b: SolutionSeed,
        strategy: str = "union",
        rng: Optional[Random] = None
    ) -> SolutionSeed:
        """Breed two solutions to create a child."""
        if rng is None:
            rng = Random()
        
        child_id = f"child_{parent_a.id[:8]}_{parent_b.id[:8]}_{int(rng.random() * 10000)}"
        
        if strategy == "union":
            return self._union_crossover(parent_a, parent_b, child_id, rng)
        elif strategy == "one_point":
            return self._one_point_crossover(parent_a, parent_b, child_id, rng)
        elif strategy == "blend":
            return self._blend_crossover(parent_a, parent_b, child_id, rng)
        else:
            return self._union_crossover(parent_a, parent_b, child_id, rng)
    
    def _union_crossover(
        self, 
        parent_a: SolutionSeed, 
        parent_b: SolutionSeed,
        child_id: str,
        rng: Random
    ) -> SolutionSeed:
        """Take all files from both parents."""
        code = {}
        code.update(parent_a.code)
        code.update(parent_b.code)
        
        return SolutionSeed(
            id=child_id,
            intent=parent_a.intent,
            code=code,
            lineage=[parent_a.id, parent_b.id],
            fitness={},
            total_fitness=0.0
        )
    
    def _one_point_crossover(
        self,
        parent_a: SolutionSeed,
        parent_b: SolutionSeed,
        child_id: str,
        rng: Random
    ) -> SolutionSeed:
        """One-point on file structure."""
        files_a = list(parent_a.code.keys())
        files_b = list(parent_b.code.keys())
        all_files = list(set(files_a + files_b))
        
        # Sort for deterministic split point
        all_files.sort()
        split = rng.randint(0, len(all_files))
        
        code = {}
        for i, f in enumerate(all_files):
            if i < split and f in parent_a.code:
                code[f] = parent_a.code[f]
            elif i >= split and f in parent_b.code:
                code[f] = parent_b.code[f]
            elif f in parent_a.code:
                code[f] = parent_a.code[f]
        
        return SolutionSeed(
            id=child_id,
            intent=parent_a.intent,
            code=code,
            lineage=[parent_a.id, parent_b.id],
            fitness={},
            total_fitness=0.0
        )
    
    def _blend_crossover(
        self,
        parent_a: SolutionSeed,
        parent_b: SolutionSeed,
        child_id: str,
        rng: Random
    ) -> SolutionSeed:
        """Line-by-line blend for shared files (BLX-alpha style)."""
        code = {}
        all_files = set(parent_a.code.keys()) | set(parent_b.code.keys())
        
        for f in all_files:
            if f in parent_a.code and f in parent_b.code:
                # Blend both files
                code[f] = self._blend_content(
                    parent_a.code[f], 
                    parent_b.code[f], 
                    rng
                )
            elif f in parent_a.code:
                code[f] = parent_a.code[f]
            else:
                code[f] = parent_b.code[f]
        
        return SolutionSeed(
            id=child_id,
            intent=parent_a.intent,
            code=code,
            lineage=[parent_a.id, parent_b.id],
            fitness={},
            total_fitness=0.0
        )
    
    def _blend_content(self, content_a: str, content_b: str, rng: Random) -> str:
        """Blend two content strings BLX-alpha style."""
        lines_a = content_a.split('\n')
        lines_b = content_b.split('\n')
        
        max_lines = max(len(lines_a), len(lines_b))
        result_lines = []
        
        for i in range(max_lines):
            if i >= len(lines_a):
                result_lines.append(lines_b[i])
            elif i >= len(lines_b):
                result_lines.append(lines_a[i])
            else:
                # Randomly choose which line to keep
                if rng.random() < 0.5:
                    result_lines.append(lines_a[i])
                else:
                    result_lines.append(lines_b[i])
        
        return '\n'.join(result_lines)


# ============================================
# SOLUTION POPULATION
# ============================================

class SolutionPopulation:
    """
    Maintain N solution variants, evolve over generations.
    
    LLM-powered evolution:
    - Uses Ollama to generate initial solutions
    - Uses LLM for intelligent mutations
    - Uses LLM for crossover
    
    Main loop:
    1. Initialize population (LLM generates N variants)
    2. Evaluate all (score each)
    3. Select (tournament or elitism)
    4. Breed (LLM-powered crossover + mutation)
    5. Repeat until convergence
    
    Key difference from sequential:
    - Explores multiple paths in PARALLEL
    - Combines partial wins
    - Archives diverse strategies
    - LLM-powered code generation
    """
    
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
        
        # LLM code generator (NEW)
        self.llm = LLMCodeGenerator(llm_model)
        
        # Evolution memory (NEW)
        self.memory: Optional[EvolutionMemory] = None
        
        self.population: List[SolutionSeed] = []
        self.generation = 0
        self.best_solution: Optional[SolutionSeed] = None
        self.history: List[Dict] = []  # Track evolution
    
    async def evolve(
        self,
        intent: str,
        initial_code: Optional[Dict[str, str]] = None,
        workspace: str = "."
    ) -> SolutionSeed:
        """Run LLM-powered evolution."""
        print(f"\n{'='*60}")
        print(f"EVOLUTION STARTING (LLM-POWERED)")
        print(f"Intent: {intent}")
        print(f"Population: {self.population_size}")
        print(f"Max generations: {self.max_generations}")
        print(f"LLM: {self.llm.model}")
        print(f"{'='*60}\n")
        
        # Initialize memory
        self.memory = EvolutionMemory(intent)
        
        # Initialize population with LLM
        await self._init_population_llm(intent, initial_code)
        
        # Evolution loop
        for gen in range(self.max_generations):
            self.generation = gen
            
            # Evaluate all
            await self._evaluate_population(workspace)
            
            # Sort by fitness
            self.population.sort(key=lambda s: s.total_fitness, reverse=True)
            
            # Track best
            if self.population:
                self.best_solution = self.population[0]
                print(f"\n[Gen {gen}] Best fitness: {self.best_solution.total_fitness:.3f}")
                print(f"  Lineage: {self.best_solution.lineage}")
            
            # Record to memory
            if self.memory:
                self.memory.record_generation(gen, self.population, self.best_solution)
            
            # Check convergence
            if self.best_solution and self.best_solution.total_fitness >= self.convergence_threshold:
                print(f"\n{'='*60}")
                print(f"CONVERGED at generation {gen}")
                print(f"Best solution: {self.best_solution.id}")
                print(f"Fitness: {self.best_solution.total_fitness:.3f}")
                print(f"{'='*60}")
                break
            
            # Create next generation with LLM
            await self._next_generation_llm()
            
            self.history.append({
                "generation": gen,
                "best_fitness": self.best_solution.total_fitness if self.best_solution else 0,
                "avg_fitness": sum(s.total_fitness for s in self.population) / len(self.population)
            })
        
        # Save memory
        if self.memory:
            memory_path = f".nexus_evolution_{int(time.time())}.json"
            self.memory.save(memory_path)
            print(f"Saved evolution memory to {memory_path}")
        
        return self.best_solution or self.population[0] if self.population else None
    
    async def _init_population_llm(
        self, 
        intent: str,
        initial_code: Optional[Dict[str, str]]
    ):
        """Initialize population using LLM."""
        self.population = []
        
        print(f"Generating initial population with {self.llm.model}...")
        
        # If we have initial code, use it as base
        base_code = initial_code or {"main.py": f"# Solution for: {intent}\n"}
        
        for i in range(self.population_size):
            # Generate unique variation
            variation_hint = f"Variation {i+1}/{self.population_size}"
            
            try:
                # Use LLM to generate
                code = await self.llm.generate(intent, variation_hint)
            except Exception as e:
                print(f"WARN: LLM failed for variant {i}: {e}")
                code = self._mutate_code(deepcopy(base_code), self.rng)
            
            solution = SolutionSeed(
                id=f"gen0_{i:03d}",
                intent=intent,
                code=code,
                lineage=[],
                fitness={},
                total_fitness=0.0
            )
            self.population.append(solution)
            
            print(f"  Created variant {i+1}/{self.population_size}")
    
    async def _next_generation_llm(self):
        """Create next generation using LLM for smarter breeding."""
        new_pop = []
        
        # Elitism - keep best K
        self.population.sort(key=lambda s: s.total_fitness, reverse=True)
        new_pop.extend(self.population[:self.elitism_count])
        
        # Breed new solutions
        while len(new_pop) < self.population_size:
            # Tournament selection
            tournament = self.rng.sample(
                self.population, 
                min(self.tournament_size, len(self.population))
            )
            tournament.sort(key=lambda s: s.total_fitness, reverse=True)
            parent_a = tournament[0]
            
            # Decide: crossover or mutation?
            if self.rng.random() < self.crossover_rate and len(self.population) > 1:
                # Crossover - pick second parent
                tournament = self.rng.sample(
                    self.population,
                    min(self.tournament_size, len(self.population))
                )
                tournament.sort(key=lambda s: s.total_fitness, reverse=True)
                parent_b = tournament[0]
                
                # Try LLM crossover
                try:
                    child_code = await self.llm.crossover(
                        parent_a.code, 
                        parent_b.code,
                        strategy="blend"
                    )
                    child_id = f"gen{self.generation+1}_x_{parent_a.id[:8]}_{parent_b.id[:8]}"
                except:
                    # Fallback to simple crossover
                    child = self.crossover.crossover(parent_a, parent_b, rng=self.rng)
                    child_code = child.code
                    child_id = child.id
            else:
                # Mutation
                mutation_types = ["variation", "fix_bug", "improve", "extend"]
                mutation = self.rng.choice(mutation_types)
                
                # Try LLM mutation
                try:
                    child_code = await self.llm.mutate(
                        parent_a.code,
                        mutation_type=mutation
                    )
                    child_id = f"gen{self.generation+1}_m_{parent_a.id[:8]}"
                except:
                    # Fallback to simple mutation
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
    
    def _mutate_code(
        self, 
        code: Dict[str, str], 
        rng: Random
    ) -> Dict[str, str]:
        """Mutate code with small variations."""
        result = {}
        
        for filepath, content in code.items():
            lines = content.split('\n')
            mutated = []
            
            for line in lines:
                # Small chance to mutate
                if rng.random() < self.mutation_rate:
                    # Various mutations
                    mutation_type = rng.randint(0, 3)
                    
                    if mutation_type == 0:
                        # Add comment
                        mutated.append(f"# Variant mutation")
                    elif mutation_type == 1:
                        # Flip if/else
                        line = line.replace('if ', 'if not ')
                    elif mutation_type == 2:
                        # Change threshold
                        line = re.sub(r'< \d+', lambda m: f"< {int(m.group()[2:]) + 1}", line)
                    else:
                        mutated.append(line)
                        continue
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
    
    async def _next_generation(self):
        """Create next generation through selection + breeding."""
        new_pop = []
        
        # Elitism - keep best K
        self.population.sort(key=lambda s: s.total_fitness, reverse=True)
        new_pop.extend(self.population[:self.elitism_count])
        
        # Breed new solutions
        while len(new_pop) < self.population_size:
            # Tournament selection
            tournament = self.rng.sample(
                self.population, 
                min(self.tournament_size, len(self.population))
            )
            tournament.sort(key=lambda s: s.total_fitness, reverse=True)
            parent_a = tournament[0]
            
            tournament = self.rng.sample(
                self.population,
                min(self.tournament_size, len(self.population))
            )
            tournament.sort(key=lambda s: s.total_fitness, reverse=True)
            parent_b = tournament[0]
            
            # Breed or mutate
            if self.rng.random() < self.crossover_rate:
                child = self.crossover.crossover(parent_a, parent_b, rng=self.rng)
            else:
                child = self._mutate(parent_a)
            
            new_pop.append(child)
        
        self.population = new_pop
    
    def _mutate(self, solution: SolutionSeed) -> SolutionSeed:
        """Mutate a single solution."""
        mutated_code = self._mutate_code(deepcopy(solution.code), self.rng)
        
        return SolutionSeed(
            id=f"gen{self.generation + 1}_{solution.id[:8]}_{self.rng.randint(0, 9999)}",
            intent=solution.intent,
            code=mutated_code,
            lineage=[solution.id],
            fitness={},
            total_fitness=0.0
        )


# ============================================
# HELPER FUNCTIONS
# ============================================

def create_seed(
    intent: str,
    code: Dict[str, str],
    parent_ids: Optional[List[str]] = None
) -> SolutionSeed:
    """Helper to create a solution seed."""
    content = json.dumps(code, sort_keys=True)
    seed_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    
    return SolutionSeed(
        id=f"seed_{seed_hash}",
        intent=intent,
        code=code,
        lineage=parent_ids or [],
        fitness={},
        total_fitness=0.0
    )


async def quick_fitness(
    code: Dict[str, str],
    intent: str = "",
    workspace: str = "."
) -> float:
    """
    Quick single-solution fitness check.
    
    Use this for simple scoring without full evolution.
    """
    seed = create_seed(intent, code)
    scorer = FitnessScorer()
    scores = await scorer.score(seed, workspace)
    return scores["total"]


# ============================================
# CLI ENTRY POINT
# ============================================

async def main():
    """CLI for testing."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python evolutionary_tools.py <intent> [code_file]")
        sys.exit(1)
    
    intent = sys.argv[1]
    
    initial_code = {}
    if len(sys.argv) > 2:
        # Load code from file
        code_path = Path(sys.argv[2])
        if code_path.is_file():
            initial_code = {code_path.name: code_path.read_text()}
    
    # Run evolution
    pop = SolutionPopulation(population_size=10, max_generations=20)
    best = await pop.evolve(intent, initial_code)
    
    print(f"\n{'='*60}")
    print("EVOLUTION COMPLETE")
    print(f"Best solution: {best.id}")
    print(f"Fitness: {best.total_fitness:.3f}")
    print(f"Scores: {best.fitness}")
    print(f"\nCode:")
    for filepath, content in best.code.items():
        print(f"\n--- {filepath} ---")
        print(content[:500])
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())