# Goose Configuration for Local Ollama Agent System
# =================================

This file configures Goose to work with our local agent system.

## Setup Instructions (for Goose Desktop/CLI)

### 1. Configure Ollama in Goose

```bash
# Open Goose
goose configure

# Select: Configure Providers
# Select: Ollama
# Model: qwen2.5-coder:14b
# Host: http://localhost:11434
```

### 2. Environment Variables

```bash
# In your shell environment or .env
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="qwen2.5-coder:14b"
```

### 3. Provider Configuration File

Create `~/.config/goose/profiles.yaml`:

```yaml
providers:
  - name: ollama
    type: openai
    api_base: http://localhost:11434/v1
    api_key: "ollama"  # any string, not validated for local
    model: qwen2.5-coder:14b
    context_length: 8192
```

### 4. Using Our Agent System with Goose

#### Option A: Launch from our system
```bash
cd agent-system
python run_agent.py mini-swe "task"
```

#### Option B: Use Goose's MCP
```bash
# Install MCP servers
npx @modelcontextprotocol/server-filesystem ./workspace
npx @modelcontextprotocol/server-shell
```

#### Option C: Connect via OpenAI-compatible API
Our system exposes an OpenAI-compatible API:
- Host: http://localhost:11434/v1
- Model: qwen2.5-coder:14b

Configure Goose to use this as custom provider.

## Integration Points

### File Access
- Point Goose to `./workspace/` for file operations
- Our tools read/write in this directory

### Tool Calling
- Our mini_swe_agent.py uses tool schemas
- Compatible with Claude's tool calling format

### Skills
- Skills in `.claude/skills/` can be referenced
- AGENTS.md provides universal instructions

## Troubleshooting

### "Model not found"
- Run: `ollama list` to see available models
- Pull needed: `ollama pull qwen2.5-coder:14b`

### "Connection refused"
- Start Ollama: `ollama serve`
- Check port: `curl http://localhost:11434/api/tags`

### "Tool not available"
- Our tools require specific format
- Use mini-swe mode for tool calling