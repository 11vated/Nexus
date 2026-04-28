from pathlib import Path
import re
from typing import List, Optional


ALLOWED_MODELS = {
    "qwen2.5-coder:14b",
    "qwen2.5-coder:7b",
    "codellama",
    "deepseek-r1:7b",
    "deepseek-r1:1.5b",
    "gpt-5-nano",
    "minimax-max-m2.5-free",
    "bigpickle",
    "ling-2.6-flash-free",
    "hy3-preview-free",
    "nemotron-super-3b",
    "llama3.2:latest",
    "llama3.2:1b",
    "llama3.2:3b",
    "mistral:7b",
    "mixtral:8x7b",
    "llava",
    "moondream",
    "dolphin-mistral",
    "phi3:mini",
    "phi3:medium",
    "gemma:2b",
    "gemma:7b",
}

ALLOWED_TOOL_ARGS = {
    "aider": ["--model", "--message", "--yes", "--no-git", "--read", "--write"],
    "opencode": ["--model", "--prompt", "--context"],
    "ollama": ["run", "list", "pull", "stop"],
}


def validate_model_name(name: str) -> str:
    """Validate model name against whitelist."""
    if not name or not isinstance(name, str):
        raise ValueError("Model name must be a non-empty string")
    
    name = name.strip()
    
    if name not in ALLOWED_MODELS:
        raise ValueError(
            f"Model '{name}' not allowed. Choose from: {', '.join(sorted(ALLOWED_MODELS))}"
        )
    return name


def validate_command_args(tool: str, args: List[str]) -> List[str]:
    """Validate command arguments to prevent injection."""
    if not args:
        return args
    
    safe_pattern = re.compile(r'^[a-zA-Z0-9_\-.:/]+$')
    
    for arg in args:
        if not safe_pattern.match(arg):
            raise ValueError(f"Unsafe argument value: {arg}")
    
    if tool in ALLOWED_TOOL_ARGS:
        allowed = ALLOWED_TOOL_ARGS[tool]
        for i, arg in enumerate(args):
            if arg.startswith("--") and arg not in allowed:
                raise ValueError(f"Argument '{arg}' not allowed for {tool}")
    
    return args


def safe_path_join(base: Path, user_path: str) -> Path:
    """Prevent directory traversal attacks."""
    if not user_path:
        raise ValueError("Path cannot be empty")
    
    user_path = user_path.replace("..", "").replace("~", str(Path.home()))
    
    resolved = (base / user_path).resolve()
    
    if not str(resolved).startswith(str(base.resolve())):
        raise ValueError(f"Path '{user_path}' escapes workspace")
    
    return resolved


def sanitize_filename(name: str) -> str:
    """Sanitize filename to prevent path traversal."""
    name = name.replace("..", "").replace("/", "").replace("\\", "")
    name = re.sub(r'[^\w\s\-.]', '', name)
    return name.strip()


def sanitize_prompt(prompt: str, max_length: int = 10000) -> str:
    """Sanitize and truncate prompt if too long."""
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt must be a non-empty string")
    
    prompt = prompt.strip()
    
    if len(prompt) > max_length:
        prompt = prompt[:max_length] + "... [truncated]"
    
    dangerous_patterns = [
        r'\x00',
        r'\r\n',
        re.compile(r'eval\s*\(', re.IGNORECASE),
        re.compile(r'exec\s*\(', re.IGNORECASE),
        re.compile(r'__import__\s*\(', re.IGNORECASE),
    ]
    
    for pattern in dangerous_patterns:
        if isinstance(pattern, re.Pattern):
            prompt = pattern.sub('[SANITIZED]', prompt)
        else:
            prompt = prompt.replace(pattern, '')
    
    return prompt


def safe_subprocess_args(cmd: List[str]) -> List[str]:
    """Ensure subprocess args are safe."""
    for arg in cmd:
        if isinstance(arg, str):
            if '\x00' in arg or '\r' in arg:
                raise ValueError(f"Invalid characters in argument: {arg}")
    return cmd