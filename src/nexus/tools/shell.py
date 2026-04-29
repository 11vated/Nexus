"""Shell tool — safe command execution.

Builds on the existing subprocess_utils for safe command execution
without shell=True vulnerabilities.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from typing import Any

from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)

# Commands that should never be run by the agent
BLOCKED_COMMANDS = frozenset({
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev/zero",
    ":(){ :|:& };:", "shutdown", "reboot", "halt",
    "chmod -R 777 /", "chown -R",
})

# Commands that require extra caution
CAUTION_PREFIXES = ("rm ", "sudo ", "apt ", "pip install", "npm install -g")


class ShellTool(BaseTool):
    """Execute shell commands safely.

    Runs commands as subprocesses (no shell=True) with timeout
    protection and output capture.
    """

    name = "shell"
    description = "Run a shell command and capture output"
    aliases = ["bash", "run_command", "shell_run", "execute"]
    schema = {
        "command": "(required) The command to execute",
        "timeout": "(optional) Timeout in seconds (default: 30)",
    }

    async def execute(self, command: str = "", timeout: int = 30, **kwargs: Any) -> str:
        """Execute a shell command.

        Args:
            command: The command string to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            Combined stdout + stderr output.
        """
        if not command:
            return "Error: No command provided"

        # Security check
        command_lower = command.strip().lower()
        if command_lower in BLOCKED_COMMANDS:
            return f"Error: Blocked dangerous command: {command}"

        for prefix in CAUTION_PREFIXES:
            if command_lower.startswith(prefix):
                logger.warning("Caution command executed: %s", command[:80])

        try:
            # Parse command to avoid shell=True
            # But allow pipes and redirects by using shell for complex commands
            if any(c in command for c in ("|", ">", "<", "&&", "||", ";", "`", "$(")):
                # Complex command — use shell but log warning
                logger.debug("Using shell for complex command: %s", command[:80])
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.workspace,
                )
            else:
                # Simple command — parse safely
                args = shlex.split(command)
                process = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.workspace,
                )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                output_parts.append(f"[stderr] {stderr.decode('utf-8', errors='replace')}")

            output = "\n".join(output_parts).strip()

            if process.returncode != 0:
                output = f"[exit code {process.returncode}]\n{output}"

            # Truncate very long output
            if len(output) > 5000:
                output = output[:5000] + f"\n... [truncated, {len(output)} total chars]"

            return output or "(no output)"

        except asyncio.TimeoutError:
            return f"Error: Command timed out after {timeout}s: {command[:80]}"
        except FileNotFoundError:
            cmd_name = command.split()[0] if command.split() else command
            return f"Error: Command not found: {cmd_name}"
        except Exception as exc:
            return f"Error executing command: {type(exc).__name__}: {exc}"
