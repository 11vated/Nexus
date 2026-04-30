# Nexus

**Your code, your models, your machine. A coding partner that thinks with you — not for you.**

```
nexus chat
```

Nexus is a local-first AI coding system that runs entirely on your hardware using Ollama. No API keys. No cloud. No subscriptions. Just open-source LLMs and a conversation.

But Nexus isn't a chatbot with file access bolted on. It's built around the idea that writing software is a *dialogue* — between you, the code, and an intelligence that understands both.

---

## What Makes Nexus Different

Most AI coding tools fall into one of two traps: autocomplete (smart but passive) or autonomous agents (powerful but opaque). Nexus occupies the space between them.

### 🧠 Multi-Model Intelligence

You see one conversation. Under the hood, Nexus routes different parts of your interaction to different specialized models — automatically.

```
You: "Let's refactor the auth module to use JWT tokens"

  ┌─ Architecture questions → reasoning model (deepseek-r1)
  ├─ Code generation       → coding model (qwen2.5-coder:14b)
  ├─ Quick fixes           → fast model (qwen2.5-coder:7b)
  └─ Review & testing      → review model (tuned temperature)
```

The `ModelRouter` analyzes each message, detects intent across 10 categories, and picks the optimal model. You never think about which model to use.

### 🎭 Adaptive Stances

Nexus shifts how it thinks based on context — not just what model it uses, but its entire personality and approach:

| Stance | When It Activates | How It Behaves |
|--------|-------------------|----------------|
| **Architect** | "How should we structure this?" | Big-picture thinking, asks probing questions, draws boundaries |
| **Pair Programmer** | "Let's build the API routes" | Writes code alongside you, explains choices, stays in flow |
| **Debugger** | "This test is failing" | Systematic hypothesis-testing, reads stack traces carefully |
| **Reviewer** | "Check this PR" | Critical eye, finds edge cases, suggests improvements |
| **Teacher** | "How does async/await work?" | Patient explanations, walks through concepts step by step |
| **Explorer** | "What libraries exist for this?" | Research mode, compares options, summarizes tradeoffs |

Stances switch automatically based on what you're discussing, or you can force one with `/stance debugger`.

### 🌿 Conversation Branching

Like `git`, but for your conversation:

```
main ─── "Build the API" ─── "Add auth" ─── "Deploy" ───▶
              │
              └── experiment/redis ─── "Try Redis cache" ─── "Benchmark" ───▶
              │
              └── experiment/sqlite ─── "Try SQLite" ─── "Compare" ───▶
```

Fork a conversation to explore approach A and approach B simultaneously. Compare results. Merge the winner. Your conversation history becomes a decision tree, not a linear chat log.

```
/branch experiment/redis    # Fork the conversation
/switch main                # Jump back to the main thread
/compare experiment/redis   # Side-by-side comparison
/merge experiment/redis     # Pull the good ideas back
/tree                       # Visualize the full branch structure
```

### 📋 Live Diff Preview

Every file write generates an inline diff *before* anything touches disk:

```
━━ Diff Preview: src/api/auth.py ━━━━━━━━━━━━━━━━━━━━━
  from fastapi import APIRouter
+ from jose import jwt
+ from datetime import timedelta
  
  router = APIRouter()
  
- @router.post("/login")
- def login(user: str, password: str):
-     return {"token": "fake"}
+ @router.post("/login", response_model=TokenResponse)
+ async def login(credentials: LoginRequest):
+     user = await authenticate(credentials)
+     token = jwt.encode({"sub": user.id}, SECRET, algorithm="HS256")
+     return TokenResponse(access_token=token)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/accept   Apply this change
/reject   Discard it
/undo     Revert the last accepted change
```

You see exactly what's changing. Accept, reject, or undo at the hunk level. Nothing happens without your say-so.

### 🔒 Safety & Trust Levels

Nexus operates within a permission system with four escalating trust levels:

```
READ        → Can read files, search code, inspect structure
WRITE       → Can create and modify files (with diff preview)
EXECUTE     → Can run tests, shell commands, code
DESTRUCTIVE → Can delete files, force-push, modify system config
```

Every tool call is logged to an audit trail. Dangerous operations require explicit escalation. You control how much autonomy the AI has.

```
/trust          # See current trust level
/trust write    # Escalate to WRITE
/audit          # View the full audit log
```

### 🪝 Hooks & Watchers

Extensible middleware around every tool call:

```python
# Auto-lint after every file write
PRE  file_write → validate syntax
POST file_write → run linter, report issues

# Block dangerous patterns
PRE  shell → reject if command contains 'rm -rf /'
```

Background file watchers monitor your project and surface changes:

```
/hooks              # List active hooks
/watch *.py         # Watch Python files for changes
/watch tests/       # Monitor test directory
```

### 🗺️ Project Intelligence

Before you even ask, Nexus understands your codebase:

- **Dependency graph** — what imports what, which modules are tightly coupled
- **Hot files** — most-changed, most-imported, highest complexity
- **Architecture detection** — FastAPI app? Django? CLI tool? Monorepo?
- **Test coverage map** — what's tested, what's not, where the gaps are
- **Concept→file mapping** — when you say "the auth module," Nexus already knows which files

```
/project            # Show project intelligence summary
/project auth       # What files relate to "auth"?
```

### 💾 Session Continuity

Save conversations. Resume them later. Nexus remembers what you were building, decisions you made, and your preferred patterns.

```
/save               # Save current session
/load               # Browse and restore sessions
/sessions           # List all saved sessions
```

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/11vated/Nexus.git
cd Nexus
pip install -e ".[dev]"
```

### 2. Start Ollama

```bash
ollama serve
ollama pull qwen2.5-coder:14b
ollama pull deepseek-r1:7b
ollama pull qwen2.5-coder:7b
```

### 3. Chat

```bash
# Collaborative chat mode (the main experience)
nexus chat

# Or launch the full TUI dashboard
nexus tui
```

### 4. (Optional) Autonomous mode

```bash
# Fire-and-forget: give a goal, let Nexus handle it
nexus run "Build a Flask API with /health endpoint and tests"
```

---

## Two Modes, One System

| | Chat Mode | Agent Mode |
|---|---|---|
| **Command** | `nexus chat` | `nexus run "goal"` |
| **Interaction** | Conversational — you and Nexus build together | Autonomous — Nexus plans and executes alone |
| **Control** | You approve every file change via diff preview | Nexus runs until done or hits max iterations |
| **Best for** | Feature development, architecture, debugging, learning | Batch tasks, boilerplate, test generation |
| **Intelligence** | Full (routing, stances, branching, hooks) | Core (planning, execution, reflection) |

Both modes share the same tools, memory, and project understanding. Chat mode is the primary experience — agent mode is for when you know exactly what you want and don't need to steer.

---

## Commands

### CLI

| Command | Description |
|---------|-------------|
| `nexus chat` | Start a collaborative chat session |
| `nexus tui` | Launch the interactive TUI dashboard |
| `nexus run "goal"` | Run the autonomous agent on a goal |
| `nexus quickstart` | Check Ollama, models, and workspace setup |
| `nexus agent tools` | List all registered tools |
| `nexus agent config` | Show agent configuration |
| `nexus agent check` | Pre-flight: verify Ollama is reachable |
| `nexus bench "issue"` | Run SWE-bench style issue resolution |
| `nexus models` | List available Ollama models |
| `nexus pull <model>` | Pull an Ollama model |

### Slash Commands (in chat)

```
Conversation        /help  /clear  /history  /quit
Intelligence        /stance [name]  /project [query]  /route  /model
Diffs               /diff  /accept  /reject  /undo
Branching           /branch [name]  /branches  /switch [name]  /compare  /merge  /tree
Safety              /trust [level]  /audit
Hooks & Watchers    /hooks  /watch [pattern]
Sessions            /save  /load  /sessions
```

### CLI Flags

```
--workspace, -w    Target project directory (default: .)
--model, -m        Override planning model
--coding-model, -c Override coding model
--max-iterations   Loop iteration limit (default: 25)
--no-reflect       Disable reflection step
--verbose, -v      Show full tool output
--json-output      Machine-readable JSON result
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI / TUI                               │
│              nexus chat  │  nexus tui  │  nexus run              │
└────────────────┬─────────┴─────────────┴─────────┬──────────────┘
                 │                                  │
    ┌────────────▼────────────┐        ┌───────────▼────────────┐
    │      ChatSession        │        │      AgentLoop          │
    │  (collaborative mode)   │        │  (autonomous mode)      │
    │                         │        │  Plan→Act→Observe→      │
    │  Intelligence Layer:    │        │  Reflect                │
    │  ├─ ModelRouter         │        └───────────┬────────────┘
    │  ├─ StanceManager       │                    │
    │  ├─ ProjectMap          │                    │
    │  └─ SessionStore        │                    │
    │                         │                    │
    │  Interactive Layer:     │                    │
    │  ├─ DiffEngine          │                    │
    │  ├─ ConversationTree    │                    │
    │  ├─ PermissionManager   │                    │
    │  ├─ HookEngine          │                    │
    │  └─ WatcherEngine       │                    │
    └────────────┬────────────┘                    │
                 │                                  │
    ┌────────────▼──────────────────────────────────▼─────────────┐
    │                    Tool Registry                             │
    │   shell · file_read · file_write · file_list                │
    │   code_run · test_run · search · git                        │
    └────────────────────────┬────────────────────────────────────┘
                             │
    ┌────────────────────────▼────────────────────────────────────┐
    │                    Ollama (Local LLMs)                       │
    │   deepseek-r1:7b  ·  qwen2.5-coder:14b  ·  qwen2.5:7b     │
    └─────────────────────────────────────────────────────────────┘
                             │
    ┌────────────────────────▼────────────────────────────────────┐
    │                      Memory                                  │
    │          Short-term (session)  │  Long-term (persistent)     │
    └─────────────────────────────────────────────────────────────┘
```

### Tools

| Tool | Description |
|------|-------------|
| `shell` | Run shell commands (dangerous commands blocked) |
| `file_read` | Read file contents |
| `file_write` | Write/create files (auto-creates directories, generates diff) |
| `file_list` | List directory contents |
| `code_run` | Execute Python/Node/Bash code in temp files |
| `test_run` | Run pytest/npm test with result parsing |
| `search` | Search codebase (ripgrep preferred, grep fallback) |
| `git` | Git operations (allowlisted safe commands) |

### Memory

- **Short-term**: Rolling window of conversation within the current session
- **Long-term**: Persistent storage across sessions (ChromaDB when available, JSON fallback)
- **Context Store**: Role/category indexed retrieval for tool-specific knowledge
- Sessions auto-save on quit and can be resumed later

---

## Configuration

Nexus reads from environment variables and `.env`:

```bash
# .env
NEXUS_OLLAMA_URL=http://localhost:11434
NEXUS_DEFAULT_MODEL=qwen2.5-coder:14b
NEXUS_WORKSPACE_ROOT=./workspace
```

| Setting | Default | Description |
|---------|---------|-------------|
| `planning_model` | `deepseek-r1:7b` | Model for planning and reasoning |
| `coding_model` | `qwen2.5-coder:14b` | Model for code generation |
| `fast_model` | `qwen2.5-coder:7b` | Model for quick edits and refactors |
| `max_iterations` | `25` | Maximum agent loop iterations |
| `quality_threshold` | `0.7` | Minimum quality score (0-1) |
| `reflection_enabled` | `true` | Enable/disable reflection step |
| `memory_enabled` | `true` | Enable/disable long-term memory |

---

## Docker

```bash
# Build
docker build -t nexus .

# Chat mode (with Ollama on host)
docker run -it --network host nexus chat

# Agent mode with workspace mount
docker run -it --network host -v $(pwd)/my-project:/workspace nexus run "Fix the tests" -w /workspace
```

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=nexus --cov-report=html

# Specific module
pytest tests/unit/test_agent/
pytest tests/unit/test_intelligence/
pytest tests/unit/test_chat_integration.py
```

630 tests covering: agent core, tools, memory, security, intelligence (routing, stances, project map, sessions), interactive features (diffs, branching, permissions, hooks, watchers), chat integration, and TUI commands.

---

## Project Structure

```
src/nexus/
├── agent/                # Core agent system
│   ├── chat.py           # ChatSession — collaborative mode (1,450 lines)
│   ├── loop.py           # AgentLoop — autonomous Plan→Act→Observe→Reflect
│   ├── planner.py        # LLM-based planning
│   ├── executor.py       # Tool dispatch with fuzzy matching
│   ├── reflector.py      # Quality assessment and self-correction
│   ├── context.py        # Context window management
│   ├── llm.py            # Ollama async client
│   └── models.py         # Agent dataclasses (State, Task, Step, Config)
├── intelligence/         # Intelligence layer
│   ├── model_router.py   # Intent detection → model routing (10 categories)
│   ├── stances.py        # 7 adaptive behavior modes
│   ├── project_map.py    # AST-based codebase analysis
│   ├── session_store.py  # Save/load/search conversations
│   └── branching.py      # Git-like conversation branching
├── diff/                 # Live diff system
│   ├── engine.py         # DiffEngine — generates and manages diffs
│   └── renderer.py       # DiffRenderer — terminal-friendly diff display
├── safety/               # Permission and trust system
│   └── permissions.py    # 4-level trust, audit trail, blocklist
├── hooks/                # Extensible middleware
│   └── engine.py         # HookEngine + WatcherEngine
├── editor/               # Editor integration
│   └── protocol.py       # JSON-RPC 2.0 for VS Code/Cursor/Neovim
├── tools/                # Tool implementations
│   ├── registry.py       # BaseTool ABC + ToolRegistry
│   ├── shell.py          # Shell command execution
│   ├── file_ops.py       # File read/write/list
│   ├── code_runner.py    # Code execution (Python/Node/Bash)
│   ├── test_runner.py    # Test runner (pytest/npm)
│   ├── search.py         # Codebase search (rg/grep)
│   └── git.py            # Git operations
├── memory/               # Memory systems
│   ├── short_term.py     # Session-scoped rolling window
│   ├── long_term.py      # Persistent ChromaDB/JSON store
│   └── context_store.py  # Role/category indexed retrieval
├── tui/                  # Terminal UI
│   ├── chat_ui.py        # Three-pane chat TUI (856 lines)
│   └── dashboard.py      # Full-screen agent dashboard
├── security/             # Input sanitization, rate limiting
├── gateway/              # Ollama gateway with middleware
├── mcp/                  # Model Context Protocol server
├── config/               # Pydantic settings
├── cli.py                # Click CLI entry point
└── __main__.py           # python -m nexus support
```

---

## Roadmap

- [x] Agent core (Plan → Act → Observe → Reflect)
- [x] 8 built-in tools with security boundaries
- [x] Short-term + long-term memory
- [x] CLI with live progress display
- [x] Interactive TUI dashboard
- [x] Collaborative chat mode with streaming
- [x] Multi-model routing (10 intent categories)
- [x] Adaptive stances (7 modes)
- [x] Project intelligence (AST analysis, concept mapping)
- [x] Session save/load/search
- [x] Live diff preview with accept/reject/undo
- [x] Conversation branching (fork/switch/compare/merge)
- [x] Permission system with 4 trust levels + audit trail
- [x] Hook engine (pre/post middleware on tool calls)
- [x] Watcher engine (background file monitoring)
- [x] Editor protocol (JSON-RPC 2.0)
- [x] MCP server
- [x] SWE-bench pipeline
- [ ] VS Code extension
- [ ] Web dashboard
- [ ] Plugin system (.nexus/ configuration)
- [ ] Fine-tuning pipeline integration
- [ ] Multi-agent collaboration

---

## Philosophy

> *"I don't want to send a command for it to build. I want to know what it's doing and planning, for it to plan with me to actually build what I want — fully crafted and fleshed out."*

Nexus exists because we believe the best code comes from collaboration — not delegation. The AI should think *with* you, not *instead* of you. It should explain its reasoning, show you diffs before touching files, let you branch conversations to explore alternatives, and remember what you decided and why.

Cloud tools charge per token and lock you into their models. Nexus runs on your machine, with your models, at your pace. The intelligence is in the system — the routing, the stances, the branching, the project understanding — not in any single model's API.

---

## License

MIT

---

*Built for developers who want a coding partner — not a vending machine.*
