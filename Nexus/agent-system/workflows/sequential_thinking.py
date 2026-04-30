import subprocess
import json
from typing import Dict, List, Optional
from datetime import datetime


class SequentialThinkingAgent:
    def __init__(self, model: str = "ollama/qwen2.5-coder:14b", max_thoughts: int = 5):
        self.model = model
        self.max_thoughts = max_thoughts
        self.thought_history = []
    
    def think(self, problem: str, context: Optional[Dict] = None) -> Dict:
        print(f"\n[THINK] Analyzing: {problem[:100]}...")
        
        thoughts = []
        
        thought_prompt = f"""You are solving this problem with deep reasoning:

PROBLEM: {problem}

{self._format_context(context)}

Think step by step. Consider:
1. What is the core issue?
2. What approaches could work?
3. What are the tradeoffs?
4. What is the best approach?
5. How would you implement it?

Output ONLY a JSON object with keys: thought, confidence, next_step
"""
        
        for i in range(self.max_thoughts):
            try:
                result = subprocess.run(
                    f'ollama run {self.model} "{thought_prompt}"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                output = result.stdout.strip()
                thought_data = self._parse_json(output)
                
                if thought_data:
                    thoughts.append(thought_data)
                    self.thought_history.append(thought_data)
                    
                    print(f"  [{i+1}] {thought_data.get('thought', '')[:80]}...")
                    
                    if thought_data.get("confidence", 0) > 0.8:
                        print(f"  [DECISION] High confidence - stopping early")
                        break
                    
                    next_step = thought_data.get("next_step", "")
                    if next_step:
                        thought_prompt += f"\n\nNew consideration: {next_step}"
            
            except Exception as e:
                print(f"  [ERROR] {e}")
                break
        
        decision = self._make_decision(thoughts)
        
        return {
            "problem": problem,
            "thoughts": thoughts,
            "decision": decision,
            "timestamp": datetime.now().isoformat()
        }
    
    def _format_context(self, context: Optional[Dict]) -> str:
        if not context:
            return ""
        
        parts = []
        for key, value in context.items():
            parts.append(f"{key}: {value}")
        
        return "\nContext: " + ", ".join(parts)
    
    def _parse_json(self, text: str) -> Optional[Dict]:
        text = text.strip().strip("`")
        if text.startswith("json"):
            text = text[4:]
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            lines = text.split("\n")
            return {
                "thought": text[:200],
                "confidence": 0.5,
                "next_step": ""
            }
    
    def _make_decision(self, thoughts: List[Dict]) -> Dict:
        if not thoughts:
            return {"action": "unknown", "confidence": 0}
        
        avg_confidence = sum(t.get("confidence", 0) for t in thoughts) / len(thoughts)
        
        best = max(thoughts, key=lambda t: t.get("confidence", 0))
        
        return {
            "action": best.get("next_step", "proceed"),
            "confidence": avg_confidence,
            "reasoning": best.get("thought", "")
        }


class MultiAgentOrchestrator:
    def __init__(self, model: str = "ollama/qwen2.5-coder:14b"):
        self.model = model
        self.thinker = SequentialThinkingAgent(model)
        self.agents = {}
    
    def register_agent(self, name: str, agent_class, config: Dict):
        self.agents[name] = {
            "class": agent_class,
            "config": config,
            "runs": 0
        }
    
    def run_parallel(self, task: str, agent_names: List[str]) -> Dict:
        results = {}
        
        for name in agent_names:
            if name in self.agents:
                print(f"[ORCHESTRATOR] Running {name}...")
                agent_info = self.agents[name]
                results[name] = {
                    "status": "completed",
                    "runs": agent_info["runs"] + 1
                }
                agent_info["runs"] += 1
        
        return {
            "task": task,
            "results": results,
            "agents_used": list(agent_names)
        }
    
    def run_distributed(self, task: str) -> Dict:
        prompt = f"""Orchestrate this task: {task}

Available agents: {list(self.agents.keys())}

Create a plan using multiple agents.
Output JSON with: plan (array of steps), estimated_time
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            plan = self._parse_json(result.stdout)
            return {"plan": plan, "status": "planned"}
        except Exception as e:
            return {"error": str(e)}
    
    def _parse_json(self, text: str) -> List:
        text = text.strip().strip("`").strip("json").strip("```")
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return []


class DeepReasoningAgent:
    def __init__(self, model: str = "ollama/qwen2.5-coder:14b"):
        self.model = model
        self.reasoning_history = []
    
    def analyze_and_solve(self, problem: str, constraints: Optional[Dict] = None) -> Dict:
        print(f"[DEEP REASONING] {problem[:80]}...")
        
        constraints_text = ""
        if constraints:
            constraints_text = f"\nConstraints: {constraints}"
        
        thinking = self.think(problem, constraints_text)
        
        self.reasoning_history.append({
            "problem": problem,
            "thinking": thinking,
            "timestamp": datetime.now().isoformat()
        })
        
        return thinking
    
    def think(self, problem: str, constraints: str) -> Dict:
        prompt = f"""Deep analyze and solve:

Problem: {problem}{constraints}

Provide:
1. Root cause analysis
2. Alternative approaches
3. Recommended solution with reasoning
4. Potential risks and mitigations
5. Implementation steps

Output ONLY valid JSON.
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=90
            )
            
            response = result.stdout.strip()
            
            try:
                data = json.loads(response.strip("`").strip("json"))
                return data
            except:
                return {"analysis": response[:500], "solution": "needs more thinking"}
        except Exception as e:
            return {"error": str(e)}
    
    def get_history(self) -> List[Dict]:
        return self.reasoning_history


def create_reasoning_agent(model: str = "ollama/qwen2.5-coder:14b") -> SequentialThinkingAgent:
    return SequentialThinkingAgent(model=model)


def create_orchestrator(model: str = "ollama/qwen2.5-coder:14b") -> MultiAgentOrchestrator:
    return MultiAgentOrchestrator(model=model)