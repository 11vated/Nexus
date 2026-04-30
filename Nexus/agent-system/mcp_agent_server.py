#!/usr/bin/env python3
"""MCP Server for Agent System - Full Features"""

import asyncio
import json
import sys
import os
from pathlib import Path

try:
    from mcp.server import Server
    from mcp.types import TextContent, Tool
    from mcp.server.stdio import stdio_server
except ImportError:
    print("Installing MCP SDK...", file=sys.stderr)
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "mcp"], check=True)
    from mcp.server import Server
    from mcp.types import TextContent, Tool
    from mcp.server.stdio import stdio_server

AGENT_SYSTEM_DIR = Path("C:/Users/11vat/Desktop/Copilot/Aider-Local-llm-agent/agent-system")

def run_agent(task: str, mode: str = "basic") -> str:
    """Run the agent system with a task"""
    import subprocess
    script = AGENT_SYSTEM_DIR / "run.py"
    cmd = [sys.executable, str(script), task]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(AGENT_SYSTEM_DIR))
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    server = Server("agent-system")
    
    @server.tool()
    async def run_agent_task(task: str, mode: str = "basic") -> list[TextContent]:
        """Run autonomous agent tasks using local Ollama models.
        
        Args:
            task: The task description
            mode: Agent mode (basic, mini-swe, multi)
        """
        result = run_agent(task, mode)
        return [TextContent(type="text", text=result)]
    
    @server.tool()
    async def run_shell_command(command: str) -> list[TextContent]:
        """Run a shell command.
        
        Args:
            command: The shell command to execute
        """
        import subprocess
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout or result.stderr
        return [TextContent(type="text", text=output)]
    
    @server.tool()
    async def read_file(path: str) -> list[TextContent]:
        """Read a file.
        
        Args:
            path: File path to read
        """
        try:
            with open(path, 'r') as f:
                content = f.read()
            return [TextContent(type="text", text=content)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    @server.tool()
    async def list_directory(path: str = ".") -> list[TextContent]:
        """List directory contents.
        
        Args:
            path: Directory path to list
        """
        try:
            items = list(Path(path).iterdir())
            output = "\n".join([f"{'d' if i.is_dir() else 'f'}: {i.name}" for i in items])
            return [TextContent(type="text", text=output)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    @server.tool()
    async def write_file(path: str, content: str) -> list[TextContent]:
        """Write a file.
        
        Args:
            path: File path to write
            content: Content to write
        """
        try:
            with open(path, 'w') as f:
                f.write(content)
            return [TextContent(type="text", text=f"Written to {path}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    @server.tool()
    async def search_code(pattern: str, path: str = ".") -> list[TextContent]:
        """Search for pattern in code.
        
        Args:
            pattern: Pattern to search
            path: Path to search in
        """
        import subprocess
        cmd = f'rg -l "{pattern}" {path}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return [TextContent(type="text", text=result.stdout or "No matches")]
    
    @server.tool()
    async def get_available_skills() -> list[TextContent]:
        """Get list of available skills (1008 total)."""
        skills_dir = AGENT_SYSTEM_DIR / ".claude" / "skills"
        skills = []
        if skills_dir.exists():
            for d in skills_dir.iterdir():
                if d.is_dir():
                    skills.append(d.name)
        return [TextContent(type="text", text=f"Available skills: {len(skills)}\n" + ", ".join(skills[:50]) + "...")]
    
    @server.tool()
    async def list_models() -> list[TextContent]:
        """List available Ollama models."""
        import subprocess
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        return [TextContent(type="text", text=result.stdout)]

    asyncio.run(stdio_server(server))

if __name__ == "__main__":
    main()