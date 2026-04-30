"""Temporal Intelligence — commit history analysis, code age, velocity tracking.

Understands time in the codebase: when code was written, how it evolved,
and how fast development is moving.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CommitInfo:
    """Parsed commit information."""
    hash: str
    author: str
    date: float
    message: str
    files_changed: List[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    category: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.hash,
            "author": self.author,
            "date": self.date,
            "message": self.message,
            "files_changed": self.files_changed,
            "additions": self.additions,
            "deletions": self.deletions,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommitInfo":
        return cls(
            hash=data["hash"],
            author=data["author"],
            date=data["date"],
            message=data["message"],
            files_changed=data.get("files_changed", []),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            category=data.get("category", "unknown"),
        )


@dataclass
class CodeAge:
    """Age information for a code entity."""
    entity: str
    file_path: str
    created_at: float
    last_modified: float
    last_author: str = ""
    churn_count: int = 0
    category: str = "unknown"

    @property
    def age_days(self) -> float:
        return (time.time() - self.created_at) / 86400

    @property
    def days_since_modified(self) -> float:
        return (time.time() - self.last_modified) / 86400

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "file_path": self.file_path,
            "created_at": self.created_at,
            "last_modified": self.last_modified,
            "last_author": self.last_author,
            "churn_count": self.churn_count,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeAge":
        return cls(
            entity=data["entity"],
            file_path=data["file_path"],
            created_at=data["created_at"],
            last_modified=data["last_modified"],
            last_author=data.get("last_author", ""),
            churn_count=data.get("churn_count", 0),
            category=data.get("category", "unknown"),
        )


@dataclass
class VelocityEntry:
    """A single velocity measurement."""
    task_description: str
    start_time: float
    end_time: float
    success: bool
    task_type: str = "general"
    complexity: str = "unknown"

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time

    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_description": self.task_description,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "success": self.success,
            "task_type": self.task_type,
            "complexity": self.complexity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VelocityEntry":
        return cls(
            task_description=data["task_description"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            success=data["success"],
            task_type=data.get("task_type", "general"),
            complexity=data.get("complexity", "unknown"),
        )


class TemporalIndex:
    """Per-entity timeline with commit hashes, authors, churn rate."""

    def __init__(self) -> None:
        self.entities: Dict[str, CodeAge] = {}

    def record_change(
        self,
        entity: str,
        file_path: str,
        commit_hash: str,
        author: str,
        timestamp: float,
        is_creation: bool = False,
    ) -> None:
        key = f"{file_path}:{entity}"
        if key not in self.entities:
            self.entities[key] = CodeAge(
                entity=entity,
                file_path=file_path,
                created_at=timestamp,
                last_modified=timestamp,
                last_author=author,
                churn_count=1,
            )
        else:
            age = self.entities[key]
            age.last_modified = timestamp
            age.last_author = author
            age.churn_count += 1

    def get_entity_age(self, file_path: str, entity: str) -> Optional[CodeAge]:
        return self.entities.get(f"{file_path}:{entity}")

    def get_most_churned(self, limit: int = 10) -> List[CodeAge]:
        return sorted(
            self.entities.values(),
            key=lambda x: x.churn_count,
            reverse=True,
        )[:limit]

    def get_stale_entities(self, days: int = 90) -> List[CodeAge]:
        cutoff = time.time() - (days * 86400)
        return [
            a for a in self.entities.values()
            if a.last_modified < cutoff
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": {k: v.to_dict() for k, v in self.entities.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemporalIndex":
        idx = cls()
        for key, edata in data.get("entities", {}).items():
            idx.entities[key] = CodeAge.from_dict(edata)
        return idx


class GitAnalyzer:
    """Semantic commit analysis via git log parsing."""

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path = repo_path

    def get_commits(self, limit: int = 100) -> List[CommitInfo]:
        """Get recent commits with semantic categorization."""
        try:
            cmd = [
                "git", "-C", self.repo_path, "log",
                f"--max-count={limit}",
                "--pretty=format:%H|%an|%at|%s",
                "--name-only",
                "--numstat",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return []
            return self._parse_log(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    def categorize_commits(self, commits: List[CommitInfo]) -> List[CommitInfo]:
        """Categorize commits by intent."""
        for commit in commits:
            commit.category = self._categorize_message(commit.message)
        return commits

    def analyze_patterns(self, commits: List[CommitInfo]) -> Dict[str, Any]:
        """Analyze commit patterns."""
        if not commits:
            return {}

        categories: Dict[str, int] = {}
        authors: Dict[str, int] = {}
        files: Dict[str, int] = {}
        total_additions = 0
        total_deletions = 0

        for c in commits:
            categories[c.category] = categories.get(c.category, 0) + 1
            authors[c.author] = authors.get(c.author, 0) + 1
            total_additions += c.additions
            total_deletions += c.deletions
            for f in c.files_changed:
                files[f] = files.get(f, 0) + 1

        most_changed = sorted(files.items(), key=lambda x: x[1], reverse=True)[:5]

        if len(commits) >= 2:
            time_span = commits[-1].date - commits[0].date
            commits_per_day = len(commits) / max(time_span / 86400, 1)
        else:
            commits_per_day = 0

        return {
            "total_commits": len(commits),
            "categories": categories,
            "authors": authors,
            "most_changed_files": most_changed,
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "commits_per_day": round(commits_per_day, 2),
        }

    def _parse_log(self, log_output: str) -> List[CommitInfo]:
        """Parse git log output into CommitInfo objects."""
        commits = []
        blocks = log_output.strip().split("\n\n")

        for block in blocks:
            lines = block.strip().split("\n")
            if not lines:
                continue

            header = lines[0]
            parts = header.split("|", 3)
            if len(parts) < 4:
                continue

            commit = CommitInfo(
                hash=parts[0],
                author=parts[1],
                date=float(parts[2]),
                message=parts[3],
            )

            for line in lines[1:]:
                if line.strip():
                    commit.files_changed.append(line.strip())

            commits.append(commit)

        return commits

    def _categorize_message(self, message: str) -> str:
        """Categorize a commit message by intent."""
        lower = message.lower()

        if any(k in lower for k in ["test", "spec", "coverage"]):
            return "test"
        if any(k in lower for k in ["feat", "add", "new", "create"]):
            return "feature"
        if any(k in lower for k in ["fix", "bug", "patch", "repair"]):
            return "fix"
        if any(k in lower for k in ["refactor", "clean", "restructure"]):
            return "refactor"
        if any(k in lower for k in ["doc", "readme", "comment"]):
            return "docs"
        if any(k in lower for k in ["chore", "deps", "update", "bump"]):
            return "chore"
        if any(k in lower for k in ["perf", "optimize", "fast"]):
            return "performance"

        return "other"


class VelocityTracker:
    """Track development velocity and estimate task times."""

    def __init__(self) -> None:
        self.entries: List[VelocityEntry] = []

    def record_task(
        self,
        description: str,
        start_time: float,
        end_time: float,
        success: bool,
        task_type: str = "general",
        complexity: str = "unknown",
    ) -> VelocityEntry:
        entry = VelocityEntry(
            task_description=description,
            start_time=start_time,
            end_time=end_time,
            success=success,
            task_type=task_type,
            complexity=complexity,
        )
        self.entries.append(entry)
        return entry

    def estimate_time(
        self,
        task_type: str = "general",
        complexity: str = "unknown",
    ) -> Optional[float]:
        """Estimate time in minutes for a similar task."""
        similar = [
            e for e in self.entries
            if e.task_type == task_type
            and e.complexity == complexity
            and e.success
        ]
        if not similar:
            return None
        avg_minutes = sum(e.duration_minutes for e in similar) / len(similar)
        return round(avg_minutes, 1)

    def get_average_velocity(self, days: int = 7) -> Dict[str, Any]:
        """Get velocity stats for the last N days."""
        cutoff = time.time() - (days * 86400)
        recent = [e for e in self.entries if e.start_time >= cutoff]

        if not recent:
            return {"tasks_completed": 0, "avg_duration_minutes": 0, "success_rate": 0}

        completed = [e for e in recent if e.success]
        total_duration = sum(e.duration_minutes for e in completed)
        success_rate = len(completed) / len(recent) if recent else 0

        return {
            "tasks_completed": len(completed),
            "total_tasks": len(recent),
            "avg_duration_minutes": round(total_duration / len(completed), 1) if completed else 0,
            "success_rate": round(success_rate, 2),
        }

    def is_unusually_slow(
        self,
        duration_minutes: float,
        task_type: str = "general",
        threshold: float = 2.0,
    ) -> bool:
        """Check if a task duration is unusually slow."""
        similar = [
            e for e in self.entries
            if e.task_type == task_type
            and e.success
        ]
        if len(similar) < 3:
            return False

        avg = sum(e.duration_minutes for e in similar) / len(similar)
        return duration_minutes > avg * threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self.entries[-500:]]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VelocityTracker":
        tracker = cls()
        for edata in data.get("entries", []):
            tracker.entries.append(VelocityEntry.from_dict(edata))
        return tracker


class TemporalMemory:
    """Extension to memory that supports time-range queries."""

    def __init__(self) -> None:
        self.entries: Dict[str, Dict[str, Any]] = {}

    def store(self, key: str, value: Any, timestamp: Optional[float] = None) -> None:
        self.entries[key] = {
            "value": value,
            "timestamp": timestamp or time.time(),
        }

    def get(self, key: str) -> Optional[Any]:
        entry = self.entries.get(key)
        return entry["value"] if entry else None

    def get_at_time(self, key: str, timestamp: float) -> Optional[Any]:
        """Get the value of a key at a specific time."""
        entry = self.entries.get(key)
        if entry and entry["timestamp"] <= timestamp:
            return entry["value"]
        return None

    def get_since(self, timestamp: float) -> Dict[str, Any]:
        """Get all entries modified since a timestamp."""
        return {
            k: v["value"]
            for k, v in self.entries.items()
            if v["timestamp"] >= timestamp
        }

    def get_between(self, start: float, end: float) -> Dict[str, Any]:
        return {
            k: v["value"]
            for k, v in self.entries.items()
            if start <= v["timestamp"] <= end
        }

    def delete(self, key: str) -> None:
        self.entries.pop(key, None)

    def clear_before(self, timestamp: float) -> int:
        """Remove entries older than timestamp. Returns count removed."""
        to_remove = [
            k for k, v in self.entries.items()
            if v["timestamp"] < timestamp
        ]
        for k in to_remove:
            del self.entries[k]
        return len(to_remove)

    def to_dict(self) -> Dict[str, Any]:
        return {"entries": self.entries}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemporalMemory":
        tm = cls()
        tm.entries = data.get("entries", {})
        return tm
