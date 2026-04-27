import json
import os
from datetime import datetime
from pathlib import Path

from core.planner import create_plan
from core.executor import execute_step
from core.memory import Memory

try:
    from core.vector_memory import VectorMemory, HybridMemory
    VECTOR_MEMORY_AVAILABLE = True
except ImportError:
    VECTOR_MEMORY_AVAILABLE = False
    VectorMemory = None
    HybridMemory = None

try:
    from sandbox.docker import DockerSandbox, SafeExecutor
    SANDBOX_AVAILABLE = True
except ImportError:
    SANDBOX_AVAILABLE = False
    DockerSandbox = None
    SafeExecutor = None

try:
    from workflows.tdd import TDDWorkflow
    TDD_AVAILABLE = True
except ImportError:
    TDD_AVAILABLE = False
    TDDWorkflow = None

try:
    from workflows.sequential_thinking import SequentialThinkingAgent
    SEQUENTIAL_AVAILABLE = True
except ImportError:
    SEQUENTIAL_AVAILABLE = False
    SequentialThinkingAgent = None


class AdvancedAgent:
    def __init__(self, config):
        self.config = config
        self.model = config.get("model", {}).get("name", "ollama/qwen2.5-coder:14b")
        self.max_iterations = config.get("loop", {}).get("max_iterations", 50)
        self.workspace_path = config.get("workspace", {}).get("path", "workspace")
        
        self.memory = Memory(config.get("memory", {}).get("path", "memory.json"))
        
        self.vector_memory = None
        if VECTOR_MEMORY_AVAILABLE and config.get("memory", {}).get("vector_enabled", True):
            try:
                self.vector_memory = VectorMemory(
                    persist_dir=config.get("memory", {}).get("vector_path", "memory_db")
                )
                self.hybrid_memory = HybridMemory(self.vector_memory)
                print("[OK] Vector memory enabled")
            except Exception as e:
                print(f"[WARN] Vector memory disabled: {e}")
        
        self.sandbox = None
        if SANDBOX_AVAILABLE and config.get("sandbox", {}).get("enabled", False):
            try:
                self.sandbox = DockerSandbox(
                    workspace_path=self.workspace_path,
                    network_enabled=config.get("sandbox", {}).get("network_enabled", False)
                )
                self.safe_executor = SafeExecutor(self.sandbox)
                print("[OK] Sandbox enabled")
            except Exception as e:
                print(f"[WARN] Sandbox disabled: {e}")
        
        self.tdd_workflow = None
        if TDD_AVAILABLE and config.get("tdd", {}).get("enabled", False):
            self.tdd_workflow = TDDWorkflow(
                workspace=self.workspace_path,
                model=self.model
            )
            print("[OK] TDD workflow enabled")
        
        self.thinker = None
        if SEQUENTIAL_AVAILABLE and config.get("thinking", {}).get("enabled", True):
            self.thinker = SequentialThinkingAgent(model=self.model)
            print("[OK] Sequential thinking enabled")
    
    def run(self, task: str, use_tdd: bool = False) -> dict:
        print(f"\n{'='*60}")
        print(f"[ADVANCED AGENT START] {task}")
        print(f"{'='*60}")
        
        workspace = Path(self.workspace_path)
        workspace.mkdir(parents=True, exist_ok=True)
        os.chdir(workspace)
        
        self.memory.add_interaction(task, "task_received", "Started")
        
        if self.vector_memory:
            similar = self.vector_memory.query(task, n_results=3)
            if similar and not similar[0].get("error"):
                print(f"[MEMORY] Found {len(similar)} similar past tasks")
        
        if use_tdd and self.tdd_workflow:
            return self._run_tdd(task)
        
        if self.thinker:
            thought_result = self.thinker.think(task)
            print(f"[THINKING] Decision: {thought_result.get('decision', {}).get('action', 'proceed')}")
            task = thought_result.get("decision", {}).get("action", task)
        
        return self._run_loop(task)
    
    def _run_tdd(self, task: str) -> dict:
        if not self.tdd_workflow:
            return {"status": "error", "error": "TDD not available"}
        
        print("[MODE] TDD (Test-Driven Development)")
        
        result = self.tdd_workflow.run(task)
        
        self.memory.add_interaction(task, "tdd_completed", str(result))
        
        if self.vector_memory:
            self.vector_memory.add(
                text=f"TDD: {task} -> {result.get('status')}",
                metadata={"type": "tdd", "status": result.get("status")}
            )
        
        return result
    
    def _run_loop(self, task: str) -> dict:
        plan = create_plan(task, self.config)
        
        if not plan:
            return {"status": "error", "error": "Failed to create plan"}
        
        print(f"[PLANNER] {len(plan)} steps")
        
        results = []
        reflection_count = 0
        max_reflections = self.config.get("loop", {}).get("max_retries", 3)
        
        for i, step in enumerate(plan[:self.max_iterations]):
            print(f"\n[STEP {i+1}] {step[:100]}")
            
            result = execute_step(step, self.config, self.workspace_path)
            
            results.append({
                "step": step,
                "result": result,
                "iteration": i
            })
            
            if "error" in result.lower():
                print(f"[ERROR] {result[:200]}")
                
                if self.thinker and reflection_count < max_reflections:
                    print(f"[REFLECT] Attempting fix ({reflection_count+1})")
                    fix_result = self.thinker.think(f"Fix error: {result}")
                    reflection_count += 1
            
            self.memory.add_interaction(step, "step_completed", result[:200])
            
            if self.vector_memory:
                self.vector_memory.add(
                    text=f"Step: {step} -> Result: {result[:100]}",
                    metadata={"type": "step", "status": "completed" if "error" not in result.lower() else "error"}
                )
            
            if any(marker in result.lower() for marker in ["done", "complete", "success"]):
                print("[SUCCESS] Task completed")
                break
        
        return {
            "status": "success",
            "task": task,
            "steps": len(plan),
            "results": results
        }
    
    def run_with_github(self, task: str, repo: str) -> dict:
        from mcp_servers.github import GitHubMCP, GitHubWorkflow
        
        github = GitHubMCP()
        workflow = GitHubWorkflow(github)
        
        task_with_context = f"[GitHub {repo}] {task}"
        
        return self.run(task_with_context)


def create_advanced_agent(config_path: str = "config/agent.yaml") -> AdvancedAgent:
    import yaml
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    return AdvancedAgent(config)


if __name__ == "__main__":
    import sys
    
    config_path = "config/agent.yaml"
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = "Create a simple Python web server"
    
    agent = create_advanced_agent(config_path)
    result = agent.run(task)
    
    print(f"\n[RESULT] {result.get('status')}")