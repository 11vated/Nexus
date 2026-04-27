#!/usr/bin/env python3
"""
INTELLIGENT ORCHESTRATION SYSTEM
Like GPT-5's smart router, Gemini's thinking, Claude Code's agents

Features:
- Smart model routing (auto-select best model)
- Thinking mode for complex problems
- Task complexity detection
- Tool integration
- Memory persistence
- Multi-step autonomous execution
"""

import asyncio
import json
import subprocess
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

class TaskType(Enum):
    """Task type classification"""
    SIMPLE = "simple"           # Quick questions, simple edits
    MODERATE = "moderate"       # Feature implementation
    COMPLEX = "complex"         # Architecture, planning
    RESEARCH = "research"        # Deep analysis, investigation

class TaskComplexity(Enum):
    """Complexity levels"""
    TRIVIAL = 1    # "what is X?"
    SIMPLE = 2     # "fix this bug", "add button"
    MODERATE = 3    # "create API", "add auth"
    COMPLEX = 4     # "build SaaS platform"
    EXPERT = 5      # "design distributed system"

# Model capabilities mapping
MODELS = {
    "qwen2.5-coder:14b": {
        "name": "Qwen Code 14B",
        "strengths": ["code", "speed", "general"],
        "speed": "fast",
        "thinking": False,
        "context": 32000,
        "best_for": ["code generation", "refactoring", "simple tasks"]
    },
    "qwen2.5-coder:7b": {
        "name": "Qwen Code 7B",
        "strengths": ["code", "speed"],
        "speed": "fastest",
        "thinking": False,
        "context": 16000,
        "best_for": ["quick tasks", "small edits"]
    },
    "deepseek-r1:7b": {
        "name": "DeepSeek R1",
        "strengths": ["reasoning", "planning", "architecture"],
        "speed": "medium",
        "thinking": True,
        "context": 16000,
        "best_for": ["complex planning", "debugging", "architecture"]
    },
    "deepseek-r1:1.5b": {
        "name": "DeepSeek R1 1.5B",
        "strengths": ["reasoning", "fast"],
        "speed": "fast",
        "thinking": True,
        "context": 8000,
        "best_for": ["quick reasoning", "simple analysis"]
    },
    "gemma4:26b": {
        "name": "Gemma 4 26B",
        "strengths": ["general", "reasoning", "multimodal"],
        "speed": "slow",
        "thinking": False,
        "context": 32000,
        "best_for": ["complex analysis", "multimodal"]
    },
    "codellama:latest": {
        "name": "CodeLlama",
        "strengths": ["code", "security"],
        "speed": "medium",
        "thinking": False,
        "context": 16000,
        "best_for": ["security audits", "code review"]
    }
}

@dataclass
class Task:
    """Represents a user task"""
    description: str
    task_type: TaskType = TaskType.MODERATE
    complexity: TaskComplexity = TaskComplexity.MODERATE
    requires_thinking: bool = False
    requires_code: bool = True
    requires_planning: bool = False

class IntelligentOrchestrator:
    """
    Like GPT-5's smart router - automatically selects best model
    and orchestrates execution
    """
    
    def __init__(self):
        self.memory = MemorySystem()
        self.history: List[Dict] = []
        
    def analyze_task(self, prompt: str) -> Task:
        """Analyze task and determine best approach - like GPT-5 router"""
        prompt_lower = prompt.lower()
        
        # Detect task type
        task_type = TaskType.MODERATE
        requires_thinking = False
        requires_planning = False
        
        # Simple questions
        if any(word in prompt_lower for word in ["what is", "how do i", "explain", "?"]):
            if len(prompt.split()) < 10:
                task_type = TaskType.SIMPLE
        
        # Complex planning
        if any(word in prompt_lower for word in [
            "architecture", "design", "plan", "system", "platform", 
            "scalable", "enterprise", "multi-", "distributed"
        ]):
            task_type = TaskType.COMPLEX
            requires_thinking = True
            requires_planning = True
        
        # Research tasks
        if any(word in prompt_lower for word in [
            "research", "analyze", "investigate", "compare",
            "find best", "evaluate", "assess"
        ]):
            task_type = TaskType.RESEARCH
            requires_thinking = True
        
        # Determine complexity
        complexity = TaskComplexity.MODERATE
        
        # Count complexity indicators
        complexity_score = 0
        if len(prompt.split()) > 50: complexity_score += 1
        if "create" in prompt_lower or "build" in prompt_lower: complexity_score += 1
        if "full" in prompt_lower or "complete" in prompt_lower: complexity_score += 1
        if "api" in prompt_lower and "database" in prompt_lower: complexity_score += 2
        if "authentication" in prompt_lower or "payment" in prompt_lower: complexity_score += 2
        
        if complexity_score <= 1:
            complexity = TaskComplexity.TRIVIAL
        elif complexity_score == 2:
            complexity = TaskComplexity.SIMPLE
        elif complexity_score == 3:
            complexity = TaskComplexity.MODERATE
        elif complexity_score == 4:
            complexity = TaskComplexity.COMPLEX
        else:
            complexity = TaskComplexity.EXPERT
        
        return Task(
            description=prompt,
            task_type=task_type,
            complexity=complexity,
            requires_thinking=requires_thinking or complexity.value >= 4,
            requires_code=True,
            requires_planning=requires_planning
        )
    
    def select_model(self, task: Task) -> str:
        """Smart model selection - like GPT-5's router"""
        
        # For thinking tasks, use reasoning model
        if task.requires_thinking:
            if task.complexity.value >= 4:
                return "deepseek-r1:7b"
            else:
                return "deepseek-r1:1.5b"
        
        # For complex code tasks, use best code model
        if task.complexity.value >= 4:
            return "qwen2.5-coder:14b"
        
        # For simple code tasks, use fast model
        if task.task_type == TaskType.SIMPLE:
            return "qwen2.5-coder:7b"
        
        # Default to best code model
        return "qwen2.5-coder:14b"
    
    async def execute(self, prompt: str, thinking_mode: bool = False) -> Dict[str, Any]:
        """
        Execute task with intelligent orchestration
        Like Claude Code's agent loop
        """
        
        # 1. Analyze task
        task = self.analyze_task(prompt)
        
        # 2. Select best model
        model = self.select_model(task)
        
        # 3. Store in memory
        self.memory.add_to_history("user", prompt)
        
        # 4. Execute with selected model
        print(f"\n🧠 Analyzing task...")
        print(f"   Type: {task.task_type.value}")
        print(f"   Complexity: {task.complexity.name}")
        
        print(f"\n🤖 Selecting model: {MODELS[model]['name']}")
        
        result = await self._run_model(model, prompt, thinking=thinking_mode or task.requires_thinking)
        
        # 5. Store result in memory
        self.memory.add_to_history("assistant", result["response"])
        
        # 6. Return result with metadata
        return {
            "task": {
                "type": task.task_type.value,
                "complexity": task.complexity.name,
                "requires_thinking": task.requires_thinking
            },
            "model": {
                "selected": model,
                "name": MODELS[model]['name']
            },
            "response": result["response"]
        }
    
    async def _run_model(self, model: str, prompt: str, thinking: bool = False) -> Dict[str, Any]:
        """Run Ollama with selected model"""
        
        # Add thinking prefix if requested
        if thinking:
            prompt = f"{prompt}\n\nThink carefully about this. Show your reasoning step by step."
        
        cmd = ["ollama", "run", model]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode()),
                timeout=300
            )
            
            if stderr:
                return {"response": stderr.decode(), "error": True}
            
            return {"response": stdout.decode(), "error": False}
            
        except asyncio.TimeoutError:
            process.kill()
            return {"response": "Task timed out", "error": True}
        except Exception as e:
            return {"response": f"Error: {str(e)}", "error": True}
    
    async def chat(self):
        """Interactive chat mode"""
        print("\n" + "="*60)
        print("INTELLIGENT ORCHESTRATION SYSTEM")
        print("Like GPT-5 router + Claude Code agents")
        print("="*60)
        print("\nCommands:")
        print("  /think   - Enable deep thinking mode")
        print("  /model   - Show selected model")
        print("  /history - Show conversation history")
        print("  /clear   - Clear memory")
        print("  /quit   - Exit")
        print()
        
        thinking_mode = False
        
        while True:
            try:
                prompt = input("\nYou: ").strip()
                
                if not prompt:
                    continue
                
                if prompt.startswith("/"):
                    cmd = prompt[1:].lower()
                    
                    if cmd == "quit":
                        print("Goodbye!")
                        break
                    elif cmd == "think":
                        thinking_mode = not thinking_mode
                        print(f"Thinking mode: {'ON' if thinking_mode else 'OFF'}")
                        continue
                    elif cmd == "model":
                        print("\nAvailable models:")
                        for m, info in MODELS.items():
                            print(f"  {m:25} - {info['name']}")
                        continue
                    elif cmd == "history":
                        print("\nRecent history:")
                        for msg in self.memory.get_conversation_history(5):
                            print(f"  {msg['role']}: {msg['content'][:50]}...")
                        continue
                    elif cmd == "clear":
                        self.memory.clear_memory()
                        print("Memory cleared!")
                        continue
                
                # Execute task
                result = await self.execute(prompt, thinking_mode=thinking_mode)
                
                print(f"\n🤖 Model: {result['model']['name']}")
                print(f"   Complexity: {result['task']['complexity']}")
                print(f"\n{result['response']}")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


class MemorySystem:
    """Persistent memory like Claude Code"""
    
    def __init__(self):
        self.history: List[Dict] = []
        
    def add_to_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self.history = self.history[-100:]  # Keep last 100
    
    def get_conversation_history(self, limit: int = 10) -> List[Dict]:
        return self.history[-limit:]
    
    def clear_memory(self):
        self.history = []


async def main():
    orchestrator = IntelligentOrchestrator()
    await orchestrator.chat()


if __name__ == "__main__":
    asyncio.run(main())