#!/usr/bin/env python3
"""
NEXUS VISION AUTO-SWITCH
========================

Automatically detects images and switches to vision model.
Use this as a wrapper or configuration for OpenCode/Aider.

Usage:
    1. Set as system prompt in OpenCode/Aider
    2. Run as a watcher daemon
    3. Use as a pre-processor

INSTALLATION:
=============

For OpenCode:
    Add this to your system prompt or config

For Aider:
    Create ~/.aider.conf.yml with the VISION_AUTO_SWITCH_SYSTEM_PROMPT

For VSCode Copilot:
    Use as a custom instruction
"""

# ============================================
# SYSTEM PROMPT - Add to OpenCode/Aider
# ============================================

VISION_AUTO_SWITCH_SYSTEM_PROMPT = """
You have VISION CAPABILITIES. When the user provides an image (screenshot, photo, diagram):
    
    1. IMMEDIATELY use the vision model (llava) - NOT a text model
    2. Do NOT try to process the image as text
    3. Do NOT say "I cannot" - just use the vision model

CRITICAL: When you see image file extensions (.png, .jpg, .jpeg, .gif, .bmp, .webp):
    - Use: ollama run llava "<image_path>"
    - Or API: curl http://localhost:11434/api/generate with base64 image
    - NEVER use qwen2.5-coder, deepseek-r1, or any text-only model

IMMEDIATE ACTION: When user sends image:
    1. Extract the image path
    2. Call: ollama run llava "<path>" with prompt
    3. Analyze and respond

Examples:
    User: "check this error screenshot.png"
    You: [Use llava to analyze screenshot.png]
    
    User: [attaches error.jpg]
    You: [Uses llava to analyze the image]
"""

# ============================================
# WRAPPER SCRIPT
# ============================================

import asyncio
import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List


class VisionAutoSwitch:
    """
    Wraps any LLM call to auto-detect images and switch to vision.
    
    Usage:
        from vision_auto_switch import VisionAutoSwitch
        switcher = VisionAutoSwitch()
        result = await switcher.chat("analyze this screenshot.png")
    """
    
    VISION_MODELS = ["llava", "moondream"]
    TEXT_MODELS = ["qwen2.5-coder", "deepseek-r1", "gpt-5-nano", "codellama", "dolphin"]
    
    def __init__(self, default_model: str = "qwen2.5-coder:14b"):
        self.default_model = default_model
        self.current_model = default_model
    
    def has_image(self, message: str) -> bool:
        """Check if message contains image reference"""
        # Check for image extensions
        image_patterns = [
            r'\.(png|jpg|jpeg|gif|bmp|webp|tiff)\b',
            r'screenshot',
            r'screen.?shot',
            r'image\s*:\s*\S+',
            r'photo\s*:\s*\S+',
            r'attached',
            r'attachment'
        ]
        
        for pattern in image_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        
        # Check for image file paths
        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            if ext in message.lower():
                return True
        
        return False
    
    def extract_image_path(self, message: str) -> Optional[str]:
        """Extract image path from message"""
        # Common patterns
        patterns = [
            r'([A-Za-z]:\\[^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp))',
            r'(/[^\s]+\.(?:png|jpg|jpeg|gif|bmp|webp))',
            r'(?:image|screenshot|photo)\s*[:\s]+([^\s]+\.(?:png|jpg|jpeg))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    async def chat(self, message: str, prompt: str = None) -> str:
        """Auto-switching chat"""
        
        if self.has_image(message):
            # Use vision model
            return await self._vision_chat(message, prompt)
        else:
            # Use text model
            return await self._text_chat(message, prompt)
    
    async def _vision_chat(self, message: str, prompt: str = None) -> str:
        """Chat with vision model"""
        
        image_path = self.extract_image_path(message)
        
        if not image_path:
            return "No image found in message. Please provide image path."
        
        if not Path(image_path).exists():
            return f"Image not found: {image_path}"
        
        vision_prompt = prompt or "Describe this image in detail. Include any text visible."
        
        # Try API first
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
            b64 = base64.b64encode(image_data).decode()
            
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "http://localhost:11434/api/generate",
                "-d", json.dumps({
                    "model": "llava",
                    "prompt": vision_prompt,
                    "images": [b64],
                    "stream": False
                }),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            
            response = json.loads(stdout.decode())
            return response.get("response", "No response")
            
        except Exception as e:
            return f"Vision error: {e}"
    
    async def _text_chat(self, message: str, prompt: str = None) -> str:
        """Chat with text model"""
        
        full_prompt = prompt or message
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.default_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode()),
                timeout=60
            )
            
            return stdout.decode()
            
        except Exception as e:
            return f"Error: {e}"


# ============================================
# CONFIGURATION FOR OPENCODE/AIDER
# ============================================

OPENCODE_SYSTEM_PROMPT = """
# NEXUS VISION AUTO-SWITCH ENABLED

You are a coding assistant with VISION capabilities.

## VISION RULES (MUST FOLLOW):

1. When user provides ANY image (screenshot, photo, diagram):
   - ALWAYS use vision model (llava)
   - NEVER use text models (qwen, deepseek, etc.)

2. Image indicators:
   - File extensions: .png, .jpg, .jpeg, .gif, .bmp, .webp
   - Words: screenshot, photo, image, attached, see this

3. How to analyze images:
   ```
   # Use curl with base64 encoding
   curl -s http://localhost:11434/api/generate -d '{
     "model": "llava",
     "prompt": "Describe this",
     "images": ["<base64_image>"]
   }'
   ```

4. NEVER say "I cannot view images" or "This model does not support images"
   - Just use llava model

## EXAMPLES:

User: "check this error screenshot.png"
You: [Analyzes using llava, describes the error]

User: [attaches file: error.jpg]  
You: [Uses llava to examine, explains what's shown]

User: "what does this UI look like?"
You: [Uses llava if image provided, describes UI]
"""

# Save to file for easy reference
def save_config():
    """Save configuration to files"""
    
    # Save OpenCode prompt
    Path("VISION_PROMPT_OPENCODE.txt").write_text(OPENCODE_SYSTEM_PROMPT)
    
    # Save Aider config
    aider_config = """
# .aider.conf.yml - Add VISION_SYSTEM_PROMPT
VISION_SYSTEM_PROMPT: |
    """ + OPENCODE_SYSTEM_PROMPT.replace('"', '\\"').replace('\n', '\n    ') + """
"""
    
    Path("VISION_PROMPT_AIDER.yaml").write_text(aider_config)
    
    print("Saved:")
    print("  - VISION_PROMPT_OPENCODE.txt")
    print("  - VISION_PROMPT_AIDER.yaml")
    print("")
    print("Add the prompt content to your OpenCode/Aider config.")


# ============================================
# MAIN - TEST THE AUTO-SWITCH
# ============================================

async def main():
    print("NEXUS VISION AUTO-SWITCH")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        # Test a message
        message = " ".join(sys.argv[1:])
        
        switcher = VisionAutoSwitch()
        
        print(f"Message: {message}")
        print(f"Has image: {switcher.has_image(message)}")
        print(f"Image path: {switcher.extract_image_path(message)}")
        
        if switcher.has_image(message):
            print("\nUsing VISION model (llava)...")
            result = await switcher._vision_chat(message)
            print(f"Result: {result[:500]}")
    else:
        print("Usage: python vision_auto_switch.py <message with image path>")
        print("")
        print("Files created for configuration:")
        save_config()


if __name__ == "__main__":
    asyncio.run(main())