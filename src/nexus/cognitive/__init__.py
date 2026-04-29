"""Cognitive Loop Engine — the core state machine for human-AI partnership.

This module replaces the linear Plan→Act→Observe→Reflect pipeline with
an open, collaborative loop where every stage is a shared state between
human and AI.

The Cognitive Loop:
    UNDERSTAND → PROPOSE → DISCUSS → REFINE → EXECUTE → REVIEW
         ↑                                           │
         └───────────────────────────────────────────┘

Key principle: The AI never advances to the next state without human
awareness and consent. Not because it's less capable, but because
partnership requires transparency.
"""
from .loop import CognitiveLoop, CognitiveState, SharedState
from .trace import ReasoningTrace, TraceNode, TraceNodeType
from .knowledge import KnowledgeStore, KnowledgeEntry, KnowledgeLayer, MembraneRule
from .verification import DesignVerifier, DesignConstraint, ConstraintSeverity, VerificationReport
from .clarification import AmbiguityDetector, ClarificationDialog, ClarificationQuestion, AmbiguityType

__all__ = [
    "CognitiveLoop",
    "CognitiveState",
    "SharedState",
    "ReasoningTrace",
    "TraceNode",
    "TraceNodeType",
    "KnowledgeStore",
    "KnowledgeEntry",
    "KnowledgeLayer",
    "MembraneRule",
    "DesignVerifier",
    "DesignConstraint",
    "ConstraintSeverity",
    "VerificationReport",
    "AmbiguityDetector",
    "ClarificationDialog",
    "ClarificationQuestion",
    "AmbiguityType",
]
