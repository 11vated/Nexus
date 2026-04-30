# Contributing to Nexus

Nexus is open to contributions. This guide explains how to set up a development environment, add new capabilities, and submit changes.

## Setup

```bash
# Clone and install
git clone https://github.com/11vated/Nexus.git
cd Nexus
pip install -e ".[dev]"

# Verify
nexus --help
pytest tests/ -v --timeout=30
```

Requirements:
- Python 3.10+
- Ollama running locally (for integration testing)

## Running Tests

```bash
# All tests
pytest tests/ -v --timeout=30

# Specific area
pytest tests/unit/test_intelligence/ -v
pytest tests/unit/test_chat_integration.py -v

# With coverage
pytest --cov=nexus --cov-report=html
```

The test suite currently has 630 passing tests. All PRs should maintain or increase this number.

## Adding a New Tool

Tools are the primary way Nexus interacts with the filesystem and external systems.

### 1. Create the tool

```python
# src/nexus/tools/my_tool.py
from nexus.tools.registry import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    
    def execute(self, arg1: str, arg2: int = 10) -> ToolResult:
        """
        Args:
            arg1: What this argument does
            arg2: Optional parameter with default
        """
        try:
            result = do_something(arg1, arg2)
            return ToolResult(success=True, output=str(result))
        except Exception as e:
            return ToolResult(success=False, output=f"Error: {e}")
```

### 2. Register it

Add the tool to the registry in `ChatSession.__init__()` and `AgentLoop` initialization:

```python
from nexus.tools.my_tool import MyTool
self._tools["my_tool"] = MyTool(workspace=self.workspace)
```

### 3. Set its permission level

In `PermissionManager`, map the tool to a trust level:

```python
TOOL_LEVELS = {
    "my_tool": TrustLevel.WRITE,  # Requires WRITE trust
    ...
}
```

### 4. Write tests

```python
# tests/unit/test_tools/test_my_tool.py
def test_my_tool_basic():
    tool = MyTool(workspace="/tmp")
    result = tool.execute(arg1="hello")
    assert result.success
    assert "expected" in result.output
```

## Adding a New Stance

Stances change how Nexus behaves during different types of conversation.

### 1. Define the stance

In `src/nexus/intelligence/stances.py`:

```python
STANCES = {
    ...,
    "optimizer": Stance(
        name="optimizer",
        description="Performance-focused mode",
        system_prompt=(
            "You are a performance optimization specialist. "
            "Focus on algorithmic complexity, memory usage, "
            "and runtime performance. Suggest profiling and "
            "benchmarking approaches."
        ),
        temperature=0.3,
        triggers=["slow", "performance", "optimize", "benchmark", "profil"],
    ),
}
```

### 2. Add detection rules

The `StanceManager.detect()` method uses keyword matching and context analysis. Add trigger words that should activate your stance.

### 3. Test it

```python
def test_optimizer_stance_detection():
    mgr = StanceManager()
    stance = mgr.detect("This endpoint is slow, how can we optimize it?")
    assert stance.name == "optimizer"
```

## Adding a Hook

Hooks let you inject behavior before or after tool execution.

### Example: Auto-format after file write

```python
from nexus.hooks.engine import HookEngine

def auto_format(tool_name, args, result):
    """Run black formatter after Python file writes."""
    if args.get("path", "").endswith(".py"):
        import subprocess
        subprocess.run(["black", args["path"]], capture_output=True)

hooks = HookEngine()
hooks.register(
    event="file_write",
    phase="POST",
    callback=auto_format,
    priority=50,  # Lower = runs first
)
```

PRE hooks can modify arguments or raise exceptions to block execution. POST hooks observe and can trigger side effects.

## Adding a Slash Command

Slash commands are handled in `src/nexus/tui/chat_ui.py`:

### 1. Add the handler

```python
# In the command dispatch section of chat_ui.py
elif command == "/mycommand":
    args = parts[1] if len(parts) > 1 else ""
    result = self._handle_mycommand(args)
    self._add_system_message(result)
```

### 2. Implement the handler

```python
def _handle_mycommand(self, args: str) -> str:
    """Handle /mycommand."""
    # Do something useful
    return f"Result: {args}"
```

### 3. Add to help text

Update the `/help` output and the CLI help text in `cli.py`.

## Code Style

- **Type hints** on all function signatures
- **Docstrings** on public methods
- **f-strings** for string formatting
- Line length: 100 characters
- Follow existing patterns in the codebase

## PR Guidelines

1. **Branch from main** — use descriptive branch names (`feat/editor-integration`, `fix/diff-undo-crash`)
2. **Write tests** — every new feature needs tests. Every bug fix needs a regression test.
3. **Zero regressions** — the test count should not go down
4. **Update docs** — if you add a feature, update README.md and ARCHITECTURE.md
5. **Small, focused PRs** — one feature or fix per PR

## Architecture Notes for Contributors

Read [ARCHITECTURE.md](./ARCHITECTURE.md) for the full technical overview. Key points:

- `ChatSession.send()` is a generator that yields `ChatEvent` objects
- The intelligence layer (ModelRouter, StanceManager, ProjectMap) runs on every message
- The interactive layer (DiffEngine, PermissionManager, HookEngine) wraps tool execution
- Unknown tools bypass the permission layer — they fall through to a "tool not found" error
- All state is local. No network calls except to Ollama on localhost.

## Questions?

Open an issue on the repository or check the existing discussions.
