# Ultimate Local AI Workstation

A production-grade, free AI coding platform rivaling Claude Code, Cursor, and OpenAI Codex - running entirely locally with Ollama.

## What's Been Built

### Core Infrastructure
- **Unified CLI** (`agent-system/unified_cli.py`) - Single interface for all tools
- **Ultimate Launcher** (`agent-system/WORKSTATION_ULTIMATE.bat`) - Windows menu launcher
- **Profound System** (`agent-system/profound_system.py`) - Multi-agent orchestration
- **Orchestrator** (`agent-system/orchestrator.py`) - Smart model routing (GPT-5 style)

### Tools Integrated
| Tool | Purpose | Status |
|------|---------|--------|
| OpenCode | AI-native IDE | ✅ Configured |
| Aider | Terminal pair programmer | ✅ Configured |
| Goose | Autonomous CLI agent | ✅ Configured |
| Profound | Multi-agent orchestrator | ✅ Custom |
| Ollama | Local LLM runtime | ✅ Running |

### Models Available (14GB RAM)
```
qwen2.5-coder:14b    - Best code generation
qwen2.5-coder:7b     - Fast code tasks
deepseek-r1:7b       - Reasoning/planning
deepseek-r1:1.5b     - Fast reasoning
dolphin-mistral      - Uncensored coding
gemma4:26b           - Large model
codellama            - Meta code model
```

### MCP Servers Configured
- **filesystem** - Full file system access
- **memory** - Persistent context
- **ollama** - Custom code generation
- **github** - Ready to configure

---

## Quick Start

### Option 1: Ultimate Launcher (Recommended)
```bash
agent-system\WORKSTATION_ULTIMATE.bat
```

### Option 2: Unified CLI
```bash
cd agent-system
python unified_cli.py
```

### Option 3: Direct Tools
```bash
# OpenCode
"C:\Users\11vat\AppData\Local\OpenCode\OpenCode.exe"

# Aider
cd agent-system
venv_aider\Scripts\activate
aider --model qwen2.5-coder:14b

# Goose
"C:\Users\11vat\Desktop\Goose-win32-x64\dist-windows\Goose.exe"

# Profound System
python agent-system/profound_system.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    UNIFIED CLI INTERFACE                    │
│              (unified_cli.py / WORKSTATION.bat)             │
└────────────────────┬────────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     ▼               ▼               ▼
┌─────────┐    ┌──────────┐    ┌──────────┐
│OpenCode │    │  Aider   │    │  Goose   │
│  Desktop│    │ Terminal │    │ Desktop  │
└────┬────┘    └────┬─────┘    └────┬─────┘
     │              │               │
     └──────────────┼───────────────┘
                    ▼
         ┌─────────────────────┐
         │   OLLAMA RUNTIME    │
         │  (Local Models)     │
         └─────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌─────────┐   ┌──────────┐   ┌──────────┐
│  Code   │   │ Reasoning│   │Uncensored│
│ Models  │   │  Models  │   │  Models  │
└─────────┘   └──────────┘   └──────────┘
```

---

## Key Features

### 1. Smart Model Routing
The orchestrator automatically selects the best model:
- **Planning/Architecture** → deepseek-r1:7b
- **Code Generation** → qwen2.5-coder:14b
- **Fast Tasks** → qwen2.5-coder:7b
- **Uncensored** → dolphin-mistral

### 2. Multi-Agent Orchestration
- Sprint Agent - Project management
- Architect Agent - System design
- Developer Agent - Code generation
- Reviewer Agent - Code review
- Tester Agent - Validation

### 3. MCP Integration
- Filesystem access
- GitHub integration
- Persistent memory
- Custom tools

### 4. Code Intelligence
- Project analyzer
- Language detection
- Complexity analysis
- AI-powered debugging

---

## Usage Examples

### Generate Code
```
> python unified_cli.py
Select: G
Describe: A React login form with email/password validation
```

### Analyze Project
```
Select: A
Project path: ./my-project
```

### Debug Problem
```
Select: D
Describe: TypeError: Cannot read property 'map' of undefined
```

### Switch Model
```
Select: C (Code Models)
Select: qwen2.5-coder:7b
```

---

## System Requirements

- **RAM**: 14GB+ (16GB recommended)
- **Storage**: 50GB+ for models
- **OS**: Windows 10/11
- **Runtime**: Ollama, Node.js, Python 3.12

---

## Future Enhancements

See `ROADMAP.md` for:
- [ ] WebGPU acceleration
- [ ] CodeRAG with embeddings
- [ ] Advanced MCPs
- [ ] Team collaboration features
- [ ] Cloud deployment option

---

## Documentation

- `AGENTS.md` - Project configuration
- `PROFOUND.md` - Multi-agent architecture
- `MCP_README.md` - MCP server setup
- `ROADMAP.md` - Future features

---

## Credits

Built with:
- [Ollama](https://ollama.ai) - Local LLM runtime
- [OpenCode](https://opencode.ai) - AI-native IDE
- [Aider](https://aider.chat) - Terminal AI pair programmer
- [Goose](https://block.github.io/goose) - Autonomous agent
- [Model Context Protocol](https://modelcontextprotocol.io) - Tool standardization