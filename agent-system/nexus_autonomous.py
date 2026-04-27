#!/usr/bin/env python3
"""
NEXUS AUTONOMOUS LOOP
=====================

Self-contained autonomous agent that:
1. Watches for new tasks (file-based queue)
2. Auto-executes them with feedback loop
3. Self-heals from errors
4. Reports progress
5. Learns from execution history

Usage:
    python nexus_autonomous.py --daemon      # Run forever
    python nexus_autonomous.py task.txt       # Execute single task
    python nexus_autonomous.py --watch       # Watch for tasks
"""

import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import hashlib


# ============================================
# AUTO-DISCOVERY SYSTEM
# ============================================

class ToolDiscovery:
    """Auto-discovers available tools and their capabilities"""
    
    def __init__(self):
        self.tools: Dict[str, Dict] = {}
        self._discover()
    
    def _discover(self):
        """Discover all available tools"""
        
        # Ollama models
        try:
            result = subprocess.run(
                ["ollama", "list"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            models = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
            self.tools['ollama'] = {
                'available': True,
                'models': models,
                'type': 'llm'
            }
        except:
            self.tools['ollama'] = {'available': False}
        
        # Vision models
        vision_models = ['llava', 'moondream']
        for m in vision_models:
            if m in self.tools.get('ollama', {}).get('models', []):
                self.tools[f'vision_{m}'] = {
                    'available': True,
                    'type': 'vision'
                }
        
        # Git
        try:
            subprocess.run(['git', '--version'], capture_output=True, timeout=5)
            self.tools['git'] = {'available': True, 'type': 'vcs'}
        except:
            self.tools['git'] = {'available': False}
        
        # Python
        try:
            ver = subprocess.run(
                [sys.executable, '--version'], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            self.tools['python'] = {
                'available': True,
                'version': ver.stdout.strip(),
                'type': 'runtime'
            }
        except:
            self.tools['python'] = {'available': False}
        
        # Node
        try:
            ver = subprocess.run(
                ['node', '--version'], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            self.tools['node'] = {
                'available': True,
                'version': ver.stdout.strip(),
                'type': 'runtime'
            }
        except:
            self.tools['node'] = {'available': False}
        
        # Screen capture
        try:
            import mss
            self.tools['screenshot'] = {'available': True, 'type': 'vision'}
        except:
            self.tools['screenshot'] = {'available': False}
        
        # Check local tools
        agent_dir = Path(__file__).parent
        for tool_file in agent_dir.glob('*.py'):
            if tool_file.stem not in ['nexus_autonomous', '__init__']:
                self.tools[f'local_{tool_file.stem}'] = {
                    'available': True,
                    'path': str(tool_file),
                    'type': 'local'
                }
    
    def get_tool(self, category: str) -> Optional[str]:
        """Get best tool for category"""
        if category == 'vision':
            for t in ['vision_llava', 'vision_moondream']:
                if self.tools.get(t, {}).get('available'):
                    return t
            return None
        if category == 'llm':
            if self.tools.get('ollama', {}).get('available'):
                models = self.tools['ollama'].get('models', [])
                for pref in ['qwen2.5-coder:14b', 'qwen2.5-coder', 'deepseek-r1']:
                    if pref in models:
                        return pref
                return models[0] if models else None
        return None
    
    def report(self) -> str:
        """Generate status report"""
        lines = ["=== TOOL DISCOVERY REPORT ==="]
        for tool, info in sorted(self.tools.items()):
            status = "OK" if info.get('available') else "SKIP"
            lines.append(f"[{status}] {tool}")
            if info.get('available'):
                if 'models' in info:
                    lines.append(f"    Models: {', '.join(info['models'][:5])}")
        return '\n'.join(lines)


# ============================================
# SELF-HEALING SYSTEM
# ============================================

@dataclass
class ErrorPattern:
    """Known error patterns and fixes"""
    pattern: str
    fix_template: str
    examples: List[str] = field(default_factory=list)


class SelfHealer:
    """Automatically recovers from errors"""
    
    PATTERNS = [
        ErrorPattern(
            pattern=r"(?i)module.*not found|ImportError",
            fix_template="pip install {module}",
            examples=["numpy", "requests", "pytest"]
        ),
        ErrorPattern(
            pattern=r"(?i)syntax error",
            fix_template="review code structure",
            examples=[]
        ),
        ErrorPattern(
            pattern=r"(?i)timeout|timed out",
            fix_template="increase timeout or simplify task",
            examples=[]
        ),
        ErrorPattern(
            pattern=r"(?i)permission denied",
            fix_template="check file permissions",
            examples=[]
        ),
        ErrorPattern(
            pattern=r"(?i)connection.*refused|ConnectionError",
            fix_template="check if service is running",
            examples=["ollama", "docker"]
        ),
    ]
    
    def __init__(self):
        self.history: List[Dict] = []
    
    def analyze(self, error: str, context: str = "") -> Dict[str, Any]:
        """Analyze error and suggest fix"""
        
        for pattern in self.PATTERNS:
            if re.search(pattern.pattern, error):
                # Try to extract module name
                module = None
                if 'module' in pattern.pattern.lower():
                    match = re.search(r"module ['\"]([^'\"]+)['\"]", error)
                    if match:
                        module = match.group(1)
                
                return {
                    'matched': True,
                    'pattern': pattern.pattern,
                    'fix': pattern.fix_template.format(module=module or 'unknown'),
                    'auto_fix': module and self._can_auto_fix(module)
                }
        
        return {
            'matched': False,
            'fix': 'Manual review required',
            'auto_fix': False
        }
    
    def _can_auto_fix(self, module: str) -> bool:
        """Check if we can auto-fix this"""
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', module, '--dry-run'],
                capture_output=True,
                timeout=30
            )
            return True
        except:
            return False
    
    def apply_fix(self, fix: str) -> bool:
        """Apply automatic fix"""
        try:
            if fix.startswith('pip install'):
                module = fix.replace('pip install', '').strip()
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', module],
                    capture_output=True,
                    timeout=60
                )
                return result.returncode == 0
        except:
            pass
        return False
    
    def learn(self, error: str, fix_applied: str, worked: bool):
        """Learn from fix outcome"""
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'error': error[:100],
            'fix': fix_applied,
            'worked': worked
        })


# ============================================
# AUTONOMOUS EXECUTOR
# ============================================

class AutonomousExecutor:
    """
    Main autonomous loop - executes tasks with self-healing.
    
    Modes:
    - single: Execute one task and exit
    - daemon: Run forever, watching for tasks
    - watch: Watch a directory for new task files
    """
    
    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace)
        self.discovery = ToolDiscovery()
        self.healer = SelfHealer()
        self.memory = Memory()
        self.running = False
        
        # Task queue
        self.queue_dir = self.workspace / ".nexus" / "tasks"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file
        self.log_dir = self.workspace / ".nexus" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    async def execute_task(self, task: str, max_iterations: int = 5) -> Dict[str, Any]:
        """Execute a single task with feedback loop"""
        
        print(f"\n{'='*60}")
        print(f"EXECUTING: {task[:80]}{'...' if len(task) > 80 else ''}")
        print(f"{'='*60}")
        
        iterations = 0
        current_output = ""
        last_error = None
        
        while iterations < max_iterations:
            iterations += 1
            print(f"\n--- Iteration {iterations}/{max_iterations} ---")
            
            try:
                # Step 1: Plan
                plan = await self._plan_execution(task, current_output)
                
                # Step 2: Execute plan
                result = await self._execute_plan(plan)
                
                if result.get('success'):
                    print(f"\n✓ SUCCESS in {iterations} iteration(s)")
                    
                    # Learn from success
                    self.memory.remember(task, result)
                    
                    return {
                        'success': True,
                        'iterations': iterations,
                        'result': result,
                        'heals': 0
                    }
                
                # Step 3: If failed, analyze and heal
                last_error = result.get('error', 'Unknown error')
                print(f"✗ Error: {last_error[:100]}")
                
                # Analyze error
                analysis = self.healer.analyze(last_error, task)
                print(f"  Analysis: {analysis.get('fix', 'Manual review')}")
                
                if analysis.get('auto_fix'):
                    print(f"  → Auto-fixing...")
                    if self.healer.apply_fix(analysis['fix']):
                        print(f"  → Fix applied, retrying...")
                        self.healer.learn(last_error, analysis['fix'], True)
                        continue
                
                # Step 4: Try AI-assisted fix
                if current_output:
                    fix = await self._get_ai_fix(task, current_output, last_error)
                    if fix:
                        current_output = fix
                        print(f"  → Applied AI fix, retrying...")
                        continue
                
                self.healer.learn(last_error, analysis['fix'], False)
                break
                
            except Exception as e:
                last_error = str(e)
                print(f"✗ Exception: {last_error}")
        
        return {
            'success': False,
            'iterations': iterations,
            'error': last_error,
            'heals': 0
        }
    
    async def _plan_execution(self, task: str, context: str = "") -> List[Dict]:
        """Plan execution steps using LLM"""
        
        prompt = f"""Analyze this task and create execution steps.

Task: {task}

{context if context else ''}

Respond with JSON array of steps:
[
  {{"tool": "bash|python|file|ollama|vision", "action": "what to do", "details": "specifics"}}
]

Keep it simple. 2-5 steps max."""
        
        try:
            result = subprocess.run(
                ["ollama", "run", "qwen2.5-coder:14b"],
                input=prompt.encode(),
                capture_output=True,
                timeout=30
            )
            
            # Try to parse JSON
            output = result.stdout.decode()
            if '[' in output:
                json_start = output.find('[')
                json_end = output.rfind(']') + 1
                steps = json.loads(output[json_start:json_end])
                return steps
        except:
            pass
        
        # Fallback: basic parsing
        return [{"tool": "bash", "action": "execute", "details": task}]
    
    async def _execute_plan(self, plan: List[Dict]) -> Dict:
        """Execute the plan"""
        
        for step in plan:
            tool = step.get('tool', 'bash')
            action = step.get('action', '')
            details = step.get('details', '')
            
            if tool == 'bash':
                result = subprocess.run(
                    details,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode != 0:
                    return {'success': False, 'error': result.stderr}
                else:
                    return {'success': True, 'output': result.stdout}
            
            elif tool == 'python':
                result = subprocess.run(
                    [sys.executable, '-c', details],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    return {'success': False, 'error': result.stderr}
                else:
                    return {'success': True, 'output': result.stdout}
            
            elif tool == 'ollama':
                result = subprocess.run(
                    ["ollama", "run", "qwen2.5-coder:14b", details],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return {'success': True, 'output': result.stdout}
            
            elif tool == 'vision':
                image_path = step.get('image', details)
                if Path(image_path).exists():
                    result = subprocess.run(
                        ["ollama", "run", "llava", image_path],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    return {'success': True, 'output': result.stdout}
                return {'success': False, 'error': f'Image not found: {image_path}'}
        
        return {'success': False, 'error': 'Empty plan'}
    
    async def _get_ai_fix(self, task: str, current_output: str, error: str) -> Optional[str]:
        """Get AI-generated fix for failed code"""
        
        prompt = f"""Fix this failed execution.

Original task: {task}

Current output/error:
{error}

Return ONLY the corrected command/code to run, nothing else."""
        
        try:
            result = subprocess.run(
                ["ollama", "run", "qwen2.5-coder:14b"],
                input=prompt.encode(),
                capture_output=True,
                timeout=30
            )
            fix = result.stdout.decode().strip()
            if fix and not fix.startswith('{'):
                return fix
        except:
            pass
        return None
    
    async def run_daemon(self):
        """Run as daemon - watch for and execute tasks"""
        print("Starting NEXUS Autonomous Daemon...")
        print("Watching for tasks in:", self.queue_dir)
        
        self.running = True
        processed = set()
        
        while self.running:
            # Check for new tasks
            for task_file in self.queue_dir.glob("*.task"):
                if task_file.name not in processed:
                    task_id = task_file.stem
                    print(f"\n>>> New task: {task_id}")
                    
                    task_content = task_file.read_text()
                    result = await self.execute_task(task_content)
                    
                    # Save result
                    result_file = self.queue_dir / f"{task_id}.result"
                    result_file.write_text(json.dumps(result, indent=2))
                    
                    # Mark as processed
                    processed.add(task_file.name)
                    
                    # Remove task file if successful
                    if result.get('success'):
                        task_file.unlink()
            
            # Check every 5 seconds
            await asyncio.sleep(5)
    
    def stop(self):
        """Stop the daemon"""
        self.running = False


# ============================================
# MEMORY SYSTEM
# ============================================

class Memory:
    """Persistent memory for learned patterns"""
    
    def __init__(self):
        self.dir = Path.home() / ".nexus" / "memory"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.dir / "learned.json"
        self.memory = self._load()
    
    def _load(self) -> Dict:
        if self.memory_file.exists():
            try:
                return json.loads(self.memory_file.read_text())
            except:
                return {}
        return {}
    
    def _save(self):
        self.memory_file.write_text(json.dumps(self.memory, indent=2))
    
    def remember(self, task: str, result: Dict):
        """Store successful execution"""
        key = hashlib.md5(task.encode()).hexdigest()[:8]
        self.memory[key] = {
            'task': task[:100],
            'success': result.get('success'),
            'timestamp': datetime.now().isoformat(),
            'result_preview': str(result.get('result', ''))[:200]
        }
        self._save()
    
    def recall(self, hint: str) -> Optional[Dict]:
        """Recall similar past executions"""
        hint_lower = hint.lower()
        for key, value in self.memory.items():
            if hint_lower[:20] in value.get('task', '').lower():
                return value
        return None


# ============================================
# TASK FILE FORMAT
# ============================================

"""
Task files (.task) contain:
- Line 1: The task description
- Lines 2+: Optional context/memory

Example:
    build a REST API with /users endpoint
    Use: Python, FastAPI
    Include: GET, POST, DELETE
"""


# ============================================
# MAIN
# ============================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Autonomous Executor")
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--watch", action="store_true", help="Watch for tasks")
    parser.add_argument("--workspace", default=".", help="Working directory")
    parser.add_argument("--status", action="store_true", help="Show tool status")
    parser.add_argument("--submit", metavar="FILE", help="Submit task file")
    
    args = parser.parse_args()
    
    print("")
    print("+==============================================================+")
    print("|         NEXUS AUTONOMOUS LOOP - SELF-HEALING                 |")
    print("+==============================================================+")
    print("")
    
    executor = AutonomousExecutor(args.workspace)
    
    # Status mode
    if args.status:
        print(executor.discovery.report())
        return
    
    # Submit task file
    if args.submit:
        task_file = Path(args.submit)
        if task_file.exists():
            # Copy to queue
            queue_file = executor.queue_dir / f"{int(time.time())}.task"
            queue_file.write_text(task_file.read_text())
            print(f"Task submitted: {queue_file}")
            return
        else:
            print(f"Task file not found: {args.submit}")
            return
    
    # Daemon mode
    if args.daemon:
        await executor.run_daemon()
        return
    
    # Single task mode
    if args.task:
        result = await executor.execute_task(args.task)
        print(f"\n{'='*60}")
        print(f"RESULT: {'SUCCESS' if result['success'] else 'FAILED'}")
        print(f"{'='*60}")
        if result.get('error'):
            print(f"Error: {result['error'][:200]}")
        return
    
    # Interactive mode
    print("Interactive mode. Type 'quit' to exit.\n")
    while True:
        try:
            task = input("> ").strip()
            if task.lower() in ['quit', 'exit', 'q']:
                break
            if not task:
                continue
            
            result = await executor.execute_task(task)
            print(f"\nResult: {'✓ SUCCESS' if result['success'] else '✗ FAILED'}")
            print(f"Iterations: {result.get('iterations', 0)}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())