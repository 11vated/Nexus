"""MetaCognitiveEngine — real IRSC dual-loop, assumptions, confidence.

Implements genuine meta-cognition: the system thinks about its own thinking,
tracks assumptions explicitly, calibrates confidence, and maintains a
reasoning journal that learns from outcomes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from nexus.agent.llm import OllamaClient
from nexus.agent.models import AgentConfig

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    VERY_LOW = 0.1
    LOW = 0.3
    MEDIUM = 0.5
    HIGH = 0.7
    VERY_HIGH = 0.9


@dataclass
class Assumption:
    """An explicit assumption the system is making."""
    id: str
    statement: str
    confidence: float = 0.5
    evidence: str = ""
    falsifiable_by: str = ""
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "falsifiable_by": self.falsifiable_by,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Assumption":
        return cls(
            id=data["id"],
            statement=data["statement"],
            confidence=data.get("confidence", 0.5),
            evidence=data.get("evidence", ""),
            falsifiable_by=data.get("falsifiable_by", ""),
            created_at=data.get("created_at", time.time()),
            resolved=data.get("resolved", False),
            resolution=data.get("resolution", ""),
        )


@dataclass
class ReasoningEntry:
    """A single entry in the reasoning journal."""
    id: str
    decision: str
    rationale: str
    alternatives_considered: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    confidence: float = 0.5
    outcome: str = ""
    outcome_quality: float = 0.0
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "decision": self.decision,
            "rationale": self.rationale,
            "alternatives_considered": self.alternatives_considered,
            "assumptions": self.assumptions,
            "confidence": self.confidence,
            "outcome": self.outcome,
            "outcome_quality": self.outcome_quality,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningEntry":
        return cls(
            id=data["id"],
            decision=data["decision"],
            rationale=data["rationale"],
            alternatives_considered=data.get("alternatives_considered", []),
            assumptions=data.get("assumptions", []),
            confidence=data.get("confidence", 0.5),
            outcome=data.get("outcome", ""),
            outcome_quality=data.get("outcome_quality", 0.0),
            timestamp=data.get("timestamp", time.time()),
            tags=data.get("tags", []),
        )


@dataclass
class StrategyProfile:
    """Performance profile for a problem-solving strategy."""
    name: str
    times_used: int = 0
    success_count: int = 0
    avg_quality: float = 0.0
    avg_time_ms: float = 0.0
    contexts: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.times_used == 0:
            return 0.0
        return self.success_count / self.times_used

    def record_outcome(self, quality: float, duration_ms: float, context: str = "") -> None:
        self.times_used += 1
        if quality >= 0.7:
            self.success_count += 1
        n = self.times_used
        self.avg_quality = (self.avg_quality * (n - 1) + quality) / n
        self.avg_time_ms = (self.avg_time_ms * (n - 1) + duration_ms) / n
        if context and context not in self.contexts:
            self.contexts.append(context)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "times_used": self.times_used,
            "success_count": self.success_count,
            "avg_quality": self.avg_quality,
            "avg_time_ms": self.avg_time_ms,
            "success_rate": self.success_rate,
            "contexts": self.contexts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyProfile":
        profile = cls(name=data["name"])
        profile.times_used = data.get("times_used", 0)
        profile.success_count = data.get("success_count", 0)
        profile.avg_quality = data.get("avg_quality", 0.0)
        profile.avg_time_ms = data.get("avg_time_ms", 0.0)
        profile.contexts = data.get("contexts", [])
        return profile


class ReasoningJournal:
    """Persistent log of reasoning decisions and their outcomes."""

    def __init__(self, max_entries: int = 1000) -> None:
        self.entries: List[ReasoningEntry] = []
        self.max_entries = max_entries

    def add(self, entry: ReasoningEntry) -> None:
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    def get_by_tag(self, tag: str) -> List[ReasoningEntry]:
        return [e for e in self.entries if tag in e.tags]

    def get_recent(self, n: int = 10) -> List[ReasoningEntry]:
        return self.entries[-n:]

    def get_low_confidence(self, threshold: float = 0.4) -> List[ReasoningEntry]:
        return [e for e in self.entries if e.confidence < threshold]

    def get_failed(self) -> List[ReasoningEntry]:
        return [e for e in self.entries if e.outcome_quality < 0.4]

    def summary_stats(self) -> Dict[str, Any]:
        if not self.entries:
            return {"total": 0}
        qualities = [e.outcome_quality for e in self.entries if e.outcome_quality > 0]
        confidences = [e.confidence for e in self.entries]
        return {
            "total": len(self.entries),
            "avg_quality": sum(qualities) / len(qualities) if qualities else 0,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "failed_count": len(self.get_failed()),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self.entries[-self.max_entries:]],
            "max_entries": self.max_entries,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReasoningJournal":
        journal = cls(max_entries=data.get("max_entries", 1000))
        for entry_data in data.get("entries", []):
            journal.entries.append(ReasoningEntry.from_dict(entry_data))
        return journal


class MetaCognitiveEngine:
    """Real IRSC dual-loop meta-cognition.

    Before every EXECUTE phase, runs a meta-cognitive check:
    1. What approach am I considering? Why?
    2. What alternatives did I dismiss? Why?
    3. What assumptions am I making?
    4. Rate confidence and explain what would change it.
    5. What information would increase confidence?

    After every REVIEW, updates the reasoning journal with outcomes.
    """

    def __init__(
        self,
        config: AgentConfig,
        llm: Optional[OllamaClient] = None,
    ) -> None:
        self.config = config
        self.llm = llm or OllamaClient(config)
        self.assumptions: Dict[str, Assumption] = {}
        self.journal = ReasoningJournal()
        self.strategies: Dict[str, StrategyProfile] = {}
        self._assumption_counter = 0

    async def pre_execute_check(
        self,
        task: str,
        approach: str,
        context: str = "",
    ) -> Dict[str, Any]:
        """Run meta-cognitive check before execution."""
        prompt = (
            f"Task: {task}\n"
            f"Proposed approach: {approach}\n"
            f"Context: {context}\n\n"
            "Analyze your own reasoning:\n"
            "1. Why is this approach appropriate?\n"
            "2. What alternatives exist? List at least 2.\n"
            "3. What assumptions are you making? List them.\n"
            "4. Rate your confidence (0.0-1.0) in this approach.\n"
            "5. What additional information would increase your confidence?\n\n"
            "Respond in JSON-like format with keys: "
            "rationale, alternatives, assumptions, confidence, needs_info"
        )

        response = await self.llm.generate(prompt, model=self.config.planning_model)
        parsed = self._parse_meta_response(response)

        for assumption_text in parsed.get("assumptions", []):
            self.add_assumption(
                statement=assumption_text,
                evidence=parsed.get("rationale", ""),
                confidence=parsed.get("confidence", 0.5),
            )

        return parsed

    async def post_review_update(
        self,
        entry_id: str,
        outcome: str,
        outcome_quality: float,
        duration_ms: float = 0,
    ) -> None:
        """Update a journal entry with its outcome."""
        for entry in self.journal.entries:
            if entry.id == entry_id:
                entry.outcome = outcome
                entry.outcome_quality = outcome_quality
                break

        for tag in self.journal.entries[-1].tags if self.journal.entries else []:
            if tag in self.strategies:
                self.strategies[tag].record_outcome(
                    quality=outcome_quality,
                    duration_ms=duration_ms,
                    context=entry_id,
                )

    def add_assumption(
        self,
        statement: str,
        evidence: str = "",
        confidence: float = 0.5,
        falsifiable_by: str = "",
    ) -> Assumption:
        """Add a new assumption to track."""
        self._assumption_counter += 1
        assumption = Assumption(
            id=f"assump_{self._assumption_counter}",
            statement=statement,
            confidence=confidence,
            evidence=evidence,
            falsifiable_by=falsifiable_by,
        )
        self.assumptions[assumption.id] = assumption
        return assumption

    def resolve_assumption(self, assumption_id: str, resolution: str, was_correct: bool) -> None:
        """Mark an assumption as resolved."""
        if assumption_id in self.assumptions:
            a = self.assumptions[assumption_id]
            a.resolved = True
            a.resolution = resolution
            if not was_correct:
                a.confidence = 0.0

    def get_unresolved_assumptions(self) -> List[Assumption]:
        return [a for a in self.assumptions.values() if not a.resolved]

    def get_low_confidence_assumptions(self, threshold: float = 0.4) -> List[Assumption]:
        return [
            a for a in self.assumptions.values()
            if not a.resolved and a.confidence < threshold
        ]

    def log_reasoning(
        self,
        decision: str,
        rationale: str,
        alternatives: Optional[List[str]] = None,
        assumptions: Optional[List[str]] = None,
        confidence: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> ReasoningEntry:
        """Log a reasoning decision to the journal."""
        entry = ReasoningEntry(
            id=f"reason_{len(self.journal.entries) + 1}",
            decision=decision,
            rationale=rationale,
            alternatives_considered=alternatives or [],
            assumptions=assumptions or [],
            confidence=confidence,
            tags=tags or [],
        )
        self.journal.add(entry)
        return entry

    def recommend_strategy(self, context: str) -> Optional[str]:
        """Recommend the best strategy for a given context."""
        candidates = {
            name: profile.success_rate
            for name, profile in self.strategies.items()
            if profile.times_used > 0
        }
        if not candidates:
            return None
        return max(candidates, key=candidates.get)

    def record_strategy_outcome(
        self,
        strategy_name: str,
        quality: float,
        duration_ms: float,
        context: str = "",
    ) -> None:
        """Record how well a strategy performed."""
        if strategy_name not in self.strategies:
            self.strategies[strategy_name] = StrategyProfile(name=strategy_name)
        self.strategies[strategy_name].record_outcome(
            quality=quality,
            duration_ms=duration_ms,
            context=context,
        )

    def calibration_score(self) -> float:
        """How well calibrated is the confidence? 1.0 = perfect."""
        entries = [e for e in self.journal.entries if e.outcome_quality > 0]
        if len(entries) < 3:
            return 0.5

        errors = []
        for e in entries:
            error = abs(e.confidence - e.outcome_quality)
            errors.append(error)

        avg_error = sum(errors) / len(errors)
        return max(0.0, 1.0 - avg_error)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assumptions": {k: v.to_dict() for k, v in self.assumptions.items()},
            "assumption_counter": self._assumption_counter,
            "journal": self.journal.to_dict(),
            "strategies": {k: v.to_dict() for k, v in self.strategies.items()},
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        config: AgentConfig,
        llm: Optional[OllamaClient] = None,
    ) -> "MetaCognitiveEngine":
        engine = cls(config=config, llm=llm)
        for aid, adata in data.get("assumptions", {}).items():
            engine.assumptions[aid] = Assumption.from_dict(adata)
        engine._assumption_counter = data.get("assumption_counter", 0)
        engine.journal = ReasoningJournal.from_dict(data.get("journal", {}))
        for sname, sdata in data.get("strategies", {}).items():
            engine.strategies[sname] = StrategyProfile.from_dict(sdata)
        return engine

    def _parse_meta_response(self, response: str) -> Dict[str, Any]:
        """Parse the meta-cognitive LLM response into structured data."""
        result: Dict[str, Any] = {
            "rationale": "",
            "alternatives": [],
            "assumptions": [],
            "confidence": 0.5,
            "needs_info": [],
        }

        lines = response.strip().split("\n")
        current_key = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            lower = stripped.lower()
            if lower.startswith("rationale"):
                current_key = "rationale"
                content = stripped.split(":", 1)[-1].strip()
                if content:
                    result["rationale"] = content
            elif lower.startswith("alternatives"):
                current_key = "alternatives"
                content = stripped.split(":", 1)[-1].strip()
                if content:
                    result["alternatives"].append(content)
            elif lower.startswith("assumptions"):
                current_key = "assumptions"
                content = stripped.split(":", 1)[-1].strip()
                if content:
                    result["assumptions"].append(content)
            elif lower.startswith("confidence"):
                current_key = "confidence"
                try:
                    val = stripped.split(":", 1)[-1].strip()
                    result["confidence"] = float(val)
                except (ValueError, IndexError):
                    result["confidence"] = 0.5
            elif lower.startswith("needs_info") or lower.startswith("information"):
                current_key = "needs_info"
                content = stripped.split(":", 1)[-1].strip()
                if content:
                    result["needs_info"].append(content)
            elif current_key and stripped.startswith("- "):
                result[current_key].append(stripped[2:])
            elif current_key and current_key == "rationale":
                result["rationale"] += " " + stripped

        return result
