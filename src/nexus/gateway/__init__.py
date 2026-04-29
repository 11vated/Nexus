"""Nexus Gateway — LLM proxy, RAG middleware, and tool emulation."""

# Lazy imports to avoid hard dependency on chromadb
try:
    from .rag_middleware import (
        RAGMiddleware,
        DynamicRAG,
        RetrievedContext,
        get_rag_middleware,
    )
except ImportError:
    RAGMiddleware = None  # type: ignore[assignment,misc]
    DynamicRAG = None  # type: ignore[assignment,misc]
    RetrievedContext = None  # type: ignore[assignment,misc]
    get_rag_middleware = None  # type: ignore[assignment,misc]

from .client import GatewayClient
from .tool_emulator import ToolEmulator

__all__ = [
    "GatewayClient",
    "ToolEmulator",
    "RAGMiddleware",
    "DynamicRAG",
    "RetrievedContext",
    "get_rag_middleware",
]
