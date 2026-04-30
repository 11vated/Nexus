"""Knowledge transfer — cross-agent learning and strategy sharing.

Enagents to share successful patterns:
- Extract successful strategies from high-fitness agents
- Transfer knowledge to lower-fitness agents
- Build a shared knowledge base of effective patterns
- Avoid negative transfer (harmful patterns)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """A single piece of knowledge extracted from agent performance."""
    id: str
    source_agent_id: str
    strategy_type: str  # "planning", "tool_use", "error_handling", "memory"
    pattern: str
    effectiveness: float  # 0-1, how well this pattern worked
    contexts: List[str]  # When this pattern is applicable
    usage_count: int = 0
    success_count: int = 0

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.usage_count, 1)


class KnowledgeTransfer:
    """Manages knowledge sharing between agent genomes.

    Knowledge transfer accelerates evolution by:
    1. Extracting patterns from successful agents
    2. Transferring them to struggling agents
    3. Building a collective knowledge base
    4. Pruning ineffective patterns over time
    """

    def __init__(
        self,
        max_knowledge_size: int = 100,
        min_effectiveness: float = 0.5,
        transfer_threshold: float = 0.3,
    ):
        self.max_knowledge_size = max_knowledge_size
        self.min_effectiveness = min_effectiveness
        self.transfer_threshold = transfer_threshold
        self._knowledge_base: List[KnowledgeEntry] = []
        self._transfer_history: List[Dict[str, Any]] = []
        self._agent_strategies: Dict[str, Dict[str, Any]] = {}

    def extract_knowledge(
        self,
        agent_id: str,
        task_history: List[Dict[str, Any]],
        fitness: float,
    ) -> List[KnowledgeEntry]:
        """Extract knowledge from an agent's task history.

        Args:
            agent_id: The source agent's ID.
            task_history: List of completed tasks with results.
            fitness: The agent's overall fitness score.

        Returns:
            List of extracted knowledge entries.
        """
        new_entries = []

        for task in task_history:
            # Extract planning patterns
            if task.get("planning_style") and task.get("success", False):
                entry = KnowledgeEntry(
                    id=f"plan_{agent_id}_{len(new_entries)}",
                    source_agent_id=agent_id,
                    strategy_type="planning",
                    pattern=task["planning_style"],
                    effectiveness=fitness,
                    contexts=task.get("task_type", []),
                )
                new_entries.append(entry)

            # Extract tool use patterns
            if task.get("tools_used") and task.get("success", False):
                for tool in task["tools_used"]:
                    entry = KnowledgeEntry(
                        id=f"tool_{agent_id}_{tool}_{len(new_entries)}",
                        source_agent_id=agent_id,
                        strategy_type="tool_use",
                        pattern=f"use_{tool}_for_{task.get('task_type', 'general')}",
                        effectiveness=task.get("tool_efficiency", 0.5),
                        contexts=[task.get("task_type", "general")],
                    )
                    new_entries.append(entry)

            # Extract error handling patterns
            if task.get("error_recovery") and task.get("success", False):
                entry = KnowledgeEntry(
                    id=f"error_{agent_id}_{len(new_entries)}",
                    source_agent_id=agent_id,
                    strategy_type="error_handling",
                    pattern=task["error_recovery"],
                    effectiveness=task.get("recovery_speed", 0.5),
                    contexts=[f"error:{task.get('error_type', 'unknown')}"],
                )
                new_entries.append(entry)

            # Extract memory usage patterns
            if task.get("memory_used", False):
                entry = KnowledgeEntry(
                    id=f"mem_{agent_id}_{len(new_entries)}",
                    source_agent_id=agent_id,
                    strategy_type="memory",
                    pattern=f"recall_depth={task.get('recall_depth', 3)}",
                    effectiveness=task.get("memory_hit_rate", 0.5),
                    contexts=task.get("task_type", []),
                )
                new_entries.append(entry)

        # Filter by effectiveness
        new_entries = [
            e for e in new_entries if e.effectiveness >= self.min_effectiveness
        ]

        # Add to knowledge base (with deduplication)
        for entry in new_entries:
            if not self._is_duplicate(entry):
                self._knowledge_base.append(entry)

        # Prune if too large
        if len(self._knowledge_base) > self.max_knowledge_size:
            self._knowledge_base.sort(key=lambda e: e.effectiveness, reverse=True)
            self._knowledge_base = self._knowledge_base[:self.max_knowledge_size]

        logger.info(
            "Extracted %d knowledge entries from agent %s (fitness: %.3f)",
            len(new_entries), agent_id, fitness,
        )
        return new_entries

    def transfer_knowledge(
        self,
        target_agent_id: str,
        target_fitness: float,
        task_context: str = "",
    ) -> List[KnowledgeEntry]:
        """Transfer relevant knowledge to a target agent.

        Only transfers knowledge that's likely to help (effectiveness > threshold)
        and is relevant to the current task context.

        Args:
            target_agent_id: The receiving agent's ID.
            target_fitness: The target's current fitness (transfers to lower-fitness).
            task_context: Current task type for relevance matching.

        Returns:
            List of knowledge entries transferred.
        """
        # Only transfer to agents below the effectiveness threshold
        if target_fitness >= 0.8:
            return []

        relevant = []
        for entry in self._knowledge_base:
            # Check effectiveness
            if entry.effectiveness < self.transfer_threshold:
                continue

            # Check relevance to task context
            if task_context and entry.contexts:
                if not any(
                    task_context.lower() in ctx.lower()
                    for ctx in entry.contexts
                ):
                    continue

            relevant.append(entry)

        # Sort by effectiveness (most helpful first)
        relevant.sort(key=lambda e: e.effectiveness, reverse=True)

        # Transfer top entries
        transferred = relevant[:5]

        for entry in transferred:
            entry.usage_count += 1

        self._transfer_history.append({
            "target": target_agent_id,
            "transferred_count": len(transferred),
            "task_context": task_context,
            "timestamp": time.time(),
        })

        logger.info(
            "Transferred %d knowledge entries to agent %s",
            len(transferred), target_agent_id,
        )
        return transferred

    def record_outcome(
        self,
        knowledge_id: str,
        success: bool,
    ) -> None:
        """Record whether a transferred knowledge entry was successful."""
        for entry in self._knowledge_base:
            if entry.id == knowledge_id:
                entry.usage_count += 1
                if success:
                    entry.success_count += 1
                break

    def prune_ineffective(self) -> int:
        """Remove knowledge entries with consistently low success rates."""
        before = len(self._knowledge_base)
        self._knowledge_base = [
            e for e in self._knowledge_base
            if e.success_rate >= self.min_effectiveness * 0.5
            or e.usage_count < 3  # Keep entries with few uses
        ]
        removed = before - len(self._knowledge_base)
        if removed > 0:
            logger.info("Pruned %d ineffective knowledge entries", removed)
        return removed

    def _is_duplicate(self, entry: KnowledgeEntry) -> bool:
        """Check if a knowledge entry already exists."""
        for existing in self._knowledge_base:
            if (
                existing.strategy_type == entry.strategy_type
                and existing.pattern == entry.pattern
                and existing.source_agent_id == entry.source_agent_id
            ):
                return True
        return False

    def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get a summary of the knowledge base."""
        by_type = {}
        for entry in self._knowledge_base:
            by_type.setdefault(entry.strategy_type, []).append(entry)

        return {
            "total_entries": len(self._knowledge_base),
            "by_type": {
                t: len(entries) for t, entries in by_type.items()
            },
            "avg_effectiveness": (
                sum(e.effectiveness for e in self._knowledge_base)
                / max(len(self._knowledge_base), 1)
            ),
            "avg_success_rate": (
                sum(e.success_rate for e in self._knowledge_base if e.usage_count > 0)
                / max(sum(1 for e in self._knowledge_base if e.usage_count > 0), 1)
            ),
            "transfer_count": len(self._transfer_history),
        }

    @property
    def knowledge_base(self) -> List[KnowledgeEntry]:
        return list(self._knowledge_base)
