#!/usr/bin/env python3
"""
NEXUS MODEL REGISTRY
==================

Unified model configuration for all Ollama models.
Includes capabilities, use cases, and auto-selection logic.

Models:
- Code Generation: Best for writing code
- Reasoning: Best for debugging/analysis
- Fast: Quick tasks with less context
- Vision: Image analysis
- Large: Complex multi-file tasks
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class ModelCapability(Enum):
    CODE = "code"           # Code generation
    REASONING = "reasoning"  # Debugging, analysis
    FAST = "fast"           # Quick edits
    VISION = "vision"       # Image understanding
    LARGE = "large"         # Big context
    MATH = "math"           # Math problems


@dataclass
class ModelConfig:
    name: str
    display_name: str
    capabilities: List[ModelCapability]
    context_window: int
    strengths: List[str]
    weaknesses: List[str]
    ram_gb: float
    description: str


# ============================================
# MODEL REGISTRY
# ============================================

MODELS: Dict[str, ModelConfig] = {
    # === CODE GENERATION MODELS ===
    "qwen2.5-coder:14b": ModelConfig(
        name="qwen2.5-coder:14b",
        display_name="Qwen Coder 14B",
        capabilities=[ModelCapability.CODE, ModelCapability.LARGE],
        context_window=32000,
        strengths=["Best overall code", "Multi-file", "Type hints"],
        weaknesses=["Slower"],
        ram_gb=9.0,
        description="Best for production code generation"
    ),
    
    "qwen2.5-coder:7b": ModelConfig(
        name="qwen2.5-coder:7b",
        display_name="Qwen Coder 7B",
        capabilities=[ModelCapability.CODE, ModelCapability.FAST],
        context_window=16000,
        strengths=["Fast code", "Good quality"],
        weaknesses=["Smaller context"],
        ram_gb=4.7,
        description="Fast code generation"
    ),
    
    "codellama": ModelConfig(
        name="codellama",
        display_name="CodeLlama",
        capabilities=[ModelCapability.CODE],
        context_window=16000,
        strengths=["Stable", "Good for patterns"],
        weaknesses=["Basic"],
        ram_gb=3.8,
        description="Meta's code model"
    ),
    
    "deepseek-r1:7b": ModelConfig(
        name="deepseek-r1:7b",
        display_name="DeepSeek R1 7B",
        capabilities=[ModelCapability.REASONING, ModelCapability.CODE],
        context_window=16000,
        strengths=["Debugging", "Analysis", "Math"],
        weaknesses=["Slow"],
        ram_gb=4.7,
        description="Strong reasoning for debugging"
    ),
    
    "deepseek-r1:1.5b": ModelConfig(
        name="deepseek-r1:1.5b",
        display_name="DeepSeek R1 1.5B",
        capabilities=[ModelCapability.REASONING, ModelCapability.FAST],
        context_window=8000,
        strengths=["Fast reasoning", "Debugging"],
        weaknesses=["Less capable"],
        ram_gb=1.1,
        description="Fast debugging"
    ),
    
    # === NEW MODELS (User Requested) ===
    
    "gpt-5-nano": ModelConfig(
        name="gpt-5-nano",
        display_name="GPT-5 Nano",
        capabilities=[ModelCapability.CODE, ModelCapability.FAST],
        context_window=16000,
        strengths=["Fast", "Code-aware"],
        weaknesses=["Limited context"],
        ram_gb=2.5,
        description="Fast code model for quick tasks"
    ),
    
    "minimax-max-m2.5-free": ModelConfig(
        name="minimax-max-m2.5-free",
        display_name="MiniMax M2.5 Free",
        capabilities=[ModelCapability.CODE, ModelCapability.REASONING],
        context_window=32000,
        strengths=["Large context", "Code generation"],
        weaknesses=["May vary"],
        ram_gb=8.0,
        description="Large context code model"
    ),
    
    "bigpickle": ModelConfig(
        name="bigpickle",
        display_name="Big Pickle",
        capabilities=[ModelCapability.CODE, ModelCapability.LARGE],
        context_window=48000,
        strengths=["Huge context", "Full project"],
        weaknesses=["Slow"],
        ram_gb=12.0,
        description="Full project context"
    ),
    
    "ling-2.6-flash-free": ModelConfig(
        name="ling-2.6-flash-free",
        display_name="Ling 2.6 Flash",
        capabilities=[ModelCapability.FAST, ModelCapability.CODE],
        context_window=16000,
        strengths=["Fast", "Responsive"],
        weaknesses=["Less depth"],
        ram_gb=3.0,
        description="Fast responsive code"
    ),
    
    "hy3-preview-free": ModelConfig(
        name="hy3-preview-free",
        display_name="Hy3 Preview",
        capabilities=[ModelCapability.CODE, ModelCapability.REASONING],
        context_window=24000,
        strengths=["Code", "Preview features"],
        weaknesses=["New model"],
        ram_gb=6.0,
        description="Preview with latest features"
    ),
    
    "nemotron-super-3b": ModelConfig(
        name="nemotron-super-3b",
        display_name="Nemotron 3 Super",
        capabilities=[ModelCapability.CODE, ModelCapability.REASONING],
        context_window=32000,
        strengths=["Code", "Analysis"],
        weaknesses=["Large"],
        ram_gb=8.0,
        description="NVIDIA Nemotron"
    ),
    
    "bartowski/llama-3.2-1b-instruct-q4_k_m": ModelConfig(
        name="bartowski/llama-3.2-1b-instruct-q4_k_m",
        display_name="Llama 3.2 1B (Q4)",
        capabilities=[ModelCapability.FAST, ModelCapability.CODE],
        context_window=8000,
        strengths=["Tiny", "Fast", "Portable"],
        weaknesses=["Less capable"],
        ram_gb=1.0,
        description="Tiny quantized Llama for speed"
    ),
    
    # === VISION MODELS ===
    "llava": ModelConfig(
        name="llava",
        display_name="LLaVA",
        capabilities=[ModelCapability.VISION],
        context_window=4000,
        strengths=["Image understanding", "Screenshots"],
        weaknesses=["Limited code"],
        ram_gb=4.1,
        description="Vision for screen analysis"
    ),
    
    "moondream": ModelConfig(
        name="moondream",
        display_name="Moondream",
        capabilities=[ModelCapability.VISION],
        context_window=2000,
        strengths=["Fast vision", "Lightweight"],
        weaknesses=["Smaller"],
        ram_gb=1.7,
        description="Fast vision model"
    ),
    
    "dolphin-mistral": ModelConfig(
        name="dolphin-mistral",
        display_name="Dolphin Mistral",
        capabilities=[ModelCapability.CODE, ModelCapability.REASONING],
        context_window=16000,
        strengths=["Chatty", "Instruction following"],
        weaknesses=["May be verbose"],
        ram_gb=4.1,
        description="Friendly instruction model"
    ),
}


# ============================================
# MODEL SELECTION HELPERS
# ============================================

def get_model_for_task(task: str) -> str:
    """Auto-select model based on task keywords."""
    task_lower = task.lower()
    
    if any(w in task_lower for w in ["debug", "fix", "error", "bug"]):
        return "deepseek-r1:7b"
    
    if any(w in task_lower for w in ["build", "create", "implement", "generate"]):
        if any(w in task_lower for w in ["complex", "full", "large", "project"]):
            return "qwen2.5-coder:14b"
        return "qwen2.5-coder:7b"
    
    if any(w in task_lower for w in ["quick", "fast", "simple"]):
        return "qwen2.5-coder:7b"
    
    if any(w in task_lower for w in ["screen", "image", "see", "visual"]):
        return "llava"
    
    if any(w in task_lower for w in ["analyze", "research", "understand"]):
        return "deepseek-r1:7b"
    
    # Default
    return "qwen2.5-coder:14b"


def get_all_models() -> List[ModelConfig]:
    """Get all registered models."""
    return list(MODELS.values())


def get_models_by_capability(cap: ModelCapability) -> List[ModelConfig]:
    """Get models by capability."""
    return [m for m in MODELS.values() if cap in m.capabilities]


def get_fast_models() -> List[ModelConfig]:
    """Get fast models (< 5GB RAM)."""
    return [m for m in MODELS.values() if m.ram_gb < 5.0]


def get_code_models() -> List[ModelConfig]:
    """Get code-capable models."""
    return get_models_by_capability(ModelCapability.CODE)


def get_available_models() -> List[str]:
    """Get list of model names for Ollama."""
    return list(MODELS.keys())


# ============================================
# TEST CONNECTION
# ============================================

async def check_available_models() -> List[str]:
    """Check which models are actually available in Ollama."""
    import subprocess
    import asyncio
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama", "list",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        
        available = []
        for line in stdout.decode().split('\n'):
            for model_name in MODELS.keys():
                if model_name in line:
                    available.append(model_name)
        
        return available
    except:
        return []


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    print("NEXUS MODEL REGISTRY")
    print("=" * 50)
    print(f"Total models: {len(MODELS)}")
    print()
    
    print("Code Models:")
    for m in get_code_models():
        print(f"  {m.name:40s} {m.ram_gb:.1f}GB")
    
    print("\nFast Models (<5GB):")
    for m in get_fast_models():
        print(f"  {m.name:40s} {m.ram_gb:.1f}GB")
    
    print("\nVision Models:")
    for m in get_models_by_capability(ModelCapability.VISION):
        print(f"  {m.name:40s} {m.ram_gb:.1f}GB")