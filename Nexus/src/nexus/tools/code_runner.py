"""Code runner tool — execute scripts in a sandboxed environment."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)


class CodeRunnerTool(BaseTool):
    """Execute code scripts and capture output.

    Runs Python (or other language) scripts in a subprocess with
    timeout protection. For dangerous code, use with the sandbox module.
    """

    name = "code_run"
    description = "Execute a code snippet (Python by default) and capture output"
    aliases = ["run_code", "execute_code", "python"]
    schema = {
        "code": "(required) The code to execute",
        "language": "(optional) Language: python, node, bash (default: python)",
        "timeout": "(optional) Timeout in seconds (default: 30)",
    }

    async def execute(
        self,
        code: str = "",
        language: str = "python",
        timeout: int = 30,
        **kwargs: Any,
    ) -> str:
        if not code:
            return "Error: No code provided"

        runners = {
            "python": self._run_python,
            "node": self._run_node,
            "bash": self._run_bash,
        }

        runner = runners.get(language.lower())
        if not runner:
            return f"Error: Unsupported language: {language}. Supported: {', '.join(runners)}"

        return await runner(code, timeout)

    async def _run_python(self, code: str, timeout: int) -> str:
        """Run Python code in a temp file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=self.workspace, delete=False
        ) as f:
            f.write(code)
            script_path = f.name

        try:
            process = await asyncio.create_subprocess_exec(
                "python3", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            result = ""
            if output:
                result += output
            if errors:
                result += f"\n[stderr] {errors}" if result else f"[stderr] {errors}"
            if process.returncode != 0:
                result = f"[exit code {process.returncode}]\n{result}"

            return result.strip() or "(no output)"

        except asyncio.TimeoutError:
            return f"Error: Script timed out after {timeout}s"
        except Exception as exc:
            return f"Error: {exc}"
        finally:
            Path(script_path).unlink(missing_ok=True)

    async def _run_node(self, code: str, timeout: int) -> str:
        """Run JavaScript code with Node.js."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", dir=self.workspace, delete=False
        ) as f:
            f.write(code)
            script_path = f.name

        try:
            process = await asyncio.create_subprocess_exec(
                "node", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")
            result = output + (f"\n[stderr] {errors}" if errors else "")

            if process.returncode != 0:
                result = f"[exit code {process.returncode}]\n{result}"

            return result.strip() or "(no output)"

        except asyncio.TimeoutError:
            return f"Error: Script timed out after {timeout}s"
        except FileNotFoundError:
            return "Error: Node.js not found. Install with: apt install nodejs"
        finally:
            Path(script_path).unlink(missing_ok=True)

    async def _run_bash(self, code: str, timeout: int) -> str:
        """Run bash script."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", dir=self.workspace, delete=False
        ) as f:
            f.write(code)
            script_path = f.name

        try:
            process = await asyncio.create_subprocess_exec(
                "bash", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")
            result = output + (f"\n[stderr] {errors}" if errors else "")

            if process.returncode != 0:
                result = f"[exit code {process.returncode}]\n{result}"

            return result.strip() or "(no output)"

        except asyncio.TimeoutError:
            return f"Error: Script timed out after {timeout}s"
        finally:
            Path(script_path).unlink(missing_ok=True)
