"""Code Analyzer Plugin — Example Nexus plugin.

Demonstrates:
- Plugin metadata
- Tool registration
- Hook registration
- Command registration
- Stance registration
"""

from nexus.plugins.base import Plugin, NexusAPI, PluginMetadata


class CodeAnalyzerTool:
    """Example tool that analyzes code quality."""

    description = "Analyze code quality metrics (complexity, imports, style)"
    schema = {
        "code": "Python code to analyze",
        "language": "Language (python, javascript, etc.)",
    }
    aliases = ["analyze", "code_check"]

    async def execute(self, code: str, language: str = "python") -> str:
        lines = code.strip().split("\n")
        line_count = len(lines)
        blank_lines = sum(1 for l in lines if not l.strip())
        comment_lines = sum(1 for l in lines if l.strip().startswith("#"))

        import_count = sum(1 for l in lines if l.strip().startswith(("import ", "from ")))

        # Simple complexity: count nested blocks
        max_indent = max((len(l) - len(l.lstrip())) for l in lines if l.strip()) if lines else 0
        complexity = max_indent // 4 + 1

        return (
            f"Code Analysis Results:\n"
            f"  Lines: {line_count} (code: {line_count - blank_lines - comment_lines}, "
            f"blank: {blank_lines}, comments: {comment_lines})\n"
            f"  Imports: {import_count}\n"
            f"  Estimated complexity: {complexity}/10\n"
            f"  Suggestions: "
            f"{'Consider refactoring deep nesting' if complexity > 3 else 'Code structure looks good'}"
        )


class CodeAnalyzerPlugin(Plugin):
    metadata = PluginMetadata(
        name="code_analyzer",
        version="1.0.0",
        description="Static code analysis tool with quality scoring",
        author="Nexus",
        tags=["analysis", "code-quality", "static-analysis"],
    )

    def register(self, api: NexusAPI) -> None:
        # Register the analysis tool
        api.register_tool(
            name="code_analyze",
            tool_class=CodeAnalyzerTool,
            description="Analyze code quality metrics",
        )

        # Register a hook that runs after file writes
        api.register_hook(
            event="post_tool_call",
            callback=self._on_file_write,
            priority=30,
        )

        # Register a CLI command
        api.register_command(
            name="analyze",
            handler=self._handle_analyze_command,
            description="Analyze the last written file for code quality",
        )

    def _on_file_write(self, event) -> None:
        """Auto-analyze files after they're written."""
        if event.data.get("tool") == "file_write":
            path = event.data.get("args", {}).get("path", "")
            if path.endswith(".py"):
                event.data.setdefault("analysis", "queued")

    def _handle_analyze_command(self, name: str, args: str) -> str:
        """Handle /analyze command."""
        return "Code analyzer ready. Use the code_analyze tool to analyze specific code."


# Plugin instance for auto-discovery (Strategy 1 in loader)
plugin = CodeAnalyzerPlugin()
