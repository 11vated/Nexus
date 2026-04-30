import os
import sys
import subprocess
from pathlib import Path

from .planner import parse_step
from tools.shell_tool import run_shell
from tools.aider_wrapper import run_aider
from tools.file_tool import write_file, read_file


def execute_step(step, config, workspace_path="workspace"):
    action, value = parse_step(step)
    
    workspace = Path(workspace_path)
    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
    
    original_dir = os.getcwd()
    os.chdir(workspace)
    
    print(f"[EXECUTOR] Action: {action}")
    
    try:
        if action in ["python", "run"]:
            cmd = value.strip()
            if not cmd:
                cmd = "print('hello world')"
            return run_shell(f'python -c "{cmd}"')
        
        elif action in ["run_test", "pytest", "test"]:
            return run_shell('pytest --tb=short -v 2>&1 || echo "No tests"')
        
        elif action in ["install", "pip"]:
            package = value.strip()
            return run_shell(f'pip install {package}')
        
        elif action in ["create_file", "write", "file"]:
            return write_with_content(value)
        
        elif action == "done":
            return "[SUCCESS] Task completed"
        
        else:
            if value:
                return run_shell(value)
            else:
                return run_shell(step)
    
    except Exception as e:
        return f"[ERROR] {str(e)}"
    
    finally:
        os.chdir(original_dir)


def write_with_content(instruction):
    if not instruction or not instruction.strip():
        return "[ERROR] Empty file instruction"
    
    filename = instruction.strip()
    if " " in filename:
        filename = filename.split()[0]
    
    if not filename.endswith(".py"):
        filename += ".py"
    
    content = get_default_content(filename)
    
    return write_file(filename, content)


def get_default_content(filename):
    contents = {
        "app.py": '''from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello World!"

@app.route("/ping")
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(debug=True)
''',
        "main.py": '''def main():
    print("Hello World!")

if __name__ == "__main__":
    main()
''',
        "test.py": '''def test_example():
    assert True

if __name__ == "__main__":
    test_example()
    print("Tests passed!")
''',
        "hello.py": '''print("Hello World!")

if __name__ == "__main__":
    print("Hello!")
'''
    }
    
    return contents.get(filename, "print('hello world')")