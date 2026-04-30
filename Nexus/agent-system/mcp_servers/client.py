import json
import subprocess
import os
from typing import Dict, List, Any, Optional


class MCPClient:
    def __init__(self, workspace_path: str = "workspace"):
        self.workspace_path = workspace_path
        self.servers = {}
        self.processes = {}
    
    def start_server(self, name: str, command: List[str], cwd: Optional[str] = None):
        if not cwd:
            cwd = self.workspace_path
        
        print(f"[MCP] Starting {name} server...")
        
        try:
            proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd
            )
            self.processes[name] = proc
            self.servers[name] = {
                "command": command,
                "running": True
            }
            return f"[SUCCESS] Started {name}"
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def stop_server(self, name: str):
        if name in self.processes:
            self.processes[name].terminate()
            self.servers[name]["running"] = False
            return f"[SUCCESS] Stopped {name}"
        return f"[ERROR] Server {name} not running"
    
    def stop_all(self):
        for name in self.processes:
            self.stop_server(name)
        return "[SUCCESS] All servers stopped"
    
    def list_servers(self) -> Dict[str, Any]:
        return {k: v for k, v in self.servers.items()}


class MCPFileServer:
    def __init__(self, workspace: str = "workspace"):
        self.workspace = workspace
    
    def list_files(self, path: str = ".") -> str:
        try:
            result = subprocess.run(
                ["npx", "-y", "@modelcontextprotocol/server-filesystem", os.path.join(self.workspace, path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout or result.stderr
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def read_file(self, path: str) -> str:
        full_path = os.path.join(self.workspace, path)
        try:
            with open(full_path, "r") as f:
                return f.read()
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def write_file(self, path: str, content: str) -> str:
        full_path = os.path.join(self.workspace, path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
            return f"[SUCCESS] Wrote {path}"
        except Exception as e:
            return f"[ERROR] {str(e)}"


class MCPShellServer:
    def __init__(self, allowed_commands: Optional[List[str]] = None):
        self.allowed = allowed_commands or ["python", "pip", "npm", "node", "git", "pytest"]
        self.blocked = ["rm -rf", "del", "format", "mkfs", "dd if="]
    
    def execute(self, command: str) -> str:
        for block in self.blocked:
            if block in command.lower():
                return f"[BLOCKED] Dangerous command: {block}"
        
        if self.allowed:
            valid = any(command.startswith(a) for a in self.allowed)
            if not valid:
                return f"[BLOCKED] Command not in allowlist"
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"[ERROR] {str(e)}"


def install_mcp_servers():
    print("[MCP] Installing MCP servers...")
    
    commands = [
        "npm install -g @modelcontextprotocol/server-filesystem",
        "npm install -g @modelcontextprotocol/server-memory",
        "npm install -g @modelcontextprotocol/server-shell"
    ]
    
    for cmd in commands:
        try:
            subprocess.run(cmd.split(), check=True)
            print(f"[OK] {cmd}")
        except Exception as e:
            print(f"[FAIL] {cmd}: {e}")
    
    return "[DONE] MCP servers installed"


if __name__ == "__main__":
    install_mcp_servers()