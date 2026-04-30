# CLAUDE.md - Agent Context

This file contains project-specific instructions for the autonomous agent system.

## Project Overview
- **Project**: Local Autonomous Developer Agent
- **Goal**: Build a coding agent that rivals Claude Code using local Ollama models
- **Models**: qwen2.5-coder:14b, mistral, deepseek-r1:7b

## Architecture

### Core Components
- `core/brain.py` - Main REACT loop
- `core/mini_swe_agent.py` - Tool-calling agent (74% SWE-bench pattern)
- `core/multi_agent.py` - 4-agent orchestrator
- `tools/` - Tool implementations

### Agent Modes
```bash
python run.py basic task           # Basic REACT
python run_agent.py mini-swe task  # Tool-calling pattern
python run_agent.py multi task   # Multi-agent
```

## Build/Test Commands
- `python run.py "<task>"` - Run basic agent
- `pytest` - Run tests
- `python -c "code"` - Run inline Python

## Code Style
- Python: PEP 8, type hints where helpful
- Use f-strings for string formatting
- Async/Await for concurrent operations

## Important Patterns

### Tool Calling Format
Always use structured tool calls:
```python
{"name": "read", "arguments": {"path": "file.py"}}
{"name": "bash", "arguments": {"command": "pytest"}}
{"name": "str_replace_editor", "arguments": {"path": "f", "old_str": "x", "new_str": "y"}}
```

### Multi-Agent Flow
1. Manager breaks task into subtasks
2. Planner creates execution plan
3. Programmer implements
4. Reviewer verifies

## Git Conventions
- Branch: `feature/description` or `fix/issue-description`
- Commits: `feat: add X` or `fix: resolve Y`
- Messages should explain *why*, not just *what*

## Environment
- Workspace: `workspace/`
- Models: Ollama locally served
- No external API calls (local only)

## Tips for Better Results
- Use qwen2.5-coder:14b for code tasks
- Enable thinking for complex tasks
- Check memory.json for past sessions