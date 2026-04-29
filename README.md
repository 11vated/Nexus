# 🧠 Nexus — Autonomous AI Coding Agent

Nexus is a local-first autonomous coding agent that plans, writes, tests, and debugs code using Ollama models. No cloud APIs, no subscriptions — just your machine and open-source LLMs.

```
nexus run "Build a Flask API with /health endpoint and tests"
```

Nexus will plan the approach, write the code, run the tests, and fix any failures — autonomously.

## ✨ Features

- **Plan → Act → Observe → Reflect** — structured agent loop with self-correction
- **Local LLMs via Ollama** — works with Qwen2.5-Coder, DeepSeek-R1, or any Ollama model
- **8 built-in tools** — shell, file I/O, code runner, test runner, search, git
- **Memory** — short-term (within session) + long-term (across sessions via ChromaDB or JSON)
- **TUI Dashboard** — full-screen Rich terminal UI showing live agent state
- **SWE-bench ready** — multi-patch generation and verification pipeline
- **Zero cost** — runs entirely on your hardware

## 🚀 Quick Start

### 1. Install

```bash
# Clone
git clone https://github.com/11vated/Nexus.git
cd Nexus

# Install (editable)
pip install -e ".[dev]"

# Or with all extras (ChromaDB, etc.)
pip install -e ".[all]"
```

### 2. Start Ollama

```bash
ollama serve
ollama pull qwen2.5-coder:14b
ollama pull deepseek-r1:7b
```

### 3. Run

```bash
# One-shot goal
nexus run "Create a Python CLI that converts CSV to JSON"

# Interactive TUI
nexus tui

# First-time setup check
nexus quickstart
```

## 📖 Commands

| Command | Description |
|---------|-------------|
| `nexus run "goal"` | Run the agent on a goal (with live progress) |
| `nexus tui` | Launch the interactive TUI dashboard |
| `nexus quickstart` | Check Ollama, models, and workspace setup |
| `nexus agent tools` | List all registered tools |
| `nexus agent config` | Show agent configuration |
| `nexus agent check` | Pre-flight: verify Ollama is reachable |
| `nexus bench "issue"` | Run SWE-bench style issue resolution |
| `nexus models` | List available Ollama models |
| `nexus pull <model>` | Pull an Ollama model |

### Flags

```
--workspace, -w    Target project directory (default: .)
--model, -m        Override planning model
--coding-model, -c Override coding model
--max-iterations   Loop iteration limit (default: 25)
--no-reflect       Disable reflection step
--verbose, -v      Show full tool output
--json-output      Machine-readable JSON result
```

## 🏗️ Architecture

```
                    ┌──────────────────────────────┐
                    │         CLI / TUI             │
                    │   nexus run | nexus tui       │
                    └──────────┬───────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │       Agent Loop              │
                    │  Plan → Act → Observe → Reflect│
                    └──┬──────┬──────┬──────┬──────┘
                       │      │      │      │
              ┌────────▼┐ ┌──▼────┐ ┌▼─────┐ ┌▼────────┐
              │ Planner  │ │Execut.│ │Reflec│ │ Context  │
              │ (LLM)   │ │(Tools)│ │(LLM) │ │ Manager  │
              └────┬─────┘ └──┬───┘ └──────┘ └──────────┘
                   │          │
         ┌─────────▼──┐  ┌───▼──────────────────────┐
         │   Ollama    │  │      Tool Registry        │
         │  LLM Client │  │  shell · files · search   │
         │             │  │  code_run · test · git     │
         └─────────────┘  └──────────────────────────┘
                               │
                    ┌──────────▼───────────────────┐
                    │         Memory                │
                    │  Short-term  │  Long-term     │
                    │  (session)   │  (ChromaDB/JSON)│
                    └──────────────────────────────┘
```

### Agent Loop

1. **Plan** — LLM creates a step-by-step execution plan from the goal
2. **Act** — Executor dispatches the next tool call (shell, file write, etc.)
3. **Observe** — Results are captured and added to context
4. **Reflect** — LLM assesses quality, decides to continue/retry/stop

Circuit breaker: 3 consecutive failures → automatic stop.

### Tools

| Tool | Description |
|------|-------------|
| `shell` | Run shell commands (with blocked dangerous commands) |
| `file_read` | Read file contents |
| `file_write` | Write/create files (auto-creates directories) |
| `file_list` | List directory contents |
| `code_run` | Execute Python/Node/Bash code in temp files |
| `test_run` | Run pytest/npm test with result parsing |
| `search` | Search codebase (ripgrep preferred, grep fallback) |
| `git` | Git operations (allowlisted safe commands) |

### Memory

- **Short-term**: Rolling window of goals, steps, and results within the current session
- **Long-term**: Persistent storage across sessions (ChromaDB when available, JSON fallback)
- At session start, Nexus recalls relevant past sessions to inform planning
- After completion, a session summary is stored for future reference

## ⚙️ Configuration

Nexus reads from environment variables and `.env`:

```bash
# .env
NEXUS_OLLAMA_URL=http://localhost:11434
NEXUS_DEFAULT_MODEL=qwen2.5-coder:14b
NEXUS_WORKSPACE_ROOT=./workspace
```

Agent defaults (overridable via CLI flags):

| Setting | Default | Description |
|---------|---------|-------------|
| `planning_model` | `deepseek-r1:7b` | Model for planning and reasoning |
| `coding_model` | `qwen2.5-coder:14b` | Model for code generation |
| `max_iterations` | `25` | Maximum agent loop iterations |
| `quality_threshold` | `0.7` | Minimum quality score (0-1) |
| `reflection_enabled` | `true` | Enable/disable reflection step |
| `memory_enabled` | `true` | Enable/disable long-term memory |

## 🐳 Docker

```bash
# Build
docker build -t nexus .

# Run (with Ollama on host)
docker run -it --network host nexus run "Build a hello world Flask app"

# Or with a workspace mount
docker run -it --network host -v $(pwd)/my-project:/workspace nexus run "Fix the tests" -w /workspace
```

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=nexus --cov-report=html

# Specific module
pytest tests/unit/test_agent/
```

## 📁 Project Structure

```
src/nexus/
├── agent/              # Core agent loop
│   ├── loop.py         # Plan→Act→Observe→Reflect cycle
│   ├── planner.py      # LLM-based planning
│   ├── executor.py     # Tool dispatch with fuzzy matching
│   ├── reflector.py    # Quality assessment and self-correction
│   ├── context.py      # Context window management
│   ├── llm.py          # Ollama async client
│   └── models.py       # Agent dataclasses (State, Task, Step, Config)
├── tools/              # Tool implementations
│   ├── registry.py     # BaseTool ABC + ToolRegistry
│   ├── shell.py        # Shell command execution
│   ├── file_ops.py     # File read/write/list
│   ├── code_runner.py  # Code execution (Python/Node/Bash)
│   ├── test_runner.py  # Test runner (pytest/npm)
│   ├── search.py       # Codebase search (rg/grep)
│   └── git.py          # Git operations
├── memory/             # Memory systems
│   ├── short_term.py   # Session-scoped rolling window
│   ├── long_term.py    # Persistent ChromaDB/JSON store
│   └── context_store.py # Role/category indexed retrieval
├── tui/                # Terminal UI
│   └── dashboard.py    # Full-screen Rich dashboard
├── gateway/            # Ollama gateway with middleware
├── security/           # Input sanitization, sandboxing
├── swe_bench/          # SWE-bench integration
├── config/             # Settings (pydantic-settings)
├── cli.py              # Click CLI entry point
└── __main__.py         # python -m nexus support
```

## 🗺️ Roadmap

- [x] Agent loop (Plan → Act → Observe → Reflect)
- [x] 8 built-in tools with security boundaries
- [x] Short-term + long-term memory
- [x] CLI with live progress display
- [x] Interactive TUI dashboard
- [x] SWE-bench multi-patch pipeline
- [ ] MCP (Model Context Protocol) tool server
- [ ] Multi-agent collaboration
- [ ] Fine-tuning pipeline integration
- [ ] Plugin system for custom tools
- [ ] Web UI

## 📄 License

MIT

---

*Built for developers who want a real coding agent — not a chatbot.*
