import subprocess
import os
from pathlib import Path


def run_aider(task, model="ollama/qwen2.5-coder:14b", auto_yes=True):
    return f"[AIDER NOT INSTALLED] Install: pip install aider-chat\n\nAlternative: Use direct Ollama for code generation:\nollama run {model.split('/')[-1]} \"{task}\""


def run_aider_ollama(task, model="ollama/qwen2.5-coder:14b"):
    code_prompt = f"""You are a code assistant. Complete this task:

{task}

Generate complete, working code. Output ONLY the code in a code block.
"""

    try:
        result = subprocess.run(
            f'ollama run {model} "{code_prompt}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        return result.stdout if result.stdout else result.stderr
    except Exception as e:
        return f"[ERROR] {str(e)}"


def check_aider_available():
    try:
        result = subprocess.run(
            ["pip", "show", "aider-chat"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except:
        return False


if __name__ == "__main__":
    print("Aider Wrapper Tool")
    print(f"Aider installed: {check_aider_available()}")
    
    if check_aider_available():
        print("\nAider is available - using pip version")
    else:
        print("\nUsing Ollama direct as fallback")