# WebGPU-Powered Autonomous Agent System

## Overview

This system leverages WebGPU for browser-native AI capabilities:

## Key Technologies

### 1. WebGPU Embeddings
- **Model**: Xenova/all-MiniLM-L6-v2 (384-dim)
- **Performance**: 40-75x faster than CPU/WASM
- **Storage**: IndexedDB with cosine similarity

### 2. LocalMode / Agentary
- WebLLM integration for full LLM inference
- Multi-worker parallelism (each agent = separate worker)
- Falls back to WASM when WebGPU unavailable

### 3. Multi-Agent Architecture
```
Main Thread (Orchestration)
    ├── Agent Worker 1: Sprint Manager (WebGPU)
    ├── Agent Worker 2: Architect (WebGPU)  
    ├── Agent Worker 3: Developer (WebGPU)
    └── Agent Worker 4: Reviewer (WebGPU)
```

## Browser Support

| Browser | WebGPU | WASM Fallback |
|---------|--------|---------------|
| Chrome 113+ | ✅ | ✅ |
| Edge 113+ | ✅ | ✅ |
| Firefox 141+ | ⚠️ Flag | ✅ |
| Safari 26+ | ✅ | ✅ |

## Performance Benchmarks

| Operation | WebGPU | WASM | Speedup |
|-----------|--------|------|---------|
| Embed (384-dim) | ~50ms | ~200ms | 4x |
| Vector Search (10K) | ~20ms | ~100ms | 5x |
| Batch Insert (1K) | ~5ms | ~50ms | 10x |

## Running the WebGPU Interface

```bash
# Start a simple HTTP server
cd agent-system/webgpu
python -m http.server 8080

# Or use Node.js
npx serve .

# Open in browser
# http://localhost:8080
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    BROWSER (Client)                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   UI Layer  │  │  IndexedDB  │  │   Web Workers       │ │
│  │  (React/JS) │  │  (Memory)   │  │ (Parallel Agents)   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                           │                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              WebGPU / WASM Runtime                     │ │
│  │  • Transformers.js (Embeddings)                       │ │
│  │  • WebLLM (LLM Inference)                             │ │
│  │  • Custom Shaders (Vector Search)                     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   LOCAL SERVER (Ollama)                     │
│  • qwen2.5-coder:14b - Code generation                     │
│  • deepseek-r1:7b - Reasoning                               │
│  • dolphin-mistral - Uncensored                             │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Implemented
- ✅ WebGPU-accelerated embeddings
- ✅ Semantic search with cosine similarity
- ✅ IndexedDB persistence
- ✅ Multi-agent orchestration (Sprint/Architect/Developer/Reviewer)
- ✅ WASM fallback

### Available via Libraries
- 🔄 WebLLM for full browser-based LLM
- 🔄 Agentary for agentic workflows
- 🔄 LocalMode for complete vector DB

## Key Libraries

| Library | Purpose | CDN |
|---------|---------|-----|
| Transformers.js | Embeddings | @huggingface/transformers |
| WebLLM | LLM Inference | mlc-ai/web-llm |
| LocalMode | VectorDB + Agents | @localmode/core |

## Future Enhancements

1. **Full WebLLM Integration** - Run quantized LLMs entirely in browser
2. **Multi-Tab Sync** - Share memory across browser tabs
3. **PWA Support** - Offline-first architecture
4. **Chrome AI Integration** - Gemini Nano fallback

## References

- [Transformers.js WebGPU](https://huggingface.co/docs/transformers.js)
- [WebLLM](https://webllm.mlc.ai/)
- [Agentary](https://www.agentary.ai/)
- [LocalMode](https://github.com/LocalMode-AI/LocalMode)