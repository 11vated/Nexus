"""Search tool — grep/ripgrep codebase search."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)


class SearchTool(BaseTool):
    """Search codebase using grep or ripgrep.

    Provides fast code search with context lines. Prefers ripgrep (rg)
    if available, falls back to grep.
    """

    name = "search"
    description = "Search codebase for a pattern (regex supported)"
    aliases = ["grep", "rg", "find_in_files"]
    schema = {
        "pattern": "(required) Search pattern (regex)",
        "path": "(optional) Directory or file to search (default: workspace)",
        "file_pattern": "(optional) File glob filter, e.g. '*.py'",
        "context_lines": "(optional) Lines of context around matches (default: 2)",
        "case_insensitive": "(optional) Case insensitive search (default: false)",
    }

    async def execute(
        self,
        pattern: str = "",
        path: str = ".",
        file_pattern: str = "",
        context_lines: int = 2,
        case_insensitive: bool = False,
        **kwargs: Any,
    ) -> str:
        if not pattern:
            return "Error: No search pattern provided"

        # Try ripgrep first (faster), fall back to grep
        rg_available = await self._check_command("rg")

        if rg_available:
            return await self._search_rg(
                pattern, path, file_pattern, context_lines, case_insensitive
            )
        else:
            return await self._search_grep(
                pattern, path, file_pattern, context_lines, case_insensitive
            )

    async def _check_command(self, cmd: str) -> bool:
        """Check if a command is available."""
        try:
            process = await asyncio.create_subprocess_exec(
                "which", cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False

    async def _search_rg(
        self,
        pattern: str,
        path: str,
        file_pattern: str,
        context_lines: int,
        case_insensitive: bool,
    ) -> str:
        """Search using ripgrep."""
        cmd = ["rg", "--no-heading", "-n", f"-C{context_lines}"]
        if case_insensitive:
            cmd.append("-i")
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        cmd.extend([pattern, path])

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

            if not output.strip():
                return f"No matches found for '{pattern}'"

            # Count matches
            match_count = sum(1 for line in output.splitlines() if line and not line.startswith("--"))

            result = f"Found {match_count} matches:\n\n{output}"

            if len(result) > 5000:
                result = result[:5000] + "\n... [truncated]"

            return result

        except asyncio.TimeoutError:
            return "Error: Search timed out"
        except Exception as exc:
            return f"Error: {exc}"

    async def _search_grep(
        self,
        pattern: str,
        path: str,
        file_pattern: str,
        context_lines: int,
        case_insensitive: bool,
    ) -> str:
        """Fallback search using grep."""
        cmd = ["grep", "-rn", f"-C{context_lines}"]
        if case_insensitive:
            cmd.append("-i")
        if file_pattern:
            cmd.extend(["--include", file_pattern])
        cmd.extend([pattern, path])

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

            if not output.strip():
                return f"No matches found for '{pattern}'"

            match_count = sum(1 for line in output.splitlines() if ":" in line and not line.startswith("--"))
            result = f"Found ~{match_count} matches:\n\n{output}"

            if len(result) > 5000:
                result = result[:5000] + "\n... [truncated]"

            return result

        except asyncio.TimeoutError:
            return "Error: Search timed out"
        except Exception as exc:
            return f"Error: {exc}"
