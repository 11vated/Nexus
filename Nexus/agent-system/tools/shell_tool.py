import subprocess
import os
import shlex


def run_shell(cmd, timeout=60, cwd=None):
    if not cmd or not cmd.strip():
        return "[ERROR] Empty command"
    
    cmd = cmd.strip()
    
    if cmd.startswith("shell:") or cmd.startswith("run:") or cmd.startswith("execute:"):
        cmd = cmd.split(":", 1)[1].strip()
    
    print(f"[SHELL TOOL] Executing: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )
        
        output = result.stdout.strip() if result.stdout else ""
        error = result.stderr.strip() if result.stderr else ""
        
        if result.returncode != 0:
            return f"[ERROR] Exit code {result.returncode}\n{error}\n{output}"
        
        if output:
            return output
        elif error and "error" not in error.lower():
            return error
        
        return "[SUCCESS] Command completed" if result.returncode == 0 else f"[ERROR] {error}"
    
    except subprocess.TimeoutExpired:
        return f"[ERROR] Command timed out after {timeout}s"
    
    except FileNotFoundError:
        return f"[ERROR] Command not found: {cmd.split()[0]}"
    
    except Exception as e:
        return f"[ERROR] {str(e)}"


def check_command_safety(cmd):
    dangerous = ["rm -rf", "del /f", "format", "mkfs", "dd if="]
    
    cmd_lower = cmd.lower()
    for word in dangerous:
        if word in cmd_lower:
            return False, f"Dangerous command detected: {word}"
    
    return True, "OK"


def run_python(code):
    return run_shell(f'python -c "{code}"')


def run_pip_install(package):
    return run_shell(f'pip install {package}')