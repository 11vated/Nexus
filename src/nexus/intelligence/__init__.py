"""Nexus Intelligence Layer — what makes Nexus unique.

This package contains the systems that differentiate Nexus from
generic LLM chat wrappers:

- model_router:    Multi-model routing (right model for each sub-task)
- project_map:     Deep project understanding (deps, architecture, hot files)
- stances:         Conversation personas (architect, debugger, reviewer, etc.)
- session_store:   Persistent session save/resume with full context
"""

from nexus.intelligence.model_router import ModelRouter, TaskIntent
from nexus.intelligence.project_map import ProjectMap
from nexus.intelligence.stances import Stance, StanceManager
from nexus.intelligence.session_store import SessionStore

__all__ = [
    "ModelRouter",
    "TaskIntent",
    "ProjectMap",
    "Stance",
    "StanceManager",
    "SessionStore",
]
