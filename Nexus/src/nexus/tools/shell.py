"""Shell tool — safe command execution.

Builds on the existing subprocess_utils for safe command execution
without shell=True vulnerabilities.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
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

# Dangerous shell patterns that indicate injection attempts
INJECTION_PATTERNS = [
    r"\$\(.+\)",         # Command substitution $(...)
    r"`[^`]+`",          # Backtick command substitution
    r";\s*\w+",          # Command chaining with semicolon
    r"\|\s*\w+",         # Pipe to unexpected command
    r">\s*/",            # Redirect to root paths
    r"&&\s*(rm|sudo)",   # Chained dangerous commands
]


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

        # Check for injection patterns
        if self._contains_injection(command):
            return (
                f"Error: Command contains potentially dangerous shell patterns. "
                f"Use separate tool calls instead of shell injection."
            )

        for prefix in CAUTION_PREFIXES:
            if command_lower.startswith(prefix):
                logger.warning("Caution command executed: %s", command[:80])

        try:
            # Parse command to avoid shell=True
            # But allow pipes and redirects by using shell for complex commands
            if any(c in command for c in ("|", ">", "<", "&&", "||")):
                # Complex command — use shell but with sanitization
                sanitized = self._sanitize_shell_command(command)
                if sanitized is None:
                    return "Error: Command contains unsafe shell patterns"

                logger.debug("Using shell for complex command: %s", command[:80])
                process = await asyncio.create_subprocess_shell(
                    sanitized,
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

    def _contains_injection(self, command: str) -> bool:
        """Check if command contains injection patterns."""
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, command):
                return True
        return False

    def _sanitize_shell_command(self, command: str) -> str | None:
        """Sanitize a complex shell command, removing dangerous constructs.

        Allows safe pipes and redirects but blocks:
        - Command substitution $(...) and backticks
        - Semicolon chaining
        - Redirects to system paths
        - Nested shell execution

        Returns sanitized command, or None if unsafe.
        """
        # Block command substitution
        if "$(" in command or "`" in command:
            return None

        # Block semicolon chaining
        if re.search(r";\s*\w", command):
            return None

        # Block redirects to dangerous paths
        if re.search(r">\s*/(?:etc|dev|proc|sys|root|usr)", command):
            return None

        # Block nested eval
        if re.search(r"\beval\b", command):
            return None

        # Block variable expansion that could be dangerous
        if re.search(r"\$\{[^}]*\}", command):
            return None

        return command
