import subprocess
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class AgentSpec:
    name: str
    role: str
    model: str
    tools: List[str]
    priority: int = 1


class SwarmAgent:
    def __init__(self, spec: AgentSpec):
        self.spec = spec
        self.results = []
        self.status = "idle"
    
    def run(self, task: str, context: Optional[Dict] = None) -> Dict:
        self.status = "running"
        
        prompt = f"""You are a {self.spec.role}.

Task: {task}

Complete this subtask and return results in JSON format:
{{"result": "...", "status": "success|error", "reason": "..."}}
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.spec.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            data = json.loads(result.stdout.strip("`").strip("json"))
            self.results.append(data)
            self.status = "completed"
            
            return data
        except Exception as e:
            self.status = "error"
            return {"result": "", "status": "error", "reason": str(e)}


class SwarmOrchestrator:
    def __init__(self, model: str = "ollama/qwen2.5-coder:14b"):
        self.model = model
        self.agents: Dict[str, SwarmAgent] = {}
        self.task_queue = []
        self.results = {}
    
    def register_agent(self, spec: AgentSpec):
        self.agents[spec.name] = SwarmAgent(spec)
        print(f"[SWARM] Registered: {spec.name} ({spec.role})")
    
    def init_default_agents(self):
        self.register_agent(AgentSpec(
            name="researcher",
            role="deep research specialist",
            model=self.model,
            tools=["search", "read", "analyze"],
            priority=1
        ))
        
        self.register_agent(AgentSpec(
            name="planner", 
            role="architect and planner",
            model=self.model,
            tools=["plan", "decompose", "prioritize"],
            priority=2
        ))
        
        self.register_agent(AgentSpec(
            name="builder",
            role="code builder and implementer",
            model=self.model,
            tools=["write", "edit", "execute"],
            priority=3
        ))
        
        self.register_agent(AgentSpec(
            name="tester",
            role="QA engineer",
            model=self.model,
            tools=["test", "verify", "benchmark"],
            priority=4
        ))
        
        self.register_agent(AgentSpec(
            name="reviewer",
            role="code reviewer",
            model=self.model,
            tools=["review", "lint", "security_check"],
            priority=5
        ))
    
    def dispatch_parallel(self, task: str, agent_names: List[str]) -> Dict:
        print(f"\n[SWARM] Dispatching: {agent_names}")
        
        with ThreadPoolExecutor(max_workers=len(agent_names)) as executor:
            futures = {}
            
            for name in agent_names:
                if name in self.agents:
                    agent = self.agents[name]
                    future = executor.submit(agent.run, task)
                    futures[future] = name
            
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    self.results[name] = result
                    print(f"[SWARM] {name}: {result.get('status', 'unknown')}")
                except Exception as e:
                    self.results[name] = {"error": str(e)}
        
        return self.results
    
    def dispatch_sequential(self, task: str) -> Dict:
        print(f"\n[SWARM] Sequential workflow")
        
        researchers = self.dispatch_parallel(task, ["researcher"])
        
        research_summary = "\n ".join([
            r.get("result", "") for r in researchers.values()
        ])
        
        planner_task = f"{task}\n\nResearch: {research_summary}"
        plan_result = self.dispatch_parallel(planner_task, ["planner"])
        
        builder_task = f"{task}\n\nPlan: {plan_result}"
        build_result = self.dispatch_parallel(builder_task, ["builder"])
        
        tester_task = f"{task}\n\nBuild output: {build_result}"
        test_result = self.dispatch_parallel(tester_task, ["tester"])
        
        return {
            "research": researchers,
            "plan": plan_result,
            "build": build_result,
            "test": test_result
        }
    
    def dispatch_hierarchical(self, task: str) -> Dict:
        print(f"\n[SWARM] Hierarchical (manager -> workers)")
        
        manager_task = f"""Break down this task into subtasks for specialized agents.
        
Task: {task}

Return JSON with keys: subtasks (array), assigned_agents (mapping), dependencies (array).
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.model} "{manager_task}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            plan = json.loads(result.stdout.strip("`").strip("json"))
        except:
            plan = {"subtasks": [task], "assigned_agents": {"builder": task}}
        
        subtasks = plan.get("subtasks", [task])
        assignments = plan.get("assigned_agents", {})
        
        parallel_groups = {}
        for subtask, agent_name in assignments.items():
            parallel_groups.setdefault(agent_name, []).append(subtask)
        
        all_results = {}
        for group_name, group_tasks in parallel_groups.items():
            group_results = self.dispatch_parallel(
                " | ".join(group_tasks),
                [group_name] if group_name in self.agents else list(self.agents.keys())[:1]
            )
            all_results.update(group_results)
        
        final_review = self.dispatch_parallel(task, ["reviewer"])
        
        return {
            "plan": plan,
            "agent_results": all_results,
            "review": final_review
        }
    
    def get_status(self) -> Dict:
        return {
            name: {"role": agent.spec.role, "status": agent.status}
            for name, agent in self.agents.items()
        }


class ParallelAgentSystem:
    def __init__(self, workspace: str = "workspace"):
        self.workspace = workspace
        self.orchestrator = SwarmOrchestrator()
        self.orchestrator.init_default_agents()
    
    def run(self, task: str, mode: str = "sequential") -> Dict:
        if mode == "parallel":
            return self.orchestrator.dispatch_parallel(task, list(self.orchestrator.agents.keys()))
        elif mode == "hierarchical":
            return self.orchestrator.dispatch_hierarchical(task)
        else:
            return self.orchestrator.dispatch_sequential(task)
    
    def get_specialist(self, role: str) -> Optional[SwarmAgent]:
        for agent in self.orchestrator.agents.values():
            if agent.spec.role == role:
                return agent
        return None


def create_swarm(model: str = "ollama/qwen2.5-coder:14b") -> SwarmOrchestrator:
    orchestrator = SwarmOrchestrator(model=model)
    orchestrator.init_default_agents()
    return orchestrator


def create_parallel_system(workspace: str = "workspace") -> ParallelAgentSystem:
    return ParallelAgentSystem(workspace=workspace)