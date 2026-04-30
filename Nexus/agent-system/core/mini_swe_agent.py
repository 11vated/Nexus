import json
import subprocess
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    DONE = "done"
    ERROR = "error"


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]
    tool_use_id: Optional[str] = None


class ToolDefinition:
    def __init__(self, name: str, description: str, input_schema: Dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema
    
    def to_openai_schema(self) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema
            }
        }


class ToolExecutor:
    def __init__(self, workspace: str = "workspace"):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.results_history = []
    
    def execute(self, tool_call: ToolCall) -> str:
        name = tool_call.name.lower()
        args = tool_call.arguments
        
        self.results_history.append({
            "tool": name,
            "args": args
        })
        
        try:
            if name == "read":
                return self._read_file(args.get("path", ""))
            elif name == "write":
                return self._write_file(args.get("path", ""), args.get("content", ""))
            elif name == "bash":
                return self._bash(args.get("command", ""))
            elif name == "str_replace_editor":
                return self._str_replace(args.get("path", ""), args.get("old_str", ""), args.get("new_str", ""))
            elif name == "insert":
                return self._insert(args.get("path", ""), args.get("content", ""), args.get("at_line", 0))
            elif name == "search_replace":
                return self._search_replace(args.get("path", ""), args.get("search", ""), args.get("replace", ""))
            elif name == "glob":
                return self._glob(args.get("pattern", "*"))
            elif name == "grep":
                return self._grep(args.get("pattern", ""), args.get("path", "."))
            elif name == "lsp_run_tests":
                return self._run_tests(args.get("path", "."))
            else:
                return f"[ERROR] Unknown tool: {name}"
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def _read_file(self, path: str) -> str:
        full_path = self.workspace / path if not os.path.isabs(path) else path
        if not full_path.exists():
            return f"[ERROR] File not found: {path}"
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def _write_file(self, path: str, content: str) -> str:
        full_path = self.workspace / path if not os.path.isabs(path) else path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[SUCCESS] Wrote {len(content)} chars to {path}"
    
    def _bash(self, command: str) -> str:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(self.workspace)
        )
        output = result.stdout.strip() or result.stderr.strip()
        if result.returncode != 0:
            return f"[ERROR] Exit {result.returncode}: {output[:500]}"
        return output[:3000]
    
    def _str_replace(self, path: str, old: str, new: str) -> str:
        content = self._read_file(path)
        if content.startswith("[ERROR]"):
            return content
        new_content = content.replace(old, new)
        return self._write_file(path, new_content)
    
    def _insert(self, path: str, content: str, at_line: int) -> str:
        full_path = self.workspace / path
        if not full_path.exists():
            return self._write_file(path, content)
        lines = self._read_file(path).split("\n")
        lines.insert(at_line - 1 if at_line > 0 else 0, content)
        return self._write_file(path, "\n".join(lines))
    
    def _search_replace(self, path: str, search: str, replace: str) -> str:
        return self._str_replace(path, search, replace)
    
    def _glob(self, pattern: str) -> str:
        files = list(self.workspace.glob(pattern))
        return "\n".join([str(f.relative_to(self.workspace)) for f in files])
    
    def _grep(self, pattern: str, path: str = ".") -> str:
        import re
        matches = []
        for p in self.workspace.rglob("*"):
            if p.is_file():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.split("\n"), 1):
                        if re.search(pattern, line):
                            matches.append(f"{p}:{i}: {line[:100]}")
                except:
                    pass
        return "\n".join(matches[:50])
    
    def _run_tests(self, path: str) -> str:
        return self._bash("pytest --tb=short -v 2>&1 || echo 'No tests found'")


class MiniSWEAgent:
    def __init__(self, 
                 model: str = "ollama/qwen2.5-coder:14b",
                 workspace: str = "workspace"):
        self.model = model
        self.workspace = workspace
        self.executor = ToolExecutor(workspace)
        self.tools = self._create_tools()
        self.messages = []
        self.max_iterations = 50
        self.state = AgentState.IDLE
    
    def _create_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name="read",
                description="Read a file from the workspace. Returns the content.",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "Relative path to file"}},
                    "required": ["path"]
                }
            ),
            ToolDefinition(
                name="write",
                description="Write content to a file in the workspace. Creates or overwrites.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                }
            ),
            ToolDefinition(
                name="bash",
                description="Run a shell command. Returns stdout/stderr.",
                input_schema={
                    "type": "object",
                    "properties": {"command": {"type": "string", "description": "Command to run"}},
                    "required": ["command"]
                }
            ),
            ToolDefinition(
                name="str_replace_editor",
                description="Edit a file by replacing old string with new string.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old_str": {"type": "string"},
                        "new_str": {"type": "string"}
                    },
                    "required": ["path", "old_str", "new_str"]
                }
            ),
            ToolDefinition(
                name="glob",
                description="List files matching a glob pattern.",
                input_schema={
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"]
                }
            ),
            ToolDefinition(
                name="grep",
                description="Search for pattern in files.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": {"type": "string"}},
                    "required": ["pattern"]
                }
            ),
            ToolDefinition(
                name="lsp_run_tests",
                description="Run tests in the workspace.",
                input_schema={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": []
                }
            )
        ]
    
    def get_tool_schemas(self) -> List[Dict]:
        return [t.to_openai_schema() for t in self.tools]
    
    def run(self, task: str) -> Dict:
        print(f"\n[AGENT] Task: {task}")
        
        self.messages = [{
            "role": "system",
            "content": f"""You are an autonomous coding agent. You have tools to read/write files and run commands.

Available tools: {', '.join([t.name for t in self.tools])}

Workspace: {self.workspace}

For each step:
1. Think about what to do
2. Call appropriate tool
3. Analyze result
4. Repeat until task is done

When task is complete, say "Task completed successfully" or provide the final result."""
        }, {
            "role": "user", 
            "content": task
        }]
        
        for i in range(self.max_iterations):
            self.state = AgentState.THINKING
            
            tool_calls = self._get_model_response()
            
            if not tool_calls:
                self.state = AgentState.DONE
                return {"status": "done", "message": self.messages[-1].get("content", "")}
            
            for tc in tool_calls:
                self.state = AgentState.EXECUTING
                result = self.executor.execute(tc)
                
                self.messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": tc.tool_use_id,
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}
                    }]
                })
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.tool_use_id,
                    "content": result
                })
                
                print(f"  [{tc.name}] {result[:100]}...")
                
                if "success" in result.lower() and "error" not in result.lower():
                    break
        
        self.state = AgentState.DONE
        return {"status": "max_iterations", "iterations": i + 1}
    
    def _get_model_response(self) -> List[ToolCall]:
        tools_json = json.dumps(self.get_tool_schemas())
        
        prompt = f"""Think step by step. Use a tool to complete the task.

Available tools (JSON schema):
{tools_json}

Current messages:
{json.dumps(self.messages[-3:] if len(self.messages) > 3 else self.messages)}

Output EXACTLY one tool call as JSON:
{{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}"""

        try:
            result = subprocess.run(
                f'ollama run {self.model} "{prompt}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            output = result.stdout.strip()
            
            tc = self._parse_tool_call(output)
            return [tc] if tc else []
            
        except Exception as e:
            print(f"[ERROR] {e}")
            return []
    
    def _parse_tool_call(self, text: str) -> Optional[ToolCall]:
        text = text.strip()
        
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    if "name" in data:
                        return ToolCall(
                            name=data["name"],
                            arguments=data.get("arguments", {}),
                            tool_use_id=f"call_{int(time.time())}"
                        )
                except:
                    pass
            
            if "read" in text.lower():
                parts = text.split()
                if len(parts) >= 2:
                    return ToolCall(name="read", arguments={"path": parts[1]}, tool_use_id=f"call_{int(time.time())}")
        
        return None


def run_mini_swe(task: str, model: str = "ollama/qwen2.5-coder:14b") -> Dict:
    agent = MiniSWEAgent(model=model)
    return agent.run(task)


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "Create a simple hello world script"
    result = run_mini_swe(task)
    print(f"\nResult: {result.get('status')}")