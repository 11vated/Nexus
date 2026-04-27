#!/usr/bin/env python3
"""
Vision Analyzer - Analyze images with Ollama vision models
"""

import asyncio
import base64
import subprocess
from pathlib import Path
from typing import Optional


class VisionAnalyzer:
    """Analyze images using Ollama vision models"""
    
    def __init__(self, model: str = "llava"):
        self.model = model
        self._verify_model()
    
    def _verify_model(self):
        """Check if model is available"""
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True
        )
        if self.model not in result.stdout:
            print(f"WARNING: {self.model} not found. Pulling...")
            subprocess.run(
                ["ollama", "pull", self.model],
                check=True
            )
    
    async def analyze_image(self, image_path: str, prompt: str = "Describe this image in detail") -> str:
        """
        Analyze an image file.
        
        Args:
            image_path: Path to image file (png, jpg, etc.)
            prompt: Question about the image
            
        Returns:
            Analysis text
        """
        # Read and encode image
        image_file = Path(image_path)
        if not image_file.exists():
            return f"ERROR: Image not found: {image_path}"
        
        # Read image bytes
        with open(image_file, "rb") as f:
            image_bytes = f.read()
        
        # For llava, use the proper image format
        # Ollama vision uses stdin with special format
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Format: describe the image based on the prompt
            # For Ollama, we pass the image as a file reference or base64
            # The proper format depends on Ollama version
            
            # Try with --verbose flag for better output
            full_prompt = f"{prompt}\nImage: {image_path}\n"
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode()),
                timeout=120
            )
            
            if stderr:
                # Try alternative - run with just the prompt
                return f"Vison model output: {stdout.decode()[:500]}"
            
            return stdout.decode().strip()[:2000]
            
        except asyncio.TimeoutError:
            return "ERROR: Vision analysis timed out"
        except Exception as e:
            return f"ERROR: {e}"
    
    async def analyze_screenshot(self, screenshot_bytes: bytes, prompt: str = "Describe what's shown in this screenshot") -> str:
        """
        Analyze screenshot bytes.
        
        Args:
            screenshot_bytes: Raw screenshot image bytes
            prompt: Question about the screenshot
            
        Returns:
            Analysis text
        """
        b64 = base64.b64encode(screenshot_bytes).decode()
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # For llava with base64 (newer Ollama versions)
            prompt_with_image = f"{prompt}\n<image:base64>\n{b64[:5000]}...\n"
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt_with_image.encode()),
                timeout=120
            )
            
            return stdout.decode().strip()[:2000]
            
        except Exception as e:
            return f"ERROR: {e}"


async def main():
    """Test the vision analyzer"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python vision_analyzer.py <image_path> [prompt]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Describe this image in detail"
    
    analyzer = VisionAnalyzer("llava")
    
    print(f"Analyzing: {image_path}")
    print(f"Prompt: {prompt}")
    print("...")
    
    result = await analyzer.analyze_image(image_path, prompt)
    print(f"\nResult:\n{result}")


if __name__ == "__main__":
    asyncio.run(main())