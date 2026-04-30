#!/usr/bin/env python3
"""
NEXUS VISION INTEGRATION
========================

Automatically handles image analysis when images are detected.
Use this as a tool that gets triggered when you send/attach images.

Usage:
    - In OpenCode: Just send/attach an image and ask a question
    - CLI: python vision_integration.py <image_path> [question]
"""

import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, List

# Default vision models (in priority order)
VISION_MODELS = ["llava", "moondream"]

# Text models that DON'T support images
NON_VISION_MODELS = [
    "qwen2.5-coder", "deepseek-r1", "gpt-5-nano", "minimax", 
    "bigpickle", "ling", "hy3", "nemotron", "codellama", "dolphin"
]


def is_image_file(path: str) -> bool:
    """Check if file is an image"""
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    return Path(path).suffix.lower() in image_extensions


def extract_image_paths(text: str) -> List[str]:
    """Extract potential image paths from text"""
    # Common patterns for image references
    patterns = [
        r'([A-Za-z]:\\[^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp|tiff))',  # Windows path
        r'(/[^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp|tiff))',  # Unix path
        r'(?:image|screenshot|photo|picture)[^\s]*[:\s]+([^\s]+\.(?:png|jpg|jpeg))',  # "image: path"
    ]
    
    paths = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        paths.extend(matches)
    
    return paths


async def call_with_image(model: str, image_path: str, prompt: str) -> str:
    """Call Ollama with image using the API"""
    
    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = f.read()
    
    b64_image = base64.b64encode(image_data).decode()
    
    # Try API call first
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl",
            "-s", "http://localhost:11434/api/generate",
            "-d", json.dumps({
                "model": model,
                "prompt": prompt,
                "images": [b64_image],
                "stream": False
            }),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=120
        )
        
        if stdout:
            response = json.loads(stdout.decode())
            return response.get("response", "No response")
        
        if stderr:
            raise Exception(stderr.decode())
    
    except Exception as e:
        # Fallback to CLI (interactive - less reliable for images)
        return f"The image analysis API call failed: {e}. Please use 'ollama run llava' directly in terminal."
    
    return "Could not analyze image."


async def auto_vision_analyze(user_message: str) -> str:
    """
    Main function - call this when you receive a message with an image.
    
    Pass the full user message and we'll extract and analyze.
    """
    
    # Check if there's an image path in the message
    image_paths = extract_image_paths(user_message)
    
    # Also check if there's a temp file or attachment
    if not image_paths:
        # Check common temp directories for recent images
        temp_paths = [
            os.environ.get('TEMP', '/tmp'),
            os.environ.get('TMP', '/tmp'),
            '.',
        ]
        
        import time
        now = time.time()
        
        for temp_dir in temp_paths:
            if os.path.exists(temp_dir):
                try:
                    files = sorted(
                        Path(temp_dir).glob('*'),
                        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
                        reverse=True
                    )
                    
                    for f in files[:5]:
                        if is_image_file(str(f)) and now - os.path.getmtime(f) < 300:
                            image_paths.append(str(f))
                except:
                    pass
    
    if not image_paths:
        return None  # Not an image-related message
    
    # Extract the question/prompt from message
    question_prompt = "Describe what's shown in this image in detail. Include any text visible."
    
    # Clean up the message to extract just the question part
    for marker in ["analyze", "describe", "what", "see", "check", "find"]:
        if marker in user_message.lower():
            # Use most of the message as the prompt
            question_prompt = user_message
    
    # Find the first available vision model
    available_model = None
    
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        for model in VISION_MODELS:
            if model in result.stdout:
                available_model = model
                break
    except:
        pass
    
    if not available_model:
        return "No vision model (llava/moondream) found. Please install one with: ollama pull llava"
    
    # Analyze with the first found image
    image_path = image_paths[0]
    
    if not Path(image_path).exists():
        return f"Image file not found: {image_path}"
    
    result = await call_with_image(available_model, image_path, question_prompt)
    
    return result


# Main entry point for CLI
async def main():
    if len(sys.argv) < 2:
        print("NEXUS Vision Integration")
        print("=" * 40)
        print("Usage:")
        print("  python vision_integration.py <image_path> [question]")
        print("")
        print("Or use auto-detection:")
        print('  python vision_integration.py --auto "check screenshot.png what error"')
        sys.exit(1)
    
    if sys.argv[1] == "--auto":
        # Auto-detect mode
        message = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        result = await auto_vision_analyze(message)
        print(result or "No image detected in message")
        return
    
    image_path = sys.argv[1]
    prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Describe this image"
    
    print(f"Analyzing: {image_path}")
    print(f"Using: llava")
    print("...")
    
    result = await call_with_image("llava", image_path, prompt)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())