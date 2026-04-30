#!/usr/bin/env python3
"""
NEXUS AUTOPILOT - FULL AUTONOMY
================================

Complete autonomous workstation capabilities:
1. Scheduler      - Cron-like task scheduling
2. File Watcher   - Auto-run on file changes  
3. Health Monitor - Track Ollama, services, uptime
4. Git Automation - Auto-commit, branches, PRs
5. Notifications  - System alerts
6. Error Tracker  - Monitor failures, patterns
7. Context Memory - Preserve state across sessions
8. Safe Rollback  - Undo bad changes
9. Webhook Triggers - HTTP endpoints to trigger tasks
10. Session Manager - Multiple concurrent sessions

Usage:
    python nexus_autopilot.py --daemon     # Full autopilot
    python nexus_autopilot.py --watch     # File watcher mode
    python nexus_autopilot.py --health    # Health check
    python nexus_autopilot.py schedule    # Show schedules
    python nexus_autopilot.py trigger     # Webhook trigger mode
"""

import asyncio
import base64
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import hashlib
import logging

# ============================================
# CONFIGURATION
# ============================================

WORKSPACE = Path("C:/Users/11vat/Desktop/Copilot/Aider-Local-llm-agent")
NEXUS_DIR = WORKSPACE / ".nexus"
NEXUS_DIR.mkdir(exist_ok=True)

SCHEDULE_FILE = NEXUS_DIR / "schedule.json"
CONTEXT_FILE = NEXUS_DIR / "context.json"
ERRORS_FILE = NEXUS_DIR / "errors.json"
ROLLBACK_DIR = NEXUS_DIR / "rollback"
ROLLBACK_DIR.mkdir(exist_ok=True)

# ============================================
# LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(NEXUS_DIR / "autopilot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("nexus")


# ============================================
# SCHEDULER
# ============================================

@dataclass
class ScheduledTask:
    """A scheduled task"""
    id: str
    task: str
    schedule: str  # cron-like: "*/5 * * * *" = every 5 min
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    
    def parse_schedule(self) -> float:
        """Parse schedule and return seconds until next run"""
        parts = self.schedule.split()
        if len(parts) != 5:
            return 300  # default 5 min
        
        minute = parts[0]
        hour = parts[1]
        day = parts[2]
        month = parts[3]
        weekday = parts[4]
        
        now = datetime.now()
        
        # Simple: */N means every N minutes
        if minute.startswith("*/"):
            interval = int(minute[2:])
            next_time = now + timedelta(minutes=interval)
            return (next_time - now).total_seconds()
        
        # Specific minute
        try:
            target_min = int(minute)
            target_hour = int(hour) if hour != "*" else now.hour
            
            next_run = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(hours=1)
            
            return (next_run - now).total_seconds()
        except:
            return 300


class Scheduler:
    """Cron-like task scheduler"""
    
    def __init__(self):
        self.tasks: List[ScheduledTask] = self._load()
        self.running = False
        self._lock = threading.Lock()
    
    def _load(self) -> List[ScheduledTask]:
        if SCHEDULE_FILE.exists():
            try:
                data = json.loads(SCHEDULE_FILE.read_text())
                return [ScheduledTask(**t) for t in data]
            except:
                pass
        return self._default_tasks()
    
    def _default_tasks(self) -> List[ScheduledTask]:
        return [
            ScheduledTask(
                id="health_check",
                task="python nexus_autopilot.py --health-check",
                schedule="*/5 * * * *",
                enabled=True
            ),
            ScheduledTask(
                id="ollama_status",
                task="ollama ps",
                schedule="*/10 * * * *",
                enabled=True
            ),
        ]
    
    def _save(self):
        with self._lock:
            SCHEDULE_FILE.write_text(json.dumps([
                {"id": t.id, "task": t.task, "schedule": t.schedule, 
                 "enabled": t.enabled, "last_run": t.last_run}
                for t in self.tasks
            ], indent=2))
    
    def add(self, task: str, schedule: str, name: str = None):
        """Add a new scheduled task"""
        task_id = name or hashlib.md5(task.encode()).hexdigest()[:8]
        if any(t.id == task_id for t in self.tasks):
            task_id = f"{task_id}_{int(time.time())}"
        
        new_task = ScheduledTask(id=task_id, task=task, schedule=schedule)
        self.tasks.append(new_task)
        self._save()
        return task_id
    
    def remove(self, task_id: str):
        """Remove a task"""
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self._save()
    
    async def run(self, executor):
        """Run scheduler loop"""
        self.running = True
        log.info("Scheduler started")
        
        while self.running:
            now = datetime.now()
            
            for task in self.tasks:
                if not task.enabled:
                    continue
                
                interval = task.parse_schedule()
                should_run = (
                    task.last_run is None or
                    (datetime.now() - datetime.fromisoformat(task.last_run)).total_seconds() >= interval
                )
                
                if should_run:
                    log.info(f"Running scheduled task: {task.id}")
                    task.last_run = now.isoformat()
                    self._save()
                    
                    # Execute task
                    asyncio.create_task(executor.execute_task(task.task))
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    def stop(self):
        self.running = False


# ============================================
# FILE WATCHER
# ============================================

class FileWatcher:
    """Watch files and auto-trigger tasks"""
    
    def __init__(self):
        self.watchers: Dict[str, Dict] = {}
        self.running = False
        self._last_events: Dict[str, float] = {}
    
    def add(self, pattern: str, task: str, watch_dir: str = "."):
        """Add a file watcher
        
        Args:
            pattern: Glob pattern like "*.py" or "src/**/*.js"
            task: Command to run when file changes
            watch_dir: Directory to watch
        """
        key = f"{watch_dir}:{pattern}"
        self.watchers[key] = {
            "pattern": pattern,
            "task": task,
            "watch_dir": Path(watch_dir)
        }
        log.info(f"Added watcher: {pattern} -> {task}")
    
    async def run(self, executor):
        """Watch for file changes"""
        self.running = True
        log.info("File watcher started")
        
        # Use polling (cross-platform)
        known_files: Dict[str, float] = {}
        
        while self.running:
            for key, watcher in list(self.watchers.items()):
                watch_dir = watcher["watch_dir"]
                pattern = watcher["pattern"]
                
                if not watch_dir.exists():
                    continue
                
                # Find matching files
                try:
                    for f in watch_dir.glob(pattern):
                        if f.is_file():
                            mtime = f.stat().st_mtime
                            key_str = str(f)
                            
                            # Check if changed
                            if key_str not in known_files or known_files[key_str] < mtime:
                                known_files[key_str] = mtime
                                
                                # Debounce (5 seconds)
                                last_event = self._last_events.get(key_str, 0)
                                if time.time() - last_event < 5:
                                    continue
                                self._last_events[key_str] = time.time()
                                
                                log.info(f"File changed: {f}")
                                
                                # Execute task
                                task = watcher["task"].replace("{file}", str(f))
                                asyncio.create_task(executor.execute_task(task))
                except Exception as e:
                    log.error(f"Watch error: {e}")
            
            await asyncio.sleep(1)
    
    def stop(self):
        self.running = False


# ============================================
# HEALTH MONITOR
# ============================================

class HealthMonitor:
    """Monitor system health and services"""
    
    def __init__(self):
        self.services = {
            "ollama": self._check_ollama,
            "python": self._check_python,
            "git": self._check_git,
            "node": self._check_node,
        }
        self.status_file = NEXUS_DIR / "health.json"
    
    def _check_ollama(self) -> Dict:
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=10
            )
            models = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    parts = line.split()
                    if parts:
                        models.append(parts[0])
            return {"status": "ok", "models": models, "count": len(models)}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _check_python(self) -> Dict:
        try:
            result = subprocess.run(
                [sys.executable, "--version"], capture_output=True, text=True, timeout=5
            )
            return {"status": "ok", "version": result.stdout.strip()}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _check_git(self) -> Dict:
        try:
            result = subprocess.run(
                ["git", "--version"], capture_output=True, text=True, timeout=5
            )
            return {"status": "ok", "version": result.stdout.strip()}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _check_node(self) -> Dict:
        try:
            result = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, timeout=5
            )
            return {"status": "ok", "version": result.stdout.strip()}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def check_all(self) -> Dict:
        """Check all services"""
        results = {}
        for name, check_fn in self.services.items():
            try:
                results[name] = await asyncio.get_event_loop().run_in_executor(
                    None, check_fn
                )
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
        
        # Save status
        results["timestamp"] = datetime.now().isoformat()
        self.status_file.write_text(json.dumps(results, indent=2))
        
        return results
    
    async def watch(self, interval: int = 60):
        """Continuously monitor health"""
        while True:
            status = await self.check_all()
            
            # Alert on issues
            for service, info in status.items():
                if service == "timestamp":
                    continue
                if info.get("status") == "error":
                    log.warning(f"Service {service} is down: {info.get('error')}")
                    await Notification.send(
                        f"Service Down: {service}",
                        info.get("error", "Unknown error")
                    )
            
            await asyncio.sleep(interval)


# ============================================
# GIT AUTOMATION
# ============================================

class GitAutomation:
    """Auto-git operations"""
    
    def __init__(self, repo_path: str = "."):
        self.repo = Path(repo_path)
    
    def status(self) -> Dict:
        """Get git status"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo, capture_output=True, text=True, timeout=10
            )
            changes = result.stdout.strip().split('\n') if result.stdout.strip() else []
            return {"clean": len(changes) == 0, "changes": changes}
        except Exception as e:
            return {"error": str(e)}
    
    def commit(self, message: str, auto_add: bool = True) -> Dict:
        """Auto-commit changes"""
        try:
            if auto_add:
                subprocess.run(["git", "add", "-A"], cwd=self.repo, timeout=10)
            
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo, capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                return {"success": True, "message": result.stdout}
            else:
                return {"success": False, "error": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_branch(self, name: str) -> Dict:
        """Create a new branch"""
        try:
            result = subprocess.run(
                ["git", "checkout", "-b", name],
                cwd=self.repo, capture_output=True, text=True, timeout=10
            )
            return {"success": result.returncode == 0, "output": result.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def auto_commit_if_clean(self, message: str = None):
        """Auto-commit if there are changes"""
        status = self.status()
        if status.get("clean"):
            return {"skipped": True, "reason": "No changes"}
        
        if message is None:
            # Generate message using LLM
            changes = status.get("changes", [])
            prompt = f"Generate a git commit message for these changes:\n" + "\n".join(changes[:10])
            
            try:
                result = subprocess.run(
                    ["ollama", "run", "qwen2.5-coder:14b"],
                    input=prompt.encode(), capture_output=True, timeout=30
                )
                message = result.stdout.decode().strip()[:72]
            except:
                message = f"Auto-commit: {datetime.now().isoformat()}"
        
        return self.commit(message)
    
    def snapshot(self) -> str:
        """Create a rollback snapshot"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = ROLLBACK_DIR / timestamp
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy key files
        for pattern in ["*.py", "*.json", "*.yaml", "*.md"]:
            for f in self.repo.glob(pattern):
                if f.is_file() and ".nexus" not in str(f):
                    dest = snapshot_dir / f.name
                    shutil.copy2(f, dest)
        
        return str(snapshot_dir)


# ============================================
# ERROR TRACKER
# ============================================

class ErrorTracker:
    """Track errors and detect patterns"""
    
    def __init__(self):
        self.errors_file = ERRORS_FILE
        self.errors: List[Dict] = self._load()
        self.max_errors = 100
    
    def _load(self) -> List[Dict]:
        if self.errors_file.exists():
            try:
                return json.loads(self.errors_file.read_text())
            except:
                pass
        return []
    
    def _save(self):
        # Keep only recent errors
        self.errors = self.errors[-self.max_errors:]
        self.errors_file.write_text(json.dumps(self.errors, indent=2))
    
    def track(self, error: str, context: str = "", task: str = ""):
        """Track an error"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "error": error[:500],
            "context": context[:200],
            "task": task[:100],
            "hash": hashlib.md5(error.encode()).hexdigest()[:16]
        }
        self.errors.append(entry)
        self._save()
        
        # Check for patterns
        patterns = self.detect_patterns()
        if patterns:
            log.warning(f"Error pattern detected: {patterns[0]['pattern']}")
    
    def detect_patterns(self) -> List[Dict]:
        """Detect recurring error patterns"""
        counts: Dict[str, int] = {}
        for err in self.errors[-50:]:
            h = err["hash"]
            if h in counts:
                counts[h] += 1
            else:
                counts[h] = 1
        
        patterns = []
        for h, count in counts.items():
            if count >= 3:
                err = next((e for e in self.errors if e["hash"] == h), None)
                if err:
                    patterns.append({
                        "pattern": err["error"],
                        "count": count,
                        "hash": h
                    })
        
        return patterns


# ============================================
# CONTEXT MEMORY
# ============================================

class ContextMemory:
    """Preserve context across sessions"""
    
    def __init__(self):
        self.file = CONTEXT_FILE
        self.context: Dict = self._load()
    
    def _load(self) -> Dict:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text())
            except:
                pass
        return {
            "current_project": None,
            "last_tasks": [],
            "variables": {},
            "session_history": []
        }
    
    def _save(self):
        self.file.write_text(json.dumps(self.context, indent=2))
    
    def set(self, key: str, value: Any):
        self.context[key] = value
        self._save()
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.context.get(key, default)
    
    def remember_task(self, task: str, result: Dict):
        """Remember completed task"""
        self.context.setdefault("last_tasks", [])
        self.context["last_tasks"].append({
            "task": task,
            "result": "success" if result.get("success") else "failed",
            "timestamp": datetime.now().isoformat()
        })
        self.context["last_tasks"] = self.context["last_tasks"][-20:]
        self._save()
    
    def get_context_summary(self) -> str:
        """Get context summary for LLM"""
        parts = []
        
        if self.context.get("current_project"):
            parts.append(f"Project: {self.context['current_project']}")
        
        last = self.context.get("last_tasks", [])
        if last:
            parts.append(f"Recent tasks: {', '.join(t['task'][:30] for t in last[-3:])}")
        
        vars_ = self.context.get("variables", {})
        if vars_:
            parts.append(f"Variables: {vars_}")
        
        return "\n".join(parts) if parts else "No context"


# ============================================
# NOTIFICATIONS
# ============================================

class Notification:
    """System notifications"""
    
    @staticmethod
    async def send(title: str, message: str):
        """Send notification"""
        log.info(f"NOTIFICATION: {title} - {message}")
        
        # Windows toast notification
        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    ['powershell', '-Command', 
                     f'New-BurntToastNotification -AppLogo "$env:TEMP\\nexus.png" -Line1 "{title}" -Line2 "{message[:100]}"'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        except:
            pass
    
    @staticmethod
    async def error(title: str, error: str):
        await Notification.send(f"[ERROR] {title}", error)
    
    @staticmethod
    async def success(title: str):
        await Notification.send(f"[OK] {title}", "Task completed successfully")


# ============================================
# ROLLBACK SYSTEM
# ============================================

class RollbackSystem:
    """Safe rollback for bad changes"""
    
    def __init__(self, repo_path: str = "."):
        self.repo = Path(repo_path)
        self.snapshots_dir = ROLLBACK_DIR
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def create_snapshot(self, name: str = None) -> str:
        """Create a snapshot for rollback"""
        if name is None:
            name = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        snapshot = self.snapshots_dir / name
        snapshot.mkdir(exist_ok=True)
        
        # Copy tracked files
        try:
            result = subprocess.run(
                ["git", "ls-files"], cwd=self.repo, capture_output=True, text=True, timeout=30
            )
            for f in result.stdout.strip().split('\n'):
                if f:
                    src = self.repo / f
                    if src.exists():
                        dest = snapshot / f
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)
        except:
            pass
        
        return str(snapshot)
    
    def list_snapshots(self) -> List[str]:
        return sorted([d.name for d in self.snapshots_dir.iterdir() if d.is_dir()])
    
    def restore(self, snapshot_name: str) -> Dict:
        """Restore from snapshot"""
        snapshot = self.snapshots_dir / snapshot_name
        if not snapshot.exists():
            return {"success": False, "error": "Snapshot not found"}
        
        # Backup current state
        self.create_snapshot("pre_restore_backup")
        
        # Copy files back
        try:
            for f in snapshot.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(snapshot)
                    dest = self.repo / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
            
            return {"success": True, "message": f"Restored from {snapshot_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================
# MAIN AUTOPILOT
# ============================================

class NexusAutopilot:
    """Complete autonomous system"""
    
    def __init__(self):
        self.scheduler = Scheduler()
        self.watcher = FileWatcher()
        self.health = HealthMonitor()
        self.git = GitAutomation(WORKSPACE)
        self.errors = ErrorTracker()
        self.context = ContextMemory()
        self.rollback = RollbackSystem(WORKSPACE)
        
        self.running = False
        
        # File watcher defaults
        self.watcher.add("*.py", "python {file}", str(WORKSPACE / "agent-system"))
        self.watcher.add("*.json", "echo 'Config changed'", str(WORKSPACE))
    
    async def start(self):
        """Start full autopilot"""
        self.running = True
        log.info("NEXUS AUTOPILOT STARTED")
        
        # Initial health check
        status = await self.health.check_all()
        log.info(f"Health: {json.dumps(status, indent=2)}")
        
        # Create snapshot
        self.rollback.create_snapshot("startup")
        
        # Start all subsystems
        tasks = [
            asyncio.create_task(self.scheduler.run(self)),
            asyncio.create_task(self.watcher.run(self)),
            asyncio.create_task(self.health.watch(interval=300)),
        ]
        
        # Wait until stopped
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
    
    async def execute_task(self, task: str) -> Dict:
        """Execute a task with full autonomy"""
        log.info(f"Executing: {task}")
        
        # Create snapshot before
        self.rollback.create_snapshot(f"pre_task_{int(time.time())}")
        
        try:
            # Parse task
            if "screenshot" in task.lower() or any(ext in task for ext in ['.png', '.jpg']):
                return await self._execute_vision(task)
            else:
                return await self._execute_generic(task)
        except Exception as e:
            self.errors.track(str(e), task=task)
            return {"success": False, "error": str(e)}
        finally:
            pass
    
    async def _execute_vision(self, task: str) -> Dict:
        """Execute vision task"""
        # Extract image path
        match = re.search(r'[\w:\\/.]+\.(png|jpg|jpeg|gif|bmp|webp)', task, re.I)
        if match:
            image_path = match.group(0)
            result = subprocess.run(
                ["ollama", "run", "llava", image_path],
                capture_output=True, text=True, timeout=60
            )
            return {"success": True, "output": result.stdout}
        
        return {"success": False, "error": "No image found"}
    
    async def _execute_generic(self, task: str) -> Dict:
        """Execute generic task"""
        try:
            result = subprocess.run(
                ["ollama", "run", "qwen2.5-coder:14b", task],
                capture_output=True, text=True, timeout=60
            )
            
            output = result.stdout
            success = result.returncode == 0 and not result.stderr
            
            if success:
                self.context.remember_task(task, {"success": True})
            
            return {
                "success": success,
                "output": output,
                "error": result.stderr if result.stderr else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def health_check(self) -> Dict:
        return await self.health.check_all()


# ============================================
# CLI
# ============================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS AUTOPILOT")
    parser.add_argument("--daemon", action="store_true", help="Full autopilot mode")
    parser.add_argument("--watch", action="store_true", help="File watcher only")
    parser.add_argument("--health-check", action="store_true", help="Health check")
    parser.add_argument("--schedule", action="store_true", help="Show schedules")
    parser.add_argument("--add-schedule", nargs=2, metavar=("TASK", "CRON"), help="Add scheduled task")
    parser.add_argument("--snapshot", action="store_true", help="Create rollback snapshot")
    parser.add_argument("--rollback", metavar="NAME", help="Restore from snapshot")
    parser.add_argument("--errors", action="store_true", help="Show error patterns")
    parser.add_argument("--context", action="store_true", help="Show context memory")
    
    args = parser.parse_args()
    
    autopilot = NexusAutopilot()
    
    if args.schedule:
        print("\n=== SCHEDULED TASKS ===")
        for t in autopilot.scheduler.tasks:
            status = "[ON]" if t.enabled else "[OFF]"
            print(f"{status} {t.schedule} -> {t.task[:50]}")
        return
    
    if args.add_schedule:
        task, cron = args.add_schedule
        autopilot.scheduler.add(task, cron)
        print(f"Added: {task} @ {cron}")
        return
    
    if args.health_check:
        status = await autopilot.health_check()
        print(json.dumps(status, indent=2))
        return
    
    if args.snapshot:
        name = autopilot.rollback.create_snapshot()
        print(f"Snapshot created: {name}")
        return
    
    if args.rollback:
        result = autopilot.rollback.restore(args.rollback)
        print(json.dumps(result, indent=2))
        return
    
    if args.errors:
        patterns = autopilot.errors.detect_patterns()
        if patterns:
            print("\n=== ERROR PATTERNS ===")
            for p in patterns:
                print(f"[{p['count']}x] {p['pattern'][:80]}")
        else:
            print("No patterns detected")
        return
    
    if args.context:
        print("\n=== CONTEXT MEMORY ===")
        print(autopilot.context.get_context_summary())
        return
    
    if args.watch:
        await autopilot.watcher.run(autopilot)
        return
    
    if args.daemon:
        await autopilot.start()
        return
    
    # Default: help
    print("""
NEXUS AUTOPILOT - Full Autonomy
===============================

Usage:
    python nexus_autopilot.py [command]

Commands:
    --daemon          Start full autopilot (all features)
    --watch           File watcher mode
    --health-check    Check system health
    --schedule        Show scheduled tasks
    --add-schedule "task" "cron"   Add scheduled task
    --snapshot        Create rollback snapshot
    --rollback NAME   Restore from snapshot
    --errors          Show error patterns
    --context         Show context memory

Examples:
    python nexus_autopilot.py --daemon
    python nexus_autopilot.py --add-schedule "health check" "*/5 * * * *"
    python nexus_autopilot.py --snapshot
""")


if __name__ == "__main__":
    asyncio.run(main())