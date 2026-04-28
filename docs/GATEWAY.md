# Nexus Unified Model Gateway

## Overview

The Nexus gateway acts as a unified API layer that normalizes access to all models (Ollama, GGUF via llama.cpp, cloud APIs like OpenAI/Anthropic). All agent tools connect to this gateway instead of directly to model APIs.

## Quick Start

### 1. Install LiteLLM

```bash
bash scripts/setup_gateway.sh
```

### 2. Start Gateway

```bash
litellm --config gateway_config.yaml --port 4000
```

### 3. Configure Tools

See the setup script output for configuring OpenCode, Aider, Goose, and CLI.

## Features

### Unified Model API

- One OpenAI-compatible endpoint: `http://localhost:4000/v1/chat/completions`
- Automatic fallback between models
- Support for Ollama, GGUF, OpenAI, Anthropic

### RAG Context Injection

The gateway automatically injects relevant code context:

```python
from nexus.gateway import get_rag_middleware

rag = get_rag_middleware()
context = rag.get_context_for_task("Fix the login bug in auth.py")
```

### Tool Use Emulation

Models without native tool calling can use XML-like tags:

```
<execute>pytest tests/</execute>
<read_file>src/main.py</read_file>
<write_file path="src/main.py">def main(): pass</write_file>
```

### Multi-Patch Verification

For SWE-bench tasks, generate 8 candidates and select the best:

```python
from nexus.core.patch_verification import MultiPatchGenerator, BestPatchSelector

generator = MultiPatchGenerator(model_callback=call_model)
patches = await generator.generate_patches(issue_desc)

selector = BestPatchSelector()
best = await selector.select_with_fallback(patches)
```

## Configuration

Edit `gateway_config.yaml` to:

- Add/remove models
- Configure fallbacks
- Set up model groups by task type

## Supported Models

| Model | Source | Use Case |
|-------|-------|----------|
| qwen2.5-coder:14b | Ollama | Coding |
| deepseek-r1:7b | Ollama | Reasoning |
| llama3.2:latest | Ollama | General |
| GGUF via llama.cpp | Local file | Custom models |
| gpt-4o | OpenAI (optional) | Cloud backup |

## API Reference

### Chat Completions

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer dummy" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:14b",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Health Check

```bash
curl http://localhost:4000/health
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Nexus Gateway                             │
├─────────────────────────────────────────────────────────────┤
│  OpenAI-Compatible API (port 4000)                          │
├──────────────┬──────────────┬─────────────────┬─────────────┤
│  Ollama    │  llama.cpp  │  OpenAI      │  Anthropic  │
│  (local)   │  (GGUF)     │  (cloud)     │  (cloud)    │
├──────────────┴──────────────┴─────────────────┴─────────────┤
│                                                              │
│  ┌──────────────────────────────────────���───────────┐         │
│  │ Middleware: RAG, Tool Emulation, Verifier       │         │
│  └──────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### Gateway won't start

Check port 4000 isn't in use:
```bash
lsof -i :4000
```

### Model not found

Verify the model is in `gateway_config.yaml` and running:

```bash
ollama list  # for Ollama models
```

### Connection refused

Ensure gateway is running and check firewall:

```bash
curl http://localhost:4000/health
```