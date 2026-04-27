# PROFOUND AUTONOMOUS CODING SYSTEM

## Architecture Overview

Based on cutting-edge research from:
- **ALMAS** - Autonomous LLM-based Multi-Agent Software Engineer
- **Codex Subagents GA** - Production-ready multi-agent coordination
- **PARC** - Hierarchical multi-agent with self-assessment
- **DepthNet** - Cyclic thinking with persistent memory
- **Orchestrator** - Context store for compound intelligence

## System Components

### 1. Hierarchical Agent Roles (ALMAS)

| Agent | Role | Model | Function |
|-------|------|-------|-----------|
| Sprint | Project Manager | deepseek-r1:7b | Goal decomposition |
| Architect | Designer | deepseek-r1:7b | System design |
| Developer | Coder | qwen2.5-coder:14b | Code generation |
| Reviewer | QA | deepseek-r1:7b | Code review |
| Tester | QA | deepseek-r1:7b | Testing/validation |

### 2. Context Store (Orchestrator Innovation)

Persistent knowledge layer enabling "compound intelligence" - each action builds on previous discoveries.

- Explorer agents gather context
- Context stored with importance scores
- Retrieved via semantic matching for future tasks

### 3. Dual Memory System (DepthNet)

- **Episodic**: Conversation history (JSON)
- **Semantic**: Embeddings for retrieval

### 4. Self-Assessment Loop (PARC)

After each task execution:
- Reflector agent evaluates result
- Quality score 0-10
- Decide: continue, retry, or escalate

### 5. MCP Tool Integration

Available tools via MCP servers:
- Filesystem operations
- GitHub API
- Browser automation
- Database queries
- Web search

## Running the System

```bash
# Start Ollama
ollama serve

# Run profound system
python agent-system/profound_system.py

# Commands:
# /goal <task> - Execute autonomous goal
# /context     - Show context store
# /memory      - Show memory
# /model       - Show available models
```

## Advanced Features

### Task Lifecycle
```
PENDING → IN_PROGRESS → VALIDATING → DONE
                              ↓
                         FAILED ← RETRY
```

### Model Selection
- Planning/Reasoning → deepseek-r1:7b
- Code Generation → qwen2.5-coder:14b
- Uncensored → dolphin-mistral
- Fast Tasks → qwen2.5-coder:7b

### MCP Tools
Configured in `~/.config/opencode/opencode.json`:
- filesystem: File operations
- ollama: Code generation
- github: GitHub API (optional)
- puppeteer: Browser automation (optional)

## Research References

1. ALMAS (arXiv) - Agile-aligned multi-agent software engineering
2. Codex Subagents - Production-ready coordination
3. PARC - Self-assessment and feedback
4. DepthNet - Laravel-based autonomous agents
5. Orchestrator - Stanford TerminalBench #13