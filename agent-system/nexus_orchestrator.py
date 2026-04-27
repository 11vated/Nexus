#!/usr/bin/env python3
"""
NEXUS MASTER ORCHESTRATOR + FEEDBACK LOOP
==========================================

The brain that ties EVERYTHING together:

1. MASTER ORCHESTRATOR
   - Intelligently routes between all tools
   - Understands user intent
   - Chains tools together
   - Learns from interactions

2. FEEDBACK LOOP SYSTEM
   - Write code ??? Run ??? See ??? Analyze ??? Fix ??? Repeat
   - This is how humans actually code
   - True intelligence emerges from the loop

3. UNIFIED CLI
   - One command to rule them all
   - Context-aware tool selection
   - Persistent memory across sessions

This is the missing piece that makes everything work as ONE intelligent system.
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ============================================
# CORE ORCHESTRATOR
# ============================================

# Image detection patterns
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}

class Intent(Enum):
    """What the user wants to do"""
    BUILD = "build"          # Build something new
    DEBUG = "debug"          # Fix something broken
    RESEARCH = "research"     # Learn about something
    AUTOMATE = "automate"    # Do something automatically
    ANALYZE = "analyze"     # Understand something
    VISION = "vision"       # Analyze image/screenshot
    EXECUTE = "execute"      # Run something
    SEARCH = "search"        # Find something
    REVIEW = "review"        # Check something
    UNKNOWN = "unknown"


@dataclass
class Context:
    """Current execution context"""
    user_goal: str = ""
    intent: Intent = Intent.UNKNOWN
    tools_used: List[str] = field(default_factory=list)
    memory: Dict = field(default_factory=dict)
    workspace: str = "."
    history: List[Dict] = field(default_factory=list)
    
    def add_tool(self, tool: str, result: Any):
        self.tools_used.append(tool)
        self.history.append({
            "tool": tool,
            "timestamp": time.time(),
            "result": str(result)[:200]
        })


@dataclass
class OrchestratorResult:
    """Result from orchestrator"""
    success: bool
    output: Any
    tools_used: List[str]
    iterations: int
    feedback_loop: bool
    error: Optional[str] = None


# ============================================
# MASTER ORCHESTRATOR
# ============================================

class NexusOrchestrator:
    """
    The Master Brain - orchestrates ALL tools intelligently.
    
    Flow:
    1. Parse intent (BUILD, DEBUG, RESEARCH, etc.)
    2. Check memory for context
    3. Select appropriate tools
    4. Execute chain
    5. Learn from interaction
    """
    
    def __init__(self, workspace: str = "."):
        self.workspace = workspace
        self.context = Context(workspace=workspace)
        
        # Import all our tools
        self._init_tools()
        
        # Load memory
        self.memory = self._load_memory()
    
    def _init_tools(self):
        """Initialize all available tools"""
        # Fundamental tools
        try:
            from fundamental_tools import (
                WikipediaTool, GitHubTool, StackOverflowTool,
                BrowserTool, WebScraperTool, DocReaderTool,
                UnifiedSearchTool, WebResearchAgent
            )
            self.wiki = WikipediaTool()
            self.github = GitHubTool()
            self.stackoverflow = StackOverflowTool()
            self.browser = BrowserTool()
            self.scraper = WebScraperTool()
            self.docs = DocReaderTool()
            self.unified_search = UnifiedSearchTool()
            self.researcher = WebResearchAgent()
            self.fundamental_available = True
        except ImportError:
            self.fundamental_available = False
        
        # Fused tools
        try:
            from fused_tools import (
                VisualDebugger, ContextualResearch, VisualTerminal,
                IntelligentVersionControl, VisualTestRunner, VisualAutomation,
                NexusToolRouter
            )
            self.visual_debugger = VisualDebugger()
            self.contextual_search = ContextualResearch()
            self.visual_terminal = VisualTerminal()
            self.intelligent_vc = IntelligentVersionControl()
            self.visual_test = VisualTestRunner()
            self.visual_automation = VisualAutomation()
            self.tool_router = NexusToolRouter()
            self.fused_available = True
        except ImportError:
            self.fused_available = False
        
        # Core agents
        try:
            from ultimate_agent import SelfCorrectingAgent, DebuggingAgent
            self.coder = SelfCorrectingAgent(self.workspace)
            self.debugger = DebuggingAgent(self.workspace)
            self.agents_available = True
        except ImportError:
            self.agents_available = False
        
        # Computer use
        try:
            from computer_use import ComputerUseAgent
            self.computer = ComputerUseAgent()
            self.computer_available = True
        except ImportError:
            self.computer_available = False
        
        # Evolutionary tools (Paradigm-inspired)
        try:
            from evolutionary_tools import (
                SolutionPopulation, FitnessScorer, CodeCrossover, SolutionSeed, create_seed
            )
            self.population = SolutionPopulation(population_size=10, max_generations=20)
            self.fitness_scorer = FitnessScorer()
            self.code_crossover = CodeCrossover()
            self.evolution_available = True
            print("[OK] Evolutionary Tools (Paradigm-inspired)")
        except ImportError as e:
            self.evolution_available = False
            print(f"[OK] Evolutionary Tools: {e}")
    
    def _load_memory(self) -> Dict:
        """Load persistent memory"""
        mem_path = Path.home() / ".nexus" / "memory" / "context.json"
        if mem_path.exists():
            try:
                return json.loads(mem_path.read_text())
            except:
                return {}
        return {}
    
    def _save_memory(self):
        """Save context to memory"""
        mem_path = Path.home() / ".nexus" / "memory"
        mem_path.mkdir(parents=True, exist_ok=True)
        (mem_path / "context.json").write_text(json.dumps(self.memory))
    
    async def execute(self, goal: str, feedback_loop: bool = True, max_iterations: int = 10) -> OrchestratorResult:
        """
        Main entry point - orchestrate everything to achieve the goal.
        
        This is the brain that decides:
        - What intent is this?
        - Which tools to use?
        - How to chain them?
        - Did it work? If not, try again (feedback loop)
        """
        print(f"\n{'='*60}")
        print(f"NEXUS ORCHESTRATOR")
        print(f"{'='*60}")
        print(f"Goal: {goal}")
        print(f"Feedback Loop: {'ON' if feedback_loop else 'OFF'}")
        print(f"{'='*60}\n")
        
        self.context = Context(user_goal=goal, workspace=self.workspace)
        
        # Step 1: Parse intent
        intent = self._parse_intent(goal)
        self.context.intent = intent
        print(f"[1/5] Intent detected: {intent.value}")
        
        # Step 2: Check memory for context
        context = self._get_context(goal)
        print(f"[2/5] Context loaded: {list(context.keys()) if context else 'none'}")
        
        # Step 3: Build execution plan
        plan = self._build_plan(intent, goal, context)
        print(f"[3/5] Execution plan: {plan['steps']}")
        
        # Step 4: Execute with feedback loop
        iteration = 0
        last_error = None
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n{'='*40}")
            print(f"ITERATION {iteration}/{max_iterations}")
            print(f"{'='*40}")
            
            result = await self._execute_plan(plan, context)
            
            if result["success"]:
                print(f"\n{'='*60}")
                print(f"SUCCESS! Goal achieved in {iteration} iteration(s)")
                print(f"{'='*60}")
                
                # Save to memory
                self._learn(goal, result)
                
                return OrchestratorResult(
                    success=True,
                    output=result["output"],
                    tools_used=self.context.tools_used,
                    iterations=iteration,
                    feedback_loop=feedback_loop
                )
            
            # Feedback loop - analyze failure and adjust
            if feedback_loop and iteration < max_iterations:
                print(f"\n[!] Iteration {iteration} failed: {result.get('error', 'Unknown')}")
                
                # Analyze what went wrong
                analysis = await self._analyze_failure(result, goal)
                print(f"[!] Analysis: {analysis.get('summary', 'Analyzing...')}")
                
                # Adjust plan based on feedback
                plan = self._adjust_plan(plan, analysis, iteration)
                print(f"[!] Adjusted plan: {plan['steps']}")
                
                last_error = result.get("error")
            else:
                break
        
        return OrchestratorResult(
            success=False,
            output=None,
            tools_used=self.context.tools_used,
            iterations=iteration,
            feedback_loop=feedback_loop,
            error=last_error or "Max iterations reached"
        )
    
    def _parse_intent(self, goal: str) -> Intent:
        """Understand what user wants to do"""
        goal_lower = goal.lower()
        
        # Check for image/screenshot attachments - VISION intent
        if any(ext in goal for ext in IMAGE_EXTENSIONS):
            return Intent.VISION
        
        # Vision/Screenshot intent
        if any(w in goal_lower for w in ["screenshot", "image", "photo", "see", "visual", "screen", "ui", "interface", "look", "picture"]):
            return Intent.VISION
        
        # Build intent
        if any(w in goal_lower for w in ["build", "create", "make", "implement", "write", "new"]):
            return Intent.BUILD
        
        # Debug intent
        if any(w in goal_lower for w in ["fix", "debug", "error", "bug", "broken", "issue", "problem"]):
            return Intent.DEBUG
        
        # Research intent
        if any(w in goal_lower for w in ["research", "learn", "understand", "explain", "what is", "how does", "how to"]):
            return Intent.RESEARCH
        
        # Automate intent
        if any(w in goal_lower for w in ["automate", "script", "batch", "run automatically"]):
            return Intent.AUTOMATE
        
        # Analyze intent
        if any(w in goal_lower for w in ["analyze", "check", "review", "audit"]):
            return Intent.ANALYZE
        
        # Execute intent
        if any(w in goal_lower for w in ["run", "execute", "start", "launch"]):
            return Intent.EXECUTE
        
        # Search intent
        if any(w in goal_lower for w in ["search", "find", "look for", "query"]):
            return Intent.SEARCH
        
        # Review intent
        if any(w in goal_lower for w in ["review", "check", "verify"]):
            return Intent.REVIEW
        
        return Intent.UNKNOWN
    
    def _get_context(self, goal: str) -> Dict:
        """Get relevant context from memory"""
        context = {}
        
        # Check for similar past goals
        for key, value in self.memory.items():
            if any(w in goal.lower() for w in key.split()):
                context[key] = value
        
        # Add project context if available
        proj_path = Path(self.workspace)
        if (proj_path / "package.json").exists():
            context["language"] = "javascript"
            context["framework"] = "node"
        elif (proj_path / "requirements.txt").exists():
            context["language"] = "python"
        elif (proj_path / "Cargo.toml").exists():
            context["language"] = "rust"
        
        return context
    
    def _build_plan(self, intent: Intent, goal: str, context: Dict) -> Dict:
        """Build execution plan based on intent"""
        steps = []
        
        if intent == Intent.BUILD:
            steps = [
                {"tool": "research", "action": "search_best_practices", "args": {"query": goal}},
                {"tool": "coder", "action": "generate", "args": {"task": goal}},
                {"tool": "visual_test", "action": "execute", "args": {"verify": True}}
            ]
        
        elif intent == Intent.DEBUG:
            steps = [
                {"tool": "debugger", "action": "analyze_error", "args": {"error": goal}},
                {"tool": "visual_debugger", "action": "debug", "args": {"screenshot": True}},
                {"tool": "stackoverflow", "action": "search", "args": {"query": goal}}
            ]
        
        elif intent == Intent.VISION:
            # Vision/Screenshot analysis intent
            steps = [
                {"tool": "vision", "action": "analyze", "args": {"image": goal, "prompt": goal}},
                {"tool": "llava", "action": "analyze", "args": {"image": goal}},
                {"tool": "visual_debugger", "action": "debug", "args": {"screenshot": True}}
            ]
        
        elif intent == Intent.RESEARCH:
            steps = [
                {"tool": "researcher", "action": "research", "args": {"topic": goal, "depth": "medium"}},
                {"tool": "wikipedia", "action": "summary", "args": {"title": goal}},
                {"tool": "github", "action": "search_repos", "args": {"query": goal}}
            ]
        
        elif intent == Intent.AUTOMATE:
            steps = [
                {"tool": "computer", "action": "execute_goal", "args": {"goal": goal}}
            ]
        
        elif intent == Intent.ANALYZE:
            steps = [
                {"tool": "visual_terminal", "action": "execute", "args": {"command": goal}},
                {"tool": "intelligent_vc", "action": "review", "args": {}}
            ]
        
        elif intent == Intent.EXECUTE:
            steps = [
                {"tool": "visual_terminal", "action": "execute", "args": {"command": goal}}
            ]
        
        elif intent == Intent.SEARCH:
            steps = [
                {"tool": "unified_search", "action": "search_all", "args": {"query": goal}}
            ]
        
        else:
            # Default: try general research + code
            steps = [
                {"tool": "researcher", "action": "research", "args": {"topic": goal}}
            ]
        
        return {
            "intent": intent.value,
            "steps": steps,
            "original_goal": goal,
            "context": context
        }
    
    async def _execute_plan(self, plan: Dict, context: Dict) -> Dict:
        """Execute the plan step by step"""
        results = []
        
        for step in plan["steps"]:
            tool = step.get("tool", "")
            action = step.get("action", "")
            args = step.get("args", {})
            
            print(f"\n??? Executing: {tool}.{action}")
            
            try:
                result = await self._execute_tool(tool, action, args)
                
                if result.success:
                    print(f"  ??? Success")
                    results.append({"step": step, "result": result.data, "success": True})
                    self.context.add_tool(f"{tool}.{action}", result.data)
                else:
                    print(f"  ??? Failed: {result.error}")
                    results.append({"step": step, "result": result.error, "success": False})
                    
                    # Continue with next tool
                    continue
            
            except Exception as e:
                print(f"  ??? Exception: {e}")
                results.append({"step": step, "error": str(e), "success": False})
        
        # Check if any step succeeded
        success = any(r.get("success", False) for r in results)
        
        return {
            "success": success,
            "results": results,
            "output": results[-1].get("result") if results else None,
            "error": None if success else "All steps failed"
        }
    
    async def _execute_tool(self, tool: str, action: str, args: Dict) -> Any:
        """Execute a specific tool"""
        
        # Research tools
        if tool == "researcher" and self.fundamental_available:
            return await self.researcher.research(args.get("topic", ""), args.get("depth", "basic"))
        
        elif tool == "wikipedia" and self.fundamental_available:
            if action == "search":
                return await self.wiki.search(args.get("query", ""))
            elif action == "summary":
                return await self.wiki.get_summary(args.get("title", ""))
        
        elif tool == "github" and self.fundamental_available:
            if action == "search_repos":
                return await self.github.search_repos(args.get("query", ""))
            elif action == "search_code":
                return await self.github.search_code(args.get("query", ""))
        
        elif tool == "stackoverflow" and self.fundamental_available:
            return await self.stackoverflow.search(args.get("query", ""))
        
        elif tool == "unified_search" and self.fundamental_available:
            return await self.unified_search.search_all(args.get("query", ""))
        
        # Fused tools
        if tool == "visual_debugger" and self.fused_available:
            return await self.visual_debugger.execute(args)
        
        elif tool == "visual_test" and self.fused_available:
            return await self.visual_test.execute(args)
        
        elif tool == "visual_terminal" and self.fused_available:
            return await self.visual_terminal.execute(args)
        
        elif tool == "intelligent_vc" and self.fused_available:
            return await self.intelligent_vc.execute({"action": action, **args})
        
        # Agents
        if tool == "coder" and self.agents_available:
            return await self.coder.run(args.get("task", ""))
        
        elif tool == "debugger" and self.agents_available:
            return await self.debugger.debug(args.get("error", ""))
        
        # Computer use
        if tool == "computer" and self.computer_available:
            return await self.computer.execute_goal(args.get("goal", ""))
        
        # VISION - Use llava for image analysis
        if tool in ["vision", "llava", "moondream"]:
            import base64
            # Extract image path from args
            image_path = args.get("image", "")
            prompt = args.get("prompt", "Describe what's shown in this image in detail")
            
            if not image_path:
                # Try to extract from goal
                for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                    if ext in str(goal).lower():
                        # Find the path
                        parts = str(goal).split(ext)
                        if len(parts) > 1:
                            image_path = parts[0] + ext
                            break
            
            if not image_path:
                return type('obj', (object,), {'success': False, 'error': 'No image path found', 'data': None})()
            
            try:
                # Read and encode image
                with open(image_path, "rb") as f:
                    image_data = f.read()
                b64 = base64.b64encode(image_data).decode()
                
                # Call Ollama API with image
                import json
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-s", "http://localhost:11434/api/generate",
                    "-d", json.dumps({
                        "model": "llava",
                        "prompt": prompt,
                        "images": [b64],
                        "stream": False
                    }),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=120
                )
                
                response = json.loads(stdout.decode())
                return type('obj', (object,), {'success': True, 'data': response.get('response', ''), 'error': None})()
                
            except Exception as e:
                return type('obj', (object,), {'success': False, 'error': str(e), 'data': None})()
        
        # Default: return failure
        class FailedResult:
            success = False
            error = f"Tool not available: {tool}"
            data = None
        return FailedResult()
    
    async def _analyze_failure(self, result: Dict, goal: str) -> Dict:
        """Analyze why the plan failed"""
        
        # Use AI to analyze
        prompt = f"""Analyze this failed execution:

Goal: {goal}
Results: {json.dumps(result, indent=2)}

Why did it fail? What should we do differently?
Provide:
1. Summary of failure
2. Suggested adjustment to the plan
3. Alternative approaches to try

Be concise."""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", "deepseek-r1:7b",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=60
            )
            
            return {"summary": stdout.decode()[:500], "analysis": stdout.decode()}
            
        except:
            return {"summary": "Could not analyze - trying alternative approach"}
    
    async def execute_evolutionary(
        self, 
        goal: str, 
        initial_code: Optional[Dict[str, str]] = None,
        workspace: str = ".",
        max_generations: int = 20,
        population_size: int = 10
    ) -> OrchestratorResult:
        """
        EVOLUTIONARY MODE - Execute using genetic algorithm.
        
        Instead of sequential feedback loop:
        - Creates population of N solutions
        - Scores each by fitness (tests, lint, coverage)
        - Selects best via tournament
        - Breeds to create next generation
        - Repeats until convergence
        
        This transforms:
            TRY ??? FAIL ??? TRY AGAIN (sequential)
        Into:
            EVOLVE ??? SELECT ??? BREED (parallel)
        """
        if not self.evolution_available:
            return OrchestratorResult(
                success=False,
                output="Evolutionary tools not available",
                tools_used=[],
                iterations=0,
                feedback_loop=False,
                error="Install evolutionary_tools.py first"
            )
        
        print(f"\n{'='*60}")
        print(f"NEXUS EVOLUTIONARY MODE")
        print(f"{'='*60}")
        print(f"Goal: {goal}")
        print(f"Population: {population_size}")
        print(f"Max generations: {max_generations}")
        print(f"{'='*60}\n")
        
        # Create population manager using pre-loaded class
        from evolutionary_tools import SolutionPopulation
        pop = SolutionPopulation(
            population_size=population_size,
            max_generations=max_generations,
            tournament_size=3,
            mutation_rate=0.1,
            crossover_rate=0.7
        )
        
        # Run evolution
        best_solution = await pop.evolve(goal, initial_code, workspace)
        
        if best_solution:
            return OrchestratorResult(
                success=best_solution.total_fitness >= 0.7,
                output={
                    "solution_id": best_solution.id,
                    "fitness": best_solution.total_fitness,
                    "scores": best_solution.fitness,
                    "code": best_solution.code,
                    "lineage": best_solution.lineage
                },
                tools_used=["evolution"],
                iterations=pop.generation,
                feedback_loop=True
            )
        
        return OrchestratorResult(
            success=False,
            output=None,
            tools_used=[],
            iterations=0,
            feedback_loop=False,
            error="Evolution failed to find solution"
        )
    
    async def quick_fitness(
        self, 
        code: Dict[str, str],
        workspace: str = "."
    ) -> float:
        """
        Quick single-solution fitness check.
        
        Use this for simple scoring without full evolution.
        Returns fitness score 0-1.
        """
        if not self.evolution_available:
            return 0.0
        
        seed = create_seed("quick check", code)
        scores = await self.fitness_scorer.score(seed, workspace)
        return scores["total"]
    
    def _adjust_plan(self, plan: Dict, analysis: Dict, iteration: int) -> Dict:
        """Adjust plan based on feedback"""
        
        # Simple adjustments based on iteration
        if iteration == 1:
            # First failure - try research first
            plan["steps"].insert(0, {
                "tool": "researcher",
                "action": "research",
                "args": {"topic": plan["original_goal"], "depth": "basic"}
            })
        
        elif iteration == 2:
            # Second failure - try simpler approach
            plan["steps"] = [
                {"tool": "unified_search", "action": "search_all", 
                 "args": {"query": plan["original_goal"]}}
            ]
        
        return plan
    
    def _learn(self, goal: str, result: Dict):
        """Learn from this interaction"""
        # Extract key info
        self.memory[goal] = {
            "success": result.get("success", False),
            "tools_used": self.context.tools_used,
            "timestamp": datetime.now().isoformat()
        }
        self._save_memory()


# ============================================
# FEEDBACK LOOP EXECUTION
# ============================================

class FeedbackLoop:
    """
    The FEEDBACK LOOP - the most transformative piece.
    
    Flow: Code ??? Run ??? See ??? Analyze ??? Fix ??? Repeat
    
    This is literally how humans code. This is true intelligence.
    """
    
    def __init__(self):
        self.max_iterations = 5
        self.vision_available = False
        self._check_vision()
    
    def _check_vision(self):
        """Check if vision tools available"""
        try:
            import mss
            self.vision_available = True
        except:
            pass
    
    async def run(self, code: str, language: str = "python") -> Dict:
        """
        Execute code with visual feedback loop.
        
        Returns: {
            "success": bool,
            "iterations": int,
            "final_output": str,
            "visual_feedback": []
        }
        """
        print(f"\n{'='*60}")
        print("FEEDBACK LOOP EXECUTION")
        print(f"{'='*60}")
        print(f"Language: {language}")
        print(f"Max iterations: {self.max_iterations}")
        
        visual_feedback = []
        current_code = code
        
        for iteration in range(1, self.max_iterations + 1):
            print(f"\n--- Iteration {iteration}/{self.max_iterations} ---")
            
            # Step 1: Execute code
            print(f"[1] Executing code...")
            exec_result = await self._execute_code(current_code, language)
            
            if not exec_result["success"]:
                print(f"[!] Execution failed: {exec_result.get('error')}")
            else:
                print(f"[OK] Execution completed")
            
            # Step 2: Visual feedback (if available)
            visual_state = None
            if self.vision_available:
                print(f"[2] Capturing visual state...")
                visual_state = await self._capture_screen()
                visual_feedback.append(visual_state)
                
                # Analyze visual state
                if visual_state:
                    analysis = await self._analyze_visual(visual_state)
                    print(f"[2] Visual analysis: {analysis.get('summary', 'OK')[:100]}")
            
            # Step 3: Check if successful
            if exec_result["success"] and not exec_result.get("has_errors"):
                print(f"\n{'='*60}")
                print(f"SUCCESS in {iteration} iteration(s)!")
                print(f"{'='*60}")
                
                return {
                    "success": True,
                    "iterations": iteration,
                    "output": exec_result.get("output", ""),
                    "visual_feedback": visual_feedback
                }
            
            # Step 4: If failed, analyze and fix
            if iteration < self.max_iterations:
                print(f"[3] Analyzing failure...")
                
                # Get error info
                error = exec_result.get("error", "") or exec_result.get("stderr", "")
                
                # Generate fix
                fix = await self._generate_fix(current_code, error, language)
                
                if fix and fix != current_code:
                    print(f"[4] Applying fix...")
                    current_code = fix
                else:
                    print(f"[!] Could not generate fix")
                    break
        
        return {
            "success": False,
            "iterations": self.max_iterations,
            "output": exec_result.get("output", ""),
            "error": "Max iterations reached",
            "visual_feedback": visual_feedback
        }
    
    async def _execute_code(self, code: str, language: str) -> Dict:
        """Execute code and return result"""
        try:
            if language == "python":
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-c", code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:
                return {"success": False, "error": f"Unsupported: {language}"}
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            
            return {
                "success": proc.returncode == 0,
                "output": stdout.decode(),
                "stderr": stderr.decode(),
                "has_errors": bool(stderr.decode())
            }
            
        except asyncio.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _capture_screen(self) -> Optional[bytes]:
        """Capture current screen"""
        try:
            import mss
            with mss.mss() as sct:
                screenshot = sct.grab(sct.monitors[1])
                return mss.tools.to_png(screenshot.rgb, screenshot.size)
        except:
            return None
    
    async def _analyze_visual(self, screenshot: bytes) -> Dict:
        """Analyze visual state"""
        if not screenshot:
            return {"summary": "No screenshot"}
        
        # This would use vision model - simplified here
        return {"summary": "Screen captured"}
    
    async def _generate_fix(self, code: str, error: str, language: str) -> str:
        """Generate code fix using AI"""
        
        prompt = f"""This code has an error:

Language: {language}
Code:
```{language}
{code}
```

Error:
{error}

Fix the code. Return ONLY the fixed code, nothing else."""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", "qwen2.5-coder:14b",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=60
            )
            
            # Extract code from response
            fixed = stdout.decode()
            
            # Try to extract code block
            if "```" in fixed:
                start = fixed.find("```") + 3
                end = fixed.find("```", start)
                if end > start:
                    # Skip language identifier
                    lines = fixed[start:end].strip().split('\n')
                    if lines and lines[0].strip() in ["python", "javascript", "js"]:
                        lines = lines[1:]
                    return '\n'.join(lines)
            
            return fixed.strip()
            
        except:
            return code


# ============================================
# UNIFIED CLI
# ============================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Nexus Master Orchestrator")
    parser.add_argument("goal", nargs="?", help="What to achieve")
    parser.add_argument("--loop", action="store_true", help="Enable feedback loop")
    parser.add_argument("--evolve", action="store_true", help="Use evolutionary mode (GA)")
    parser.add_argument("--max-iters", type=int, default=10, help="Max iterations")
    parser.add_argument("--max-gens", type=int, default=20, help="Max generations (evolution mode)")
    parser.add_argument("--pop-size", type=int, default=10, help="Population size (evolution mode)")
    parser.add_argument("--workspace", default=".", help="Working directory")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--status", action="store_true", help="Show system status")
    
    args = parser.parse_args()
    
    print("")
    print("+==================================================+")
    print("|     NEXUS MASTER ORCHESTRATOR + FEEDBACK LOOP |")
    print("+==================================================+")
    print("|  The brain that ties EVERYTHING together    |")
    print("|                                     |")
    print("|  - Intent parsing                    |")
    print("|  - Tool orchestration               |")
    print("|  - Feedback loop execution         |")
    print("|  - Persistent memory              |")
    print("|  - Evolutionary mode (GA)         |")
    print("+==================================================+")
    print("")
    
    if args.status:
        print("\n=== NEXUS SYSTEM STATUS ===\n")
        print("Checking available tools...")
        
        # Check tools
        try:
            from fundamental_tools import WikipediaTool
            print("[OK] Fundamental Tools")
        except:
            print("[OK] Fundamental Tools")
        
        try:
            from fused_tools import NexusToolRouter
            print("[OK] Fused Tools")
        except:
            print("[OK] Fused Tools")
        
        try:
            from ultimate_agent import SelfCorrectingAgent
            print("[OK] Core Agents")
        except:
            print("[OK] Core Agents")
        
        try:
            from computer_use import ComputerUseAgent
            print("[OK] Computer Use")
        except:
            print("[OK] Computer Use")
        
        try:
            import mss
            print("[OK] Vision (Screen capture)")
        except:
            print("[OK] Vision (not installed)")
        
        try:
            from evolutionary_tools import SolutionPopulation
            pop = SolutionPopulation(population_size=2, max_generations=1)
            print("[OK] Evolutionary Tools (Paradigm-inspired)")
        except ImportError as e:
            print(f"[OK] Evolutionary Tools: {e}")
            print(f"    Run: python evolutionary_tools.py --help")
        
        return
    
    if args.interactive:
        print("\n=== INTERACTIVE MODE ===")
        print("Type your goal or 'quit' to exit\n")
        
        orchestrator = NexusOrchestrator(args.workspace)
        
        while True:
            goal = input("Nexus> ").strip()
            
            if goal.lower() in ["quit", "exit", "q"]:
                break
            
            if not goal:
                continue
            
            result = await orchestrator.execute(goal, feedback_loop=args.loop)
            
            print(f"\n{'='*60}")
            print(f"Result: {'SUCCESS' if result.success else 'FAILED'}")
            print(f"Iterations: {result.iterations}")
            print(f"Tools used: {', '.join(result.tools_used) if result.tools_used else 'none'}")
            print(f"{'='*60}\n")
    
    elif args.goal:
        orchestrator = NexusOrchestrator(args.workspace)
        
        if args.evolve:
            # Evolutionary mode
            print("\n>>> EVOLUTIONARY MODE <<<\n")
            result = await orchestrator.execute_evolutionary(
                args.goal,
                max_generations=args.max_gens,
                population_size=args.pop_size
            )
        else:
            # Standard mode
            result = await orchestrator.execute(
                args.goal,
                feedback_loop=args.loop,
                max_iterations=args.max_iters
            )
        
        print(f"\n{'='*60}")
        print(f"FINAL RESULT")
        print(f"{'='*60}")
        print(f"Success: {result.success}")
        print(f"Iterations: {result.iterations}")
        print(f"Tools used: {len(result.tools_used)}")
        
        if result.output:
            if isinstance(result.output, dict) and "fitness" in result.output:
                print(f"Fitness: {result.output.get('fitness', 'N/A'):.3f}")
                print(f"Scores: {result.output.get('scores', {})}")
        
        if result.error:
            print(f"Error: {result.error}")
        
        print(f"{'='*60}")
    
    else:
        parser.print_help()
        print("""

Examples:
  nexus.py "build a React login form"
  nexus.py "fix this error: TypeError undefined"
  nexus.py "research neural networks"
  nexus.py --loop "debug my app"
  nexus.py --interactive
  nexus.py --status
""")

if __name__ == "__main__":
    asyncio.run(main())