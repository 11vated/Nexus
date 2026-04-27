#!/usr/bin/env python3
"""
Vision Wrapper - Pre-processes images before sending to OpenCode.
This wrapper detects images and returns their descriptions to OpenCode.
"""

import base64
import json
import subprocess
import sys
import re
from pathlib import Path

def extract_image_paths(message: str) -> list:
    """Extract all image paths from message."""
    paths = []
    
    # Windows and Unix paths
    patterns = [
        r'([A-Za-z]:\\[^\s"<>]+\.(?:png|jpg|jpeg|gif|bmp|webp))',
        r'([/][^\s"<>]+\.(?:png|jpg|jpeg|gif|bmp|webp))',
        r'"([^"]+\.(?:png|jpg|jpeg|gif|bmp|webp))"',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, message, re.IGNORECASE):
            path = match.group(1)
            if Path(path).exists():
                paths.append(path)
    
    return paths

def analyze_image(image_path: str) -> str:
    """Analyze image using llava."""
    try:
        result = subprocess.run(
            ["ollama", "run", "llava", image_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"[Vision error: {result.stderr[:200] if result.stderr else 'unknown'}]"
    except Exception as e:
        return f"[Vision error: {str(e)[:100]}]"

def main():
    """Main entry - check if message has images."""
    
    if len(sys.argv) < 2:
        sys.exit(0)
    
    message = sys.argv[1]
    
    # Check for image extensions
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
    has_image = any(ext in message.lower() for ext in image_extensions)
    
    if not has_image:
        sys.exit(0)
    
    # Extract paths
    paths = extract_image_paths(message)
    
    if not paths:
        # No valid paths found
        sys.exit(0)
    
    # Analyze first image
    image_path = paths[0]
    print(f"\n[Vision Analysis] Processing: {Path(image_path).name}")
    print("="*60)
    
    description = analyze_image(image_path)
    print(description)
    print("="*60)
    print("\n[End Vision Analysis]")
    print("Above is the analysis of the image you sent.")

if __name__ == "__main__":
    main()