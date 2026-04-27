# AGENTS.md - Universal AI Agent Instructions

This file provides project instructions for ANY AI coding tool (Claude Code, Cursor, Codex, OpenAI, local agents, etc.)

## Project Overview
- **Name**: Local Autonomous Developer Agent
- **Purpose**: Build a coding agent using local Ollama models that rivals frontier systems
- **Language**: Python primarily

## Architecture

### Core Files
- `core/brain.py` - Main agent loop
- `core/mini_swe_agent.py` - Tool-calling agent (74% SWE-bench)
- `core/multi_agent.py` - 4-agent orchestration
- `tools/` - Tool implementations

### Running Agents
```bash
# Basic mode
python run.py "task description"

# Mini-SWE mode (tool calling)
python run_agent.py mini-swe "task"

# Multi-agent mode  
python run_agent.py multi "task"

# Advanced mode (all features)
python run_advanced.py --tdd "task"
```

## Build Commands
- Run agent: `python run.py "<task>"`
- Run tests: `pytest`
- Lint: `ruff check .`

## Code Style
- Python: PEP 8
- Use type hints
- Async for concurrent ops
- F-strings for formatting

## Git Conventions
- Branch: `feature/name` or `fix/name`
- Commit: `feat:`, `fix:`, `docs:`, `refactor:`

## Important Patterns

### Tool Format (for tool-calling)
```json
{"name": "read", "arguments": {"path": "file.py"}}
{"name": "bash", "arguments": {"command": "ls"}}
{"name": "str_replace_editor", "arguments": {"path": "f", "old_str": "x", "new_str": "y"}}
```

## Tools Available
- `read` - Read files
- `write` - Write files
- `bash` - Run commands
- `str_replace_editor` - Edit code
- `grep` - Search code
- `glob` - Find files
- `lsp_run_tests` - Run tests