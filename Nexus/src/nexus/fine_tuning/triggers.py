"""Auto-retraining triggers — when to fine-tune based on performance.

Monitors agent performance and triggers retraining when:
- Performance degradation detected
- Sufficient new training data accumulated
- Specific tags/domains need improvement
- Scheduled retraining intervals elapsed
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TriggerConfig:
    """Configuration for retraining triggers."""
    min_session_count: int = 50  # Minimum sessions before triggering
    min_new_sessions: int = 20  # New sessions since last training
    performance_threshold: float = 0.6  # Trigger if avg score drops below
    max_days_since_training: int = 30  # Force retrain after this many days
    check_interval_seconds: int = 3600  # Check every hour
    tags_to_monitor: Optional[List[str]] = None  # Only monitor these tags


@dataclass
class TriggerResult:
    """Result of a trigger check."""
    should_retrain: bool
    reason: str = ""
    training_data_available: int = 0
    current_performance: float = 0.0
    days_since_last_training: int = 0


class RetrainingTrigger:
    """Monitors agent performance and triggers retraining.

    Usage:
        trigger = RetrainingTrigger(workspace="/path/to/project")
        result = trigger.check()
        if result.should_retrain:
            pipeline.run(TrainingConfig(...))
    """

    def __init__(
        self,
        workspace: str = ".",
        config: Optional[TriggerConfig] = None,
    ):
        self.workspace = Path(workspace).resolve()
        self.config = config or TriggerConfig()
        self._state_file = self.workspace / ".nexus_models" / "trigger_state.json"
        self._state = self._load_state()

    def check(self) -> TriggerResult:
        """Check if retraining should be triggered.

        Returns:
            TriggerResult with decision and reasoning.
        """
        reasons = []
        session_count = self._count_sessions()
        new_sessions = self._count_new_sessions()
        performance = self._estimate_performance()
        days_since = self._days_since_last_training()

        # Check 1: Sufficient new data
        if new_sessions >= self.config.min_new_sessions:
            reasons.append(
                f"{new_sessions} new sessions since last training "
                f"(threshold: {self.config.min_new_sessions})"
            )

        # Check 2: Performance degradation
        if performance < self.config.performance_threshold:
            reasons.append(
                f"Performance dropped to {performance:.2f} "
                f"(threshold: {self.config.performance_threshold})"
            )

        # Check 3: Time-based retraining
        if days_since >= self.config.max_days_since_training:
            reasons.append(
                f"{days_since} days since last training "
                f"(max: {self.config.max_days_since_training})"
            )

        # Check 4: Minimum data threshold
        if session_count < self.config.min_session_count:
            return TriggerResult(
                should_retrain=False,
                reason=f"Only {session_count} sessions (need {self.config.min_session_count})",
                training_data_available=session_count,
                current_performance=performance,
                days_since_last_training=days_since,
            )

        should_retrain = len(reasons) > 0
        result = TriggerResult(
            should_retrain=should_retrain,
            reason="; ".join(reasons) if reasons else "No triggers activated",
            training_data_available=session_count,
            current_performance=performance,
            days_since_last_training=days_since,
        )

        if should_retrain:
            logger.info("Retraining triggered: %s", result.reason)
            self._update_state()

        return result

    def force_trigger(self) -> TriggerResult:
        """Force a retraining trigger regardless of conditions."""
        session_count = self._count_sessions()
        result = TriggerResult(
            should_retrain=True,
            reason="Force triggered by user",
            training_data_available=session_count,
        )
        self._update_state()
        return result

    def _count_sessions(self) -> int:
        """Count total session files."""
        sessions_dir = self.workspace / ".nexus" / "sessions"
        if not sessions_dir.exists():
            return 0
        return len(list(sessions_dir.glob("*.json")))

    def _count_new_sessions(self) -> int:
        """Count sessions since last training."""
        sessions_dir = self.workspace / ".nexus" / "sessions"
        if not sessions_dir.exists():
            return 0

        last_training = self._state.get("last_training_time", 0)
        count = 0

        for session_file in sessions_dir.glob("*.json"):
            try:
                mtime = session_file.stat().st_mtime
                if mtime > last_training:
                    count += 1
            except OSError:
                continue

        return count

    def _estimate_performance(self) -> float:
        """Estimate current agent performance from recent sessions."""
        sessions_dir = self.workspace / ".nexus" / "sessions"
        if not sessions_dir.exists():
            return 0.5  # Neutral

        scores = []
        recent_files = sorted(
            sessions_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:20]  # Check last 20 sessions

        for session_file in recent_files:
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                # Look for success indicators
                result = data.get("result", {})
                if isinstance(result, dict):
                    success = result.get("success", False)
                    scores.append(1.0 if success else 0.0)
            except (json.JSONDecodeError, OSError):
                continue

        if not scores:
            return 0.5

        return sum(scores) / len(scores)

    def _days_since_last_training(self) -> int:
        """Get days since last training."""
        last_training = self._state.get("last_training_time", 0)
        if last_training == 0:
            return 999  # Never trained
        return int((time.time() - last_training) / 86400)

    def _update_state(self) -> None:
        """Update trigger state after a training trigger."""
        self._state["last_training_time"] = time.time()
        self._state["trigger_count"] = self._state.get("trigger_count", 0) + 1
        self._save_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load trigger state from disk."""
        if self._state_file.exists():
            try:
                return json.loads(self._state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_state(self) -> None:
        """Save trigger state to disk."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(self._state, indent=2),
            encoding="utf-8",
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get trigger statistics."""
        return {
            "total_sessions": self._count_sessions(),
            "new_sessions": self._count_new_sessions(),
            "current_performance": self._estimate_performance(),
            "days_since_training": self._days_since_last_training(),
            "trigger_count": self._state.get("trigger_count", 0),
            "last_training_time": self._state.get("last_training_time", 0),
        }
