import subprocess
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class TDDWorkflow:
    def __init__(self, workspace: str = "workspace", model: str = "ollama/qwen2.5-coder:14b"):
        self.workspace = workspace
        self.model = model
        self.phases = ["red", "green", "refactor"]
        self.test_results = []
        
        Path(workspace).mkdir(parents=True, exist_ok=True)
    
    def run(self, task: str) -> Dict:
        print(f"\n[TDD] Starting: {task}")
        
        plan = self._create_test_plan(task)
        print(f"[TDD] Test plan: {len(plan)} tests")
        
        results = {
            "task": task,
            "tests_written": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "phases_completed": [],
            "start_time": datetime.now().isoformat()
        }
        
        for phase in self.phases:
            print(f"\n[TDD PHASE] {phase.upper()}")
            
            if phase == "red":
                test_result = self._write_tests(plan)
                results["tests_written"] = test_result.get("count", 0)
                
            elif phase == "green":
                impl_result = self._implement_code(task, plan)
                test_result = self._run_tests()
                results["tests_passed"] = test_result.get("passed", 0)
                results["tests_failed"] = test_result.get("failed", 0)
                
            elif phase == "refactor":
                refactor_result = self._refactor_code()
            
            results["phases_completed"].append(phase)
            
            if phase == "green" and results["tests_failed"] > 0:
                print("[TDD] Tests failing - implementing fixes...")
                self._fix_until_pass()
                results["tests_passed"] = results["tests_failed"] = 0
                test_result = self._run_tests()
                results["tests_passed"] = test_result.get("passed", 0)
                results["tests_failed"] = test_result.get("failed", 0)
        
        results["end_time"] = datetime.now().isoformat()
        results["status"] = "success" if results["tests_passed"] > 0 else "failed"
        
        print(f"\n[TDD COMPLETE] Passed: {results['tests_passed']}/{results['tests_written']}")
        
        return results
    
    def _create_test_plan(self, task: str) -> List[Dict]:
        prompt = f"""Create test cases for this task: {task}

Output ONLY a JSON array of test objects with:
- name: test function name
- assertion: what it should test
- expected: expected behavior

Example:
[{{"name": "test_ping_returns_ok", "assertion": "/ping returns 200", "expected": "status 200"}}]

Output ONLY JSON, no explanation.
"""
        
        try:
            result = subprocess.run(
                f'ollama run {self.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            import json
            plan = json.loads(result.stdout.strip().strip("`").strip("json"))
            return plan if isinstance(plan, list) else []
        except Exception as e:
            print(f"[TDD PLAN ERROR] {e}")
            return [{"name": "test_basic", "assertion": "basic functionality", "expected": "works"}]
    
    def _write_tests(self, plan: List[Dict]) -> Dict:
        test_file = os.path.join(self.workspace, "test_task.py")
        
        test_code = '"""Auto-generated tests"""\nimport pytest\n\n'
        
        for test in plan:
            test_name = test.get("name", "test_unknown")
            test_code += f'def {test_name}():\n    pass\n\n'
        
        with open(test_file, "w") as f:
            f.write(test_code)
        
        return {"file": test_file, "count": len(plan)}
    
    def _implement_code(self, task: str, plan: List[Dict]) -> Dict:
        test_instructions = "\n".join([
            f"- {t.get('assertion', '')}: {t.get('expected', '')}" 
            for t in plan
        ])
        
        prompt = f"""Implement code to pass these tests:
{test_instructions}

Task: {task}

Create the implementation in the workspace.
"""
        
        try:
            result = subprocess.run(
                f'aider --model {self.model} --yes --message "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=180
            )
            return {"status": "implemented", "output": result.stdout}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _run_tests(self) -> Dict:
        test_file = os.path.join(self.workspace, "test_task.py")
        
        if not os.path.exists(test_file):
            return {"passed": 0, "failed": 0, "total": 0}
        
        try:
            result = subprocess.run(
                ["pytest", test_file, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=self.workspace
            )
            
            output = result.stdout + result.stderr
            
            passed = output.count(" PASSED")
            failed = output.count(" FAILED")
            
            return {
                "passed": passed,
                "failed": failed,
                "total": passed + failed,
                "output": output[:500]
            }
        except Exception as e:
            return {"passed": 0, "failed": 1, "error": str(e)}
    
    def _refactor_code(self) -> Dict:
        prompt = "Refactor the code to be cleaner, more readable, and follow best practices."
        
        try:
            result = subprocess.run(
                f'aider --model {self.model} --yes --message "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            return {"status": "refactored"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _fix_until_pass(self, max_attempts: int = 3) -> bool:
        for attempt in range(max_attempts):
            print(f"[TDD FIX ATTEMPT] {attempt + 1}/{max_attempts}")
            
            test_result = self._run_tests()
            
            if test_result.get("failed", 1) == 0:
                return True
            
            if test_result.get("output"):
                fix_prompt = f"Fix test failures:\n{test_result['output']}"
                
                try:
                    subprocess.run(
                        f'aider --model {self.model} --yes --message "{fix_prompt}"',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                except:
                    pass
        
        return False


class TDDExecutor:
    def __init__(self, tdd: TDDWorkflow):
        self.tdd = tdd
    
    def execute_with_tdd(self, task: str) -> Dict:
        return self.tdd.run(task)


def run_tdd(task: str, workspace: str = "workspace") -> Dict:
    tdd = TDDWorkflow(workspace=workspace)
    return tdd.run(task)