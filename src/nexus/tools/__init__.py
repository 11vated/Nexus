"""Nexus Tool System — extensible tool registry for the agent."""

from nexus.tools.registry import ToolRegistry, BaseTool
from nexus.tools.shell import ShellTool
from nexus.tools.file_ops import FileReadTool, FileWriteTool, FileListTool
from nexus.tools.code_runner import CodeRunnerTool
from nexus.tools.test_runner import TestRunnerTool
from nexus.tools.search import SearchTool
from nexus.tools.git import GitTool

__all__ = [
    "ToolRegistry",
    "BaseTool",
    "ShellTool",
    "FileReadTool",
    "FileWriteTool",
    "FileListTool",
    "CodeRunnerTool",
    "TestRunnerTool",
    "SearchTool",
    "GitTool",
]


def create_default_tools(workspace: str = ".") -> dict:
    """Create the standard set of tools for the agent.

    Args:
        workspace: Root workspace path.

    Returns:
        Dict of tool_name -> tool_instance.
    """
    return {
        "shell": ShellTool(workspace=workspace),
        "file_read": FileReadTool(workspace=workspace),
        "file_write": FileWriteTool(workspace=workspace),
        "file_list": FileListTool(workspace=workspace),
        "code_run": CodeRunnerTool(workspace=workspace),
        "test_run": TestRunnerTool(workspace=workspace),
        "search": SearchTool(workspace=workspace),
        "git": GitTool(workspace=workspace),
    }
