"""Safe subprocess execution utilities."""
import asyncio
import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from nexus.security.sanitizer import safe_subprocess_args


logger = logging.getLogger(__name__)

SAFE_ENV_VARS = {
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    "TERM",
    "LANG",
    "LC_ALL",
}


def get_safe_env(extra_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Create safe environment for subprocess execution."""
    safe_env = {k: v for k, v in os.environ.items() if k in SAFE_ENV_VARS}
    safe_env.update(extra_env or {})
    
    dangerous_vars = ["PYTHONPATH", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES"]
    for var in dangerous_vars:
        safe_env.pop(var, None)
    
    return safe_env


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = 300,
    capture_output: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run command safely without shell=True."""
    safe_subprocess_args(cmd)
    
    safe_env = get_safe_env(env)
    
    logger.debug(f"Running command: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=safe_env,
        capture_output=capture_output,
        text=True,
        timeout=timeout,
        check=check,
    )
    
    logger.debug(f"Command completed with return code: {result.returncode}")
    return result


async def run_command_async(
    cmd: List[str],
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = 300,
) -> tuple[bytes, bytes]:
    """Run command asynchronously without shell=True."""
    safe_subprocess_args(cmd)
    
    safe_env = get_safe_env(env)
    
    logger.debug(f"Running async command: {' '.join(cmd)}")
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=safe_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise
    
    logger.debug(f"Async command completed with return code: {process.returncode}")
    return stdout, stderr


def run_ollama(
    subcommand: str,
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    timeout: float = 120,
) -> str:
    """Run Ollama commands safely."""
    cmd = ["ollama", subcommand]
    
    if model:
        from nexus.security.sanitizer import validate_model_name
        model = validate_model_name(model)
        if subcommand == "run":
            cmd.append(model)
            if prompt:
                cmd.append(prompt)
        elif subcommand in ("pull", "stop"):
            cmd.append(model)
    elif prompt:
        cmd.append(prompt)
    
    result = run_command(cmd, timeout=timeout)
    
    if result.returncode != 0:
        logger.error(f"Ollama command failed: {result.stderr}")
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )
    
    return result.stdout


class CommandRunner:
    """Safe command execution with logging and error handling."""
    
    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace
    
    def run(self, cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run command with workspace defaults."""
        kwargs.setdefault("cwd", self.workspace)
        kwargs.setdefault("timeout", 300)
        
        try:
            return run_command(cmd, **kwargs)
        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Command failed: {' '.join(cmd)}\n"
                f"stdout: {e.stdout}\nstderr: {e.stderr}"
            )
            raise
        except FileNotFoundError:
            logger.error(f"Command not found: {cmd[0]}")
            raise
    
    async def run_async(self, cmd: List[str], **kwargs) -> tuple[bytes, bytes]:
        """Run command asynchronously."""
        kwargs.setdefault("cwd", self.workspace)
        kwargs.setdefault("timeout", 300)
        
        return await run_command_async(cmd, **kwargs)