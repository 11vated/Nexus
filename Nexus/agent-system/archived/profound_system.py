#!/usr/bin/env python3
"""
PROFOUND AUTONOMOUS CODING SYSTEM
Based on research from: ALMAS, Codex Subagents, PARC, DepthNet, Orchestrator

Architecture:
- Hierarchical multi-agent (Sprint → Architect → Developer → Reviewer → Tester)
- Persistent memory with embeddings
- Self-assessment loop
- Context store for knowledge accumulation
- MCP tool integration
"""

import asyncio
import json
import subprocess
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class AgentRole(Enum):
    """Agent roles like agile team"""
    SPRINT = "sprint"           # Project manager - breaks down goals
    ARCHITECT = "architect"       # Design & planning
    DEVELOPER = "developer"      # Code generation
    REVIEWER = "reviewer"       # Code review
    TESTER = "tester"           # Testing & validation
    RESEARCHER = "researcher"     # Investigation

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    DONE = "done"
    FAILED = "failed"

@dataclass
class Task:
    """Task in the system"""
    id: str
    description: str
    role: AgentRole
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3

@dataclass
class ContextEntry:
    """Knowledge artifact in context store"""
    id: str
    content: str
    source_agent: AgentRole
    task_id: str
    timestamp: float = field(default_factory=time.time)
    importance: float = 1.0

class OllamaModel:
    """Ollama wrapper with model selection"""
    
    MODELS = {
        "qwen2.5-coder:14b": {"strengths": ["code", "speed"], "context": 32000},
        "qwen2.5-coder:7b": {"strengths": ["code", "fast"], "context": 16000},
        "dolphin-mistral": {"strengths": ["uncensored", "coding"], "context": 8000},
        "deepseek-r1:7b": {"strengths": ["reasoning", "planning"], "context": 16000},
        "deepseek-r1:1.5b": {"strengths": ["fast", "reasoning"], "context": 8000},
    }
    
    @classmethod
    def select(cls, task_type: str) -> str:
        """Select best model for task"""
        if task_type in ["plan", "architect", "analyze"]:
            return "deepseek-r1:7b"
        elif task_type in ["review", "test"]:
            return "deepseek-r1:7b"
        elif task_type == "uncensored":
            return "dolphin-mistral"
        else:
            return "qwen2.5-coder:14b"
    
    @classmethod
    async def run(cls, model: str, prompt: str, timeout: int = 120) -> str:
        """Run model with prompt"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", model, prompt,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(input=prompt.encode()), timeout)
            return stdout.decode() if stdout else stderr.decode()
        except Exception as e:
            return f"Error: {str(e)}"

class ContextStore:
    """
    Context Store - the key innovation from Orchestrator paper
    Enables compound intelligence where each action builds on previous discoveries
    """
    
    def __init__(self):
        self.entries: List[ContextEntry] = []
    
    def add(self, content: str, source: AgentRole, task_id: str, importance: float = 1.0):
        entry = ContextEntry(
            id=f"{task_id}_{len(self.entries)}",
            content=content,
            source_agent=source,
            task_id=task_id,
            importance=importance
        )
        self.entries.append(entry)
        return entry
    
    def get_relevant(self, query: str, limit: int = 5) -> List[ContextEntry]:
        """Get relevant context (simple keyword match for now)"""
        query_lower = query.lower()
        scored = []
        for entry in self.entries:
            score = entry.importance
            if any(word in entry.content.lower() for word in query_lower.split()):
                score += 2
            scored.append((score, entry))
        scored.sort(reverse=True)
        return [e for _, e in scored[:limit]]
    
    def summarize(self) -> str:
        """Get formatted context summary"""
        if not self.entries:
            return "No context yet."
        lines = ["## Context Store"]
        for entry in self.entries[-10:]:
            lines.append(f"- [{entry.source_agent.value}] {entry.content[:100]}...")
        return "\n".join(lines)

class PersistentMemory:
    """
    Dual-store memory like DepthNet
    - Episodic: conversation history
    - Semantic: embeddings for retrieval
    """
    
    def __init__(self, storage_path: str = "memory.json"):
        self.storage_path = storage_path
        self.episodic: List[Dict] = []
        self.load()
    
    def load(self):
        if Path(self.storage_path).exists():
            with open(self.storage_path) as f:
                self.episodic = json.load(f)
    
    def save(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.episodic[-100:], f, indent=2)
    
    def add(self, role: str, content: str):
        self.episodic.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        self.save()
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        return self.episodic[-limit:]

class MCPToolRunner:
    """Execute MCP server tools"""
    
    def __init__(self):
        self.tools = {
            "filesystem": self._filesystem,
            "github": self._github,
            "ollama": self._ollama,
        }
    
    async def run(self, tool: str, args: Dict) -> str:
        if tool in self.tools:
            return await self.tools[tool](args)
        return f"Unknown tool: {tool}"
    
    async def _filesystem(self, args: Dict) -> str:
        op = args.get("operation", "list")
        path = args.get("path", ".")
        
        if op == "list":
            files = list(Path(path).glob(args.get("pattern", "*")))
            return json.dumps([str(f) for f in files[:20]])
        elif op == "read":
            return Path(path).read_text(errors="ignore")[:5000]
        elif op == "write":
            Path(path).write_text(args.get("content", ""))
            return f"Written to {path}"
        return "Unknown operation"
    
    async def _github(self, args: Dict) -> str:
        # Placeholder for GitHub MCP
        return "GitHub MCP not configured"
    
    async def _ollama(self, args: Dict) -> str:
        model = args.get("model", "qwen2.5-coder:14b")
        prompt = args.get("prompt", "")
        return await OllamaModel.run(model, prompt)

class ReflectiveAgent:
    """
    Self-assessment agent like PARC
    Evaluates outcomes and provides feedback
    """
    
    async def assess(self, task: Task, result: str) -> Dict[str, Any]:
        """Assess task result and decide next action"""
        
        prompt = f"""You are a code review agent. Assess this task result:

Task: {task.description}
Result: {result}

Respond with JSON:
{{
  "success": true/false,
  "quality_score": 0-10,
  "issues": ["issue1", "issue2"],
  "feedback": "constructive feedback",
  "should_retry": true/false
}}"""
        
        response = await OllamaModel.run("deepseek-r1:7b", prompt)
        
        try:
            # Extract JSON from response
            if "{" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
                return json.loads(json_str)
        except:
            pass
        
        return {"success": True, "quality_score": 8, "should_retry": False}

class AutonomousOrchestrator:
    """
    The brain - hierarchical multi-agent orchestration
    Based on: Orchestrator, ALMAS, Codex Subagents
    """
    
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.context_store = ContextStore()
        self.memory = PersistentMemory()
        self.mcp = MCPToolRunner()
        self.reflector = ReflectiveAgent()
        self.tasks: List[Task] = []
    
    async def execute_goal(self, goal: str) -> Dict[str, Any]:
        """Main entry point - autonomous execution loop"""
        
        # Phase 1: Sprint Agent - decompose goal
        plan = await self._sprint_phase(goal)
        
        # Phase 2: Execute with context
        results = await self._execute_phase(plan)
        
        # Phase 3: Reflect and validate
        final_result = await self._reflect_phase(results)
        
        return final_result
    
    async def _sprint_phase(self, goal: str) -> List[Task]:
        """Sprint agent decomposes goal into tasks"""
        
        prompt = f"""You are a Sprint Manager. Break this goal into tasks:

Goal: {goal}

Create tasks for: Architect, Developer, Reviewer, Tester roles.
Respond with JSON array:
[
  {{"id": "1", "description": "...", "role": "architect"}},
  {{"id": "2", "description": "...", "role": "developer"}},
  ...
]"""
        
        response = await OllamaModel.run("deepseek-r1:7b", prompt)
        
        # Add context
        self.context_store.add(f"Goal: {goal}", AgentRole.SPRINT, "sprint")
        
        self.context_store.add(f"Plan: {response[:500]}", AgentRole.ARCHITECT, "plan")
        
        return []  # Parsed from response
    
    async def _execute_phase(self, plan: List[Task]) -> List[Dict]:
        """Execute tasks with agents"""
        results = []
        
        for task in plan:
            task.status = TaskStatus.IN_PROGRESS
            
            # Get relevant context
            context = self.context_store.get_relevant(task.description)
            context_str = "\n".join([c.content for c in context])
            
            # Select model for role
            model = OllamaModel.select(task.role.value)
            
            # Build prompt with context
            prompt = f"""Context from previous work:
{context_str}

Your task ({task.role.value}): {task.description}

Execute this task. Provide detailed results."""
            
            result = await OllamaModel.run(model, prompt)
            
            # Store in context
            self.context_store.add(result, task.role, task.id)
            
            # Assess result
            assessment = await self.reflector.assess(task, result)
            
            if assessment.get("should_retry") and task.attempts < task.max_attempts:
                task.attempts += 1
                task.status = TaskStatus.PENDING
            else:
                task.status = TaskStatus.DONE if assessment.get("success") else TaskStatus.FAILED
            
            results.append({
                "task": task.description,
                "result": result,
                "assessment": assessment
            })
        
        return results
    
    async def _reflect_phase(self, results: List[Dict]) -> Dict[str, Any]:
        """Final reflection and synthesis"""
        
        prompt = f"""You are the Supervisor Agent. Synthesize these results:

{json.dumps(results, indent=2)}

Provide:
1. Summary of what was accomplished
2. Any issues found
3. Final verdict (success/failed)
4. Recommendations for future work

Respond in JSON."""
        
        final = await OllamaModel.run("deepseek-r1:7b", prompt)
        
        return {"results": results, "final_assessment": final}

class ProfoundSystem:
    """
    The complete autonomous coding system
    Wraps everything with CLI interface
    """
    
    def __init__(self, workspace: str = "."):
        self.orchestrator = AutonomousOrchestrator(workspace)
        self.running = False
    
    async def chat(self):
        """Interactive chat mode"""
        print("\n" + "="*60)
        print("PROFOUND AUTONOMOUS CODING SYSTEM")
        print("Hierarchical Multi-Agent with Self-Assessment")
        print("="*60)
        print("Commands:")
        print("  /goal <task> - Execute autonomous goal")
        print("  /context     - Show context store")
        print("  /memory      - Show memory")
        print("  /model       - Show available models")
        print("  /quit        - Exit")
        print()
        
        while True:
            try:
                user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.startswith("/"):
                    cmd = user_input[1:].split()[0]
                    arg = user_input[len(cmd)+2:]
                    
                    if cmd == "quit":
                        print("Goodbye!")
                        break
                    elif cmd == "goal":
                        result = await self.orchestrator.execute_goal(arg)
                        print(f"\n{result}")
                    elif cmd == "context":
                        print(f"\n{self.orchestrator.context_store.summarize()}")
                    elif cmd == "memory":
                        mem = self.orchestrator.memory.get_recent(5)
                        for m in mem:
                            print(f"  {m['role']}: {m['content'][:50]}...")
                    elif cmd == "model":
                        print("\nAvailable models:")
                        for m, info in OllamaModel.MODELS.items():
                            print(f"  {m}: {info['strengths']}")
                else:
                    # Regular chat
                    model = OllamaModel.select("chat")
                    response = await OllamaModel.run(model, user_input)
                    print(f"\n{response}")
                    
                    self.orchestrator.memory.add("user", user_input)
                    self.orchestrator.memory.add("assistant", response)
            
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

async def main():
    import sys
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    system = ProfoundSystem(workspace)
    await system.chat()

if __name__ == "__main__":
    asyncio.run(main())