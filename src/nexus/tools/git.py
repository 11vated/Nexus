"""Git tool — version control operations."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)


class GitTool(BaseTool):
    """Git operations for the agent workspace.

    Provides safe git operations: status, diff, add, commit, log.
    Does NOT support push/pull (those should be explicit user actions).
    """

    name = "git"
    description = "Run git commands (status, diff, add, commit, log)"
    aliases = ["git_tool"]
    schema = {
        "command": "(required) Git subcommand: status, diff, add, commit, log, branch",
        "args": "(optional) Additional arguments as a string",
    }

    # Only allow safe git operations
    ALLOWED_COMMANDS = frozenset({
        "status", "diff", "add", "commit", "log", "branch",
        "show", "stash", "checkout", "reset", "restore",
    })

    # Explicitly blocked
    BLOCKED_COMMANDS = frozenset({
        "push", "pull", "fetch", "remote", "clone",
        "force-push", "rebase",
    })

    async def execute(self, command: str = "", args: str = "", **kwargs: Any) -> str:
        if not command:
            return "Error: No git command provided"

        command = command.strip().lower()

        if command in self.BLOCKED_COMMANDS:
            return (
                f"Error: '{command}' is not allowed via the agent. "
                "Use the CLI directly for remote operations."
            )

        if command not in self.ALLOWED_COMMANDS:
            return (
                f"Error: Unknown git command: {command}. "
                f"Allowed: {', '.join(sorted(self.ALLOWED_COMMANDS))}"
            )

        # Build the git command
        cmd = ["git", command]
        if args:
            cmd.extend(args.split())

        # Special handling for commit (require -m message)
        if command == "commit" and "-m" not in args:
            return "Error: Commit requires a message. Use args: '-m \"your message\"'"

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=30
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            result = output.strip()
            if errors:
                # Git often writes to stderr for info (not just errors)
                result += f"\n{errors.strip()}" if result else errors.strip()

            if len(result) > 5000:
                result = result[:5000] + "\n... [truncated]"

            return result or "(no output)"

        except asyncio.TimeoutError:
            return "Error: Git command timed out"
        except FileNotFoundError:
            return "Error: git not found"
        except Exception as exc:
            return f"Error: {exc}"
