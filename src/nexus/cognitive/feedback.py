"""Persistent Memory with Feedback Learning.

Implements the "preference learning" pillar from the Cognitive Partnership
Manifesto. Nexus learns from both explicit feedback (thumbs up/down, /learn)
and implicit signals (accepted diffs, rejected suggestions, repeated patterns).

Storage: `.nexus/profile.yaml` — portable, human-readable, git-trackable.

Architecture:
    FeedbackCollector → PreferenceLearner → UserProfile → .nexus/profile.yaml
                                                ↕
                                         MemoryMesh (integration)

The profile accumulates over time:
  - Coding style preferences (naming, patterns, framework choices)
  - Communication preferences (verbosity, explanation depth, emoji usage)
  - Tool preferences (which tools the user prefers/avoids)
  - Decision patterns (what trade-offs the user favors)
  - Correction history (what the user has corrected before)
"""

from __future__ import annotations

import time
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Types ───────────────────────────────────────────────────────────────────


class FeedbackType(str, Enum):
    """Categories of feedback signals."""
    EXPLICIT_POSITIVE = "explicit_positive"     # User said "good", thumbs up
    EXPLICIT_NEGATIVE = "explicit_negative"     # User said "bad", thumbs down
    EXPLICIT_CORRECTION = "explicit_correction" # User corrected output
    DIFF_ACCEPTED = "diff_accepted"             # User accepted a diff
    DIFF_REJECTED = "diff_rejected"             # User rejected a diff
    PLAN_APPROVED = "plan_approved"             # User approved a plan step
    PLAN_MODIFIED = "plan_modified"             # User modified a plan step
    STYLE_SIGNAL = "style_signal"               # Implicit style detection
    TOOL_PREFERENCE = "tool_preference"         # User prefers certain tools
    REPEATED_PATTERN = "repeated_pattern"       # User does X consistently


class PreferenceCategory(str, Enum):
    """Broad categories for preference grouping."""
    CODING_STYLE = "coding_style"
    COMMUNICATION = "communication"
    TOOLS = "tools"
    WORKFLOW = "workflow"
    ARCHITECTURE = "architecture"
    TESTING = "testing"


@dataclass
class FeedbackSignal:
    """A single feedback event, either explicit or implicit."""
    feedback_type: FeedbackType
    category: PreferenceCategory
    signal: str                          # What was observed
    context: str = ""                    # Surrounding context
    strength: float = 1.0                # 0.0-1.0, how strong the signal is
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Preference:
    """A learned preference with confidence from accumulated signals."""
    key: str                             # e.g., "naming_convention"
    value: str                           # e.g., "snake_case"
    category: PreferenceCategory
    confidence: float = 0.5              # 0.0-1.0, grows with evidence
    signal_count: int = 0                # How many signals support this
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    contradictions: int = 0              # Signals that contradicted this
    examples: List[str] = field(default_factory=list)  # Max 5 examples

    @property
    def is_strong(self) -> bool:
        """A preference is strong when confidence > 0.7 and seen 3+ times."""
        return self.confidence > 0.7 and self.signal_count >= 3

    def reinforce(self, example: str = "") -> None:
        """Strengthen this preference with a new supporting signal."""
        self.signal_count += 1
        self.last_seen = time.time()
        # Confidence approaches 1.0 asymptotically
        self.confidence = min(0.99, self.confidence + (1 - self.confidence) * 0.15)
        if example and len(self.examples) < 5:
            self.examples.append(example[:200])

    def contradict(self) -> None:
        """Weaken this preference with a contradicting signal."""
        self.contradictions += 1
        self.confidence = max(0.1, self.confidence * 0.75)
        self.last_seen = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category.value,
            "confidence": round(self.confidence, 3),
            "signal_count": self.signal_count,
            "contradictions": self.contradictions,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "examples": self.examples,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Preference":
        return cls(
            key=data["key"],
            value=data["value"],
            category=PreferenceCategory(data.get("category", "coding_style")),
            confidence=data.get("confidence", 0.5),
            signal_count=data.get("signal_count", 0),
            contradictions=data.get("contradictions", 0),
            first_seen=data.get("first_seen", time.time()),
            last_seen=data.get("last_seen", time.time()),
            examples=data.get("examples", []),
        )


# ── UserProfile ─────────────────────────────────────────────────────────────


class UserProfile:
    """Persistent user profile stored in `.nexus/profile.yaml`.

    Tracks preferences, corrections, tool usage patterns, and
    communication style — everything Nexus needs to personalize
    its behavior over time.
    """

    def __init__(self, workspace: str = ".") -> None:
        self.workspace = Path(workspace)
        self.profile_path = self.workspace / ".nexus" / "profile.yaml"
        self.preferences: Dict[str, Preference] = {}
        self.corrections: List[Dict[str, Any]] = []  # Max 50
        self.tool_usage: Dict[str, int] = {}
        self.session_count: int = 0
        self.total_turns: int = 0
        self.created_at: float = time.time()
        self.updated_at: float = time.time()

        # Load existing profile if present
        self._load()

    def _load(self) -> None:
        """Load profile from disk."""
        if not self.profile_path.exists():
            return
        try:
            data = yaml.safe_load(self.profile_path.read_text(encoding="utf-8"))
            if not data:
                return

            self.session_count = data.get("session_count", 0)
            self.total_turns = data.get("total_turns", 0)
            self.created_at = data.get("created_at", self.created_at)
            self.updated_at = data.get("updated_at", self.updated_at)
            self.tool_usage = data.get("tool_usage", {})
            self.corrections = data.get("corrections", [])

            for pref_data in data.get("preferences", []):
                pref = Preference.from_dict(pref_data)
                self.preferences[pref.key] = pref
        except Exception:
            pass  # Corrupt file — start fresh

    def save(self) -> None:
        """Persist profile to disk."""
        self.updated_at = time.time()
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "# Nexus User Profile": None,
            "# This file is auto-generated. Edit preferences manually if desired.": None,
            "session_count": self.session_count,
            "total_turns": self.total_turns,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tool_usage": dict(sorted(self.tool_usage.items(), key=lambda x: -x[1])),
            "preferences": [p.to_dict() for p in sorted(
                self.preferences.values(),
                key=lambda x: -x.confidence,
            )],
            "corrections": self.corrections[-50:],  # Keep last 50
        }

        # Filter out comment keys for YAML output
        clean_data = {k: v for k, v in data.items() if not k.startswith("#")}

        header = (
            "# Nexus User Profile\n"
            "# Auto-generated — tracks coding preferences, patterns, and feedback.\n"
            "# Edit manually to teach Nexus your preferences directly.\n"
            "# ---\n\n"
        )
        yaml_content = yaml.dump(clean_data, default_flow_style=False, sort_keys=False)
        self.profile_path.write_text(header + yaml_content, encoding="utf-8")

    def get_preference(self, key: str) -> Optional[Preference]:
        """Get a preference by key."""
        return self.preferences.get(key)

    def get_strong_preferences(self) -> List[Preference]:
        """Get all preferences with high confidence."""
        return [p for p in self.preferences.values() if p.is_strong]

    def get_preferences_by_category(self, category: PreferenceCategory) -> List[Preference]:
        """Get preferences in a specific category."""
        return [p for p in self.preferences.values() if p.category == category]

    def get_context_prompt(self) -> str:
        """Generate a system prompt fragment from strong preferences.

        This is injected into the LLM system prompt so Nexus
        naturally adapts its behavior.
        """
        strong = self.get_strong_preferences()
        if not strong:
            return ""

        lines = ["User preferences (learned from past interactions):"]
        by_category: Dict[str, List[str]] = {}
        for p in strong:
            cat = p.category.value.replace("_", " ").title()
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f"- {p.key}: {p.value} (confidence: {p.confidence:.0%})")

        for cat, prefs in by_category.items():
            lines.append(f"\n{cat}:")
            lines.extend(prefs)

        return "\n".join(lines)

    def record_tool_usage(self, tool_name: str) -> None:
        """Track tool usage frequency."""
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

    def record_correction(self, original: str, corrected: str, context: str = "") -> None:
        """Record a user correction for future learning."""
        self.corrections.append({
            "original": original[:300],
            "corrected": corrected[:300],
            "context": context[:200],
            "timestamp": time.time(),
        })
        # Keep bounded
        if len(self.corrections) > 50:
            self.corrections = self.corrections[-50:]

    def summary(self) -> str:
        """Human-readable profile summary."""
        lines = [
            f"📋 User Profile ({self.session_count} sessions, {self.total_turns} turns)",
            f"   Strong preferences: {len(self.get_strong_preferences())}",
            f"   Total preferences: {len(self.preferences)}",
            f"   Corrections recorded: {len(self.corrections)}",
            f"   Tools used: {len(self.tool_usage)}",
        ]
        strong = self.get_strong_preferences()
        if strong:
            lines.append("\n   Top preferences:")
            for p in sorted(strong, key=lambda x: -x.confidence)[:5]:
                lines.append(f"   • {p.key} = {p.value} ({p.confidence:.0%})")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_count": self.session_count,
            "total_turns": self.total_turns,
            "preferences_count": len(self.preferences),
            "strong_preferences": len(self.get_strong_preferences()),
            "corrections_count": len(self.corrections),
            "tool_usage": dict(self.tool_usage),
        }


# ── FeedbackCollector ───────────────────────────────────────────────────────


class FeedbackCollector:
    """Collects feedback signals from various sources.

    The collector doesn't interpret signals — it normalizes them
    into FeedbackSignal objects and passes them to the learner.
    """

    def __init__(self) -> None:
        self._signals: List[FeedbackSignal] = []
        self._max_signals = 200

    @property
    def signals(self) -> List[FeedbackSignal]:
        return list(self._signals)

    def collect(self, signal: FeedbackSignal) -> None:
        """Add a feedback signal."""
        self._signals.append(signal)
        if len(self._signals) > self._max_signals:
            self._signals = self._signals[-self._max_signals:]

    def collect_diff_accepted(self, path: str, diff_stats: Dict[str, Any]) -> None:
        """Record that the user accepted a diff."""
        self.collect(FeedbackSignal(
            feedback_type=FeedbackType.DIFF_ACCEPTED,
            category=PreferenceCategory.CODING_STYLE,
            signal=f"Accepted diff for {path}",
            context=str(diff_stats),
            strength=0.7,
        ))

    def collect_diff_rejected(self, path: str, reason: str = "") -> None:
        """Record that the user rejected a diff."""
        self.collect(FeedbackSignal(
            feedback_type=FeedbackType.DIFF_REJECTED,
            category=PreferenceCategory.CODING_STYLE,
            signal=f"Rejected diff for {path}",
            context=reason,
            strength=0.8,
        ))

    def collect_explicit(self, text: str, positive: bool) -> None:
        """Record explicit thumbs up/down."""
        self.collect(FeedbackSignal(
            feedback_type=(
                FeedbackType.EXPLICIT_POSITIVE if positive
                else FeedbackType.EXPLICIT_NEGATIVE
            ),
            category=PreferenceCategory.COMMUNICATION,
            signal=text,
            strength=1.0,
        ))

    def collect_correction(self, original: str, corrected: str) -> None:
        """Record a user correction."""
        self.collect(FeedbackSignal(
            feedback_type=FeedbackType.EXPLICIT_CORRECTION,
            category=PreferenceCategory.CODING_STYLE,
            signal=f"Corrected: {original[:100]} → {corrected[:100]}",
            strength=0.9,
        ))

    def collect_tool_preference(self, tool: str, used: bool) -> None:
        """Record tool usage or avoidance."""
        self.collect(FeedbackSignal(
            feedback_type=FeedbackType.TOOL_PREFERENCE,
            category=PreferenceCategory.TOOLS,
            signal=f"{'Used' if used else 'Avoided'} tool: {tool}",
            strength=0.5,
        ))

    def collect_style(self, key: str, value: str, context: str = "") -> None:
        """Record an implicit style signal."""
        self.collect(FeedbackSignal(
            feedback_type=FeedbackType.STYLE_SIGNAL,
            category=PreferenceCategory.CODING_STYLE,
            signal=f"{key}: {value}",
            context=context,
            strength=0.6,
        ))

    def drain(self) -> List[FeedbackSignal]:
        """Get and clear all accumulated signals."""
        signals = list(self._signals)
        self._signals.clear()
        return signals


# ── PreferenceLearner ───────────────────────────────────────────────────────


class PreferenceLearner:
    """Learns user preferences from accumulated feedback signals.

    Takes FeedbackSignals and updates the UserProfile. Uses simple
    reinforcement — repeated signals strengthen preferences,
    contradictions weaken them.
    """

    # Style patterns we can detect from code
    STYLE_DETECTORS = {
        "naming_convention": {
            "snake_case": r"[a-z]+_[a-z]+",
            "camelCase": r"[a-z]+[A-Z][a-z]+",
            "PascalCase": r"[A-Z][a-z]+[A-Z]",
        },
        "quote_style": {
            "double_quotes": '"',
            "single_quotes": "'",
        },
        "docstring_style": {
            "google": "Args:",
            "numpy": "Parameters\n----------",
            "sphinx": ":param ",
        },
    }

    def __init__(self, profile: UserProfile) -> None:
        self.profile = profile

    def learn_from_signals(self, signals: List[FeedbackSignal]) -> List[str]:
        """Process a batch of signals and update preferences.

        Returns list of human-readable learning summaries.
        """
        summaries: List[str] = []

        for signal in signals:
            result = self._process_signal(signal)
            if result:
                summaries.append(result)

        if summaries:
            self.profile.save()

        return summaries

    def learn_from_code(self, code: str, file_path: str = "") -> List[str]:
        """Detect style preferences from code the user wrote or accepted.

        This is called when the user accepts a diff or writes code directly.
        """
        summaries: List[str] = []
        import re

        # Detect naming convention
        snake = len(re.findall(r'\b[a-z]+_[a-z]+\b', code))
        camel = len(re.findall(r'\b[a-z]+[A-Z][a-z]+\b', code))
        if snake > camel and snake > 3:
            s = self._update_preference(
                "naming_convention", "snake_case",
                PreferenceCategory.CODING_STYLE,
                f"file: {file_path}",
            )
            if s:
                summaries.append(s)
        elif camel > snake and camel > 3:
            s = self._update_preference(
                "naming_convention", "camelCase",
                PreferenceCategory.CODING_STYLE,
                f"file: {file_path}",
            )
            if s:
                summaries.append(s)

        # Detect quote style
        double_count = code.count('"') - code.count('"""') * 3
        single_count = code.count("'") - code.count("'''") * 3
        if double_count > single_count + 5:
            s = self._update_preference(
                "quote_style", "double_quotes",
                PreferenceCategory.CODING_STYLE,
            )
            if s:
                summaries.append(s)
        elif single_count > double_count + 5:
            s = self._update_preference(
                "quote_style", "single_quotes",
                PreferenceCategory.CODING_STYLE,
            )
            if s:
                summaries.append(s)

        # Detect docstring style
        if "Args:" in code:
            s = self._update_preference(
                "docstring_style", "google",
                PreferenceCategory.CODING_STYLE,
            )
            if s:
                summaries.append(s)
        elif "Parameters\n" in code and "----------" in code:
            s = self._update_preference(
                "docstring_style", "numpy",
                PreferenceCategory.CODING_STYLE,
            )
            if s:
                summaries.append(s)
        elif ":param " in code:
            s = self._update_preference(
                "docstring_style", "sphinx",
                PreferenceCategory.CODING_STYLE,
            )
            if s:
                summaries.append(s)

        # Detect type hint usage
        type_hints = len(re.findall(r':\s*(str|int|float|bool|List|Dict|Optional|Any)\b', code))
        if type_hints > 3:
            s = self._update_preference(
                "type_hints", "yes",
                PreferenceCategory.CODING_STYLE,
                f"{type_hints} type hints found",
            )
            if s:
                summaries.append(s)

        # Detect test framework
        if "def test_" in code or "class Test" in code:
            if "import pytest" in code or "@pytest" in code:
                s = self._update_preference(
                    "test_framework", "pytest",
                    PreferenceCategory.TESTING,
                )
                if s:
                    summaries.append(s)
            elif "import unittest" in code:
                s = self._update_preference(
                    "test_framework", "unittest",
                    PreferenceCategory.TESTING,
                )
                if s:
                    summaries.append(s)

        if summaries:
            self.profile.save()

        return summaries

    def _process_signal(self, signal: FeedbackSignal) -> Optional[str]:
        """Process a single feedback signal."""
        if signal.feedback_type == FeedbackType.EXPLICIT_CORRECTION:
            self.profile.record_correction(
                signal.signal, signal.context or signal.signal,
            )
            return f"Recorded correction: {signal.signal[:80]}"

        if signal.feedback_type == FeedbackType.TOOL_PREFERENCE:
            # Extract tool name and usage from signal text
            parts = signal.signal.split(": ", 1)
            if len(parts) == 2:
                action, tool = parts
                if action == "Used tool":
                    self.profile.record_tool_usage(tool)
            return None

        if signal.feedback_type == FeedbackType.STYLE_SIGNAL:
            # Parse "key: value" from signal
            if ": " in signal.signal:
                key, value = signal.signal.split(": ", 1)
                return self._update_preference(
                    key, value, signal.category, signal.context,
                )

        if signal.feedback_type in (
            FeedbackType.DIFF_ACCEPTED,
            FeedbackType.PLAN_APPROVED,
            FeedbackType.EXPLICIT_POSITIVE,
        ):
            # Positive reinforcement — if we know what preference
            # was being exercised, reinforce it
            return None  # Need more context to map to a specific pref

        if signal.feedback_type in (
            FeedbackType.DIFF_REJECTED,
            FeedbackType.EXPLICIT_NEGATIVE,
        ):
            # Negative signal — weaken recent preferences
            return None  # Would need to correlate with specific prefs

        return None

    def _update_preference(
        self,
        key: str,
        value: str,
        category: PreferenceCategory,
        example: str = "",
    ) -> Optional[str]:
        """Update or create a preference. Returns summary if changed."""
        existing = self.profile.preferences.get(key)

        if existing:
            if existing.value == value:
                existing.reinforce(example)
                if existing.signal_count == 3:  # Just became strong
                    return f"✨ Learned preference: {key} = {value} (confident)"
                return None
            else:
                existing.contradict()
                # If contradicted enough, switch the preference
                if existing.confidence < 0.3:
                    self.profile.preferences[key] = Preference(
                        key=key,
                        value=value,
                        category=category,
                        confidence=0.5,
                        signal_count=1,
                        examples=[example] if example else [],
                    )
                    return f"🔄 Updated preference: {key} = {value} (was {existing.value})"
                return None
        else:
            self.profile.preferences[key] = Preference(
                key=key,
                value=value,
                category=category,
                confidence=0.5,
                signal_count=1,
                examples=[example] if example else [],
            )
            return f"📝 Noted preference: {key} = {value}"


# ── Integration point ──────────────────────────────────────────────────────


class FeedbackSystem:
    """Top-level feedback system that ties everything together.

    Usage:
        feedback = FeedbackSystem(workspace="/path/to/project")
        feedback.on_diff_accepted(path, stats)
        feedback.on_code_written(code, path)
        feedback.on_explicit_feedback("good", positive=True)
        feedback.process()  # Batch-processes accumulated signals
        feedback.get_prompt_context()  # For system prompt injection
    """

    def __init__(self, workspace: str = ".") -> None:
        self.profile = UserProfile(workspace=workspace)
        self.collector = FeedbackCollector()
        self.learner = PreferenceLearner(self.profile)
        self._pending_code: List[Tuple[str, str]] = []  # (code, path)

    def on_diff_accepted(self, path: str, stats: Dict[str, Any] = None) -> None:
        """User accepted a diff."""
        self.collector.collect_diff_accepted(path, stats or {})

    def on_diff_rejected(self, path: str, reason: str = "") -> None:
        """User rejected a diff."""
        self.collector.collect_diff_rejected(path, reason)

    def on_code_written(self, code: str, path: str = "") -> None:
        """New code was written/accepted — queue for style analysis."""
        self._pending_code.append((code, path))

    def on_explicit_feedback(self, text: str, positive: bool) -> None:
        """User gave explicit feedback."""
        self.collector.collect_explicit(text, positive)

    def on_correction(self, original: str, corrected: str) -> None:
        """User corrected something."""
        self.collector.collect_correction(original, corrected)

    def on_tool_used(self, tool: str) -> None:
        """Track tool usage."""
        self.collector.collect_tool_preference(tool, used=True)
        self.profile.record_tool_usage(tool)

    def on_session_start(self) -> None:
        """Mark a new session."""
        self.profile.session_count += 1

    def on_turn(self) -> None:
        """Mark a conversation turn."""
        self.profile.total_turns += 1

    def process(self) -> List[str]:
        """Process all accumulated signals. Returns learning summaries."""
        summaries: List[str] = []

        # Process collected signals
        signals = self.collector.drain()
        if signals:
            summaries.extend(self.learner.learn_from_signals(signals))

        # Process pending code for style detection
        for code, path in self._pending_code:
            summaries.extend(self.learner.learn_from_code(code, path))
        self._pending_code.clear()

        # Save if anything changed
        if summaries:
            self.profile.save()

        return summaries

    def get_prompt_context(self) -> str:
        """Get preference context for system prompt injection."""
        return self.profile.get_context_prompt()

    def get_summary(self) -> str:
        """Human-readable summary."""
        return self.profile.summary()

    def stats(self) -> Dict[str, Any]:
        """Machine-readable stats."""
        return self.profile.to_dict()
