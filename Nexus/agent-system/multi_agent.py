#!/usr/bin/env python3
"""
MULTI-AGENT COORDINATION SYSTEM
Like Claude Code's multi-agent, Codex's parallel agents
Coordinates multiple AI agents to work on complex tasks simultaneously
"""

import asyncio
import json
import subprocess
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid

@dataclass
class Agent:
    name: str
    role: str
    model: str
    status: str = "idle"
    current_task: Optional[str] = None
    output: List[str] = field(default_factory=list)
    
class MultiAgentCoordinator:
    """Coordinates multiple agents to work on complex tasks"""
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {
            "planner": Agent(
                name="planner",
                role="Analyzes requirements, creates architecture, develops implementation plans",
                model="ollama/deepseek-r1:7b"
            ),
            "builder": Agent(
                name="builder", 
                role="Implements features, writes code, follows specs",
                model="ollama/qwen2.5-coder:14b"
            ),
            "reviewer": Agent(
                name="reviewer",
                role="Reviews code, identifies issues, ensures quality",
                model="ollama/qwen2.5-coder:14b"
            ),
            "tester": Agent(
                name="tester",
                role="Writes tests, verifies functionality, validates solutions",
                model="ollama/qwen2.5-coder:7b"
            )
        }
        self.task_history: List[Dict] = []
        
    async def assign_task(self, agent_name: str, task: str) -> str:
        """Assign a task to a specific agent"""
        if agent_name not in self.agents:
            return f"Agent {agent_name} not found"
            
        agent = self.agents[agent_name]
        agent.status = "working"
        agent.current_task = task
        
        # Run the agent with Ollama
        result = await self._run_agent(agent.model, task)
        
        agent.output.append(result)
        agent.status = "completed"
        agent.current_task = None
        
        return result
    
    async def _run_agent(self, model: str, prompt: str) -> str:
        """Run an agent with Ollama"""
        cmd = ["ollama", "run", model]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate(
            input=prompt.encode()
        )
        
        if stderr:
            return f"Error: {stderr.decode()}"
        return stdout.decode()
    
    async def coordinate_task(self, task: str) -> Dict[str, Any]:
        """
        Coordinate multiple agents for a complex task
        Like Codex's parallel agent system
        """
        task_id = str(uuid.uuid4())
        results = {}
        
        # Phase 1: Planning (planner analyzes and creates plan)
        print("🔄 [Planner] Analyzing task and creating plan...")
        plan = await self.assign_task("planner", 
            f"Analyze this task and create a detailed implementation plan: {task}"
        )
        results["plan"] = plan
        
        # Phase 2: Building (builder implements based on plan)
        print("🔄 [Builder] Implementing based on plan...")
        build_result = await self.assign_task("builder",
            f"Implement the following plan. Create all necessary files:\n{plan}"
        )
        results["build"] = build_result
        
        # Phase 3: Testing (tester verifies)
        print("🔄 [Tester] Writing tests and verifying...")
        test_result = await self.assign_task("tester",
            f"Write comprehensive tests for the implementation and verify it works: {build_result}"
        )
        results["tests"] = test_result
        
        # Phase 4: Review (reviewer does final review)
        print("🔄 [Reviewer] Final review and quality check...")
        review = await self.assign_task("reviewer",
            f"Review this implementation for quality, security, and best practices: {build_result}"
        )
        results["review"] = review
        
        # Store in history
        self.task_history.append({
            "task_id": task_id,
            "task": task,
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "status": "completed"
        })
        
        return {
            "task_id": task_id,
            "status": "completed",
            "phases": results
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        return {
            name: {
                "role": agent.role,
                "status": agent.status,
                "current_task": agent.current_task
            }
            for name, agent in self.agents.items()
        }
    
    def get_history(self) -> List[Dict]:
        """Get task history"""
        return self.task_history


async def main():
    """Example usage"""
    coordinator = MultiAgentCoordinator()
    
    # Show agent status
    print("=" * 60)
    print("MULTI-AGENT COORDINATION SYSTEM")
    print("=" * 60)
    print("\nAvailable Agents:")
    for name, status in coordinator.get_status().items():
        print(f"  {name:12} - {status['role']}")
    
    print("\n" + "=" * 60)
    print("\nExample: Run a coordinated task")
    print("=" * 60)
    
    # Example task
    task = "Create a REST API for a todo list with authentication"
    
    result = await coordinator.coordinate_task(task)
    
    print(f"\n✅ Task completed: {result['task_id']}")
    print("\nResults by phase:")
    for phase, output in result["phases"].items():
        print(f"\n[{phase.upper()}]")
        print(output[:500] + "..." if len(output) > 500 else output)


if __name__ == "__main__":
    asyncio.run(main())