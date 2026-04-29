"""Test runner tool — execute test suites and parse results."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)


class TestRunnerTool(BaseTool):
    """Run test suites and parse results.

    Supports pytest (Python) and basic npm test (Node.js).
    Parses output to extract pass/fail counts and failure details.
    """

    name = "test_run"
    description = "Run test suite (pytest or npm test) and get structured results"
    aliases = ["run_tests", "pytest", "test"]
    schema = {
        "path": "(optional) Test file or directory (default: current directory)",
        "framework": "(optional) Test framework: pytest, npm (default: pytest)",
        "verbose": "(optional) Verbose output (default: true)",
        "timeout": "(optional) Timeout in seconds (default: 60)",
    }

    async def execute(
        self,
        path: str = ".",
        framework: str = "pytest",
        verbose: bool = True,
        timeout: int = 60,
        **kwargs: Any,
    ) -> str:
        if framework == "pytest":
            return await self._run_pytest(path, verbose, timeout)
        elif framework == "npm":
            return await self._run_npm_test(timeout)
        else:
            return f"Error: Unknown framework: {framework}. Supported: pytest, npm"

    async def _run_pytest(self, path: str, verbose: bool, timeout: int) -> str:
        """Run pytest and parse results."""
        cmd = ["python3", "-m", "pytest", path]
        if verbose:
            cmd.append("-v")
        cmd.append("--tb=short")  # Short tracebacks

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            # Parse pytest summary
            summary = self._parse_pytest_summary(output)

            result = output
            if errors and "warning" not in errors.lower():
                result += f"\n[stderr] {errors}"

            if summary:
                result = f"SUMMARY: {summary}\n\n{result}"

            # Truncate if too long
            if len(result) > 5000:
                result = result[:5000] + "\n... [truncated]"

            return result

        except asyncio.TimeoutError:
            return f"Error: Tests timed out after {timeout}s"
        except FileNotFoundError:
            return "Error: pytest not found. Install with: pip install pytest"
        except Exception as exc:
            return f"Error running tests: {exc}"

    def _parse_pytest_summary(self, output: str) -> str:
        """Extract pytest summary line."""
        # Look for "X passed, Y failed" pattern
        for line in reversed(output.splitlines()):
            if "passed" in line or "failed" in line or "error" in line:
                # Clean up ANSI codes
                clean = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
                if clean.startswith("="):
                    clean = clean.strip("= ")
                return clean
        return ""

    async def _run_npm_test(self, timeout: int) -> str:
        """Run npm test."""
        try:
            process = await asyncio.create_subprocess_exec(
                "npm", "test",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            result = output + (f"\n{errors}" if errors else "")

            if process.returncode != 0:
                result = f"[TESTS FAILED - exit code {process.returncode}]\n{result}"

            if len(result) > 5000:
                result = result[:5000] + "\n... [truncated]"

            return result

        except asyncio.TimeoutError:
            return f"Error: Tests timed out after {timeout}s"
        except FileNotFoundError:
            return "Error: npm not found"
