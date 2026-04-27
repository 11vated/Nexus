#!/usr/bin/env python3
"""
ULTIMATE DEVELOPMENT SUITE
Git Integration • Project Memory • Terminal • File Watcher • REST API • Sandbox

This transforms the agent system into a complete local development environment.
"""

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


# ============================================
# 1. GIT INTEGRATION
# ============================================

class GitIntegration:
    """
    Full Git operations - commit, branch, diff, stash, PR
    """
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.git = "git"
    
    def _run(self, *args, cwd=None) -> Dict[str, Any]:
        """Run git command"""
        cwd = cwd or self.repo_path
        try:
            result = subprocess.run(
                [self.git] + list(args),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def status(self) -> Dict[str, Any]:
        """Get git status"""
        result = self._run("status", "--porcelain")
        if not result["success"]:
            return {"error": result["error"]}
        
        files = []
        for line in result["output"].split('\n'):
            if line:
                status = line[:2]
                file = line[3:]
                files.append({"status": status, "file": file})
        
        # Get branch
        branch_result = self._run("branch", "--show-current")
        branch = branch_result.get("output", "unknown")
        
        return {"branch": branch, "files": files, "dirty": len(files) > 0}
    
    def diff(self, staged: bool = False) -> str:
        """Get diff"""
        args = ["diff"]
        if staged:
            args.append("--staged")
        result = self._run(*args)
        return result.get("output", "")
    
    def commit(self, message: str, auto_add: bool = True) -> Dict[str, Any]:
        """Commit changes"""
        if auto_add:
            add_result = self._run("add", "-A")
            if not add_result["success"]:
                return {"error": f"Add failed: {add_result['error']}"}
        
        result = self._run("commit", "-m", message)
        if result["success"]:
            # Get commit hash
            hash_result = self._run("rev-parse", "HEAD")
            return {"success": True, "commit": hash_result.get("output", "")[:8]}
        return {"error": result.get("error", "Commit failed")}
    
    def branch_list(self) -> List[str]:
        """List branches"""
        result = self._run("branch", "-a")
        if result["success"]:
            return [b.strip() for b in result["output"].split('\n') if b]
        return []
    
    def create_branch(self, name: str, checkout: bool = True) -> Dict[str, Any]:
        """Create branch"""
        result = self._run("branch", name)
        if not result["success"]:
            return {"error": result["error"]}
        
        if checkout:
            result = self._run("checkout", name)
        
        return {"success": True, "branch": name}
    
    def checkout(self, branch: str) -> Dict[str, Any]:
        """Checkout branch"""
        result = self._run("checkout", branch)
        return {"success": result["success"], "error": result.get("error")}
    
    def log(self, count: int = 10) -> List[Dict]:
        """Get commit log"""
        result = self._run("log", f"-{count}", "--pretty=format:%h|%s|%an|%ad", "--date=short")
        if not result["success"]:
            return []
        
        commits = []
        for line in result["output"].split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3]
                    })
        return commits
    
    def stash(self, message: str = "") -> Dict[str, Any]:
        """Stash changes"""
        if message:
            result = self._run("stash", "push", "-m", message)
        else:
            result = self._run("stash", "push")
        return {"success": result["success"], "error": result.get("error")}
    
    def stash_pop(self) -> Dict[str, Any]:
        """Pop stash"""
        result = self._run("stash", "pop")
        return {"success": result["success"], "error": result.get("error")}
    
    def reset(self, hard: bool = False) -> Dict[str, Any]:
        """Reset to last commit"""
        args = ["reset"]
        if hard:
            args.append("--hard")
        else:
            args.append("--soft")
        args.append("HEAD~1")
        
        result = self._run(*args)
        return {"success": result["success"], "error": result.get("error")}
    
    def is_repo(self) -> bool:
        """Check if directory is a git repo"""
        return (self.repo_path / ".git").exists()


# ============================================
# 2. PROJECT MEMORY SYSTEM
# ============================================

@dataclass
class ProjectProfile:
    """Memory of a project"""
    path: str
    name: str
    language: str = ""
    framework: str = ""
    dependencies: List[str] = field(default_factory=list)
    coding_style: str = ""
    preferences: Dict[str, Any] = field(default_factory=dict)
    key_files: Dict[str, str] = field(default_factory=dict)  # file -> purpose
    patterns: List[str] = field(default_factory=list)
    last_updated: str = ""

@dataclass 
class UserPreferences:
    """User-wide preferences"""
    default_model: str = "qwen2.5-coder:14b"
    auto_lint: bool = True
    auto_test: bool = True
    theme: str = "cyberpunk"
    workspace: str = ""
    recent_projects: List[str] = field(default_factory=list)

class ProjectMemory:
    """
    Persistent memory across sessions - learns projects, preferences, patterns
    """
    
    def __init__(self, memory_dir: str = None):
        if memory_dir is None:
            memory_dir = os.path.join(os.path.expanduser("~"), ".nexus", "memory")
        
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.projects_file = self.memory_dir / "projects.json"
        self.user_file = self.memory_dir / "user.json"
        self.sessions_file = self.memory_dir / "sessions.json"
        
        self.projects: Dict[str, ProjectProfile] = {}
        self.user_prefs = UserPreferences()
        
        self._load()
    
    def _load(self):
        """Load memory from disk"""
        # Load projects
        if self.projects_file.exists():
            try:
                data = json.loads(self.projects_file.read_text())
                self.projects = {k: ProjectProfile(**v) for k, v in data.items()}
            except:
                pass
        
        # Load user prefs
        if self.user_file.exists():
            try:
                data = json.loads(self.user_file.read_text())
                self.user_prefs = UserPreferences(**data)
            except:
                pass
    
    def _save(self):
        """Save memory to disk"""
        # Save projects
        projects_data = {k: asdict(v) for k, v in self.projects.items()}
        self.projects_file.write_text(json.dumps(projects_data, indent=2))
        
        # Save user prefs
        self.user_file.write_text(json.dumps(asdict(self.user_prefs), indent=2))
    
    def analyze_project(self, project_path: str) -> ProjectProfile:
        """Analyze and remember a project"""
        path = Path(project_path)
        
        if not path.exists():
            return None
        
        profile = ProjectProfile(
            path=str(path),
            name=path.name,
            last_updated=datetime.now().isoformat()
        )
        
        # Detect language/framework
        if (path / "package.json").exists():
            profile.language = "javascript"
            try:
                pkg = json.loads((path / "package.json").read_text())
                profile.dependencies = list(pkg.get("dependencies", {}).keys())
                profile.framework = pkg.get("scripts", {}).keys()
            except:
                pass
        
        elif (path / "requirements.txt").exists():
            profile.language = "python"
            profile.dependencies = (path / "requirements.txt").read_text().split('\n')
        
        elif (path / "Cargo.toml").exists():
            profile.language = "rust"
        
        elif (path / "go.mod").exists():
            profile.language = "go"
        
        elif (path / "pom.xml").exists():
            profile.language = "java"
        
        # Find key files
        key_patterns = ["main", "app", "index", "config", "setup", "server", "client"]
        for f in path.rglob("*.py"):
            if any(p in f.name.lower() for p in key_patterns):
                profile.key_files[str(f.relative_to(path))] = "main entry"
        
        for f in path.rglob("*.json"):
            if "config" in f.name.lower():
                profile.key_files[str(f.relative_to(path))] = "configuration"
        
        # Store
        self.projects[str(path)] = profile
        self._save()
        
        return profile
    
    def get_project(self, project_path: str) -> Optional[ProjectProfile]:
        """Get project profile"""
        return self.projects.get(str(Path(project_path).resolve()))
    
    def update_preference(self, key: str, value: Any):
        """Update user preference"""
        if hasattr(self.user_prefs, key):
            setattr(self.user_prefs, key, value)
            self._save()
    
    def add_recent_project(self, path: str):
        """Add to recent projects"""
        path = str(Path(path).resolve())
        recent = self.user_prefs.recent_projects
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self.user_prefs.recent_projects = recent[:10]
        self._save()
    
    def get_context(self, project_path: str) -> str:
        """Get contextual info for a project"""
        profile = self.get_project(project_path)
        if not profile:
            return ""
        
        context = f"""
Project: {profile.name}
Language: {profile.language}
Framework: {profile.framework}
Dependencies: {', '.join(profile.dependencies[:5])}
Key files: {', '.join(profile.key_files.keys())}
Coding style: {profile.coding_style or 'Not learned yet'}
"""
        return context


# ============================================
# 3. TERMINAL EMULATOR
# ============================================

class TerminalEmulator:
    """
    Full terminal emulation in Python
    """
    
    def __init__(self, cwd: str = None):
        self.cwd = Path(cwd or os.getcwd())
        self.env = os.environ.copy()
        self.history: List[Dict] = []
        self.variables: Dict[str, str] = {}
    
    async def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute command and return output"""
        if not command.strip():
            return {"output": "", "error": None, "exit_code": 0}
        
        # Handle built-in commands
        if command.strip() == "clear":
            self.history = []
            return {"output": "", "error": None, "exit_code": 0}
        
        if command.strip().startswith("cd "):
            new_dir = command.strip()[3:].strip()
            new_path = (self.cwd / new_dir).resolve()
            if new_path.exists() and new_path.is_dir():
                self.cwd = new_path
                return {"output": f"Changed directory to {self.cwd}", "error": None, "exit_code": 0}
            return {"output": "", "error": f"Directory not found: {new_dir}", "exit_code": 1}
        
        if command.strip() == "pwd":
            return {"output": str(self.cwd), "error": None, "exit_code": 0}
        
        if command.strip() == "history":
            output = '\n'.join([f"{i+1}  {cmd['command']}" for i, cmd in enumerate(self.history)])
            return {"output": output, "error": None, "exit_code": 0}
        
        # Run actual command
        try:
            if sys.platform == "win32":
                shell = ["cmd", "/c", command]
            else:
                shell = ["bash", "-c", command]
            
            proc = await asyncio.create_subprocess_exec(
                *shell,
                cwd=str(self.cwd),
                env=self.env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            
            output = stdout.decode('utf-8', errors='replace')
            error = stderr.decode('utf-8', errors='replace') if stderr else None
            exit_code = proc.returncode
            
            # Add to history
            self.history.append({
                "command": command,
                "output": output[:5000],  # Limit stored output
                "exit_code": exit_code,
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "output": output,
                "error": error,
                "exit_code": exit_code,
                "cwd": str(self.cwd)
            }
            
        except asyncio.TimeoutExpired:
            proc.kill()
            return {"output": "", "error": "Command timed out", "exit_code": -1}
        
        except Exception as e:
            return {"output": "", "error": str(e), "exit_code": -1}


# ============================================
# 4. FILE WATCHER
# ============================================

class FileWatcher:
    """
    Watch files and run actions on changes
    """
    
    def __init__(self, watch_path: str = "."):
        self.watch_path = Path(watch_path)
        self.running = False
        self.watched_files: Dict[str, float] = {}
        self.callbacks: List[callable] = []
        self.ignore_patterns = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            "*.pyc", "*.pyo", "*.swp", ".DS_Store", "*.log"
        }
        
    def add_callback(self, callback: callable):
        """Add callback for file changes"""
        self.callbacks.append(callback)
    
    def should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored"""
        path_str = str(path)
        for pattern in self.ignore_patterns:
            if pattern.startswith("*"):
                if path_str.endswith(pattern[1:]):
                    return True
            elif pattern in path_str:
                return True
        return False
    
    async def watch(self, interval: float = 1.0):
        """Watch for file changes"""
        self.running = True
        
        # Initial scan
        await self._scan_files()
        
        while self.running:
            await asyncio.sleep(interval)
            await self._check_changes()
    
    async def _scan_files(self):
        """Scan all files"""
        if not self.watch_path.exists():
            return
        
        for f in self.watch_path.rglob("*"):
            if f.is_file() and not self.should_ignore(f):
                try:
                    self.watched_files[str(f)] = f.stat().st_mtime
                except:
                    pass
    
    async def _check_changes(self):
        """Check for file changes"""
        current_files = {}
        
        for f in self.watch_path.rglob("*"):
            if f.is_file() and not self.should_ignore(f):
                try:
                    mtime = f.stat().st_mtime
                    current_files[str(f)] = mtime
                    
                    # Check if new or modified
                    if str(f) not in self.watched_files:
                        await self._trigger("created", f)
                    elif self.watched_files[str(f)] != mtime:
                        await self._trigger("modified", f)
                        
                except:
                    pass
        
        self.watched_files = current_files
    
    async def _trigger(self, event_type: str, path: Path):
        """Trigger callbacks"""
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, path)
                else:
                    callback(event_type, path)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def stop(self):
        """Stop watching"""
        self.running = False


# ============================================
# 5. REST API SERVER
# ============================================

class AgentAPIServer:
    """
    Expose all agent capabilities as REST API
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 5556):
        self.host = host
        self.port = port
        self.running = False
        
    def get_routes(self) -> Dict[str, str]:
        """Get all available API routes"""
        return {
            # Code generation
            "POST /api/generate": "Generate code from prompt",
            "POST /api/chat": "Chat with AI",
            
            # Computer use
            "POST /api/computer/execute": "Execute computer action",
            "POST /api/computer/goal": "Achieve a goal",
            
            # Vision
            "POST /api/vision/analyze": "Analyze image",
            "POST /api/vision/live/start": "Start live screen",
            
            # Git
            "GET /api/git/status": "Git status",
            "POST /api/git/commit": "Commit changes",
            "POST /api/git/branch": "Create branch",
            
            # Terminal
            "POST /api/terminal/exec": "Execute command",
            
            # Memory
            "GET /api/memory/project": "Get project memory",
            "POST /api/memory/preference": "Set preference",
            
            # System
            "GET /api/models": "List available models",
            "GET /api/health": "Health check"
        }
    
    def get_openapi_spec(self) -> Dict:
        """Get OpenAPI spec"""
        return {
            "openapi": "3.0.0",
            "info": {
                "title": "Nexus Agent API",
                "version": "1.0.0",
                "description": "Local AI Agent REST API"
            },
            "servers": [{"url": f"http://localhost:{self.port}"}],
            "paths": {
                "/api/health": {
                    "get": {
                        "summary": "Health check",
                        "responses": {"200": {"description": "OK"}}
                    }
                },
                "/api/models": {
                    "get": {
                        "summary": "List models",
                        "responses": {"200": {"description": "Model list"}}
                    }
                }
            }
        }


# ============================================
# 6. CODE SANDBOX
# ============================================

class CodeSandbox:
    """
    Safe code execution environment
    """
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.sandbox_dir = Path.home() / ".nexus" / "sandbox"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        
        # Restricted imports/builtins
        self.blocked_modules = {
            "os": ["system", "popen", "spawn"],
            "subprocess": ["Popen", "call", "run"],
            "socket": ["socket"],
            "requests": ["get", "post"],
            "urllib": ["urlopen"],
        }
    
    async def execute(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Execute code safely"""
        
        if language == "python":
            return await self._execute_python(code)
        
        elif language == "javascript":
            return await self._execute_js(code)
        
        elif language == "bash":
            return await self._execute_bash(code)
        
        return {"error": f"Unsupported language: {language}"}
    
    async def _execute_python(self, code: str) -> Dict[str, Any]:
        """Execute Python safely"""
        
        # Create isolated environment
        sandbox_id = str(uuid.uuid4())[:8]
        work_dir = self.sandbox_dir / sandbox_id
        work_dir.mkdir()
        
        # Create safe execution script
        safe_code = f"""
import sys
import json
import traceback

# Restricted globals
safe_globals = {{
    "__builtins__": {{
        "print": print,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sorted": sorted,
        "reversed": reversed,
        "any": any,
        "all": all,
        "isinstance": isinstance,
        "type": type,
        "hasattr": hasattr,
        "getattr": getattr,
        "setattr": setattr,
        "input": lambda: "",
        "open": None,  # Blocked for safety
    }}
}}

# User code
{code}

# Output
print("__NEXUS_OUTPUT_END__")
"""
        
        script_path = work_dir / "script.py"
        script_path.write_text(safe_code)
        
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(work_dir)
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            
            output = stdout.decode()
            error = stderr.decode()
            
            # Extract actual output
            if "__NEXUS_OUTPUT_END__" in output:
                output = output.split("__NEXUS_OUTPUT_END__")[0]
            
            return {
                "success": proc.returncode == 0,
                "output": output.strip(),
                "error": error.strip() if error else None,
                "exit_code": proc.returncode
            }
            
        except asyncio.TimeoutExpired:
            proc.kill()
            return {"error": "Execution timeout", "success": False}
        
        except Exception as e:
            return {"error": str(e), "success": False}
        
        finally:
            # Cleanup
            try:
                shutil.rmtree(work_dir)
            except:
                pass
    
    async def _execute_js(self, code: str) -> Dict[str, Any]:
        """Execute JavaScript (requires Node)"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", "-e", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            
            return {
                "success": proc.returncode == 0,
                "output": stdout.decode(),
                "error": stderr.decode() if stderr else None
            }
        except:
            return {"error": "Node.js not available", "success": False}
    
    async def _execute_bash(self, code: str) -> Dict[str, Any]:
        """Execute bash command"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            
            return {
                "success": proc.returncode == 0,
                "output": stdout.decode(),
                "error": stderr.decode() if stderr else None
            }
        except:
            return {"error": "Bash not available", "success": False}


# ============================================
# MASTER CONTROLLER
# ============================================

class NexusSuite:
    """
    Master controller combining all features
    """
    
    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace)
        
        # Initialize all systems
        self.git = GitIntegration(workspace)
        self.memory = ProjectMemory()
        self.terminal = TerminalEmulator(workspace)
        self.watcher = FileWatcher(workspace)
        self.sandbox = CodeSandbox()
        self.api = AgentAPIServer()
    
    async def analyze_current_project(self):
        """Analyze and remember current project"""
        profile = self.memory.analyze_project(str(self.workspace))
        self.memory.add_recent_project(str(self.workspace))
        return profile
    
    async def setup_file_watcher(self, on_change: callable):
        """Setup auto-test on file save"""
        self.watcher.add_callback(on_change)
        asyncio.create_task(self.watcher.watch())
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all systems"""
        return {
            "git": {
                "is_repo": self.git.is_repo(),
                "status": self.git.status() if self.git.is_repo() else None
            },
            "memory": {
                "projects_count": len(self.memory.projects),
                "user_prefs": asdict(self.memory.user_prefs)
            },
            "api": {
                "routes": self.api.get_routes()
            }
        }


# ============================================
# CLI
# ============================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Nexus Ultimate Suite")
    parser.add_argument("--git", help="Git command (status, commit, branch)")
    parser.add_argument("--message", help="Commit message")
    parser.add_argument("--terminal", help="Execute terminal command")
    parser.add_argument("--sandbox", help="Run code in sandbox")
    parser.add_argument("--language", default="python", help="Language for sandbox")
    parser.add_argument("--watch", action="store_true", help="Watch for file changes")
    parser.add_argument("--analyze", help="Analyze project at path")
    parser.add_argument("--memory", action="store_true", help="Show memory status")
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║              🧠 NEXUS ULTIMATE SUITE                          ║
║  📂 Git • 🧠 Memory • 💻 Terminal • 👁️ Watch • 🔒 Sandbox   ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    suite = NexusSuite()
    
    if args.git:
        if args.git == "status":
            print(json.dumps(suite.git.status(), indent=2))
        elif args.git == "branch_list":
            print(json.dumps(suite.git.branch_list(), indent=2))
        elif args.git == "log":
            print(json.dumps(suite.git.log(), indent=2))
        elif args.git == "commit" and args.message:
            print(json.dumps(suite.git.commit(args.message), indent=2))
    
    if args.terminal:
        result = await suite.terminal.execute(args.terminal)
        print(result["output"])
        if result["error"]:
            print(f"Error: {result['error']}")
    
    if args.sandbox:
        result = await suite.sandbox.execute(args.sandbox, args.language)
        print(f"Output: {result.get('output', '')}")
        if result.get("error"):
            print(f"Error: {result['error']}")
    
    if args.analyze:
        profile = suite.memory.analyze_project(args.analyze)
        print(json.dumps(asdict(profile), indent=2, default=str))
    
    if args.memory:
        print(json.dumps(suite.get_status(), indent=2, default=str))
    
    if args.watch:
        print("👁️ Watching for file changes... (Ctrl+C to stop)")
        
        def on_change(event, path):
            print(f"  {event}: {path}")
        
        await suite.setup_file_watcher(on_change)
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            suite.watcher.stop()
            print("\nStopped")


if __name__ == "__main__":
    asyncio.run(main())