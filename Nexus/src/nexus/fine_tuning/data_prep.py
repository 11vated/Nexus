"""Session data extraction and preparation for fine-tuning.

Extracts high-quality training pairs from Nexus conversations:
- Filters for successful interactions
- Removes low-quality or ambiguous exchanges
- Formats as instruction/input/output triples
- Supports Alpaca and OpenAI chat formats
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrainingPair:
    """A single instruction-response training pair."""
    instruction: str
    input_text: str = ""
    output: str = ""
    source: str = ""  # "chat", "agent_run", "tool_use"
    quality_score: float = 0.0  # 0-1, estimated quality
    tags: List[str] = field(default_factory=list)

    def to_alpaca(self) -> Dict[str, str]:
        return {
            "instruction": self.instruction,
            "input": self.input_text,
            "output": self.output,
        }

    def to_openai(self) -> List[Dict[str, str]]:
        messages = [{"role": "user", "content": self.instruction}]
        if self.input_text:
            messages.append({"role": "user", "content": self.input_text})
        messages.append({"role": "assistant", "content": self.output})
        return messages


class SessionDataExtractor:
    """Extracts training data from Nexus session files.

    Usage:
        extractor = SessionDataExtractor(workspace="/path/to/project")
        pairs = extractor.extract_from_sessions()
        extractor.export_alpaca(pairs, "output.json")
    """

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()
        self._sessions_dir = self.workspace / ".nexus" / "sessions"
        self._memory_dir = self.workspace / ".nexus_memory"

    def extract_from_sessions(self) -> List[TrainingPair]:
        """Extract training pairs from saved session files.

        Returns:
            List of TrainingPair objects.
        """
        pairs = []

        if not self._sessions_dir.exists():
            logger.warning("No sessions directory found at %s", self._sessions_dir)
            return pairs

        for session_file in self._sessions_dir.glob("*.json"):
            try:
                session = json.loads(session_file.read_text(encoding="utf-8"))
                session_pairs = self._extract_from_session(session, source="chat")
                pairs.extend(session_pairs)
                logger.info(
                    "Extracted %d pairs from %s",
                    len(session_pairs), session_file.name,
                )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read session %s: %s", session_file.name, exc)

        logger.info("Total training pairs extracted: %d", len(pairs))
        return pairs

    def extract_from_memory(self) -> List[TrainingPair]:
        """Extract training pairs from long-term memory.

        Returns:
            List of TrainingPair objects.
        """
        pairs = []

        if not self._memory_dir.exists():
            return pairs

        for memory_file in self._memory_dir.glob("*.json"):
            try:
                data = json.loads(memory_file.read_text(encoding="utf-8"))
                memory_pairs = self._extract_from_memory_entry(data)
                pairs.extend(memory_pairs)
            except (json.JSONDecodeError, OSError):
                continue

        return pairs

    def _extract_from_session(
        self, session: Dict[str, Any], source: str = "chat",
    ) -> List[TrainingPair]:
        """Extract pairs from a single session.

        Strategy:
        - User message followed by assistant response = training pair
        - Filter out short/low-quality responses
        - Score based on response length, code content, etc.
        """
        pairs = []
        messages = session.get("messages", [])

        for i in range(len(messages) - 1):
            msg = messages[i]
            next_msg = messages[i + 1]

            if msg.get("role") != "user":
                continue
            if next_msg.get("role") != "assistant":
                continue

            instruction = msg.get("content", "").strip()
            output = next_msg.get("content", "").strip()

            # Filter low-quality pairs
            if len(output) < 50:
                continue
            if output.lower().startswith(("i'm sorry", "i cannot", "i don't")):
                continue

            # Extract tags
            tags = self._extract_tags(instruction + output)

            # Score quality
            quality = self._score_quality(instruction, output)

            if quality < 0.3:
                continue

            pairs.append(TrainingPair(
                instruction=instruction,
                output=output,
                source=source,
                quality_score=quality,
                tags=tags,
            ))

        return pairs

    def _extract_from_memory_entry(
        self, entry: Dict[str, Any],
    ) -> List[TrainingPair]:
        """Extract training pairs from a memory entry."""
        pairs = []

        content = entry.get("content", "")
        metadata = entry.get("metadata", {})

        if not content:
            return pairs

        goal = metadata.get("goal", "")
        if not goal:
            return pairs

        # Memory entries are typically session summaries
        pairs.append(TrainingPair(
            instruction=f"How do I: {goal}",
            output=content,
            source="memory",
            quality_score=0.5,
            tags=["session_summary"],
        ))

        return pairs

    def _extract_tags(self, text: str) -> List[str]:
        """Extract topic tags from text."""
        tags = []

        # Code language detection
        if re.search(r'def\s+\w+|class\s+\w+|import\s+\w+', text):
            tags.append("python")
        if re.search(r'function\s+\w+|const\s+\w+\s*=|=>', text):
            tags.append("javascript")
        if re.search(r'fn\s+\w+|let\s+\w+|impl\s+', text):
            tags.append("rust")

        # Topic detection
        if any(kw in text.lower() for kw in ["api", "endpoint", "route"]):
            tags.append("api")
        if any(kw in text.lower() for kw in ["test", "pytest", "assert"]):
            tags.append("testing")
        if any(kw in text.lower() for kw in ["database", "sql", "query"]):
            tags.append("database")
        if any(kw in text.lower() for kw in ["deploy", "docker", "kubernetes"]):
            tags.append("devops")
        if any(kw in text.lower() for kw in ["refactor", "pattern", "design"]):
            tags.append("architecture")

        return tags

    def _score_quality(self, instruction: str, output: str) -> float:
        """Estimate the quality of a training pair."""
        score = 0.0

        # Response length (substantive responses score higher)
        output_len = len(output)
        if output_len > 500:
            score += 0.3
        elif output_len > 200:
            score += 0.2
        elif output_len > 100:
            score += 0.1

        # Code content (code responses are valuable)
        if "```" in output:
            score += 0.3
        if re.search(r'def |class |import ', output):
            score += 0.1

        # Specificity (avoids vague responses)
        vague_patterns = ["i think", "maybe", "perhaps", "not sure"]
        if not any(p in output.lower() for p in vague_patterns):
            score += 0.1

        # Structure (numbered lists, sections)
        if re.search(r'^\d+\.', output, re.MULTILINE):
            score += 0.1

        # Instruction clarity
        if len(instruction) > 20:
            score += 0.1

        return min(score, 1.0)

    def filter_by_quality(
        self, pairs: List[TrainingPair], min_score: float = 0.5,
    ) -> List[TrainingPair]:
        """Filter training pairs by quality score."""
        return [p for p in pairs if p.quality_score >= min_score]

    def filter_by_tags(
        self, pairs: List[TrainingPair], tags: List[str],
    ) -> List[TrainingPair]:
        """Filter training pairs by tags."""
        return [p for p in pairs if any(t in p.tags for t in tags)]

    def export_alpaca(
        self,
        pairs: List[TrainingPair],
        output_path: str,
    ) -> int:
        """Export pairs in Alpaca format.

        Args:
            pairs: Training pairs to export.
            output_path: Path to output JSON file.

        Returns:
            Number of pairs exported.
        """
        data = [p.to_alpaca() for p in pairs]
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Exported %d pairs to %s (Alpaca format)", len(data), output_path)
        return len(data)

    def export_openai(
        self,
        pairs: List[TrainingPair],
        output_path: str,
    ) -> int:
        """Export pairs in OpenAI chat format (JSONL).

        Args:
            pairs: Training pairs to export.
            output_path: Path to output JSONL file.

        Returns:
            Number of pairs exported.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for pair in pairs:
                messages = pair.to_openai()
                f.write(json.dumps({"messages": messages}) + "\n")

        logger.info("Exported %d pairs to %s (OpenAI format)", len(pairs), output_path)
        return len(pairs)

    def get_stats(self, pairs: List[TrainingPair]) -> Dict[str, Any]:
        """Get statistics about extracted training data."""
        if not pairs:
            return {"total_pairs": 0}

        tag_counts: Dict[str, int] = {}
        for pair in pairs:
            for tag in pair.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        scores = [p.quality_score for p in pairs]

        return {
            "total_pairs": len(pairs),
            "avg_quality": sum(scores) / len(scores),
            "min_quality": min(scores),
            "max_quality": max(scores),
            "avg_output_length": sum(len(p.output) for p in pairs) / len(pairs),
            "tags": tag_counts,
            "sources": {
                p.source: sum(1 for x in pairs if x.source == p.source)
                for p in pairs
            },
        }
