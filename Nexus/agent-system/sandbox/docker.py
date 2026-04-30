import os
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


class DockerSandbox:
    def __init__(self, 
                 image: str = "python:3.11-slim",
                 workspace_path: str = "workspace",
                 network_enabled: bool = False):
        self.image = image
        self.workspace_path = workspace_path
        self.network_enabled = network_enabled
        self.container_id = None
        self.audit_log = []
        
        self._ensure_workspace()
    
    def _ensure_workspace(self):
        Path(self.workspace_path).mkdir(parents=True, exist_ok=True)
    
    def build_image(self, dockerfile: str = None) -> str:
        if dockerfile:
            try:
                result = subprocess.run(
                    ["docker", "build", "-t", "agent-sandbox", "-f", dockerfile, "."],
                    capture_output=True,
                    text=True,
                    cwd=self.workspace_path
                )
                if result.returncode == 0:
                    self.image = "agent-sandbox"
                    return "[SUCCESS] Built custom image"
                return f"[ERROR] {result.stderr}"
            except Exception as e:
                return f"[ERROR] {str(e)}"
        return "[INFO] Using default image"
    
    def check_docker(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def run_command(self, command: str, timeout: int = 120) -> Dict[str, str]:
        if not self.check_docker():
            return {
                "status": "error",
                "output": "",
                "error": "Docker not available"
            }
        
        docker_cmd = self._build_docker_command(command)
        
        self._log("command", command)
        
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.workspace_path
            )
            
            output = result.stdout.strip()
            error = result.stderr.strip()
            
            self._log("result", output or error)
            
            return {
                "status": "success" if result.returncode == 0 else "error",
                "output": output,
                "error": error,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            self._log("timeout", command)
            return {
                "status": "error",
                "output": "",
                "error": f"Command timed out after {timeout}s"
            }
        except Exception as e:
            error = str(e)
            self._log("error", error)
            return {
                "status": "error",
                "output": "",
                "error": error
            }
    
    def _build_docker_command(self, command: str) -> List[str]:
        cmd = ["docker", "run", "--rm"]
        
        if not self.network_enabled:
            cmd.extend(["--network", "none"])
        
        cmd.extend([
            "-v", f"{os.path.abspath(self.workspace_path)}:/workspace",
            "-w", "/workspace",
            "--memory", "512m",
            "--cpus", "1.0",
            self.image,
            "sh", "-c", command
        ])
        
        return cmd
    
    def _log(self, event: str, data: str):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data[:500]
        }
        self.audit_log.append(entry)
    
    def get_audit_log(self) -> List[Dict]:
        return self.audit_log
    
    def export_audit_log(self, path: str = "audit_log.json"):
        with open(path, "w") as f:
            json.dump(self.audit_log, f, indent=2)
        return f"[OK] Exported to {path}"


class SafeExecutor:
    DANGEROUS_PATTERNS = [
        "rm -rf /",
        "rm -rf ~",
        "del /f /s /q",
        "format c:",
        "mkfs",
        "dd if=",
        "> /dev/sd",
        "chmod -R 777 /",
        "wget | sh",
        "curl | sh",
        "&& rm ",
    ]
    
    def __init__(self, sandbox: DockerSandbox = None):
        self.sandbox = sandbox
        self.command_history = []
    
    def is_safe(self, command: str) -> tuple:
        cmd_lower = command.lower()
        
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in cmd_lower:
                return False, f"Dangerous pattern detected: {pattern}"
        
        return True, "Safe"
    
    def execute(self, command: str, force_docker: bool = False) -> Dict[str, str]:
        is_safe, reason = self.is_safe(command)
        
        if not is_safe:
            return {
                "status": "blocked",
                "output": "",
                "error": reason
            }
        
        self.command_history.append(command)
        
        if self.sandbox and force_docker:
            return self.sandbox.run_command(command)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return {
                "status": "success" if result.returncode == 0 else "error",
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "returncode": result.returncode
            }
        except Exception as e:
            return {
                "status": "error",
                "output": "",
                "error": str(e)
            }


def create_dockerfile(base_image: str = "python:3.11-slim") -> str:
    return f"""FROM {base_image}

WORKDIR /workspace

RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    git \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \\
    pytest \\
    aider \\
    pyyaml

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

CMD ["python", "-u", "-i"]
"""