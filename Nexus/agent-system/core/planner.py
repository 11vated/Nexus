import json
import subprocess
import shlex


def create_plan(task, config):
    model = config.get("model", {}).get("name", "ollama/qwen2.5-coder:14b")
    task_lower = task.lower()
    
    commands = []
    
    if "flask" in task_lower or "web" in task_lower or "api" in task_lower:
        commands = [
            "shell: pip install flask",
            "create_file: app.py",
            "run_test: python app.py",
            "done: done"
        ]
    elif "create" in task_lower or "file" in task_lower or "new" in task_lower:
        commands = [
            "create_file: test.py",
            "shell: python test.py",
            "done: done"
        ]
    elif "install" in task_lower:
        pkg = task_lower.replace("install", "").replace("pip", "").strip()
        pkg = pkg.strip() if pkg else "requests"
        commands = [f"shell: pip install {pkg}", "done: done"]
    elif "test" in task_lower or "pytest" in task_lower:
        commands = ["shell: pytest", "done: done"]
    else:
        commands = [
            "shell: echo Done",
            "done: done"
        ]
    
    return commands


def parse_step(step):
    step = step.strip()
    
    if ":" in step:
        parts = step.split(":", 1)
        action = parts[0].strip().lower()
        value = parts[1].strip() if len(parts) > 1 else ""
        return action, value
    
    return step, step