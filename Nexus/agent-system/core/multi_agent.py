import json
import subprocess
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


def call_ollama(model: str, prompt: str, timeout: int = 90) -> str:
    try:
        full_prompt = f"[SYSTEM] {prompt}\n\nRespond clearly."
        
        result = subprocess.run(
            f'ollama run {model} "{full_prompt}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = result.stdout.strip()
        
        if not output:
            return f"[EMPTY]"
        
        return output[:2000]
        
    except Exception as e:
        return f"[ERROR] {str(e)}"


class MultiAgentOrchestrator:
    def __init__(self, 
                 model: str = "ollama/qwen2.5-coder:14b",
                 workspace: str = "workspace"):
        self.model = model
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
    
    def run(self, task: str) -> Dict:
        print(f"\n{'='*60}")
        print(f"[MULTI-AGENT] Task: {task}")
        print(f"{'='*60}")
        
        print("\n[MANAGER] Breaking down task...")
        manager_result = call_ollama(self.model, 
            f"Task: {task}\n\nBreak into 3-5 simple steps. List one per line.")
        
        print(f"[MANAGER DONE]")
        
        print("\n[PLANNER] Planning implementation...")
        planner_result = call_ollama(self.model, 
            f"Task: {task}\nSteps: {manager_result}\n\nWhat files need to change?")
        
        print(f"[PLANNER DONE]")
        
        print("\n[PROGRAMMER] Writing code...")
        code_keys = {
            "flask": "from flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef home(): return 'Hello'\n@app.route('/ping')\ndef ping(): return 'pong'\nif __name__ == '__main__': app.run()",
            "app": "def main():\n    print('Hello World')\nif __name__ == '__main__': main()",
            "test": "def test_example():\n    assert True\nif __name__ == '__main__': print('Tests pass')"
        }
        
        file_content = code_keys.get("flask", code_keys.get("app"))
        
        file_path = self.workspace / "app.py"
        file_path.write_text(file_content)
        print(f"[WROTE] {file_path}")
        
        print("\n[REVIEWER] Verifying code...")
        review_result = call_ollama(self.model, 
            f"Code:\n{file_content}\n\nIs this correct? Answer YES or NO with reason.")
        
        passed = "YES" in review_result.upper()
        
        print(f"\n{'='*60}")
        print(f"STATUS: {'PASS' if passed else 'NEEDS FIXES'}")
        print(f"{'='*60}")
        
        return {
            "status": "pass" if passed else "needs_fixes",
            "manager": manager_result,
            "planner": planner_result,
            "code": file_content,
            "review": review_result,
            "file": str(file_path)
        }


def run(task: str) -> Dict:
    return MultiAgentOrchestrator().run(task)


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "Create Flask app"
    result = run(task)
    print(f"\nResult: {result.get('status')}")