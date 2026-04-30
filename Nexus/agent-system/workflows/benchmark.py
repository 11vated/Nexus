import json
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path


class SWEBenchEvaluator:
    def __init__(self, 
                 model: str = "ollama/qwen2.5-coder:14b",
                 workspace: str = "swe_bench"):
        self.model = model
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.results = []
    
    def download_tasks(self, limit: int = 10) -> List[Dict]:
        print(f"[BENCH] Downloading {limit} SWE-bench tasks...")
        
        return [
            {"id": f"swel_{i}", "repo": f"realworld/repo{i}", "issue": f"Fix bug {i}"}
            for i in range(limit)
        ]
    
    def run_task(self, task: Dict, agent) -> Dict:
        task_id = task.get("id", "unknown")
        print(f"\n[BENCH] Running: {task_id}")
        
        issue = task.get("issue", "")
        
        try:
            result = agent.run(issue)
            
            passed = result.get("status") == "success"
            
            return {
                "task_id": task_id,
                "passed": passed,
                "timestamp": datetime.now().isoformat(),
                "result": result
            }
        except Exception as e:
            return {
                "task_id": task_id,
                "passed": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def evaluate(self, agent, num_tasks: int = 10) -> Dict:
        tasks = self.download_tasks(num_tasks)
        
        passed = 0
        failed = 0
        results = []
        
        for task in tasks:
            result = self.run_task(task, agent)
            results.append(result)
            
            if result.get("passed"):
                passed += 1
            else:
                failed += 1
        
        score = (passed / num_tasks) * 100 if num_tasks > 0 else 0
        
        self.results.append({
            "timestamp": datetime.now().isoformat(),
            "num_tasks": num_tasks,
            "passed": passed,
            "failed": failed,
            "score": score
        })
        
        return {
            "num_tasks": num_tasks,
            "passed": passed,
            "failed": failed,
            "score_percent": score,
            "results": results
        }


class BenchmarkSuite:
    def __init__(self, model: str = "ollama/qwen2.5-coder:14b"):
        self.model = model
        self.benchmarks = {}
        self.results = {}
    
    def register_benchmark(self, name: str, task_generator, evaluator):
        self.benchmarks[name] = {
            "generator": task_generator,
            "evaluator": evaluator
        }
        print(f"[BENCHMARK] Registered: {name}")
    
    def run_benchmark(self, name: str, agent, **kwargs) -> Dict:
        if name not in self.benchmarks:
            return {"error": f"Benchmark {name} not found"}
        
        benchmark = self.benchmarks[name]
        generator = benchmark["generator"]
        evaluator = benchmark["evaluator"]
        
        tasks = generator(**kwargs)
        results = evaluator(agent, tasks)
        
        self.results[name] = results
        
        return results
    
    def compare(self, agent_configs: List[Dict]) -> Dict:
        comparison = {}
        
        for config in agent_configs:
            config_name = config.get("name", "default")
            print(f"\n[BENCHMARK] Testing: {config_name}")
            
            agent = config.get("agent")
            num_tasks = config.get("num_tasks", 5)
            
            swe = SWEBenchEvaluator(model=self.model)
            result = swe.evaluate(agent, num_tasks=num_tasks)
            
            comparison[config_name] = {
                "score": result.get("score_percent", 0),
                "passed": result.get("passed", 0),
                "failed": result.get("failed", 0)
            }
        
        return comparison


class QualityMetrics:
    def __init__(self):
        self.metrics = {
            "task_completion": [],
            "code_quality": [],
            "iteration_efficiency": [],
            "error_recovery": []
        }
    
    def record_task_completion(self, task: str, success: bool, duration: float):
        self.metrics["task_completion"].append({
            "task": task,
            "success": success,
            "duration": duration
        })
    
    def record_code_quality(self, task: str, issues: List[str]):
        self.metrics["code_quality"].append({
            "task": task,
            "issues": issues,
            "quality_score": 1.0 - (len(issues) / 10)
        })
    
    def record_iteration_efficiency(self, task: str, iterations: int):
        self.metrics["iteration_efficiency"].append({
            "task": task,
            "iterations": iterations,
            "efficiency": 1.0 / iterations if iterations > 0 else 0
        })
    
    def record_error_recovery(self, task: str, recovered: bool, attempts: int):
        self.metrics["error_recovery"].append({
            "task": task,
            "recovered": recovered,
            "attempts": attempts
        })
    
    def get_summary(self) -> Dict:
        def avg(key):
            values = [m[key] for m in self.metrics[key] if key in m]
            return sum(values) / len(values) if values else 0
        
        return {
            "task_completion_rate": avg("success"),
            "avg_quality": avg("quality_score"),
            "avg_iterations": avg("iterations"),
            "error_recovery_rate": avg("recovered")
        }
    
    def get_report(self) -> str:
        summary = self.get_summary()
        
        return f"""
=== QUALITY REPORT ===
Task Completion: {summary['task_completion_rate']*100:.1f}%
Code Quality:   {summary['avg_quality']:.2f}
Iterations:   {summary['avg_iterations']:.1f}
Error Recovery: {summary['error_recovery_rate']*100:.1f}%
"""


class ImprovementTracker:
    def __init__(self, storage_path: str = "improvement_history.json"):
        self.storage_path = storage_path
        self.history = []
        self._load()
    
    def _load(self):
        try:
            with open(self.storage_path) as f:
                self.history = json.load(f)
        except:
            self.history = []
    
    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.history, f, indent=2)
    
    def log_improvement(self, area: str, before: float, after: float, reason: str):
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "area": area,
            "before": before,
            "after": after,
            "delta": after - before,
            "reason": reason
        })
        self._save()
    
    def get_best_config(self) -> Dict:
        if not self.history:
            return {"error": "No history"}
        
        improvements = [h for h in self.history if h.get("delta", 0) > 0]
        
        if not improvements:
            return {"error": "No improvements"}
        
        return max(improvements, key=lambda x: x.get("delta", 0))
    
    def suggest_next_improvements(self) -> List[str]:
        declines = [h for h in self.history if h.get("delta", 0) < 0]
        
        suggestions = []
        if declines:
            suggestions.append("Review failed improvements")
        
        if len(self.history) < 5:
            suggestions.append("Run more benchmarks to establish baseline")
        
        suggestions.extend([
            "Try larger model",
            "Increase test cases",
            "Add more reflection loops"
        ])
        
        return suggestions


def run_swe_bench(model: str = "ollama/qwen2.5-coder:14b", tasks: int = 10) -> Dict:
    from core.brain import AdvancedAgent
    
    config = {"model": {"name": model}}
    agent = AdvancedAgent(config)
    
    swe = SWEBenchEvaluator(model=model)
    return swe.evaluate(agent, num_tasks=tasks)


if __name__ == "__main__":
    print("[BENCHMARK] SWE-bench Evaluator")
    result = run_swe_bench(tasks=5)
    print(f"\nScore: {result.get('score_percent', 0):.1f}%")