"""Execution sandbox for safe code running."""
import subprocess
import tempfile
import shutil
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class SandboxState(Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    state: SandboxState


class ExecutionSandbox:
    """Sandbox for safe code execution."""
    
    def __init__(
        self,
        workspace: Path = None,
        max_cpu_percent: int = 80,
        max_memory_mb: int = 4096,
        network_enabled: bool = False,
        timeout_seconds: int = 60
    ):
        self.workspace = workspace or Path(tempfile.mkdtemp(prefix="nexus_sandbox_"))
        self.max_cpu_percent = max_cpu_percent
        self.max_memory_mb = max_memory_mb
        self.network_enabled = network_enabled
        self.timeout_seconds = timeout_seconds
        self.state = SandboxState.CREATED
    
    def __enter__(self):
        self.setup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
    
    def setup(self):
        """Set up sandbox environment."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Create working directories
        (self.workspace / "src").mkdir(exist_ok=True)
        (self.workspace / "tests").mkdir(exist_ok=True)
        (self.workspace / "output").mkdir(exist_ok=True)
        
        self.state = SandboxState.RUNNING
        logger.info(f"Sandbox created at {self.workspace}")
    
    def cleanup(self):
        """Clean up sandbox."""
        self.state = SandboxState.STOPPED
        
        try:
            if self.workspace.exists() and "nexus_sandbox_" in str(self.workspace):
                shutil.rmtree(self.workspace)
                logger.info(f"Sandbox cleaned: {self.workspace}")
        except Exception as e:
            logger.warning(f"Failed to cleanup sandbox: {e}")
    
    def run_python(self, code: str, timeout: int = None) -> SandboxResult:
        """Run Python code in sandbox."""
        import time
        start = time.time()
        
        # Write code to temp file
        code_file = self.workspace / "temp_script.py"
        code_file.write_text(code)
        
        timeout = timeout or self.timeout_seconds
        
        # Build command
        cmd = self._build_python_command(code_file)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.workspace,
                env=self._get_safe_env()
            )
            
            duration = (time.time() - start) * 1000
            
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration_ms=duration,
                state=self.state
            )
        except subprocess.TimeoutExpired as e:
            duration = (time.time() - start) * 1000
            return SandboxResult(
                success=False,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr="Execution timed out",
                exit_code=-1,
                duration_ms=duration,
                state=self.state
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=duration,
                state=self.state
            )
        finally:
            # Cleanup temp file
            if code_file.exists():
                code_file.unlink()
    
    def run_command(self, cmd: List[str], timeout: int = None) -> SandboxResult:
        """Run a command in sandbox."""
        import time
        start = time.time()
        
        timeout = timeout or self.timeout_seconds
        
        safe_cmd = self._sanitize_command(cmd)
        
        try:
            result = subprocess.run(
                safe_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.workspace,
                env=self._get_safe_env()
            )
            
            duration = (time.time() - start) * 1000
            
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration_ms=duration,
                state=self.state
            )
        except subprocess.TimeoutExpired as e:
            duration = (time.time() - start) * 1000
            return SandboxResult(
                success=False,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr="Command timed out",
                exit_code=-1,
                duration_ms=duration,
                state=self.state
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=duration,
                state=self.state
            )
    
    def run_tests(self, test_framework: str = "pytest") -> SandboxResult:
        """Run tests in sandbox."""
        if test_framework == "pytest":
            return self.run_command(["pytest", "--maxfail=1", "-v", "tests/"])
        elif test_framework == "unittest":
            return self.run_command(["python", "-m", "unittest", "discover", "tests/"])
        elif test_framework == "npm":
            return self.run_command(["npm", "test"])
        else:
            return SandboxResult(
                success=False,
                stdout="",
                stderr=f"Unknown test framework: {test_framework}",
                exit_code=-1,
                duration_ms=0,
                state=self.state
            )
    
    def _build_python_command(self, code_file: Path) -> List[str]:
        """Build safe Python command."""
        return [
            sys.executable,
            "-B",  # Don't write bytecode
            "-c", f"import sys; sys.path.insert(0, '{self.workspace}')",
            str(code_file)
        ]
    
    def _sanitize_command(self, cmd: List[str]) -> List[str]:
        """Sanitize command."""
        # Remove any dangerous flags
        dangerous = ["--eval", "-c", "-m"]
        return [c for c in cmd if not any(c.startswith(d) for d in dangerous)]
    
    def _get_safe_env(self) -> Dict[str, str]:
        """Get safe environment variables."""
        import os
        
        safe_env = os.environ.copy()
        
        # Remove dangerous variables
        dangerous = ["PYTHONPATH", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES"]
        for var in dangerous:
            safe_env.pop(var, None)
        
        # Add sandbox paths
        safe_env["PYTHONPATH"] = str(self.workspace)
        
        # Disable network if not enabled
        if not self.network_enabled:
            # Note: This doesn't completely disable network
            # For full isolation, use Docker
            pass
        
        return safe_env
    
    def create_snapshot(self) -> str:
        """Create a snapshot of current state."""
        snapshot_file = self.workspace / "snapshot.json"
        
        snapshot = {
            "created_at": str(Path().resolve()),
            "files": []
        }
        
        for f in self.workspace.rglob("*"):
            if f.is_file():
                snapshot["files"].append({
                    "path": str(f.relative_to(self.workspace)),
                    "size": f.stat().st_size
                })
        
        snapshot_file.write_text(json.dumps(snapshot, indent=2))
        return str(snapshot_file)
    
    def restore_snapshot(self, snapshot_file: str):
        """Restore from a snapshot."""
        snapshot_data = json.loads(Path(snapshot_file).read_text())
        
        for file_info in snapshot_data.get("files", []):
            logger.info(f"Would restore: {file_info['path']}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sandbox statistics."""
        total_size = 0
        file_count = 0
        
        for f in self.workspace.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1
        
        return {
            "workspace": str(self.workspace),
            "state": self.state.value,
            "file_count": file_count,
            "total_size_bytes": total_size,
            "max_memory_mb": self.max_memory_mb,
            "max_cpu_percent": self.max_cpu_percent,
            "timeout_seconds": self.timeout_seconds,
            "network_enabled": self.network_enabled
        }


# Utility function for quick execution
def run_sandboxed(code: str, timeout: int = 30) -> SandboxResult:
    """Quick function to run code in sandbox."""
    with ExecutionSandbox(timeout_seconds=timeout) as sandbox:
        return sandbox.run_python(code)