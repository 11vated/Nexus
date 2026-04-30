"""Nexus Web Dashboard — FastAPI backend.

Exposes Nexus functionality over HTTP/WebSocket:
- Chat sessions with streaming responses
- Autonomous agent execution
- Plugin management
- Evolution monitoring
- Project intelligence
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# -- Request/Response Models ------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    workspace: str = "."
    stream: bool = False


class AgentRunRequest(BaseModel):
    goal: str
    workspace: str = "."
    model: Optional[str] = None
    max_iterations: int = 25


class PluginAction(BaseModel):
    action: str  # "list", "enable", "disable", "reload", "info"
    plugin_name: Optional[str] = None
    workspace: str = "."


class EvolutionRequest(BaseModel):
    workspace: str = "."
    max_generations: int = 10
    population_size: int = 10


# -- State Management -------------------------------------------------------

active_sessions: Dict[str, Dict[str, Any]] = {}
active_agents: Dict[str, Dict[str, Any]] = {}


# -- Lifespan ---------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Nexus Web Dashboard starting")
    yield
    logger.info("Nexus Web Dashboard shutting down")


# -- App Setup --------------------------------------------------------------

app = FastAPI(
    title="Nexus AI Dashboard",
    description="Web interface for the Nexus AI coding assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Health -----------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "active_sessions": len(active_sessions),
        "active_agents": len(active_agents),
    }


# -- Chat -------------------------------------------------------------------

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Send a chat message and get a response."""
    from nexus.agent.chat import ChatSession
    from nexus.agent.models import AgentConfig

    config = AgentConfig(
        workspace_path=request.workspace,
        coding_model=request.model or "qwen2.5-coder:14b",
    )
    session = ChatSession(workspace=request.workspace, config=config)

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    response_text = ""
    async for event in session.send(messages[-1]["content"]):
        if event.type.value in ("text", "chunk"):
            response_text += event.content

    return {"response": response_text, "session_id": str(uuid.uuid4())[:8]}


# -- WebSocket Chat --------------------------------------------------------

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for streaming chat."""
    await websocket.accept()

    active_sessions[session_id] = {
        "history": [],
        "created_at": __import__("time").time(),
    }

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Store in history
            active_sessions[session_id]["history"].append({
                "role": "user",
                "content": message.get("content", ""),
            })

            # Send streaming response
            await websocket.send_json({
                "type": "streaming",
                "content": "Processing...",
            })

            # Simulate response (replace with actual LLM call)
            response = f"Received: {message.get('content', '')[:50]}..."

            await websocket.send_json({
                "type": "response",
                "content": response,
                "session_id": session_id,
            })

            active_sessions[session_id]["history"].append({
                "role": "assistant",
                "content": response,
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", session_id)
    finally:
        active_sessions.pop(session_id, None)


# -- Autonomous Agent -------------------------------------------------------

@app.post("/api/agent/run")
async def run_agent(request: AgentRunRequest):
    """Start an autonomous agent run."""
    agent_id = str(uuid.uuid4())[:8]

    active_agents[agent_id] = {
        "goal": request.goal,
        "status": "running",
        "workspace": request.workspace,
        "started_at": __import__("time").time(),
    }

    # Run agent in background
    async def run_background():
        try:
            from nexus.agent.loop import AgentLoop
            from nexus.agent.models import AgentConfig

            config = AgentConfig(
                workspace_path=request.workspace,
                coding_model=request.model or "qwen2.5-coder:14b",
                max_iterations=request.max_iterations,
            )
            agent = AgentLoop(config)

            result = await agent.run(request.goal)
            active_agents[agent_id]["status"] = "completed"
            active_agents[agent_id]["result"] = result
        except Exception as exc:
            active_agents[agent_id]["status"] = "error"
            active_agents[agent_id]["error"] = str(exc)

    asyncio.create_task(run_background())

    return {
        "agent_id": agent_id,
        "status": "started",
        "goal": request.goal,
    }


@app.get("/api/agent/{agent_id}")
async def get_agent_status(agent_id: str):
    """Get the status of an agent run."""
    if agent_id not in active_agents:
        return {"error": "Agent not found"}
    return active_agents[agent_id]


@app.get("/api/agents")
async def list_agents():
    """List all active and completed agent runs."""
    return list(active_agents.values())


# -- Plugins ----------------------------------------------------------------

@app.post("/api/plugins")
async def plugin_action(request: PluginAction):
    """Manage plugins."""
    from nexus.plugins.manager import PluginManager

    manager = PluginManager(workspace=request.workspace)
    manager.loader.discover()

    if request.action == "list":
        return {"plugins": manager.list_plugins()}
    elif request.action == "enable" and request.plugin_name:
        result = manager.enable_plugin(request.plugin_name)
        return result
    elif request.action == "disable" and request.plugin_name:
        result = manager.disable_plugin(request.plugin_name)
        return result
    elif request.action == "info" and request.plugin_name:
        info = manager.get_plugin_info(request.plugin_name)
        return info or {"error": "Plugin not found"}
    elif request.action == "stats":
        return manager.get_stats()

    return {"error": f"Unknown action: {request.action}"}


# -- Evolution --------------------------------------------------------------

@app.post("/api/evolution/run")
async def run_evolution(request: EvolutionRequest):
    """Start an evolution run."""
    from nexus.evolution.evolution_engine import EvolutionConfig, EvolutionEngine

    config = EvolutionConfig(
        population_size=request.population_size,
        max_generations=request.max_generations,
    )
    engine = EvolutionEngine(config)

    # Placeholder evaluation function
    async def dummy_eval(genome):
        return {
            "test_results": {"tests_passed": 5, "tests_total": 10},
            "execution_stats": {"time_seconds": 5, "tokens_used": 1000, "steps": 3},
        }

    results = await engine.run(dummy_eval)

    return {
        "generations": len(results),
        "best_fitness": engine.population.best_fitness,
        "best_genome": engine.best_genome.to_dict() if engine.best_genome else None,
        "stats": engine.get_full_stats(),
    }


# -- Session Management ----------------------------------------------------

@app.get("/api/sessions")
async def list_sessions():
    """List active chat sessions."""
    return list(active_sessions.values())


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    if session_id in active_sessions:
        del active_sessions[session_id]
        return {"status": "deleted"}
    return {"error": "Session not found"}
