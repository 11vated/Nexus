# NEXUS Command Center

The ultimate jaw-dropping AI coding dashboard - a production-grade interface for your autonomous coding workstation.

![NEXUS Dashboard](https://img.shields.io/badge/Version-2.0-00f0ff?style=for-the-badge)

## Features

### 🎨 Cyberpunk Interface
- Deep space dark theme with neon accents
- Animated grid background with particle effects
- Glowing borders and scanline overlays
- Real-time neural network visualization

### 🤖 Multi-Agent Visualization
- See all 4 agents working in parallel
- Real-time status: Idle, Thinking, Active
- Progress bars for each agent
- Live task descriptions

### ⚡ Real-Time Terminal
- Streaming code generation output
- Syntax highlighted terminal
- Command history
- Multiple tabs (Terminal, Output, Logs)

### 📊 System Metrics
- Tokens generated
- Tasks completed
- Files modified
- Lines of code
- Tool usage graphs
- Neural thought visualization

### 🧠 Model Selection
- One-click model switching
- Visual model cards
- Model status indicators
- Code, Reasoning, Uncensored, Fast categories

## Quick Start

### Option 1: Ultimate Launcher (Recommended)
```bash
agent-system\NEXUS_ULTIMATE.bat
```
Then press `1` for NEXUS Dashboard

### Option 2: Direct Launch
```bash
cd agent-system/nexus_dashboard
pip install flask flask-cors
python server.py
```
Open http://localhost:5555

### Option 3: Static Dashboard
```bash
cd agent-system/nexus_dashboard
python -m http.server 5556
```
Open http://localhost:5556

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      NEXUS DASHBOARD                        │
│                     (Browser - UI)                          │
├─────────────────────────────────────────────────────────────┤
│  Header        │ Sidebar │ Main    │ Metrics │ Models     │
│  - Logo        │ - Nav   │ Terminal│ - Stats │ - Cards    │
│  - Status      │ - Items │ - Input │ - Neural│ - Select   │
│  - Controls    │         │ - Stream│ - Graph │            │
└────────────────┴─────────┴─────────┴─────────┴────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    FLASK BACKEND                            │
│                     (Python)                                │
├─────────────────────────────────────────────────────────────┤
│  /api/status     - System status                           │
│  /api/agents     - Agent management                        │
│  /api/execute    - Multi-agent orchestration               │
│  /api/chat       - Direct Ollama chat                      │
│  /api/metrics    - System metrics                          │
│  /api/terminal   - Terminal history                        │
└────────────────┴────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    OLLAMA RUNTIME                           │
├─────────────────────────────────────────────────────────────┤
│  qwen2.5-coder:14b  - Code generation                      │
│  deepseek-r1:7b     - Reasoning/planning                   │
│  dolphin-mistral    - Uncensored                            │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | System status |
| `/api/agents` | GET | All agents |
| `/api/agents/<id>` | POST | Update agent |
| `/api/models` | GET | Ollama models |
| `/api/execute` | POST | Run multi-agent task |
| `/api/chat` | POST | Direct chat |
| `/api/metrics` | GET | System metrics |
| `/api/terminal` | GET | Terminal history |

## Multi-Agent System

The dashboard integrates with your Profound System:

1. **Sprint Manager** - Decomposes goals into tasks
2. **Architect** - Designs system architecture
3. **Developer** - Generates production code
4. **Reviewer** - Reviews and validates code

Each agent runs with the optimal model:
- Planning → deepseek-r1:7b
- Code → qwen2.5-coder:14b
- Review → deepseek-r1:7b

## Requirements

- Python 3.12+
- Flask
- Flask-CORS
- Ollama running locally
- Modern browser (Chrome/Edge recommended)

## Installation

```bash
# Install dependencies
pip install flask flask-cors

# Run the server
python server.py
```

## Screenshots

The dashboard features:
- Animated particle effects
- Real-time agent status cards
- Streaming terminal output
- Neural network visualization
- Model selection cards with status

## Future Enhancements

- [ ] 3D Cyberdrome visualization (like AI Agent Session Center)
- [ ] Sound effects and ambient audio
- [ ] Team collaboration features
- [ ] Voice input (Whisper STT)
- [ ] Plugin system
- [ ] Mobile PWA support

## Credits

Inspired by:
- [AI Agent Session Center](https://github.com/coding-by-feng/ai-agent-session-center)
- [OctoAlly](https://octoally.com)
- [CodeGrid](https://codegrid.app)

---

**NEXUS** - Where local AI meets cyberpunk elegance.