# Nexus — Architecture Guide

This document describes the internal architecture of Nexus for developers who want to understand, extend, or contribute to the project.

## Overview

Nexus is organized around two execution modes that share a common foundation:

```
                    ┌──────────────┐
                    │   CLI Entry  │  (cli.py)
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
     ┌────────────────┐      ┌──────────────────┐
     │   ChatSession  │      │    AgentLoop      │
     │  (chat.py)     │      │   (loop.py)       │
     └───────┬────────┘      └────────┬──────────┘
             │                        │
             ▼                        ▼
     ┌───────────────────────────────────────────┐
     │              Shared Foundation             │
     │  Tools · Memory · Security · Config        │
     └───────────────────────────────────────────┘
             │
             ▼
     ┌───────────────────────────────────────────┐
     │            Ollama (Local LLMs)             │
     └───────────────────────────────────────────┘
```

## Entry Point

`pyproject.toml` defines the CLI entry point:

```toml
[project.scripts]
nexus = "nexus.cli:main"
```

`cli.py` is a Click application with subcommands: `chat`, `tui`, `run`, `quickstart`, `agent`, `bench`, `models`, `pull`.

## ChatSession — The Primary Mode

`src/nexus/agent/chat.py` (~1,450 lines) is the heart of Nexus. It manages:

### Initialization

```python
ChatSession(
    model="qwen2.5-coder:14b",
    workspace="/path/to/project",
    ollama_url="http://localhost:11434"
)
```

On creation, ChatSession:
1. Initializes the Ollama client
2. Registers all 8 tools
3. Sets up the intelligence layer (ModelRouter, StanceManager, ProjectMap, SessionStore)
4. Sets up the interactive layer (DiffEngine, ConversationTree, PermissionManager, HookEngine, WatcherEngine)

### Message Flow

When the user sends a message:

```
User message
    │
    ▼
┌─ Intelligence Layer ─────────────────────────────┐
│  1. ModelRouter.route(message) → best model       │
│  2. StanceManager.detect(message) → stance        │
│  3. ProjectMap.resolve(message) → relevant files   │
│  4. Build system prompt (stance + context + tools) │
└──────────────────────────────────────────────────┘
    │
    ▼
┌─ LLM Call ───────────────────────────────────────┐
│  Send to Ollama with conversation history +       │
│  system prompt + tool descriptions                │
│  Response may include tool calls                  │
└──────────────────────────────────────────────────┘
    │
    ▼
┌─ Tool Execution (if tools called) ───────────────┐
│  For each tool call:                              │
│  1. Permission check (known tools only)           │
│  2. PRE hooks → can block or modify               │
│  3. Diff preview (for file_write)                 │
│  4. Execute tool                                  │
│  5. POST hooks → observe and log                  │
│  6. Audit trail entry                             │
└──────────────────────────────────────────────────┘
    │
    ▼
Response to user (text + events)
```

### Event System

ChatSession uses a generator-based event system. The `send()` method yields `ChatEvent` objects:

```python
class EventType(Enum):
    TEXT = "text"           # LLM response text
    TOOL_CALL = "tool"     # Tool was called
    TOOL_RESULT = "result" # Tool returned a result
    THINKING = "thinking"  # LLM is processing
    ERROR = "error"        # Something went wrong
    DIFF_PREVIEW = "diff"  # Diff generated for file write
    PERMISSION = "perm"    # Permission check result
    HOOK = "hook"          # Hook fired
    BRANCH = "branch"      # Branch operation
```

This allows the TUI to render events as they happen — streaming text, showing diff previews inline, displaying permission decisions, etc.

## Intelligence Layer

### ModelRouter (`intelligence/model_router.py`)

Analyzes each message to determine the best model:

```python
router = ModelRouter(config)
route = router.route("How should we structure the auth module?")
# route.model = "deepseek-r1:7b" (planning/architecture question)
# route.category = "architecture"
# route.confidence = 0.85
```

Intent categories: `architecture`, `code_generation`, `debugging`, `review`, `refactor`, `testing`, `documentation`, `quick_edit`, `exploration`, `general`.

Each category maps to a model and temperature configuration.

### StanceManager (`intelligence/stances.py`)

Manages adaptive behavior modes:

```python
stance_mgr = StanceManager()
stance = stance_mgr.detect(message, context)
system_prompt_addition = stance.system_prompt
```

Seven stances: Architect, Pair Programmer, Debugger, Reviewer, Teacher, Explorer, Default. Each provides:
- A system prompt addition that shapes LLM behavior
- Temperature and response length preferences
- Transition rules (what stances can follow what)

### ProjectMap (`intelligence/project_map.py`)

AST-based codebase analysis:

```python
project = ProjectMap("/path/to/project")
project.scan()

# Find files related to a concept
files = project.resolve("authentication")

# Get dependency graph
deps = project.dependencies("src/api/auth.py")

# Find hot files (most imported/changed)
hot = project.hot_files(top_n=10)
```

### SessionStore (`intelligence/session_store.py`)

Persistence for conversations:

```python
store = SessionStore(storage_dir=".nexus/sessions")
store.save(session_id, messages, metadata)
sessions = store.list()
messages = store.load(session_id)
results = store.search("auth refactor")
```

## Interactive Layer

### DiffEngine (`diff/engine.py`)

Generates and manages diffs for file operations:

```python
engine = DiffEngine()
diff = engine.preview(path, old_content, new_content)
engine.accept(diff_id)
engine.reject(diff_id)
engine.undo()  # Revert last accept
```

`DiffRenderer` formats diffs for terminal display with syntax highlighting.

### ConversationTree (`intelligence/branching.py`)

Git-like branching for conversations:

```python
tree = ConversationTree()
tree.create_branch("experiment/redis")
tree.switch("experiment/redis")
comparison = tree.compare("main", "experiment/redis")
tree.merge("experiment/redis")  # Merge into current branch
history = tree.history()  # Full tree visualization
```

Each branch maintains its own message history. The system prompt includes the current branch name when multiple branches exist.

### PermissionManager (`safety/permissions.py`)

Four trust levels with granular control:

```python
perms = PermissionManager(trust_level=TrustLevel.WRITE)
perms.check("file_write", {"path": "src/main.py"})  # True
perms.check("shell", {"command": "rm -rf /"})        # False (blocked)
perms.is_blocked("shell", {"command": "rm -rf /"})   # Returns reason string
audit = perms.audit_log()  # Full history of all checks
```

Trust levels: `READ` < `WRITE` < `EXECUTE` < `DESTRUCTIVE`. Each tool has a required trust level. Operations below the current level are denied.

### HookEngine (`hooks/engine.py`)

Pre/post middleware for tool execution:

```python
hooks = HookEngine()

# Register a hook
hooks.register(
    event="file_write",
    phase="PRE",
    callback=validate_syntax,
    priority=10
)

# Fire hooks
results = hooks.fire("file_write", "PRE", tool_args)
# PRE hooks can return modified args or raise to block
```

### WatcherEngine (`hooks/engine.py`)

Background file monitoring:

```python
watcher = WatcherEngine()
watcher.watch("*.py", callback=on_python_change)
watcher.watch("tests/", callback=on_test_change)
status = watcher.status()
```

## AgentLoop — Autonomous Mode

`src/nexus/agent/loop.py` implements the classic agent cycle:

```
Plan → Act → Observe → Reflect → (repeat or stop)
```

1. **Planner** (`planner.py`) — sends goal + context to the reasoning model, gets a structured plan
2. **Executor** (`executor.py`) — dispatches tool calls from the plan, captures results
3. **Reflector** (`reflector.py`) — evaluates quality, decides to continue/retry/stop
4. **Context Manager** (`context.py`) — manages the rolling context window

Circuit breaker: 3 consecutive failures → automatic stop.

## Tool System

All tools inherit from `BaseTool` and register with `ToolRegistry`:

```python
class BaseTool(ABC):
    name: str
    description: str
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        ...
```

Tools are defined in `src/nexus/tools/`:

| File | Tool | Key Details |
|------|------|-------------|
| `shell.py` | `shell` | Blocked command list, timeout, working directory |
| `file_ops.py` | `file_read`, `file_write`, `file_list` | Auto-creates directories, path validation |
| `code_runner.py` | `code_run` | Temp file execution, Python/Node/Bash |
| `test_runner.py` | `test_run` | pytest/npm, result parsing, exit code handling |
| `search.py` | `search` | ripgrep preferred, grep fallback |
| `git.py` | `git` | Allowlisted commands only |

## Memory System

```
src/nexus/memory/
├── short_term.py     # Deque-based rolling window (current session)
├── long_term.py      # ChromaDB vector store or JSON fallback
└── context_store.py  # Role/category indexed retrieval
```

- **Short-term**: Bounded deque of recent messages and tool results
- **Long-term**: At session start, recalls relevant past sessions. At session end, stores a summary.
- **Context Store**: Indexed by role (user/assistant/tool) and category for targeted retrieval

## Security

```
src/nexus/security/
├── sanitizer.py      # Input validation, prompt injection detection
└── rate_limit.py     # Token bucket rate limiting
```

Plus `src/nexus/sandbox/sandbox.py` for isolated code execution.

## Editor Protocol

`src/nexus/editor/protocol.py` implements JSON-RPC 2.0 for editor integration:

- VS Code, Cursor, Neovim can connect via the protocol
- Exposes ChatSession capabilities over a standardized interface
- Methods: `initialize`, `chat/send`, `chat/branch`, `diff/preview`, `diff/accept`, etc.

## MCP Server

`src/nexus/mcp/server.py` implements the Model Context Protocol for external tool integration.

## Configuration

`src/nexus/config/settings.py` uses Pydantic Settings:

```python
class NexusSettings(BaseSettings):
    ollama_url: str = "http://localhost:11434"
    default_model: str = "qwen2.5-coder:14b"
    workspace_root: str = "./workspace"
    # ... more settings
    
    class Config:
        env_prefix = "NEXUS_"
        env_file = ".env"
```

## Test Structure

```
tests/
├── unit/
│   ├── test_agent/              # AgentLoop, planner, executor, reflector
│   ├── test_intelligence/       # ModelRouter, ProjectMap, StanceManager, SessionStore
│   ├── test_diff/               # DiffEngine, DiffRenderer
│   ├── test_safety/             # PermissionManager
│   ├── test_hooks/              # HookEngine, WatcherEngine
│   ├── test_editor/             # Editor protocol
│   ├── test_chat_integration.py # ChatSession + all modules (75 tests)
│   ├── test_tui_commands.py     # TUI slash commands (50 tests)
│   ├── test_security/           # Sanitizer, edge cases
│   └── test_utils/              # Caching, logging, retry
└── integration/
    └── test_subprocess.py       # Shell execution integration tests
```

Run with: `pytest tests/ -v --timeout=30`

## Key Design Decisions

1. **Generator-based events** — `send()` yields events instead of returning a final response. This enables streaming, progressive rendering, and real-time TUI updates.

2. **Unknown tools bypass permissions** — If a tool name isn't in the registry, it skips the permission check and falls through to a clean "unknown tool" error. This prevents the permission layer from masking tool-not-found errors.

3. **Branch-aware prompts** — When multiple conversation branches exist, the system prompt includes the current branch name so the LLM knows which context it's operating in.

4. **Local-first, always** — No cloud API calls. Everything runs through Ollama on localhost. The user's code never leaves their machine.

5. **Diff-before-write** — Every file write generates a diff preview. The DiffEngine intercepts `file_write` tool calls and shows the change before applying it. This is the core of the "build with you, not for you" philosophy.
