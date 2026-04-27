#!/usr/bin/env python3
"""
NEXUS VISION TOOL
=================

Analyzes images using Ollama vision models (llava, moondream)

Usage:
    python vision_tool.py <image_path> "<question>"
    
Examples:
    python vision_tool.py screenshot.png "What error is shown?"
    python vision_tool.py ui.png "Describe this UI layout"
    python vision_tool.py error.png "What does this error say?"
    
Or use programmatically:
    from vision_tool import analyze_image
    result = await analyze_image("image.png", "What's in this?")
"""

import asyncio
import base64
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Optional


async def analyze_image(
    image_path: str, 
    prompt: str = "Describe this image in detail. Focus on any text, UI elements, or important visual information.",
    model: str = "llava"
) -> str:
    """
    Analyze an image using Ollama vision model.
    
    Args:
        image_path: Path to image file
        prompt: Question about the image
        model: Vision model to use (llava, moondream)
    
    Returns:
        Analysis text
    """
    path = Path(image_path)
    if not path.exists():
        return f"ERROR: Image file not found: {image_path}"
    
    # Get absolute path
    abs_path = str(path.absolute())
    
    try:
        # For Ollama vision models, the format differs
        # llava accepts direct image file path passed via stdin
        
        # Build the analysis prompt
        full_prompt = f"""Analyze this image and answer the question.

Question: {prompt}

Provide a detailed, accurate response based solely on what's visible in the image."""

        # Use Ollama API instead of CLI for better image handling
        import subprocess
        
        # First, base64 encode the image
        with open(abs_path, "rb") as f:
            image_data = f.read()
        
        # Call Ollama via API (more reliable for images)
        proc = await asyncio.create_subprocess_exec(
            "curl",
            "-s", "http://localhost:11434/api/generate",
            "-d", json.dumps({
                "model": model,
                "prompt": full_prompt,
                "images": [base64.b64encode(image_data).decode()],
                "stream": False
            }),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=120
        )
        
        if stderr:
            # Try alternative - CLI mode
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Format for CLI - pass image and prompt
            input_text = f"Analyze this image file: {abs_path}\n\nQuestion: {prompt}\n\nProvide a detailed response."
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_text.encode()),
                timeout=120
            )
            
            result = stdout.decode()
            
            # Clean up result
            if "okay" in result.lower():
                result = "Image analyzed. " + result
            
            return result[:3000] if result else "No analysis returned"
        
        # Parse API response
        try:
            response = json.loads(stdout.decode())
            return response.get("response", "No response")[:3000]
        except:
            return stdout.decode()[:3000]
    
    except asyncio.TimeoutError:
        return f"ERROR: Vision analysis timed out after 120s"
    except Exception as e:
        return f"ERROR: {str(e)}\n{traceback.format_exc()}"


async def quick_analyze(image_path: str) -> str:
    """Quick analysis - just describe what's in the image"""
    return await analyze_image(
        image_path,
        "Provide a concise description of what's shown in this image. Include any text that is visible."
    )


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    image_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Analyzing: {image_path}")
    print(f"Model: llava")
    print("...")
    
    if prompt:
        result = await analyze_image(image_path, prompt)
    else:
        result = await quick_analyze(image_path)
    
    print(f"\n{'='*60}")
    print("ANALYSIS RESULT:")
    print(f"{'='*60}")
    print(result)
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())