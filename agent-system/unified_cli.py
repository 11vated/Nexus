#!/usr/bin/env python3
"""
ULTIMATE CODING WORKSTATION - Unified CLI Interface
Brings together: OpenCode, Aider, Goose, Profound System, MCPs

Features:
- Unified command interface
- Model switching on the fly
- Project context management
- MCP server management
- Code intelligence (LSP integration)
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List, Dict
import json
import time

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

class WorkstationCLI:
    """Unified CLI for all AI coding tools"""
    
    def __init__(self):
        self.workspace = Path("C:/Users/11vat/Desktop/Copilot/Aider-Local-llm-agent")
        self.current_tool = None
        self.current_model = "qwen2.5-coder:14b"
        self.ollama_running = False
        self.mcp_servers = {}
        
        # Available tools
        self.tools = {
            "opencode": {
                "path": "C:/Users/11vat/AppData/Local/OpenCode/OpenCode.exe",
                "description": "AI-native IDE with MCP support",
                "model_option": True
            },
            "aider": {
                "path": str(self.workspace / "venv_aider/Scripts/python.exe"),
                "description": "Terminal-first AI pair programmer",
                "args": ["-m", "aider", "--model", "qwen2.5-coder:14b"],
                "model_option": True
            },
            "goose": {
                "path": "C:/Users/11vat/Desktop/Goose-win32-x64/dist-windows/Goose.exe",
                "description": "Autonomous CLI agent",
                "model_option": True
            },
            "profound": {
                "description": "Multi-agent orchestrator (our system)",
                "model_option": True
            }
        }
        
        # Models for different tasks - ALL MODELS SUPPORTED
        self.models = {
            # Code generation (best)
            "code": [
                "qwen2.5-coder:14b",     # Best overall
                "qwen2.5-coder:7b",     # Fast
                "codellama",           # Meta
                "gpt-5-nano",          # NEW
                "minimax-max-m2.5-free", # NEW
                "bigpickle",           # NEW
                "hy3-preview-free",    # NEW
                "nemotron-super-3b",   # NEW
            ],
            # Reasoning / Debugging
            "reason": [
                "deepseek-r1:7b",       # Best reasoning
                "deepseek-r1:1.5b",     # Fast
                "nemotron-super-3b",    # NEW
            ],
            # Fast / Quick tasks  
            "fast": [
                "qwen2.5-coder:7b",
                "deepseek-r1:1.5b",
                "ling-2.6-flash-free",  # NEW
                "gpt-5-nano",          # NEW
                "bartowski/llama-3.2-1b-instruct-q4_k_m",  # NEW
            ],
            # Vision
            "vision": [
                "llava",
                "moondream",
            ],
            # All available
            "all": [
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
                "bartowski/llama-3.2-1b-instruct-q4_k_m",
                "llava",
                "moondream",
                "dolphin-mistral",
            ]
        }
    
    def print_header(self):
        """Print ASCII art header"""
        print(f"""
{GREEN}{BOLD}
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   █████╗ ██╗      ██████╗  ██████╗ ██████╗ ██╗████████╗██╗  ██╗   ║
║  ██╔══██╗██║     ██╔════╝ ██╔═══██╗██╔══██╗██║╚══██╔══╝██║  ██║   ║
║  ███████║██║     ██║  ███╗██║   ██║██████╔╝██║   ██║   ███████║   ║
║  ██╔══██║██║     ██║   ██║██║   ██║██╔══██╗██║   ██║   ██╔══██║   ║
║  ██║  ██║███████╗╚██████╔╝╚██████╔╝██║  ██║██║   ██║   ██║  ██║   ║
║  ╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝   ╚═╝   ╚═╝  ╚═╝   ║
║                                                                      ║
║              ULTIMATE LOCAL AI WORKSTATION v2.0                     ║
║                  (OpenCode + Aider + Goose + MCP)                   ║
╚══════════════════════════════════════════════════════════════════════╝
{RESET}
""")
    
    def print_status(self):
        """Print current status"""
        print(f"{CYAN}─── Current Status ───{RESET}")
        
        # Check Ollama
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.ollama_running = True
                print(f"  {GREEN}●{RESET} Ollama: Running")
                # Count models
                lines = result.stdout.strip().split("\n")
                model_count = len([l for l in lines[1:] if l.strip()])
                print(f"    Models: {model_count}")
            else:
                print(f"  {YELLOW}●{RESET} Ollama: Not running")
        except:
            print(f"  {RED}●{RESET} Ollama: Not installed")
        
        # Current tool
        print(f"  Current Tool: {MAGENTA}{self.current_tool or 'None'}{RESET}")
        print(f"  Current Model: {BLUE}{self.current_model}{RESET}")
        
        # MCP servers
        print(f"  MCP Servers: {len(self.mcp_servers)} active")
        
        print()
    
    def print_menu(self):
        """Print main menu"""
        print(f"""
{BOLD}═══ TOOLS ═══{RESET}
  {GREEN}[1]{RESET} OpenCode Desktop      - AI-native IDE with MCP
  {GREEN}[2]{RESET} Aider                 - Terminal-first pair programmer  
  {GREEN}[3]{RESET} Goose                 - Autonomous CLI agent
  {GREEN}[4]{RESET} Profound System       - Multi-agent orchestrator (ours)

{BOLD}═══ MODELS ═══{RESET}
  {BLUE}[C]{RESET} Code Models            - qwen2.5-coder, codellama
  {BLUE}[R]{RESET} Reasoning Models       - deepseek-r1
  {BLUE}[U]{RESET} Uncensored Models      - dolphin-mistral, mixtral
  {BLUE}[F]{RESET} Fast Models            - Quick tasks, 7B variants
  {BLUE}[M]{RESET} Model Info             - Show all available models

{BOLD}═══ UTILITIES ═══{RESET}
  {YELLOW}[L]{RESET} List Ollama Models
  {YELLOW}[O]{RESET} Ollama Chat (direct)
  {YELLOW}[S]{RESET} System Status
  {YELLOW}[P]{RESET} Project Analyzer
  {YELLOW}[T]{RESET} MCP Server Manager

{BOLD}═══ QUICK ACTIONS ═══{RESET}
  {MAGENTA}[G]{RESET} Generate Code       - Ask AI to generate code
  {MAGENTA}[A]{RESET} Analyze Codebase    - Deep codebase analysis
  {MAGENTA}[D]{RESET} Debug Problem       - AI debugging assistant

{RESET}{BOLD}═══ SYSTEM ═══{RESET}
  {RESET}[Q] Quit
""")
    
    def list_models(self):
        """List all available Ollama models"""
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
            print(f"\n{GREEN}{BOLD}═══ Available Models ═══{RESET}\n")
            print(result.stdout)
        except Exception as e:
            print(f"Error listing models: {e}")
    
    def run_opencode(self, model: Optional[str] = None):
        """Launch OpenCode"""
        model = model or self.current_model
        print(f"Launching OpenCode with {model}...")
        try:
            subprocess.Popen([
                "C:/Users/11vat/AppData/Local/OpenCode/OpenCode.exe",
                "--model", f"ollama/{model}"
            ])
            print(f"{GREEN}OpenCode launched!{RESET}")
        except Exception as e:
            print(f"Error launching OpenCode: {e}")
    
    def run_aider(self, model: Optional[str] = None):
        """Launch Aider"""
        model = model or self.current_model
        print(f"Launching Aider with {model}...")
        try:
            os.chdir(self.workspace)
            # Activate venv and run aider
            subprocess.run([
                "cmd", "/c", 
                f"venv_aider\\Scripts\\activate && aider --model qwen2.5-coder:14b"
            ], shell=True)
        except Exception as e:
            print(f"Error launching Aider: {e}")
    
    def run_profound(self):
        """Launch Profound System"""
        print("Launching Profound Multi-Agent System...")
        try:
            subprocess.run([
                sys.executable, 
                str(self.workspace / "agent-system" / "profound_system.py")
            ])
        except Exception as e:
            print(f"Error launching Profound: {e}")
    
    def run_ollama_chat(self, model: Optional[str] = None):
        """Direct Ollama chat"""
        model = model or self.current_model
        print(f"Starting chat with {model}... (Ctrl+C to exit)")
        try:
            subprocess.run(["ollama", "run", model])
        except KeyboardInterrupt:
            print("\nExiting chat...")
    
    def analyze_project(self, path: str = "."):
        """Analyze a project with AI"""
        print(f"Analyzing project at {path}...")
        
        # Get file count and structure
        project_path = Path(path)
        if not project_path.exists():
            project_path = self.workspace / "projects" / path
        
        stats = {
            "files": 0,
            "lines": 0,
            "languages": {},
            "largest_files": []
        }
        
        for f in project_path.rglob("*"):
            if f.is_file() and not any(x in str(f) for x in [".git", "node_modules", "__pycache__", ".venv"]):
                try:
                    stats["files"] += 1
                    ext = f.suffix or "noext"
                    stats["languages"][ext] = stats["languages"].get(ext, 0) + 1
                    
                    # Count lines
                    try:
                        lines = len(f.read_text(errors="ignore").splitlines())
                        stats["lines"] += lines
                        stats["largest_files"].append((str(f), lines))
                    except: pass
                except: pass
        
        # Sort largest files
        stats["largest_files"].sort(key=lambda x: x[1], reverse=True)
        stats["largest_files"] = stats["largest_files"][:10]
        
        print(f"\n{GREEN}{BOLD}═══ Project Analysis ═══{RESET}")
        print(f"  Files: {stats['files']}")
        print(f"  Lines of Code: {stats['lines']:,}")
        print(f"\n  Languages:")
        for ext, count in sorted(stats["languages"].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {ext}: {count} files")
        
        print(f"\n  Largest Files:")
        for f, lines in stats["largest_files"]:
            print(f"    {lines:6,} - {f}")
        
        # Ask AI for analysis
        print(f"\n{YELLOW}Would you like AI analysis of this project? (y/n){RESET}")
        if input("> ").lower() == "y":
            prompt = f"""Analyze this codebase and provide:
1. Architecture overview
2. Key technologies used
3. Potential issues or debt
4. Recommendations for improvement

Project stats: {stats['files']} files, {stats['lines']} lines of code
Languages: {stats['languages']}"""

            # Run with reasoning model
            print(f"\nRunning analysis with deepseek-r1:7b...")
            subprocess.run(["ollama", "run", "deepseek-r1:7b", prompt])
    
    def generate_code(self, prompt: str):
        """Generate code from prompt"""
        print(f"{GREEN}Generating code...{RESET}")
        print(f"Prompt: {prompt[:100]}...")
        
        # Select best model for code
        model = "qwen2.5-coder:14b"
        
        full_prompt = f"""You are a senior software engineer. Generate production-ready code.

Task: {prompt}

Requirements:
- Use TypeScript/JavaScript with proper typing
- Follow best practices
- Include error handling
- Add comments for complex logic

Generate the complete code:"""

        try:
            subprocess.run(["ollama", "run", model, full_prompt])
        except KeyboardInterrupt:
            print("\nStopping generation...")
    
    def mcp_manager(self):
        """Manage MCP servers"""
        print(f"""
{GREEN}{BOLD}═══ MCP Server Manager ═══{RESET}

Current MCP servers configured:
  - filesystem (OpenCode)
  - memory (OpenCode)  
  - ollama (Custom)

Available to install:
  - github (npx @modelcontextprotocol/server-github)
  - playwright (npx @modelcontextprotocol/server-playwright)
  - brave-search (npx @modelcontextprotocol/server-brave-search)
  - postgres (npx @modelcontextprotocol/server-postgres)

Actions:
  [1] Start all MCP servers
  [2] Install new MCP server
  [3] Configure MCP in OpenCode
  [4] View MCP logs

  [Q] Back to main menu
""")
        
        choice = input("> ").lower()
        
        if choice == "1":
            print("Starting MCP servers...")
            # Start filesystem MCP
            subprocess.Popen([
                "npx", "-y", "@modelcontextprotocol/server-filesystem",
                str(self.workspace)
            ])
            print(f"{GREEN}MCP servers started!{RESET}")
        
        elif choice == "2":
            server = input("Server name to install (github/playwright/brave-search/postgres): ")
            print(f"Installing {server}...")
            subprocess.run(["npm", "install", "-g", f"@modelcontextprotocol/server-{server}"])
            print(f"{GREEN}Installed!{RESET}")
    
    def run(self):
        """Main CLI loop"""
        while True:
            self.print_header()
            self.print_status()
            self.print_menu()
            
            choice = input(f"{CYAN}Select option: {RESET}").lower().strip()
            
            if choice == "q":
                print("Goodbye!")
                break
            
            elif choice == "1":
                self.run_opencode()
            elif choice == "2":
                self.run_aider()
            elif choice == "3":
                print("Launching Goose...")
                subprocess.Popen([
                    "C:/Users/11vat/Desktop/Goose-win32-x64/dist-windows/Goose.exe"
                ])
            elif choice == "4":
                self.run_profound()
            
            elif choice == "c":
                self.print_model_group("code")
                model = input("Select model: ")
                if model in self.models["code"]:
                    self.current_model = model
                    print(f"Model set to {model}")
            elif choice == "r":
                self.print_model_group("reason")
                model = input("Select model: ")
                if model in self.models["reason"]:
                    self.current_model = model
            elif choice == "u":
                self.print_model_group("uncensored")
                model = input("Select model: ")
                if model in self.models["uncensored"]:
                    self.current_model = model
            elif choice == "f":
                self.print_model_group("fast")
                model = input("Select model: ")
                if model in self.models["fast"]:
                    self.current_model = model
            elif choice == "m":
                self.list_models()
                input("\nPress Enter to continue...")
            
            elif choice == "l":
                self.list_models()
            elif choice == "o":
                self.run_ollama_chat()
            elif choice == "s":
                self.print_status()
                input("\nPress Enter to continue...")
            elif choice == "p":
                path = input("Project path (or Enter for default): ") or "."
                self.analyze_project(path)
            elif choice == "t":
                self.mcp_manager()
            
            elif choice == "g":
                prompt = input("Describe what you want to build: ")
                if prompt:
                    self.generate_code(prompt)
            elif choice == "a":
                self.analyze_project()
            elif choice == "d":
                problem = input("Describe the bug/error: ")
                if problem:
                    prompt = f"""Debug this problem and provide a solution:

{problem}

Provide:
1. Root cause analysis
2. Suggested fix
3. Prevention tips"""
                    subprocess.run(["ollama", "run", "deepseek-r1:7b", prompt])
            
            # Clear screen for next iteration
            print("\n")
    
    def print_model_group(self, group: str):
        """Print models in a group"""
        print(f"\n{GREEN}{BOLD}═══ {group.upper()} Models ═══{RESET}")
        for m in self.models.get(group, []):
            print(f"  - {m}")

def main():
    cli = WorkstationCLI()
    cli.run()

if __name__ == "__main__":
    main()