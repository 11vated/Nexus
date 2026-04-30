"""Session Persistence — save and resume coding conversations.

Unlike cloud tools where your chat history lives on someone else's server,
Nexus stores sessions locally as JSON files. You own your data.

Sessions capture everything needed to resume a conversation:
- Message history (what was said)
- Active files (what was being worked on)
- Stance at time of save (what mode Nexus was in)
- Model routing history (which models were used)
- Project context snapshot (what Nexus understood about the project)

Sessions are stored in .nexus/sessions/ as JSON.

Usage:
    store = SessionStore("/path/to/project")

    # Save current session
    session_id = store.save(
        messages=[...],
        metadata={"stance": "pair_programmer", "files": ["src/api.py"]},
    )

    # List saved sessions
    sessions = store.list_sessions()

    # Resume a session
    data = store.load(session_id)
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionSnapshot:
    """A saved conversation session."""
    session_id: str
    created_at: float
    updated_at: float
    title: str                          # Auto-generated or user-set
    messages: List[Dict[str, str]]      # Full message history
    metadata: Dict[str, Any]            # Stance, model routing, active files
    project_context: Dict[str, Any]     # ProjectMap snapshot
    tags: List[str] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def duration_display(self) -> str:
        """Human-readable time since creation."""
        elapsed = time.time() - self.created_at
        if elapsed < 3600:
            return f"{int(elapsed / 60)}m ago"
        elif elapsed < 86400:
            return f"{int(elapsed / 3600)}h ago"
        else:
            return f"{int(elapsed / 86400)}d ago"


class SessionStore:
    """Persistent session storage for Nexus conversations.

    Stores sessions as individual JSON files in .nexus/sessions/.
    Supports save, load, list, delete, and search operations.
    """

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()
        self.sessions_dir = self.workspace / ".nexus" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        messages: List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None,
        project_context: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Save a conversation session.

        Args:
            messages: Chat message history.
            metadata: Stance, routing, active files, etc.
            project_context: ProjectMap snapshot for context.
            title: Session title (auto-generated if not provided).
            session_id: Explicit ID (for updating existing sessions).
            tags: Optional tags for organization.

        Returns:
            The session ID.
        """
        now = time.time()

        if not session_id:
            session_id = self._generate_id()

        if not title:
            title = self._auto_title(messages)

        snapshot = SessionSnapshot(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            title=title,
            messages=messages,
            metadata=metadata or {},
            project_context=project_context or {},
            tags=tags or [],
        )

        # Check if updating existing session
        existing_path = self.sessions_dir / f"{session_id}.json"
        if existing_path.exists():
            try:
                existing = json.loads(existing_path.read_text())
                snapshot.created_at = existing.get("created_at", now)
            except (json.JSONDecodeError, KeyError):
                pass

        # Write to disk
        existing_path.write_text(
            json.dumps(asdict(snapshot), indent=2, default=str),
            encoding="utf-8",
        )

        logger.info("Session saved: %s (%d messages)", session_id, len(messages))
        return session_id

    def load(self, session_id: str) -> Optional[SessionSnapshot]:
        """Load a saved session by ID.

        Returns None if the session doesn't exist.
        """
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SessionSnapshot(**data)
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.warning("Failed to load session %s: %s", session_id, exc)
            return None

    def list_sessions(self, limit: int = 20) -> List[SessionSnapshot]:
        """List saved sessions, most recent first."""
        sessions = []
        for path in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append(SessionSnapshot(**data))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue

        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def delete(self, session_id: str) -> bool:
        """Delete a saved session."""
        path = self.sessions_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            logger.info("Session deleted: %s", session_id)
            return True
        return False

    def search(self, query: str) -> List[SessionSnapshot]:
        """Search sessions by title, content, or tags (deduplicated)."""
        query_lower = query.lower()
        results = []
        seen: set[str] = set()

        for session in self.list_sessions(limit=100):
            if session.session_id in seen:
                continue

            matched = False

            # Search in title
            if query_lower in session.title.lower():
                matched = True

            # Search in tags
            if not matched:
                for tag in session.tags:
                    if query_lower in tag.lower():
                        matched = True
                        break

            # Search in messages
            if not matched:
                for msg in session.messages:
                    if query_lower in msg.get("content", "").lower():
                        matched = True
                        break

            if matched:
                results.append(session)
                seen.add(session.session_id)

        return results

    def _generate_id(self) -> str:
        """Generate a unique session ID."""
        # Use timestamp + short uuid for readability
        ts = time.strftime("%Y%m%d-%H%M")
        short = uuid.uuid4().hex[:6]
        return f"{ts}-{short}"

    def _auto_title(self, messages: List[Dict[str, str]]) -> str:
        """Generate a title from the first user message."""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                if content:
                    # Take first line, truncate
                    first_line = content.split("\n")[0]
                    if len(first_line) > 60:
                        return first_line[:57] + "..."
                    return first_line
        return "Untitled Session"

    @property
    def count(self) -> int:
        """Number of saved sessions."""
        return len(list(self.sessions_dir.glob("*.json")))
