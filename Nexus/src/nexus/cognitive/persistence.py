"""PersistenceManager — auto-save/load for all stateful Nexus components.

Knowledge learned during a session shouldn't die on exit. This module
handles persistent storage of:
- KnowledgeStore (stratified project knowledge)
- MemoryMesh (episodic, semantic, procedural memories)
- Conversation archives (completed sessions with semantic index)
- CognitiveLayer state (loop state, reasoning trace, verification)

Directory structure:
    .nexus/
    ├── knowledge.json          # Stratified knowledge store
    ├── memory.json             # Multi-memory mesh
    ├── cognitive.json          # Cognitive layer state
    ├── profile.yaml            # User preferences (managed by FeedbackSystem)
    └── conversations/          # Archived conversations
        ├── session_001.json
        ├── session_002.json
        └── index.json          # Semantic index of all conversations
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
class PersistenceStats:
    """Statistics about persistence operations."""
    last_save_time: float = 0.0
    last_load_time: float = 0.0
    save_count: int = 0
    load_count: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_save": self.last_save_time,
            "last_load": self.last_load_time,
            "saves": self.save_count,
            "loads": self.load_count,
            "errors": self.errors[-5:],
        }


class ConversationArchive:
    """Manages archived conversations with indexing.

    Completed conversations are archived to .nexus/conversations/
    with a semantic index for future reference.
    """

    def __init__(self, conversations_dir: Path):
        self.dir = conversations_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.dir / "index.json"
        self._index: List[Dict[str, Any]] = self._load_index()

    def archive(self, session_id: str, messages: List[Dict[str, str]],
                metadata: Optional[Dict[str, Any]] = None) -> str:
        """Archive a completed conversation.

        Args:
            session_id: Unique session identifier.
            messages: Conversation messages.
            metadata: Optional session metadata.

        Returns:
            Path to the archived file.
        """
        archive_data = {
            "session_id": session_id,
            "archived_at": time.time(),
            "message_count": len(messages),
            "messages": messages,
            "metadata": metadata or {},
        }

        # Extract summary for index
        summary = self._extract_summary(messages)

        archive_path = self.dir / f"{session_id}.json"
        archive_path.write_text(json.dumps(archive_data, indent=2))

        # Update index
        index_entry = {
            "session_id": session_id,
            "archived_at": archive_data["archived_at"],
            "message_count": archive_data["message_count"],
            "summary": summary,
            "tags": self._extract_tags(messages),
        }
        self._index.append(index_entry)
        self._save_index()

        logger.info("Archived conversation %s (%d messages)", session_id, len(messages))
        return str(archive_path)

    def load_archive(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load an archived conversation.

        Args:
            session_id: Session identifier to load.

        Returns:
            Archive data dict, or None if not found.
        """
        archive_path = self.dir / f"{session_id}.json"
        if not archive_path.exists():
            return None

        try:
            data = json.loads(archive_path.read_text())
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load archive %s: %s", session_id, exc)
            return None

    def list_archives(self) -> List[Dict[str, Any]]:
        """List all archived conversations."""
        return list(self._index)

    def search_archives(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search archived conversations by summary and tags.

        Args:
            query: Search query string.
            limit: Maximum results.

        Returns:
            Matching archive index entries.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for entry in self._index:
            score = 0.0
            # Search in summary
            summary_lower = entry.get("summary", "").lower()
            matches = sum(1 for w in query_words if w in summary_lower)
            if matches:
                score += matches / len(query_words)

            # Search in tags
            tags = entry.get("tags", [])
            tag_matches = sum(1 for t in tags if query_lower in t.lower())
            if tag_matches:
                score += tag_matches * 0.5

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def delete_archive(self, session_id: str) -> bool:
        """Delete an archived conversation."""
        archive_path = self.dir / f"{session_id}.json"
        if archive_path.exists():
            archive_path.unlink()
            self._index = [e for e in self._index if e["session_id"] != session_id]
            self._save_index()
            return True
        return False

    def _load_index(self) -> List[Dict[str, Any]]:
        """Load the conversation index."""
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text())
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save_index(self) -> None:
        """Save the conversation index."""
        try:
            self._index_path.write_text(json.dumps(self._index, indent=2))
        except OSError as exc:
            logger.warning("Failed to save conversation index: %s", exc)

    @staticmethod
    def _extract_summary(messages: List[Dict[str, str]]) -> str:
        """Extract a brief summary from conversation messages."""
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if not user_msgs:
            return ""

        # Use first user message as summary base
        first = user_msgs[0].get("content", "")
        # Truncate
        if len(first) > 200:
            first = first[:200] + "..."
        return first

    @staticmethod
    def _extract_tags(messages: List[Dict[str, str]]) -> List[str]:
        """Extract tags from conversation content."""
        tags = set()
        for msg in messages:
            content = msg.get("content", "").lower()
            # Detect tool usage patterns
            if "file_write" in content or "written" in content:
                tags.add("file_modification")
            if "test" in content and ("fail" in content or "pass" in content):
                tags.add("testing")
            if "error" in content or "exception" in content:
                tags.add("error_handling")
            if "refactor" in content:
                tags.add("refactoring")
        return sorted(tags)


class PersistenceManager:
    """Auto-save/load for all stateful Nexus components.

    Usage:
        manager = PersistenceManager(workspace="/my/project")

        # Load state at session start
        state = manager.load_all()
        cognitive_layer = CognitiveLayer.from_dict(state["cognitive"], workspace=...)

        # Save state at session end (or periodically)
        manager.save_all(
            knowledge=knowledge_store.to_dict(),
            memory=memory_mesh.to_dict(),
            cognitive=cognitive_layer.to_dict(),
        )

        # Archive a conversation
        manager.archive_conversation(session_id, messages, metadata)
    """

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace)
        self.nexus_dir = self.workspace / ".nexus"
        self.nexus_dir.mkdir(parents=True, exist_ok=True)

        self.stats = PersistenceStats()
        self.conversation_archive = ConversationArchive(
            self.nexus_dir / "conversations"
        )

        # Periodic save interval (seconds)
        self._save_interval = 300  # 5 minutes
        self._last_autosave = time.time()

    # ─── KnowledgeStore persistence ─────────────────────────────────────

    def save_knowledge(self, data: Dict[str, Any]) -> bool:
        """Save knowledge store data.

        Args:
            data: Serialized KnowledgeStore (from to_dict()).

        Returns:
            True if saved successfully.
        """
        path = self.nexus_dir / "knowledge.json"
        try:
            path.write_text(json.dumps(data, indent=2))
            logger.debug("Saved knowledge store (%d entries)", len(data.get("entries", [])))
            return True
        except OSError as exc:
            logger.warning("Failed to save knowledge store: %s", exc)
            self.stats.errors.append(f"knowledge save: {exc}")
            return False

    def load_knowledge(self) -> Optional[Dict[str, Any]]:
        """Load knowledge store data.

        Returns:
            Serialized data dict, or None if not found.
        """
        path = self.nexus_dir / "knowledge.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            logger.debug("Loaded knowledge store (%d entries)", len(data.get("entries", [])))
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load knowledge store: %s", exc)
            return None

    # ─── MemoryMesh persistence ────────────────────────────────────────

    def save_memory(self, data: Dict[str, Any]) -> bool:
        """Save memory mesh data.

        Args:
            data: Serialized MemoryMesh (from to_dict()).

        Returns:
            True if saved successfully.
        """
        path = self.nexus_dir / "memory.json"
        try:
            path.write_text(json.dumps(data, indent=2))
            logger.debug("Saved memory mesh (%d banks)", len(data.get("banks", {})))
            return True
        except OSError as exc:
            logger.warning("Failed to save memory mesh: %s", exc)
            self.stats.errors.append(f"memory save: {exc}")
            return False

    def load_memory(self) -> Optional[Dict[str, Any]]:
        """Load memory mesh data.

        Returns:
            Serialized data dict, or None if not found.
        """
        path = self.nexus_dir / "memory.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            logger.debug("Loaded memory mesh (%d banks)", len(data.get("banks", {})))
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load memory mesh: %s", exc)
            return None

    # ─── CognitiveLayer persistence ────────────────────────────────────

    def save_cognitive(self, data: Dict[str, Any]) -> bool:
        """Save cognitive layer state.

        Args:
            data: Serialized CognitiveLayer (from to_dict()).

        Returns:
            True if saved successfully.
        """
        path = self.nexus_dir / "cognitive.json"
        try:
            path.write_text(json.dumps(data, indent=2))
            logger.debug("Saved cognitive layer state")
            return True
        except OSError as exc:
            logger.warning("Failed to save cognitive state: %s", exc)
            self.stats.errors.append(f"cognitive save: {exc}")
            return False

    def load_cognitive(self) -> Optional[Dict[str, Any]]:
        """Load cognitive layer state.

        Returns:
            Serialized data dict, or None if not found.
        """
        path = self.nexus_dir / "cognitive.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            logger.debug("Loaded cognitive layer state")
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load cognitive state: %s", exc)
            return None

    # ─── Bulk operations ───────────────────────────────────────────────

    def save_all(self, knowledge: Optional[Dict[str, Any]] = None,
                 memory: Optional[Dict[str, Any]] = None,
                 cognitive: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Save all stateful components.

        Args:
            knowledge: Serialized KnowledgeStore data.
            memory: Serialized MemoryMesh data.
            cognitive: Serialized CognitiveLayer data.

        Returns:
            Dict of component name → success status.
        """
        results = {}

        if knowledge is not None:
            results["knowledge"] = self.save_knowledge(knowledge)
        if memory is not None:
            results["memory"] = self.save_memory(memory)
        if cognitive is not None:
            results["cognitive"] = self.save_cognitive(cognitive)

        self.stats.last_save_time = time.time()
        self.stats.save_count += 1

        logger.info(
            "Saved all state: %s",
            ", ".join(f"{k}={'ok' if v else 'fail'}" for k, v in results.items()),
        )
        return results

    def load_all(self) -> Dict[str, Optional[Dict[str, Any]]]:
        """Load all stateful components.

        Returns:
            Dict of component name → serialized data (or None if not found).
        """
        results = {
            "knowledge": self.load_knowledge(),
            "memory": self.load_memory(),
            "cognitive": self.load_cognitive(),
        }

        self.stats.last_load_time = time.time()
        self.stats.load_count += 1

        loaded = [k for k, v in results.items() if v is not None]
        if loaded:
            logger.info("Loaded state: %s", ", ".join(loaded))
        else:
            logger.info("No persisted state found")

        return results

    # ─── Conversation archival ─────────────────────────────────────────

    def archive_conversation(self, session_id: str,
                              messages: List[Dict[str, str]],
                              metadata: Optional[Dict[str, Any]] = None) -> str:
        """Archive a completed conversation.

        Args:
            session_id: Session identifier.
            messages: Conversation messages.
            metadata: Optional metadata.

        Returns:
            Path to archived file.
        """
        return self.conversation_archive.archive(session_id, messages, metadata)

    def load_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load an archived conversation.

        Args:
            session_id: Session identifier.

        Returns:
            Archive data, or None if not found.
        """
        return self.conversation_archive.load_archive(session_id)

    def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search archived conversations.

        Args:
            query: Search query.
            limit: Maximum results.

        Returns:
            Matching archive entries.
        """
        return self.conversation_archive.search_archives(query, limit)

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all archived conversations."""
        return self.conversation_archive.list_archives()

    # ─── Periodic autosave ─────────────────────────────────────────────

    def should_autosave(self) -> bool:
        """Check if it's time for a periodic autosave.

        Returns:
            True if the autosave interval has elapsed.
        """
        elapsed = time.time() - self._last_autosave
        return elapsed >= self._save_interval

    def record_autosave(self) -> None:
        """Record that an autosave was performed."""
        self._last_autosave = time.time()

    # ─── Cleanup ───────────────────────────────────────────────────────

    def cleanup_old_archives(self, max_age_days: int = 30) -> int:
        """Delete conversation archives older than max_age_days.

        Args:
            max_age_days: Maximum age in days.

        Returns:
            Number of archives deleted.
        """
        cutoff = time.time() - (max_age_days * 86400)
        deleted = 0

        for entry in self.conversation_archive.list_archives():
            if entry.get("archived_at", 0) < cutoff:
                if self.conversation_archive.delete_archive(entry["session_id"]):
                    deleted += 1

        if deleted:
            logger.info("Cleaned up %d old conversation archives", deleted)
        return deleted

    # ─── Stats ─────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get persistence statistics."""
        stats = {
            "nexus_dir": str(self.nexus_dir),
            "autosave_interval": self._save_interval,
            "last_autosave_age": round(time.time() - self._last_autosave, 1),
        }
        stats.update(self.stats.to_dict())

        # Conversation archive stats
        archives = self.conversation_archive.list_archives()
        stats["archived_conversations"] = len(archives)

        # File sizes
        for filename in ["knowledge.json", "memory.json", "cognitive.json"]:
            path = self.nexus_dir / filename
            if path.exists():
                stats[f"{filename}_size"] = path.stat().st_size

        return stats
