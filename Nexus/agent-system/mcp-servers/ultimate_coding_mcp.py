#!/usr/bin/env python3
"""
ULTIMATE CODING MCP SERVER
Powered by Ollama - gives AI coding agents full dev capabilities
"""

import subprocess
import json
import os
from pathlib import Path

# MCP Protocol imports - uses standard interface
class MCPServer:
    def __init__(self):
        self.name = "ultimate-coding-mcp"
        self.version = "1.0.0"
    
    def handle_request(self, method, params=None):
        """Handle MCP protocol requests"""
        
        if method == "initialize":
            return {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": self.name,
                    "version": self.version
                },
                "capabilities": {
                    "tools": {},
                    "resources": {}
                }
            }
        
        elif method == "tools/list":
            return {"tools": self.get_tools()}
        
        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            return self.execute_tool(tool_name, args)
        
        return {}
    
    def get_tools(self):
        """Define available tools"""
        return [
            {
                "name": "run_ollama",
                "description": "Run Ollama model for code generation",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Code request"},
                        "model": {"type": "string", "description": "Model name (default: qwen2.5-coder:14b)"}
                    },
                    "required": ["prompt"]
                }
            },
            {
                "name": "list_files",
                "description": "List directory contents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"},
                        "pattern": {"type": "string", "description": "Glob pattern"}
                    }
                }
            },
            {
                "name": "read_file",
                "description": "Read file contents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write file contents",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "run_command",
                "description": "Execute shell command",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "string"},
                        "cwd": {"type": "string"}
                    },
                    "required": ["cmd"]
                }
            },
            {
                "name": "get_ollama_models",
                "description": "List available Ollama models",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "analyze_codebase",
                "description": "Analyze code structure",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            }
        ]
    
    def execute_tool(self, name, args):
        """Execute a tool"""
        try:
            if name == "run_ollama":
                model = args.get("model", "qwen2.5-coder:14b")
                prompt = args["prompt"]
                result = subprocess.run(
                    ["ollama", "run", model, prompt],
                    capture_output=True, text=True, timeout=120
                )
                return {"content": result.stdout or result.stderr}
            
            elif name == "list_files":
                path = args.get("path", ".")
                pattern = args.get("pattern", "*")
                files = list(Path(path).glob(pattern))
                return {"content": json.dumps([str(f) for f in files[:50]])}
            
            elif name == "read_file":
                with open(args["path"], "r") as f:
                    return {"content": f.read()[:10000]}
            
            elif name == "write_file":
                with open(args["path"], "w") as f:
                    f.write(args["content"])
                return {"content": f"Written to {args['path']}"}
            
            elif name == "run_command":
                result = subprocess.run(
                    args["cmd"], shell=True, 
                    capture_output=True, text=True,
                    cwd=args.get("cwd"), timeout=60
                )
                return {"content": result.stdout + result.stderr}
            
            elif name == "get_ollama_models":
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True, text=True
                )
                return {"content": result.stdout}
            
            elif name == "analyze_codebase":
                path = Path(args["path"])
                stats = {"files": 0, "lines": 0, "extensions": {}}
                for f in path.rglob("*"):
                    if f.is_file() and not any(x in str(f) for x in ["node_modules", ".git", "__pycache__"]):
                        stats["files"] += 1
                        try:
                            ext = f.suffix or "noext"
                            stats["extensions"][ext] = stats["extensions"].get(ext, 0) + 1
                            stats["lines"] += len(f.read_text(errors="ignore").splitlines())
                        except: pass
                return {"content": json.dumps(stats, indent=2)}
            
            return {"content": "Unknown tool"}
        except Exception as e:
            return {"content": f"Error: {str(e)}", "isError": True}


def main():
    """MCP Server entry point"""
    import sys
    server = MCPServer()
    
    # Read JSON-RPC messages from stdin
    for line in sys.stdin:
        if line.strip():
            try:
                msg = json.loads(line)
                method = msg.get("method")
                params = msg.get("params")
                result = server.handle_request(method, params)
                if result:
                    response = json.dumps({"jsonrpc": "2.0", "id": msg.get("id"), "result": result})
                    print(response)
            except: pass


if __name__ == "__main__":
    main()