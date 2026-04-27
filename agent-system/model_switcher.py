#!/usr/bin/env python3
"""
NEXUS MODEL SWITCHER
==================

Quickly switch between ALL available models in any tool.
Works with: Aider, OpenCode, VSCode, Goose, CLI, any Ollama app.

USAGE:
    python model_switcher.py            # Interactive picker
    python model_switcher.py code       # Best code model
    python model_switcher.py debug      # Best debugging model
    python model_switcher.py gpt5     # GPT-5 Nano
    python model_switcher.py list      # Show all models

EXAMPLES:
    python model_switcher.py code_best
    python model_switcher.py deepseek
    python model_switcher.py gpt5
    python model_switcher.py vision
"""

import sys
import subprocess
from pathlib import Path


# ============================================
# ALL MODELS REGISTRY
# ============================================

MODELS = {
    # Code Generation Models
    "code_best": {
        "model": "qwen2.5-coder:14b",
        "description": "Best overall code generation",
        "ram": "9GB",
        "use": "Full project generation"
    },
    "code_fast": {
        "model": "qwen2.5-coder:7b", 
        "description": "Fast code generation",
        "ram": "4.7GB",
        "use": "Quick edits"
    },
    "code_meta": {
        "model": "codellama",
        "description": "Meta's CodeLlama",
        "ram": "3.8GB",
        "use": "Stable code"
    },
    
    # User Requested Models
    "gpt5": {
        "model": "gpt-5-nano",
        "description": "GPT-5 Nano",
        "ram": "2.5GB",
        "use": "Fast code"
    },
    "minimax": {
        "model": "minimax-max-m2.5-free",
        "description": "MiniMax M2.5 Free",
        "ram": "8GB",
        "use": "Large context"
    },
    "bigpickle": {
        "model": "bigpickle",
        "description": "Big Pickle", 
        "ram": "12GB",
        "use": "Full projects"
    },
    "ling": {
        "model": "ling-2.6-flash-free",
        "description": "Ling 2.6 Flash",
        "ram": "3GB",
        "use": "Fast responsive"
    },
    "hy3": {
        "model": "hy3-preview-free",
        "description": "Hy3 Preview",
        "ram": "6GB",
        "use": "Latest features"
    },
    "nemotron": {
        "model": "nemotron-super-3b",
        "description": "Nemotron 3 Super",
        "ram": "8GB",
        "use": "NVIDIA reasoning"
    },
    "llama_tiny": {
        "model": "bartowski/llama-3.2-1b-instruct-q4_k_m",
        "description": "Llama 3.2 1B (Q4)",
        "ram": "1GB",
        "use": "Tiny portable"
    },
    
    # Reasoning Models  
    "reason_best": {
        "model": "deepseek-r1:7b",
        "description": "Best reasoning/debugging",
        "ram": "4.7GB",
        "use": "Debug, analyze, fix"
    },
    "reason_fast": {
        "model": "deepseek-r1:1.5b",
        "description": "Fast reasoning", 
        "ram": "1.1GB",
        "use": "Quick analysis"
    },
    
    # Vision Models
    "vision": {
        "model": "llava",
        "description": "Vision for screen analysis",
        "ram": "4.1GB",
        "use": "Screen understanding"
    },
    "vision_fast": {
        "model": "moondream", 
        "description": "Fast vision",
        "ram": "1.7GB",
        "use": "Quick vision"
    },
    
    # General
    "dolphin": {
        "model": "dolphin-mistral",
        "description": "Friendly instruction model",
        "ram": "4.1GB",
        "use": "Chatty assistance"
    }
}


# Shortcuts mapping
SHORTCUTS = {
    "code": "code_best",
    "fast": "code_fast", 
    "debug": "reason_best",
    "fix": "reason_best",
    "analyze": "reason_best",
    "gpt5": "gpt5",
    "mini": "minimax",
    "big": "bigpickle",
    "vision": "vision",
    "see": "vision",
    "all": None  # Special case - list all
}


def resolve_model(name: str) -> str:
    """Resolve model name from shortcut or alias."""
    if name in MODELS:
        return MODELS[name]["model"]
    if name in SHORTCUTS:
        resolved = SHORTCUTS[name]
        if resolved:
            return MODELS[resolved]["model"]
    return name  # Assume it's already a full model name


def list_models():
    """List all available models."""
    print("\n" + "=" * 60)
    print("NEXUS MODEL REGISTRY - ALL AVAILABLE MODELS")
    print("=" * 60)
    
    categories = {
        "CODE GENERATION": ["code_best", "code_fast", "code_meta", "gpt5", "minimax", "bigpickle", "ling", "hy3", "nemotron", "llama_tiny"],
        "REASONING/DEBUG": ["reason_best", "reason_fast", "nemotron"],
        "VISION": ["vision", "vision_fast"],
        "GENERAL": ["dolphin"]
    }
    
    for category, models in categories.items():
        print(f"\n{category}:")
        for m in models:
            info = MODELS[m]
            print(f"  {m:20s} {info['model']:35s} {info['ram']:6s} - {info['use']}")
    
    print("\n" + "=" * 60)
    print("QUICK ALIASES:")
    for shortcut, target in SHORTCUTS.items():
        if target:
            print(f"  {shortcut:20s} -> {MODELS[target]['model']}")
    print()


def switch_model(model_key: str):
    """Switch to the specified model."""
    model_name = resolve_model(model_key)
    print(f"\nSwitching to: {model_name}")
    
    # Check if model is installed
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True
    )
    
    if model_name not in result.stdout:
        print(f"Model not found. Pulling {model_name}...")
        subprocess.run(
            ["ollama", "pull", model_name],
            check=True
        )
        print(f"Pulled successfully!")
    
    print(f"\nModel ready: {model_name}")
    print(f"\nCommands to use with different tools:")
    print(f"  Aider:    aider --model {model_name}")
    print(f"  Ollama:  ollama run {model_name}")
    print(f"  API:     http://localhost:11434 (with model={model_name})")


def main():
    if len(sys.argv) < 2:
        # Interactive mode
        list_models()
        print("Usage: python model_switcher.py <code|debug|gpt5|vision|list>")
        print("Example: python model_switcher.py debug")
        return
    
    command = sys.argv[1].lower()
    
    if command in ["list", "ls", "all"]:
        list_models()
    elif command == "test":
        # Test all models
        print("Testing Ollama connection...")
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
    else:
        # Switch to model
        switch_model(command)


if __name__ == "__main__":
    main()