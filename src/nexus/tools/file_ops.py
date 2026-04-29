"""File operation tools — read, write, list files safely.

Includes path traversal protection via the existing security module.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from nexus.tools.registry import BaseTool

logger = logging.getLogger(__name__)


def safe_resolve(workspace: str, path: str) -> Path:
    """Resolve a path safely within the workspace.

    Prevents path traversal attacks (../../etc/passwd).
    """
    workspace_path = Path(workspace).resolve()
    target = (workspace_path / path).resolve()

    if not str(target).startswith(str(workspace_path)):
        raise ValueError(
            f"Path traversal detected: {path} resolves outside workspace"
        )

    return target


class FileReadTool(BaseTool):
    """Read file contents."""

    name = "file_read"
    description = "Read the contents of a file"
    aliases = ["read_file", "read", "cat"]
    schema = {
        "path": "(required) File path relative to workspace",
        "max_lines": "(optional) Maximum lines to read (default: all)",
    }

    async def execute(self, path: str = "", max_lines: int = 0, **kwargs: Any) -> str:
        if not path:
            return "Error: No path provided"

        try:
            target = safe_resolve(self.workspace, path)
        except ValueError as e:
            return f"Error: {e}"

        if not target.exists():
            return f"Error: File not found: {path}"

        if not target.is_file():
            return f"Error: Not a file: {path}"

        try:
            content = target.read_text(encoding="utf-8", errors="replace")

            if max_lines > 0:
                lines = content.splitlines()
                if len(lines) > max_lines:
                    content = "\n".join(lines[:max_lines])
                    content += f"\n... [{len(lines) - max_lines} more lines]"

            # Truncate very large files
            if len(content) > 10000:
                content = content[:10000] + f"\n... [truncated, {len(content)} total chars]"

            return content
        except Exception as exc:
            return f"Error reading {path}: {exc}"


class FileWriteTool(BaseTool):
    """Write content to a file."""

    name = "file_write"
    description = "Write content to a file (creates directories if needed)"
    aliases = ["write_file", "write", "create_file"]
    schema = {
        "path": "(required) File path relative to workspace",
        "content": "(required) Content to write",
    }

    async def execute(self, path: str = "", content: str = "", **kwargs: Any) -> str:
        if not path:
            return "Error: No path provided"

        try:
            target = safe_resolve(self.workspace, path)
        except ValueError as e:
            return f"Error: {e}"

        try:
            # Create parent directories
            target.parent.mkdir(parents=True, exist_ok=True)

            target.write_text(content, encoding="utf-8")
            lines = content.count("\n") + 1
            return f"Written {len(content)} chars ({lines} lines) to {path}"
        except Exception as exc:
            return f"Error writing {path}: {exc}"


class FileListTool(BaseTool):
    """List files in a directory."""

    name = "file_list"
    description = "List files and directories in a path"
    aliases = ["list_files", "ls", "dir"]
    schema = {
        "path": "(optional) Directory path (default: workspace root)",
        "pattern": "(optional) Glob pattern (default: *)",
        "recursive": "(optional) List recursively (default: false)",
    }

    async def execute(
        self,
        path: str = ".",
        pattern: str = "*",
        recursive: bool = False,
        **kwargs: Any,
    ) -> str:
        try:
            target = safe_resolve(self.workspace, path)
        except ValueError as e:
            return f"Error: {e}"

        if not target.exists():
            return f"Error: Directory not found: {path}"

        if not target.is_dir():
            return f"Error: Not a directory: {path}"

        try:
            if recursive:
                files = sorted(target.rglob(pattern))
            else:
                files = sorted(target.glob(pattern))

            # Filter out common noise
            files = [
                f for f in files
                if not any(part.startswith(".") for part in f.relative_to(target).parts)
                or f.name in (".env", ".gitignore")
            ]

            if not files:
                return f"No files matching '{pattern}' in {path}"

            lines = []
            for f in files[:100]:
                rel = f.relative_to(target)
                prefix = "📁 " if f.is_dir() else "📄 "
                size = ""
                if f.is_file():
                    size_bytes = f.stat().st_size
                    if size_bytes < 1024:
                        size = f" ({size_bytes}B)"
                    else:
                        size = f" ({size_bytes // 1024}KB)"
                lines.append(f"{prefix}{rel}{size}")

            result = "\n".join(lines)
            if len(files) > 100:
                result += f"\n... [{len(files) - 100} more files]"
            return result

        except Exception as exc:
            return f"Error listing {path}: {exc}"
