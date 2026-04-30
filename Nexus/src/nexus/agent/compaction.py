"""Context Compaction Pipeline — 5-stage context management for long conversations.

The critical gap: after ~15 turns with tool use, the context window fills and the
LLM loses coherence. This pipeline prevents that by intelligently compacting context
before the budget is exceeded.

5-Stage Pipeline:
    Stage 1: DETECT    — Monitor token/character count, trigger compaction at threshold
    Stage 2: CLASSIFY  — Score every message by dynamic importance (not static priority)
    Stage 3: PRUNE     — Remove lowest-importance items first, preserve critical ones
    Stage 4: SUMMARIZE — Fast model compresses removed turns into summary paragraph
    Stage 5: RESIDUAL  — Build session state snapshot for continuity

Usage:
    pipeline = ContextCompactionPipeline(
        model_context_window=8000,  # chars for 14B model (~2K tokens)
        fast_model="qwen2.5-coder:7b",
        ollama_url="http://localhost:11434",
    )

    # Before each LLM turn, check if compaction is needed:
    if pipeline.should_compact(history_chars):
        compacted = await pipeline.compact(history, goal, plan, assumptions)
        # compacted contains: messages, summary, residual_state
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4

MODEL_CONTEXT_WINDOWS = {
    "7b": 16000,
    "14b": 32000,
    "26b": 32000,
    "70b": 32000,
    "default": 16000,
}

COMPACTION_TRIGGER_RATIO = 0.70


class ImportanceLevel(Enum):
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1


@dataclass
class CompactionConfig:
    model_context_window: int = 16000
    trigger_ratio: float = COMPACTION_TRIGGER_RATIO
    fast_model: str = "qwen2.5-coder:7b"
    ollama_url: str = "http://localhost:11434"
    preserve_last_n_user: int = 2
    preserve_last_n_assistant: int = 1
    max_summary_chars: int = 2000
    min_kept_chars_ratio: float = 0.30


@dataclass
class ImportanceScore:
    level: ImportanceLevel
    reason: str
    score: float


@dataclass
class ResidualState:
    goal: str = ""
    plan_summary: str = ""
    key_decisions: List[str] = field(default_factory=list)
    active_assumptions: List[str] = field(default_factory=list)
    user_preferences: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    errors_encountered: List[str] = field(default_factory=list)
    session_stats: Dict[str, Any] = field(default_factory=dict)

    def to_prompt(self) -> str:
        parts = ["[SESSION STATE — Compressed Context]"]
        if self.goal:
            parts.append(f"Goal: {self.goal}")
        if self.plan_summary:
            parts.append(f"Plan: {self.plan_summary}")
        if self.key_decisions:
            parts.append(f"Key decisions: {'; '.join(self.key_decisions)}")
        if self.active_assumptions:
            parts.append(f"Active assumptions: {'; '.join(self.active_assumptions)}")
        if self.user_preferences:
            parts.append(f"User preferences: {'; '.join(self.user_preferences)}")
        if self.files_modified:
            parts.append(f"Files modified: {', '.join(self.files_modified)}")
        if self.errors_encountered:
            parts.append(f"Errors encountered (resolved): {'; '.join(self.errors_encountered)}")
        if self.session_stats:
            stats_str = ", ".join(f"{k}={v}" for k, v in self.session_stats.items())
            parts.append(f"Session stats: {stats_str}")
        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "plan_summary": self.plan_summary,
            "key_decisions": self.key_decisions,
            "active_assumptions": self.active_assumptions,
            "user_preferences": self.user_preferences,
            "files_modified": self.files_modified,
            "errors_encountered": self.errors_encountered,
            "session_stats": self.session_stats,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResidualState":
        return cls(
            goal=data.get("goal", ""),
            plan_summary=data.get("plan_summary", ""),
            key_decisions=data.get("key_decisions", []),
            active_assumptions=data.get("active_assumptions", []),
            user_preferences=data.get("user_preferences", []),
            files_modified=data.get("files_modified", []),
            errors_encountered=data.get("errors_encountered", []),
            session_stats=data.get("session_stats", {}),
        )


@dataclass
class CompactionResult:
    messages: List[Dict[str, str]]
    summary: str
    residual: ResidualState
    chars_before: int
    chars_after: int
    messages_removed: int
    compaction_ratio: float


class ImportanceClassifier:
    _CRITICAL_PATTERNS = [
        r"(?:no|not|don't|stop|wait|undo|reject|wrong|incorrect|actually)",
        r"(?:prefer|like it (?:when|better|more)|style|convention|rule)",
        r"(?:plan|step \d+|proceed|approve|go ahead)",
    ]

    _HIGH_PATTERNS = [
        r"(?:error|fail|exception|traceback|crash|bug|issue)",
        r"(?:assume|assuming|assumption|believe|think that)",
        r"(?:tool.*result|tool:|exit code \d+)",
        r"(?:test.*fail|\d+ failed|assertionerror)",
    ]

    _LOW_PATTERNS = [
        r"^(?:ok|okay|sure|thanks|great|awesome|nice|cool|got it|understood)$",
        r"^(?:hello|hi|hey|good morning|good afternoon|good evening)$",
        r"^(?:yes|no|yep|nope|yeah)$",
        r"(?:let me know|feel free|happy to help|glad to help)",
    ]

    @classmethod
    def classify(cls, message: Dict[str, str], is_last: bool = False,
                 message_index: int = 0, total_messages: int = 0) -> ImportanceScore:
        role = message.get("role", "")
        content = message.get("content", "").strip()
        content_lower = content.lower()

        if is_last and role == "user":
            return ImportanceScore(
                level=ImportanceLevel.CRITICAL,
                reason="Most recent user message",
                score=1.0,
            )

        if role == "system":
            return ImportanceScore(
                level=ImportanceLevel.CRITICAL,
                reason="System prompt",
                score=1.0,
            )

        for pattern in cls._CRITICAL_PATTERNS:
            if re.search(pattern, content_lower):
                return ImportanceScore(
                    level=ImportanceLevel.CRITICAL,
                    reason=f"Matches critical pattern",
                    score=0.9,
                )

        if role == "user" and "[tool:" in content_lower:
            if any(kw in content_lower for kw in ["error", "fail", "exit code", "denied", "blocked"]):
                return ImportanceScore(
                    level=ImportanceLevel.HIGH,
                    reason="Tool failure result",
                    score=0.75,
                )
            return ImportanceScore(
                level=ImportanceLevel.MEDIUM,
                reason="Successful tool result",
                score=0.5,
            )

        for pattern in cls._HIGH_PATTERNS:
            if re.search(pattern, content_lower):
                return ImportanceScore(
                    level=ImportanceLevel.HIGH,
                    reason="Matches high-importance pattern",
                    score=0.7,
                )

        for pattern in cls._LOW_PATTERNS:
            if re.search(pattern, content_lower):
                return ImportanceScore(
                    level=ImportanceLevel.LOW,
                    reason="Matches low-importance pattern",
                    score=0.2,
                )

        if role == "assistant":
            return ImportanceScore(
                level=ImportanceLevel.MEDIUM,
                reason="Assistant response",
                score=0.5,
            )

        if role == "user":
            return ImportanceScore(
                level=ImportanceLevel.HIGH,
                reason="User message",
                score=0.65,
            )

        return ImportanceScore(
            level=ImportanceLevel.MEDIUM,
            reason="Default",
            score=0.4,
        )


class ContextSummarizer:
    SUMMARIZE_PROMPT = """\
Summarize the following conversation turns into a concise paragraph.
Focus on: what was discussed, what decisions were made, what was built or changed,
and any errors that were fixed. Omit greetings and filler.

Conversation:
{conversation}

Summary (max 2000 chars):"""

    def __init__(self, fast_model: str = "qwen2.5-coder:7b",
                 ollama_url: str = "http://localhost:11434"):
        self.fast_model = fast_model
        self.ollama_url = ollama_url

    async def summarize(self, messages: List[Dict[str, str]],
                        max_chars: int = 2000) -> str:
        if not messages:
            return ""

        conv_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if len(content) > 500:
                content = content[:500] + "..."
            conv_parts.append(f"[{role}]: {content}")

        conversation = "\n\n".join(conv_parts)
        prompt = self.SUMMARIZE_PROMPT.format(conversation=conversation)

        try:
            summary = await self._call_model(prompt)
            if len(summary) > max_chars:
                summary = summary[:max_chars] + "..."
            return summary
        except Exception as exc:
            logger.warning("Summarization failed, using fallback: %s", exc)
            return self._fallback_summary(messages)

    async def _call_model(self, prompt: str) -> str:
        import aiohttp

        payload = {
            "model": self.fast_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 500},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()
                return data.get("message", {}).get("content", "").strip()

    @staticmethod
    def _fallback_summary(messages: List[Dict[str, str]]) -> str:
        user_msgs = [m for m in messages if m.get("role") == "user"]
        tool_results = [m for m in messages if m.get("role") == "user"
                        and "[tool:" in m.get("content", "").lower()]

        parts = [f"[Compressed: {len(messages)} turns, {len(user_msgs)} user messages]"]

        if tool_results:
            tools_used = set()
            for m in tool_results:
                match = re.search(r"\[tool:\s*(\w+)", m.get("content", "").lower())
                if match:
                    tools_used.add(match.group(1))
            if tools_used:
                parts.append(f"Tools used: {', '.join(tools_used)}")

        user_contents = []
        for m in user_msgs:
            content = m.get("content", "")
            if not content.startswith("[Tool:"):
                user_contents.append(content[:100])

        if user_contents:
            parts.append(f"User asked about: {'; '.join(user_contents[:3])}")

        return " ".join(parts)


class ResidualStateBuilder:
    @classmethod
    def build(cls, messages: List[Dict[str, str]],
              goal: str = "",
              plan_steps: Optional[List[str]] = None,
              assumptions: Optional[List[str]] = None,
              user_preferences: Optional[List[str]] = None,
              session_stats: Optional[Dict[str, Any]] = None) -> ResidualState:
        residual = ResidualState(
            goal=goal,
            session_stats=session_stats or {},
        )

        if plan_steps:
            completed = sum(1 for s in plan_steps if "done" in s.lower() or "complete" in s.lower())
            total = len(plan_steps)
            residual.plan_summary = f"{completed}/{total} steps completed"
            for step in plan_steps[:5]:
                if step.strip():
                    residual.key_decisions.append(f"Plan: {step.strip()[:80]}")

        if assumptions:
            residual.active_assumptions = list(assumptions)

        if user_preferences:
            residual.user_preferences = list(user_preferences)

        files_modified = set()
        errors = []
        decisions = []

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            file_write_patterns = [
                r"(?:written|wrote|created|saved).*?(\S+\.\w+)",
                r"file[_ ]?write.*?(\S+\.\w+)",
                r"(?:to|in)\s+(\S+\.py|\S+\.js|\S+\.ts|\S+\.tsx|\S+\.html|\S+\.css)",
            ]
            for pattern in file_write_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    files_modified.add(match.group(1))

            if role == "user" and ("[tool:" in content.lower() or "[exit code" in content.lower()):
                if any(kw in content.lower() for kw in ["error", "fail", "exit code"]):
                    error_match = re.search(r"(error|fail|exception)[:\s]+(.+?)(?:\n|$)", content, re.IGNORECASE)
                    if error_match:
                        errors.append(error_match.group(2).strip()[:100])

            if role == "assistant" and any(kw in content.lower() for kw in ["i'll use", "i'll create", "approach", "decided to"]):
                decision = content[:100].strip()
                if decision:
                    decisions.append(decision)

        residual.files_modified = sorted(files_modified)
        residual.errors_encountered = errors[:5]
        residual.key_decisions.extend(decisions[:5])

        return residual


class ContextCompactionPipeline:
    def __init__(self, model_context_window: int = 16000,
                 config: Optional[CompactionConfig] = None):
        self.config = config or CompactionConfig(
            model_context_window=model_context_window,
        )
        self.classifier = ImportanceClassifier()
        self.summarizer = ContextSummarizer(
            fast_model=self.config.fast_model,
            ollama_url=self.config.ollama_url,
        )
        self.state_builder = ResidualStateBuilder()

        self._compaction_count = 0
        self._total_chars_compacted = 0
        self._total_messages_removed = 0

    @property
    def trigger_threshold(self) -> int:
        return int(self.config.model_context_window * self.config.trigger_ratio)

    @property
    def target_chars(self) -> int:
        return int(self.config.model_context_window * 0.50)

    def should_compact(self, current_chars: int) -> bool:
        threshold = self.trigger_threshold
        should = current_chars > threshold
        if should:
            logger.info(
                "Compaction triggered: %d chars > %d threshold (%.0f%% of window)",
                current_chars, threshold,
                current_chars / self.config.model_context_window * 100,
            )
        return should

    def classify_messages(self, messages: List[Dict[str, str]]) -> List[Tuple[Dict[str, str], ImportanceScore]]:
        total = len(messages)
        scored = []
        for i, msg in enumerate(messages):
            is_last = (i == total - 1)
            score = self.classifier.classify(
                msg,
                is_last=is_last,
                message_index=i,
                total_messages=total,
            )
            scored.append((msg, score))
        return scored

    @staticmethod
    def prune(scored: List[Tuple[Dict[str, str], ImportanceScore]],
              target_chars: int,
              min_kept_ratio: float = 0.30) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        by_importance = sorted(
            scored,
            key=lambda x: (x[1].score, scored.index(x)),
        )

        min_keep = max(int(len(scored) * min_kept_ratio), 2)

        kept = list(scored)
        removed = []

        for msg, score in by_importance:
            if len(kept) <= min_keep:
                break

            current_chars = sum(len(m.get("content", "")) for m, _ in kept)
            if current_chars <= target_chars:
                break

            if score.level == ImportanceLevel.CRITICAL:
                continue

            kept.remove((msg, score))
            removed.append(msg)

        kept_messages = [msg for msg, _ in kept]
        return kept_messages, removed

    async def summarize_removed(self, removed: List[Dict[str, str]]) -> str:
        if not removed:
            return ""
        return await self.summarizer.summarize(
            removed,
            max_chars=self.config.max_summary_chars,
        )

    def build_residual(self, messages: List[Dict[str, str]],
                       goal: str = "",
                       plan_steps: Optional[List[str]] = None,
                       assumptions: Optional[List[str]] = None,
                       user_preferences: Optional[List[str]] = None,
                       session_stats: Optional[Dict[str, Any]] = None) -> ResidualState:
        return self.state_builder.build(
            messages=messages,
            goal=goal,
            plan_steps=plan_steps,
            assumptions=assumptions,
            user_preferences=user_preferences,
            session_stats=session_stats,
        )

    async def compact(self, messages: List[Dict[str, str]],
                      goal: str = "",
                      plan_steps: Optional[List[str]] = None,
                      assumptions: Optional[List[str]] = None,
                      user_preferences: Optional[List[str]] = None,
                      session_stats: Optional[Dict[str, Any]] = None) -> CompactionResult:
        chars_before = sum(len(m.get("content", "")) for m in messages)

        logger.info("Starting compaction: %d messages, %d chars", len(messages), chars_before)

        scored = self.classify_messages(messages)

        kept, removed = self.prune(
            scored,
            target_chars=self.target_chars,
            min_kept_ratio=self.config.min_kept_chars_ratio,
        )

        summary = await self.summarizer.summarize(
            removed,
            max_chars=self.config.max_summary_chars,
        )

        residual = self.build_residual(
            messages,
            goal=goal,
            plan_steps=plan_steps,
            assumptions=assumptions,
            user_preferences=user_preferences,
            session_stats=session_stats,
        )

        final_messages: List[Dict[str, str]] = []

        residual_prompt = residual.to_prompt()
        if residual_prompt:
            final_messages.append({
                "role": "system",
                "content": residual_prompt,
            })

        if summary:
            final_messages.append({
                "role": "system",
                "content": f"[Previous conversation summary]\n{summary}",
            })

        final_messages.extend(kept)

        chars_after = sum(len(m.get("content", "")) for m in final_messages)

        result = CompactionResult(
            messages=final_messages,
            summary=summary,
            residual=residual,
            chars_before=chars_before,
            chars_after=chars_after,
            messages_removed=len(removed),
            compaction_ratio=chars_after / chars_before if chars_before > 0 else 1.0,
        )

        self._compaction_count += 1
        self._total_chars_compacted += chars_before - chars_after
        self._total_messages_removed += len(removed)

        logger.info(
            "Compaction complete: %d → %d chars (%.0f%% reduction), %d messages removed",
            chars_before, chars_after,
            (1 - result.compaction_ratio) * 100,
            len(removed),
        )

        return result

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "compaction_count": self._compaction_count,
            "total_chars_compacted": self._total_chars_compacted,
            "total_messages_removed": self._total_messages_removed,
            "trigger_threshold": self.trigger_threshold,
            "target_chars": self.target_chars,
        }
