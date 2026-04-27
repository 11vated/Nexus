#!/usr/bin/env python3
"""
NEXUS COMMAND CENTER - Backend Server
Provides real-time API for the Nexus Dashboard
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
import threading
from datetime import datetime
import uuid

# Flask for web server
from flask import Flask, jsonify, request, Response, stream_with_context, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__, static_folder=os.path.dirname(__file__))
CORS(app)

DASHBOARD_DIR = os.path.dirname(__file__)

# ============================================
# DATA MODELS
# ============================================

class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTIVE = "active"
    WAITING = "waiting"

@dataclass
class Agent:
    id: str
    name: str
    role: str
    icon: str
    status: AgentStatus = AgentStatus.IDLE
    current_task: str = ""
    progress: int = 0
    model: str = "qwen2.5-coder:14b"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "icon": self.icon,
            "status": self.status.value,
            "current_task": self.current_task,
            "progress": self.progress,
            "model": self.model
        }

@dataclass
class Session:
    id: str
    command: str
    start_time: float
    tokens: int = 0
    files_modified: int = 0
    lines_generated: int = 0
    agents_used: List[str] = field(default_factory=list)

# ============================================
# STATE MANAGEMENT
# ============================================

class NexusState:
    """Central state for the Nexus system"""
    
    def __init__(self):
        self.agents = {
            "sprint": Agent("sprint", "Sprint Manager", "Project Management", "🏃"),
            "architect": Agent("architect", "Architect", "System Design", "🏗️"),
            "developer": Agent("developer", "Developer", "Code Generation", "💻"),
            "reviewer": Agent("reviewer", "Code Reviewer", "Quality Assurance", "�"),
        }
        self.sessions: Dict[str, Session] = {}
        self.current_session: Optional[Session] = None
        self.metrics = {
            "total_tokens": 0,
            "tasks_completed": 0,
            "files_modified": 0,
            "lines_generated": 0
        }
        self.terminal_lines: List[Dict] = []
        self.mcp_servers = {
            "filesystem": True,
            "memory": True,
            "ollama": True,
            "github": False
        }
    
    def add_terminal_line(self, type: str, content: str):
        """Add a line to the terminal output"""
        self.terminal_lines.append({
            "type": type,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # Keep last 100 lines
        self.terminal_lines = self.terminal_lines[-100:]
    
    def get_system_status(self) -> dict:
        """Get overall system status"""
        return {
            "ollama": self.check_ollama(),
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "metrics": self.metrics,
            "mcp": self.mcp_servers,
            "active_session": self.current_session is not None
        }
    
    def check_ollama(self) -> bool:
        """Check if Ollama is running"""
        try:
            result = subprocess.run(
                ["ollama", "list"], 
                capture_output=True, 
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

# Create global state
state = NexusState()

# ============================================
# OLLAMA INTEGRATION
# ============================================

async def stream_ollama(model: str, prompt: str, session: Session):
    """Stream response from Ollama"""
    
    try:
        proc = await asyncio.create_subprocess_exec(
            "ollama", "run", model, prompt,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        buffer = ""
        
        while True:
            char = await proc.stdout.read(1)
            if not char:
                break
            
            char = char.decode()
            buffer += char
            
            # Emit character for streaming
            yield {"type": "char", "content": char, "model": model}
            
            # Update tokens
            session.tokens += 1
            state.metrics["total_tokens"] += 1
            
            # Check for newlines to emit as words
            if char == '\n':
                if buffer.strip():
                    state.add_terminal_line("output", buffer.strip())
                    yield {"type": "word", "content": buffer.strip()}
                buffer = ""
        
        await proc.wait()
        
    except Exception as e:
        yield {"type": "error", "content": str(e)}

# ============================================
# MULTI-AGENT ORCHESTRATION
# ============================================

async def execute_goal(goal: str) -> AsyncIterator[dict]:
    """Execute a goal using the multi-agent system"""
    
    # Create session
    session = Session(
        id=str(uuid.uuid4())[:8],
        command=goal,
        start_time=time.time()
    )
    state.current_session = session
    state.sessions[session.id] = session
    
    yield {"type": "session_start", "session_id": session.id}
    state.add_terminal_line("system", f"[NEXUS] Starting session {session.id}")
    yield {"type": "system", "content": f"[NEXUS] Goal: {goal}"}
    
    # Phase 1: Sprint - Decompose
    state.agents["sprint"].status = AgentStatus.THINKING
    state.agents["sprint"].current_task = f"Decomposing: {goal}"
    yield {"type": "agent_update", "agent": state.agents["sprint"].to_dict()}
    
    state.add_terminal_line("system", "[Sprint Manager] Decomposing goal into tasks...")
    
    sprint_prompt = f"""You are a Sprint Manager. Break this goal into 5 specific tasks:

Goal: {goal}

Respond with a numbered list of tasks, one per line. Keep each task brief (5 words max)."""
    
    async for event in stream_ollama("deepseek-r1:7b", sprint_prompt, session):
        if event["type"] == "char":
            yield {"type": "stream", **event}
    
    state.agents["sprint"].status = AgentStatus.ACTIVE
    state.agents["sprint"].progress = 100
    state.agents["sprint"].current_task = "Completed task decomposition"
    yield {"type": "agent_update", "agent": state.agents["sprint"].to_dict()}
    
    # Phase 2: Architect - Design
    state.agents["architect"].status = AgentStatus.THINKING
    state.agents["architect"].current_task = "Designing system architecture"
    yield {"type": "agent_update", "agent": state.agents["architect"].to_dict()}
    
    state.add_terminal_line("system", "[Architect] Designing system architecture...")
    state.add_terminal_line("output", "[Architect] Technology Stack:")
    yield {"type": "system", "content": "[Architect] Designing architecture..."}
    
    architect_prompt = f"""You are a System Architect. Design the tech stack for:

{goal}

Respond with:
1. Technology stack (bullet points)
2. Key components (3-5 items)
3. Data flow (brief)"""

    async for event in stream_ollama("deepseek-r1:7b", architect_prompt, session):
        if event["type"] == "char":
            yield {"type": "stream", **event}
    
    state.agents["architect"].status = AgentStatus.ACTIVE
    state.agents["architect"].progress = 100
    yield {"type": "agent_update", "agent": state.agents["architect"].to_dict()}
    
    # Phase 3: Developer - Generate Code
    state.agents["developer"].status = AgentStatus.THINKING
    state.agents["developer"].current_task = "Generating code"
    yield {"type": "agent_update", "agent": state.agents["developer"].to_dict()}
    
    state.add_terminal_line("system", "[Developer] Generating code...")
    yield {"type": "system", "content": "[Developer] Writing code..."}
    
    dev_prompt = f"""You are a Senior Developer. Generate production-ready code for:

{goal}

Provide:
1. File structure
2. Key code files (show implementation)
3. Setup instructions"""

    async for event in stream_ollama("qwen2.5-coder:14b", dev_prompt, session):
        if event["type"] == "char":
            yield {"type": "stream", **event}
    
    state.agents["developer"].status = AgentStatus.ACTIVE
    state.agents["developer"].progress = 100
    state.agents["developer"].current_task = "Code generation complete"
    yield {"type": "agent_update", "agent": state.agents["developer"].to_dict()}
    
    # Phase 4: Reviewer
    state.agents["reviewer"].status = AgentStatus.THINKING
    state.agents["reviewer"].current_task = "Reviewing code"
    yield {"type": "agent_update", "agent": state.agents["reviewer"].to_dict()}
    
    state.add_terminal_line("system", "[Reviewer] Reviewing code...")
    yield {"type": "system", "content": "[Reviewer] Quality check..."}
    
    # Complete
    session.tokens = state.metrics["total_tokens"]
    state.metrics["tasks_completed"] += 1
    
    yield {"type": "session_complete", "session_id": session.id}
    state.add_terminal_line("system", f"[NEXUS] Session {session.id} complete!")
    
    # Reset agents
    for agent in state.agents.values():
        agent.status = AgentStatus.IDLE
        agent.progress = 0
        agent.current_task = "Waiting for task"
    
    state.current_session = None

# ============================================
# API ROUTES
# ============================================

@app.route('/')
def index():
    """Serve the main dashboard"""
    return send_from_directory(DASHBOARD_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory(DASHBOARD_DIR, filename)

@app.route('/api/status')
def get_status():
    """Get system status"""
    return jsonify(state.get_system_status())

@app.route('/api/agents')
def get_agents():
    """Get all agents"""
    return jsonify({k: v.to_dict() for k, v in state.agents.items()})

@app.route('/api/agents/<agent_id>', methods=['POST'])
def update_agent(agent_id):
    """Update agent state"""
    if agent_id not in state.agents:
        return jsonify({"error": "Agent not found"}), 404
    
    data = request.json
    agent = state.agents[agent_id]
    
    if "status" in data:
        agent.status = AgentStatus(data["status"])
    if "current_task" in data:
        agent.current_task = data["current_task"]
    if "progress" in data:
        agent.progress = data["progress"]
    if "model" in data:
        agent.model = data["model"]
    
    return jsonify(agent.to_dict())

@app.route('/api/models')
def get_models():
    """Get available Ollama models"""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        models = []
        for line in result.stdout.strip().split('\n')[1:]:
            if line.strip():
                parts = line.split()
                if parts:
                    models.append({
                        "name": parts[0],
                        "size": parts[1] if len(parts) > 1 else "Unknown"
                    })
        
        return jsonify(models)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/terminal')
def get_terminal():
    """Get terminal history"""
    return jsonify(state.terminal_lines[-50:])

@app.route('/api/execute', methods=['POST'])
def execute():
    """Execute a goal - streaming response"""
    data = request.json
    goal = data.get('goal', '')
    
    if not goal:
        return jsonify({"error": "No goal provided"}), 400
    
    def generate():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def run():
                async for event in execute_goal(goal):
                    yield f"data: {json.dumps(event)}\n\n"
            
            # Run the async generator
            gen = run()
            while True:
                try:
                    event = loop.run_until_complete(gen.__anext__())
                    yield f"data: {json.dumps(event)}\n\n"
                except StopAsyncIteration:
                    break
        finally:
            loop.close()
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/chat', methods=['POST'])
def chat():
    """Simple chat with Ollama"""
    data = request.json
    message = data.get('message', '')
    model = data.get('model', 'qwen2.5-coder:14b')
    
    if not message:
        return jsonify({"error": "No message provided"}), 400
    
    try:
        result = subprocess.run(
            ["ollama", "run", model, message],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        return jsonify({
            "response": result.stdout or result.stderr,
            "model": model
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/metrics')
def get_metrics():
    """Get system metrics"""
    return jsonify(state.metrics)

@app.route('/api/vision/analyze', methods=['POST'])
def vision_analyze():
    """Analyze an uploaded image"""
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
    
    file = request.files['image']
    analysis_type = request.form.get('type', 'general')  # general, error, ui, crash, mockup, architecture
    
    if file.filename == '':
        return jsonify({"error": "No image selected"}), 400
    
    # Save the uploaded file temporarily
    import tempfile
    import os
    
    temp_dir = tempfile.gettempdir()
    image_path = os.path.join(temp_dir, f"vision_{int(time.time())}_{file.filename}")
    file.save(image_path)
    
    try:
        # Run vision analysis using subprocess (synchronous)
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        
        # Build the command
        cmd = [
            sys.executable, "-c",
            f"""
import asyncio
import sys
sys.path.insert(0, r'{os.path.dirname(os.path.dirname(__file__))}')
from ultimate_agent import VisionAgent

async def main():
    agent = VisionAgent()
    if '{analysis_type}' == 'error':
        result = await agent.debug_from_screenshot(r'{image_path}', 'error')
    elif '{analysis_type}' == 'ui':
        result = await agent.debug_from_screenshot(r'{image_path}', 'ui')
    elif '{analysis_type}' == 'crash':
        result = await agent.debug_from_screenshot(r'{image_path}', 'crash')
    elif '{analysis_type}' == 'mockup':
        result = await agent.review_ui_mockup(r'{image_path}')
    elif '{analysis_type}' == 'architecture':
        result = await agent.describe_architecture(r'{image_path}')
    else:
        result = await agent.analyze_screenshot(r'{image_path}')
    print(result)

asyncio.run(main())
"""
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        # Parse result (it prints a dict representation)
        try:
            import ast
            analysis_result = ast.literal_eval(result.stdout) if result.stdout else {"error": "No result"}
        except:
            analysis_result = {"raw_output": result.stdout, "error": result.stderr}
        
        return jsonify({
            "success": True,
            "type": analysis_type,
            "result": analysis_result,
            "image_path": image_path
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Cleanup temp file
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except:
                pass

@app.route('/api/vision/live/start', methods=['POST'])
def start_live_view():
    """Start live screen watching"""
    try:
        data = request.json or {}
        monitor = data.get('monitor', 1)
        
        # Start screen capture in background thread
        import threading
        import queue
        
        capture_queue = queue.Queue()
        
        def capture_loop():
            try:
                import mss
                import numpy as np
                
                with mss.mss() as sct:
                    monitor_info = sct.monitors[monitor]
                    
                    while True:
                        screenshot = sct.grab(monitor_info)
                        img_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
                        
                        # Encode as base64 for transmission
                        import base64
                        b64 = base64.b64encode(img_bytes).decode('utf-8')
                        
                        capture_queue.put({
                            "image": b64,
                            "timestamp": time.time()
                        })
                        
                        time.sleep(2)  # Capture every 2 seconds
                        
            except Exception as e:
                capture_queue.put({"error": str(e)})
        
        thread = threading.Thread(target=capture_loop, daemon=True)
        thread.start()
        
        # Store queue in global state
        state.live_capture = capture_queue
        
        return jsonify({"success": True, "message": "Live capture started"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vision/live/frame')
def get_live_frame():
    """Get current frame from live capture"""
    if not hasattr(state, 'live_capture') or state.live_capture.empty():
        return jsonify({"error": "No live capture", "image": None})
    
    try:
        # Get latest frame (drain queue)
        frame = {}
        while not state.live_capture.empty():
            frame = state.live_capture.get_nowait()
        
        if "error" in frame:
            return jsonify({"error": frame["error"]})
        
        return jsonify(frame)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vision/live/analyze', methods=['POST'])
def analyze_live_frame():
    """Analyze current live frame"""
    if not hasattr(state, 'live_capture') or state.live_capture.empty():
        return jsonify({"error": "No live capture"})
    
    try:
        # Get latest frame
        frame = {}
        while not state.live_capture.empty():
            frame = state.live_capture.get_nowait()
        
        if "error" in frame:
            return jsonify({"error": frame["error"]})
        
        # Analyze with vision model
        image_b64 = frame.get("image", "")
        
        cmd = [
            sys.executable, "-c",
            f"""
import asyncio
import base64

async def main():
    prompt = \"\"\"Analyze this screen capture and provide:
    1. What's currently displayed
    2. Any important changes from before
    3. Any errors or warnings visible
    4. What application is in focus
    
    Be concise.\"\"\"
    
    # Decode image for analysis
    img_data = base64.b64decode('{image_b64}')
    
    # Call llava via subprocess
    import subprocess
    proc = await asyncio.create_subprocess_exec(
        "ollama", "run", "llava", prompt,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, _ = await asyncio.wait_for(proc.communicate(timeout=60), timeout=90)
    print(stdout.decode())

asyncio.run(main())
"""
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        return jsonify({
            "timestamp": frame.get("timestamp"),
            "analysis": result.stdout if result.returncode == 0 else result.stderr
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vision/live/stop', methods=['POST'])
def stop_live_view():
    """Stop live capture"""
    if hasattr(state, 'live_capture'):
        delattr(state, 'live_capture')
    return jsonify({"success": True, "message": "Live capture stopped"})

# ============================================
# COMPUTER CONTROL API
# ============================================

@app.route('/api/computer/action', methods=['POST'])
def computer_action():
    """Execute a computer action"""
    data = request.json
    action = data.get('action', '')
    x = data.get('x', 0)
    y = data.get('y', 0)
    extra = data.get('extra', '')
    
    try:
        # Use pyautogui via subprocess
        cmd = []
        
        if action == 'click':
            cmd = [sys.executable, "-c", f"import pyautogui; pyautogui.click({x}, {y})"]
        elif action == 'right_click':
            cmd = [sys.executable, "-c", f"import pyautogui; pyautogui.click({x}, {y}, button='right')"]
        elif action == 'double_click':
            cmd = [sys.executable, "-c", f"import pyautogui; pyautogui.doubleClick({x}, {y})"]
        elif action == 'scroll_up':
            cmd = [sys.executable, "-c", "import pyautogui; pyautogui.scroll(3)"]
        elif action == 'scroll_down':
            cmd = [sys.executable, "-c", "import pyautogui; pyautogui.scroll(-3)"]
        elif action == 'type':
            cmd = [sys.executable, "-c", f"import pyautogui; pyautogui.write('{extra}')"]
        elif action == 'hotkey':
            keys = extra.split('+')
            keys_str = ', '.join([f"'{k}'" for k in keys])
            cmd = [sys.executable, "-c", f"import pyautogui; pyautogui.hotkey({keys_str})"]
        else:
            return jsonify({"error": "Unknown action"}), 400
        
        if cmd:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0:
                return jsonify({"success": True, "message": f"{action} executed"})
            else:
                return jsonify({"error": result.stderr.decode()[:100]})
        
        return jsonify({"error": "No command generated"}), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/computer/goal', methods=['POST'])
def computer_goal():
    """Execute a goal using AI planning"""
    data = request.json
    goal = data.get('goal', '')
    
    if not goal:
        return jsonify({"error": "No goal provided"}), 400
    
    try:
        # Run computer use agent to achieve goal
        cmd = [
            sys.executable, "-c",
            f"""
import asyncio
import sys
sys.path.insert(0, r'{os.path.dirname(os.path.dirname(__file__))}')
from computer_use import ComputerUseAgent

async def main():
    agent = ComputerUseAgent()
    result = await agent.execute_goal("{goal}", max_steps=5)
    print(result)

asyncio.run(main())
"""
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # Parse result
            try:
                import ast
                result_data = ast.literal_eval(result.stdout) if result.stdout else {}
            except:
                result_data = {"raw": result.stdout[:500]}
            
            return jsonify({
                "success": result_data.get("success", False),
                "steps": result_data.get("steps", 0),
                "message": "Goal execution complete"
            })
        else:
            return jsonify({
                "error": result.stderr.decode()[:200] if result.stderr else "Execution failed",
                "success": False
            })
        
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout - goal took too long", "success": False}), 500
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/computer/info')
def computer_info():
    """Get computer state info"""
    try:
        cmd = [sys.executable, "-c", """
import pyautogui
import pygetwindow as gw
width, height = pyautogui.size()
active = gw.getActiveWindow()
print(f'{width},{height},{active.title if active else "None"}')
"""]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            return jsonify({
                "screen_size": f"{parts[0]}x{parts[1]}",
                "active_window": parts[2] if len(parts) > 2 else "Unknown"
            })
    except Exception as e:
        pass
    
    return jsonify({"error": "Could not get info"})

# ============================================
# GIT API
# ============================================

@app.route('/api/git/status')
def git_status():
    """Get git status"""
    try:
        cmd = [sys.executable, "-c", """
import sys
sys.path.insert(0, r'{0}')
from nexus_suite import GitIntegration
git = GitIntegration('.')
import json
print(json.dumps(git.status()))
""".format(os.path.dirname(os.path.dirname(__file__)))]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        return jsonify({"error": result.stderr[:100]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/git/commit', methods=['POST'])
def git_commit():
    """Commit changes"""
    data = request.json
    message = data.get('message', 'Update')
    
    try:
        cmd = [sys.executable, "-c", """
import sys
sys.path.insert(0, r'{0}')
from nexus_suite import GitIntegration
git = GitIntegration('.')
import json
print(json.dumps(git.commit('{1}')))
""".format(os.path.dirname(os.path.dirname(__file__)), message)]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        return jsonify({"error": result.stderr[:100]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/git/log')
def git_log():
    """Get commit log"""
    try:
        cmd = [sys.executable, "-c", """
import sys
sys.path.insert(0, r'{0}')
from nexus_suite import GitIntegration
git = GitIntegration('.')
import json
print(json.dumps(git.log(10)))
""".format(os.path.dirname(os.path.dirname(__file__)))]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# TERMINAL API
# ============================================

@app.route('/api/terminal/exec', methods=['POST'])
def terminal_exec():
    """Execute terminal command"""
    data = request.json
    command = data.get('command', '')
    
    if not command:
        return jsonify({"error": "No command"}), 400
    
    try:
        # Simple shell execution
        if sys.platform == "win32":
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        else:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        
        return jsonify({
            "output": proc.stdout,
            "error": proc.stderr if proc.returncode != 0 else None,
            "exit_code": proc.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout", "exit_code": -1}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# MEMORY API
# ============================================

@app.route('/api/memory/project')
def memory_project():
    """Get project memory"""
    try:
        cmd = [sys.executable, "-c", """
import sys
sys.path.insert(0, r'{0}')
from nexus_suite import ProjectMemory
import json
mem = ProjectMemory()
project = mem.get_project('.')
if project:
    print(json.dumps({{'name': project.name, 'language': project.language, 'framework': project.framework, 'dependencies': project.dependencies[:10]}}))
else:
    print('null')
""".format(os.path.dirname(os.path.dirname(__file__)))]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                return jsonify(json.loads(result.stdout))
            except:
                return jsonify({"name": "Unknown"})
        return jsonify({"name": "Not analyzed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memory/analyze', methods=['POST'])
def memory_analyze():
    """Analyze current project"""
    try:
        cmd = [sys.executable, "-c", """
import sys
sys.path.insert(0, r'{0}')
from nexus_suite import ProjectMemory
import json
mem = ProjectMemory()
profile = mem.analyze_project('.')
if profile:
    print(json.dumps({{'success': True, 'name': profile.name, 'language': profile.language}}))
else:
    print(json.dumps({{'success': False}}))
""".format(os.path.dirname(os.path.dirname(__file__)))]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        return jsonify({"success": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# SANDBOX API
# ============================================

@app.route('/api/sandbox/exec', methods=['POST'])
def sandbox_exec():
    """Execute code in sandbox"""
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'python')
    
    if not code:
        return jsonify({"error": "No code"}), 400
    
    try:
        cmd = [sys.executable, "-c", """
import sys
import asyncio
sys.path.insert(0, r'{0}')
from nexus_suite import CodeSandbox
import json

async def main():
    sandbox = CodeSandbox()
    result = await sandbox.execute('''{1}''', '{2}')
    print(json.dumps(result))

asyncio.run(main())
""".format(os.path.dirname(os.path.dirname(__file__)), code.replace("'", "''"), language)]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        return jsonify({"error": result.stderr[:200]})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# AUTOPILOT API
# ============================================

@app.route('/api/autopilot/health', methods=['GET'])
def autopilot_health():
    """Get health status of all services"""
    try:
        cmd = [sys.executable, os.path.join(DASHBOARD_DIR, "..", "nexus_autopilot.py"), "--health-check"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        return jsonify({"error": "Health check failed"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/autopilot/schedule', methods=['GET'])
def autopilot_schedule():
    """Get scheduled tasks"""
    try:
        cmd = [sys.executable, os.path.join(DASHBOARD_DIR, "..", "nexus_autopilot.py"), "--schedule"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return jsonify({"output": result.stdout})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/autopilot/schedule', methods=['POST'])
def autopilot_add_schedule():
    """Add a scheduled task"""
    data = request.json
    task = data.get('task', '')
    cron = data.get('cron', '*/5 * * * *')
    try:
        cmd = [sys.executable, os.path.join(DASHBOARD_DIR, "..", "nexus_autopilot.py"), "--add-schedule", task, cron]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return jsonify({"success": result.returncode == 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/autopilot/snapshot', methods=['POST'])
def autopilot_snapshot():
    """Create rollback snapshot"""
    try:
        cmd = [sys.executable, os.path.join(DASHBOARD_DIR, "..", "nexus_autopilot.py"), "--snapshot"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return jsonify({"success": result.returncode == 0, "message": result.stdout.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/autopilot/snapshots', methods=['GET'])
def autopilot_list_snapshots():
    """List rollback snapshots"""
    try:
        from nexus_autopilot import RollbackSystem
        rollback = RollbackSystem()
        return jsonify({"snapshots": rollback.list_snapshots()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/autopilot/rollback/<name>', methods=['POST'])
def autopilot_rollback(name):
    """Restore from snapshot"""
    try:
        cmd = [sys.executable, os.path.join(DASHBOARD_DIR, "..", "nexus_autopilot.py"), "--rollback", name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return jsonify({"success": result.returncode == 0, "output": result.stdout})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/autopilot/errors', methods=['GET'])
def autopilot_errors():
    """Get error patterns"""
    try:
        cmd = [sys.executable, os.path.join(DASHBOARD_DIR, "..", "nexus_autopilot.py"), "--errors"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return jsonify({"output": result.stdout})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/autopilot/context', methods=['GET'])
def autopilot_context():
    """Get context memory"""
    try:
        cmd = [sys.executable, os.path.join(DASHBOARD_DIR, "..", "nexus_autopilot.py"), "--context"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return jsonify({"output": result.stdout})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    print("NEXUS COMMAND CENTER v2.0")
    print("=" * 50)
    print("Starting NEXUS server...")
    print("Open http://localhost:5555 in your browser")
    print("Press Ctrl+C to stop\n")
    
    app.run(host='0.0.0.0', port=5555, debug=True)