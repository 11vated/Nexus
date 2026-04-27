#!/usr/bin/env python3
"""
Vision Intercept - Catches images before they reach non-vision models.
Run this as a pre-processor or use with OpenCode's hook system.
"""

import base64
import json
import subprocess
import sys
import os
from pathlib import Path

def analyze_image(image_path: str, question: str = None) -> str:
    """Analyze image using llava."""
    
    if not Path(image_path).exists():
        return f"Error: Image not found: {image_path}"
    
    # Build prompt
    if question:
        prompt = question
    else:
        prompt = "Describe this image in detail. If there are errors, code issues, or UI problems, explain them clearly."
    
    try:
        # Method 1: Use ollama CLI
        result = subprocess.run(
            ["ollama", "run", "llava", image_path, prompt],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return "Error: Vision analysis timed out"
    except Exception as e:
        return f"Error: {str(e)}"


def check_for_images(message: str) -> bool:
    """Check if message contains image references."""
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff']
    keywords = ['screenshot', 'image', 'photo', 'attached', 'see this']
    
    message_lower = message.lower()
    
    for ext in image_extensions:
        if ext in message_lower:
            return True
    
    for kw in keywords:
        if kw in message_lower:
            return True
    
    return False


def extract_image_path(message: str) -> str:
    """Extract image path from message."""
    import re
    
    # Windows paths
    patterns = [
        r'([A-Za-z]:\\[^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp))',
        r'([/][^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp))',
        r'((?:screenshot|photo|image)\s*[:\s]+([^\s]+\.(?:png|jpg|jpeg)))',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def main():
    """Main entry point."""
    
    if len(sys.argv) > 1:
        # Direct call with image path
        image_path = sys.argv[1]
        question = sys.argv[2] if len(sys.argv) > 2 else None
        result = analyze_image(image_path, question)
        print(result)
        return
    
    # Read from stdin (pipe mode)
    try:
        message = sys.stdin.read()
    except:
        message = ""
    
    if not message:
        print("")
        return
    
    # Check for images
    if check_for_images(message):
        image_path = extract_image_path(message)
        
        if image_path:
            print(f"[VISION] Analyzing: {image_path}")
            result = analyze_image(image_path)
            print(result)
            return
    
    # No images found, pass through
    print("")


if __name__ == "__main__":
    main()