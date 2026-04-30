"""Model routing configuration — explicit model assignments for each task type.

This ensures Nexus never guesses which model to use. Every operation
has a designated model based on capability and performance profile.

Current Ollama models (verified available):
  - qwen2.5-coder:14b    → Best code generation (large, slower)
  - qwen2.5-coder:7b     → Fast code tasks, UI generation, quick edits
  - qwen2.5-coder:1.5b   → Ultra-fast trivial tasks
  - gemma4:e4b           → Medium tasks, documentation, planning drafts
  - gemma4:e2b           → Light reasoning, summaries
  - gemma4:26b           → Heavy reasoning, architecture (largest, slowest)
  - deepseek-r1:7b       → Deep reasoning, complex planning
  - deepseek-r1:1.5b     → Quick reasoning
  - codellama:7b         → Code understanding, review
  - dolphin-mistral:7b   → Creative writing, brainstorming
  - qwen2.5-coder:14b-instruct → Instruction-following code tasks
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ModelProfile:
    """Performance profile for a model."""
    name: str
    purpose: str
    avg_response_time_s: float  # typical time for 500-token response
    timeout_s: int              # safe timeout ceiling
    max_tokens: int
    cost: str = "local"         # all local, but for future cloud routing


# --- Model registry (only models confirmed available) ---
MODEL_REGISTRY: Dict[str, ModelProfile] = {
    "qwen2.5-coder:14b": ModelProfile(
        name="qwen2.5-coder:14b",
        purpose="Best code generation",
        avg_response_time_s=15.0,
        timeout_s=180,
        max_tokens=8192,
    ),
    "qwen2.5-coder:7b": ModelProfile(
        name="qwen2.5-coder:7b",
        purpose="Fast code tasks, UI, quick edits",
        avg_response_time_s=6.0,
        timeout_s=120,
        max_tokens=4096,
    ),
    "qwen2.5-coder:1.5b": ModelProfile(
        name="qwen2.5-coder:1.5b",
        purpose="Ultra-fast trivial tasks",
        avg_response_time_s=2.0,
        timeout_s=30,
        max_tokens=2048,
    ),
    "gemma4:e4b": ModelProfile(
        name="gemma4:e4b",
        purpose="Medium tasks, docs, planning drafts",
        avg_response_time_s=8.0,
        timeout_s=120,
        max_tokens=4096,
    ),
    "gemma4:e2b": ModelProfile(
        name="gemma4:e2b",
        purpose="Light reasoning, summaries",
        avg_response_time_s=4.0,
        timeout_s=60,
        max_tokens=4096,
    ),
    "gemma4:26b": ModelProfile(
        name="gemma4:26b",
        purpose="Heavy reasoning, architecture",
        avg_response_time_s=30.0,
        timeout_s=300,
        max_tokens=8192,
    ),
    "deepseek-r1:7b": ModelProfile(
        name="deepseek-r1:7b",
        purpose="Deep reasoning, complex planning",
        avg_response_time_s=20.0,
        timeout_s=240,
        max_tokens=4096,
    ),
    "deepseek-r1:1.5b": ModelProfile(
        name="deepseek-r1:1.5b",
        purpose="Quick reasoning",
        avg_response_time_s=5.0,
        timeout_s=60,
        max_tokens=2048,
    ),
    "codellama:7b": ModelProfile(
        name="codellama:7b",
        purpose="Code understanding, review",
        avg_response_time_s=8.0,
        timeout_s=120,
        max_tokens=4096,
    ),
    "dolphin-mistral:7b": ModelProfile(
        name="dolphin-mistral:7b",
        purpose="Creative writing, brainstorming",
        avg_response_time_s=7.0,
        timeout_s=120,
        max_tokens=4096,
    ),
}


# --- Task-to-model routing map ---
# Every task type has a primary and fallback model.
# If primary times out, automatically fall back.
TASK_ROUTES: Dict[str, Dict[str, Optional[str]]] = {
    # Code generation tasks
    "code_generation": {
        "primary": "qwen2.5-coder:14b",
        "fallback": "qwen2.5-coder:7b",
        "ultra_fast": "qwen2.5-coder:1.5b",
    },
    "code_review": {
        "primary": "codellama:7b",
        "fallback": "qwen2.5-coder:7b",
        "ultra_fast": "qwen2.5-coder:1.5b",
    },
    "code_edit": {
        "primary": "qwen2.5-coder:7b",
        "fallback": "qwen2.5-coder:1.5b",
    },
    # Planning and reasoning
    "planning": {
        "primary": "deepseek-r1:7b",
        "fallback": "gemma4:e4b",
    },
    "reasoning": {
        "primary": "deepseek-r1:7b",
        "fallback": "gemma4:e4b",
    },
    "architecture": {
        "primary": "gemma4:26b",
        "fallback": "deepseek-r1:7b",
    },
    # UI/UX generation
    "ui_generation": {
        "primary": "qwen2.5-coder:7b",
        "fallback": "gemma4:e4b",
    },
    "css_styling": {
        "primary": "qwen2.5-coder:7b",
        "fallback": "qwen2.5-coder:1.5b",
    },
    # Documentation
    "documentation": {
        "primary": "gemma4:e4b",
        "fallback": "gemma4:e2b",
    },
    "readme": {
        "primary": "gemma4:e4b",
        "fallback": "dolphin-mistral:7b",
    },
    # Testing
    "test_generation": {
        "primary": "qwen2.5-coder:7b",
        "fallback": "qwen2.5-coder:1.5b",
    },
    # Creative/brainstorming
    "brainstorm": {
        "primary": "dolphin-mistral:7b",
        "fallback": "gemma4:e4b",
    },
    "research": {
        "primary": "gemma4:e4b",
        "fallback": "deepseek-r1:1.5b",
    },
    # System/ops
    "shell_command": {
        "primary": "qwen2.5-coder:1.5b",
        "fallback": None,  # No LLM needed, just execute
    },
    "summarize": {
        "primary": "gemma4:e2b",
        "fallback": "qwen2.5-coder:1.5b",
    },
    # Chat/conversation
    "chat": {
        "primary": "qwen2.5-coder:7b",
        "fallback": "gemma4:e4b",
    },
}


def get_model_for_task(task_type: str, quality: str = "normal") -> str:
    """Get the best model for a given task type.

    Args:
        task_type: One of the keys in TASK_ROUTES.
        quality: "ultra_fast", "normal", or "best".

    Returns:
        Model name string.

    Raises:
        ValueError: If task_type is unknown.
    """
    route = TASK_ROUTES.get(task_type)
    if route is None:
        raise ValueError(
            f"Unknown task type: {task_type}. "
            f"Available: {list(TASK_ROUTES.keys())}"
        )

    if quality == "ultra_fast" and "ultra_fast" in route:
        return route["ultra_fast"] or route["primary"]
    elif quality == "best":
        return route["primary"]
    else:
        return route["primary"]


def get_fallback_model(task_type: str) -> Optional[str]:
    """Get the fallback model if primary fails."""
    route = TASK_ROUTES.get(task_type)
    if route is None:
        return None
    return route.get("fallback")


def get_timeout_for_model(model: str) -> int:
    """Get the safe timeout for a model."""
    profile = MODEL_REGISTRY.get(model)
    if profile is None:
        return 120  # default
    return profile.timeout_s


def list_available_models() -> list[str]:
    """List all registered models."""
    return list(MODEL_REGISTRY.keys())


def print_model_summary() -> str:
    """Print a human-readable model routing summary."""
    lines = ["=== Nexus Model Routing ===", ""]
    lines.append("Available Models:")
    for name, profile in MODEL_REGISTRY.items():
        lines.append(f"  {name}")
        lines.append(f"    Purpose: {profile.purpose}")
        lines.append(f"    Avg response: {profile.avg_response_time_s}s | Timeout: {profile.timeout_s}s")
        lines.append("")

    lines.append("Task Routing:")
    for task, route in TASK_ROUTES.items():
        lines.append(f"  {task}:")
        lines.append(f"    Primary: {route['primary']}")
        if route.get("fallback"):
            lines.append(f"    Fallback: {route['fallback']}")
        if route.get("ultra_fast"):
            lines.append(f"    Ultra-fast: {route['ultra_fast']}")
        lines.append("")

    return "\n".join(lines)
