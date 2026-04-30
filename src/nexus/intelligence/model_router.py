"""Multi-Model Intelligence Router.

The killer feature of local-first AI: you have MULTIPLE specialized models.
Instead of forcing everything through one model, Nexus routes each sub-task
to the best model available.

The user sees one conversation. Under the hood:
  - Architecture questions → reasoning model (deepseek-r1)
  - Code generation → coding model (qwen2.5-coder:14b)
  - Quick refactors → fast model (qwen2.5-coder:7b)
  - Code review → review model (lower temperature)
  - Explanations → whatever model the user prefers

This is something cloud tools CAN'T do — they're locked to one model.
Nexus orchestrates a whole team of local specialists.

Usage:
    router = ModelRouter(config)
    model, params = router.route("Refactor this function to use async/await")
    # → ("qwen2.5-coder:14b", {"temperature": 0.3})

    model, params = router.route("Why is this architecture bad?")
    # → ("deepseek-r1:7b", {"temperature": 0.5})
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from nexus.agent.models import AgentConfig


class TaskIntent(Enum):
    """Classification of what the user is asking for."""
    CODE_GENERATION = "code_generation"    # Write new code
    CODE_EDIT = "code_edit"                # Modify existing code
    CODE_REVIEW = "code_review"            # Review / find bugs
    ARCHITECTURE = "architecture"          # Design / planning
    DEBUGGING = "debugging"                # Fix a bug / investigate
    EXPLANATION = "explanation"            # Teach / explain
    REFACTOR = "refactor"                  # Restructure existing code
    TESTING = "testing"                    # Write or run tests
    QUICK_TASK = "quick_task"              # Simple/fast operation
    GENERAL = "general"                    # Catch-all


@dataclass
class ModelProfile:
    """A model's capabilities and optimal use cases."""
    name: str
    strengths: List[TaskIntent]
    temperature: float = 0.3
    max_tokens: int = 4096
    speed_tier: int = 2       # 1=fast, 2=medium, 3=slow
    reasoning_depth: int = 2  # 1=shallow, 2=medium, 3=deep


@dataclass
class RoutingDecision:
    """The result of routing a task to a model."""
    model: str
    temperature: float
    max_tokens: int
    intent: TaskIntent
    confidence: float
    reasoning: str


# Intent detection patterns — keywords and regex that signal intent
_INTENT_PATTERNS: Dict[TaskIntent, List[str]] = {
    TaskIntent.CODE_GENERATION: [
        r"\b(write|create|build|implement|add|generate|make)\b.*\b(function|class|module|endpoint|api|file|component|script)\b",
        r"\b(new|scaffold|bootstrap|initialize|setup)\b",
    ],
    TaskIntent.CODE_EDIT: [
        r"\b(change|modify|update|edit|replace|rename|move)\b",
        r"\b(fix the|update the|change the|modify the)\b",
    ],
    TaskIntent.CODE_REVIEW: [
        r"\b(review|check|audit|inspect|evaluate|assess)\b.*\b(code|implementation|logic)\b",
        r"\b(what('s| is) wrong|find (bugs|issues|problems))\b",
        r"\b(code smell|anti.?pattern|best practice)\b",
    ],
    TaskIntent.ARCHITECTURE: [
        r"\b(architect|design|plan|structure|organize|layout)\b",
        r"\b(how should (I|we)|what('s| is) the best (way|approach))\b",
        r"\b(system design|high.?level|overview|tradeoff)\b",
        r"\b(microservice|monolith|pattern|separation of concerns)\b",
    ],
    TaskIntent.DEBUGGING: [
        r"\b(debug|fix|error|bug|crash|broken|failing|exception|traceback)\b",
        r"\b(doesn('t| not) work|why (is|does)|investigate)\b",
        r"\b(stack trace|segfault|undefined|null|NoneType)\b",
    ],
    TaskIntent.EXPLANATION: [
        r"\b(explain|teach|what (is|are|does)|how (does|do)|why (does|do|is))\b",
        r"\b(walk me through|help me understand|what happens when)\b",
        r"\b(difference between|compared to|versus|vs\.?)\b",
    ],
    TaskIntent.REFACTOR: [
        r"\b(refactor|restructure|reorganize|simplify|clean.?up|extract)\b",
        r"\b(DRY|SOLID|decompose|decouple|abstract)\b",
    ],
    TaskIntent.TESTING: [
        r"\b(test|spec|assert|mock|fixture|coverage)\b",
        r"\b(write tests|add tests|test for|unit test|integration test)\b",
        r"\b(pytest|jest|mocha|unittest)\b",
    ],
    TaskIntent.QUICK_TASK: [
        r"\b(quick|fast|simple|just|only)\b.*\b(change|fix|add|update)\b",
        r"\b(one.?liner|snippet|quick fix|hotfix)\b",
    ],
}


class ModelRouter:
    """Routes tasks to the optimal local model.

    Analyzes user messages to detect intent, then picks the best model
    from the locally available set based on task requirements.

    This is the core of Nexus's multi-model intelligence — the user
    has a single conversation, but different parts are handled by
    different specialists.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self._profiles = self._build_default_profiles()
        self._available_models: List[str] = []
        self._routing_history: List[RoutingDecision] = []

    def _build_default_profiles(self) -> Dict[str, ModelProfile]:
        """Build model profiles from config."""
        return {
            self.config.planning_model: ModelProfile(
                name=self.config.planning_model,
                strengths=[
                    TaskIntent.ARCHITECTURE,
                    TaskIntent.DEBUGGING,
                    TaskIntent.CODE_REVIEW,
                    TaskIntent.EXPLANATION,
                ],
                temperature=0.5,
                speed_tier=3,
                reasoning_depth=3,
            ),
            self.config.coding_model: ModelProfile(
                name=self.config.coding_model,
                strengths=[
                    TaskIntent.CODE_GENERATION,
                    TaskIntent.CODE_EDIT,
                    TaskIntent.REFACTOR,
                    TaskIntent.TESTING,
                ],
                temperature=0.3,
                speed_tier=2,
                reasoning_depth=2,
            ),
            self.config.fast_model: ModelProfile(
                name=self.config.fast_model,
                strengths=[
                    TaskIntent.QUICK_TASK,
                    TaskIntent.CODE_EDIT,
                ],
                temperature=0.2,
                speed_tier=1,
                reasoning_depth=1,
            ),
        }

    def set_available_models(self, models: List[str]) -> None:
        """Set which models are actually available on this machine."""
        self._available_models = models

    def add_profile(self, profile: ModelProfile) -> None:
        """Register a custom model profile."""
        self._profiles[profile.name] = profile

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def detect_intent(self, message: str) -> Tuple[TaskIntent, float]:
        """Classify a user message into a task intent.

        Uses pattern matching with confidence scoring.
        Returns (intent, confidence) where confidence is 0.0-1.0.
        """
        message_lower = message.lower()
        scores: Dict[TaskIntent, float] = {}

        for intent, patterns in _INTENT_PATTERNS.items():
            score = 0.0
            for pattern in patterns:
                matches = re.findall(pattern, message_lower)
                if matches:
                    score += 0.3 * len(matches)
            scores[intent] = min(score, 1.0)

        if not scores or max(scores.values()) == 0:
            return TaskIntent.GENERAL, 0.3

        best_intent = max(scores, key=lambda k: scores[k])
        confidence = scores[best_intent]

        # Boost confidence if multiple patterns matched
        if confidence > 0.3:
            confidence = min(confidence + 0.2, 1.0)

        return best_intent, confidence

    # ------------------------------------------------------------------
    # Model routing
    # ------------------------------------------------------------------

    def route(self, message: str) -> RoutingDecision:
        """Route a message to the optimal model.

        This is the main entry point. Analyzes the message,
        detects intent, and picks the best available model.

        Args:
            message: The user's message text.

        Returns:
            RoutingDecision with model name, parameters, and reasoning.
        """
        intent, confidence = self.detect_intent(message)

        # Find best model for this intent
        best_model = None
        best_score = -1.0

        for model_name, profile in self._profiles.items():
            # Skip models that aren't available (if we know)
            if self._available_models and model_name not in self._available_models:
                continue

            score = 0.0
            if intent in profile.strengths:
                # Primary match — this model is built for this
                idx = profile.strengths.index(intent)
                score = 1.0 - (idx * 0.15)  # First strength > second > etc.
            else:
                # Fallback: coding model can do anything, just not optimally
                score = 0.3

            # Prefer faster models for quick tasks
            if intent == TaskIntent.QUICK_TASK:
                score += (3 - profile.speed_tier) * 0.2

            # Prefer deeper reasoning for architecture/debugging
            if intent in (TaskIntent.ARCHITECTURE, TaskIntent.DEBUGGING):
                score += profile.reasoning_depth * 0.1

            if score > best_score:
                best_score = score
                best_model = profile

        # Fallback to coding model if nothing matched
        if not best_model:
            best_model = self._profiles.get(
                self.config.coding_model,
                ModelProfile(name=self.config.coding_model, strengths=[]),
            )

        decision = RoutingDecision(
            model=best_model.name,
            temperature=best_model.temperature,
            max_tokens=best_model.max_tokens,
            intent=intent,
            confidence=confidence,
            reasoning=self._explain_routing(intent, best_model),
        )

        self._routing_history.append(decision)
        return decision

    def _explain_routing(self, intent: TaskIntent, profile: ModelProfile) -> str:
        """Generate a human-readable routing explanation."""
        intent_desc = {
            TaskIntent.CODE_GENERATION: "writing new code",
            TaskIntent.CODE_EDIT: "modifying existing code",
            TaskIntent.CODE_REVIEW: "reviewing code quality",
            TaskIntent.ARCHITECTURE: "design and architecture",
            TaskIntent.DEBUGGING: "debugging and investigation",
            TaskIntent.EXPLANATION: "explanation and teaching",
            TaskIntent.REFACTOR: "code refactoring",
            TaskIntent.TESTING: "writing or running tests",
            TaskIntent.QUICK_TASK: "a quick task",
            TaskIntent.GENERAL: "general assistance",
        }
        return (
            f"Detected: {intent_desc.get(intent, intent.value)} → "
            f"Using {profile.name} "
            f"(temp={profile.temperature}, depth={profile.reasoning_depth})"
        )

    @property
    def history(self) -> List[RoutingDecision]:
        """Get routing decision history for this session."""
        return list(self._routing_history)

    def stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        if not self._routing_history:
            return {"total_routes": 0}

        intent_counts: Dict[str, int] = {}
        model_counts: Dict[str, int] = {}
        for d in self._routing_history:
            intent_counts[d.intent.value] = intent_counts.get(d.intent.value, 0) + 1
            model_counts[d.model] = model_counts.get(d.model, 0) + 1

        return {
            "total_routes": len(self._routing_history),
            "intent_distribution": intent_counts,
            "model_distribution": model_counts,
            "avg_confidence": sum(d.confidence for d in self._routing_history) / len(self._routing_history),
        }
