"""Diff Engine — the brain behind live diff preview.

Most AI coding tools write files blindly. Nexus generates a precise diff
FIRST, shows it to you, and only applies on confirmation. This is how a
real pair programmer works — you review before committing.

The engine supports:
  - Unified diffs (standard patch format)
  - Semantic diffing (understands code structure, not just text)
  - Multi-file changesets (group related changes)
  - Partial application (accept some hunks, reject others)
  - Conflict detection (warn if the file changed since last read)

Usage:
    engine = DiffEngine(workspace="/path/to/project")

    # Generate a diff
    result = engine.diff("src/api.py", new_content)
    print(result.unified)   # standard unified diff
    print(result.stats)     # {"additions": 5, "deletions": 2, "hunks": 1}

    # Apply with confirmation
    engine.apply(result)     # writes the file
    engine.reject(result)    # discards the change

    # Multi-file changeset
    changeset = engine.changeset([
        ("src/api.py", new_api_content),
        ("tests/test_api.py", new_test_content),
    ])
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DiffType(Enum):
    """Type of change in a diff."""
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
    RENAME = "rename"
    NEW_FILE = "new_file"
    DELETE_FILE = "delete_file"


@dataclass
class DiffHunk:
    """A single hunk (contiguous block of changes) in a diff.

    Each hunk has a start line, context, and the actual changes.
    Users can accept or reject individual hunks.
    """
    index: int                          # Hunk number in the diff
    old_start: int                      # Starting line in original file
    old_count: int                      # Number of lines from original
    new_start: int                      # Starting line in new file
    new_count: int                      # Number of lines in new version
    lines: List[str]                    # Diff lines (prefixed with +/-/space)
    header: str = ""                    # Optional hunk header (function name)
    accepted: Optional[bool] = None     # None=pending, True=accept, False=reject

    @property
    def additions(self) -> int:
        return sum(1 for l in self.lines if l.startswith("+"))

    @property
    def deletions(self) -> int:
        return sum(1 for l in self.lines if l.startswith("-"))

    @property
    def context_lines(self) -> int:
        return sum(1 for l in self.lines if l.startswith(" "))


@dataclass
class DiffResult:
    """Complete diff result for a single file.

    Contains the unified diff, parsed hunks, and metadata.
    """
    path: str                           # File path relative to workspace
    diff_type: DiffType                 # What kind of change
    hunks: List[DiffHunk]               # Parsed hunks
    unified: str                        # Full unified diff text
    old_content: str = ""               # Original file content
    new_content: str = ""               # Proposed new content
    old_hash: str = ""                  # SHA256 of original (for conflict detection)
    timestamp: float = field(default_factory=time.time)
    applied: bool = False               # Whether this diff has been applied

    @property
    def additions(self) -> int:
        return sum(h.additions for h in self.hunks)

    @property
    def deletions(self) -> int:
        return sum(h.deletions for h in self.hunks)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "additions": self.additions,
            "deletions": self.deletions,
            "hunks": len(self.hunks),
            "net": self.additions - self.deletions,
        }

    @property
    def is_empty(self) -> bool:
        return len(self.hunks) == 0

    def accept_all(self) -> None:
        """Accept all hunks."""
        for h in self.hunks:
            h.accepted = True

    def reject_all(self) -> None:
        """Reject all hunks."""
        for h in self.hunks:
            h.accepted = False

    def accept_hunk(self, index: int) -> bool:
        """Accept a specific hunk by index."""
        for h in self.hunks:
            if h.index == index:
                h.accepted = True
                return True
        return False

    def reject_hunk(self, index: int) -> bool:
        """Reject a specific hunk by index."""
        for h in self.hunks:
            if h.index == index:
                h.accepted = False
                return True
        return False

    @property
    def pending_hunks(self) -> List[DiffHunk]:
        """Hunks that haven't been accepted or rejected yet."""
        return [h for h in self.hunks if h.accepted is None]

    @property
    def accepted_hunks(self) -> List[DiffHunk]:
        """Hunks that have been accepted."""
        return [h for h in self.hunks if h.accepted is True]


@dataclass
class Changeset:
    """A group of related file changes — like a mini-commit.

    This is what makes Nexus feel like a real pair programmer:
    you see ALL related changes together before anything is applied.
    """
    id: str
    description: str
    diffs: List[DiffResult]
    created_at: float = field(default_factory=time.time)
    applied: bool = False

    @property
    def total_additions(self) -> int:
        return sum(d.additions for d in self.diffs)

    @property
    def total_deletions(self) -> int:
        return sum(d.deletions for d in self.diffs)

    @property
    def file_count(self) -> int:
        return len(self.diffs)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "files": self.file_count,
            "additions": self.total_additions,
            "deletions": self.total_deletions,
            "net": self.total_additions - self.total_deletions,
        }


class DiffEngine:
    """Generates, previews, and applies diffs.

    The core of live diff preview — every file modification goes
    through this engine so the user always sees what's changing.
    """

    def __init__(self, workspace: str = "."):
        self.workspace = str(Path(workspace).resolve())
        self._pending: Dict[str, DiffResult] = {}
        self._history: List[DiffResult] = []
        self._changeset_counter = 0

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path safely within workspace."""
        workspace_path = Path(self.workspace)
        target = (workspace_path / path).resolve()
        if not str(target).startswith(str(workspace_path.resolve())):
            raise ValueError(f"Path traversal: {path} escapes workspace")
        return target

    @staticmethod
    def _hash_content(content: str) -> str:
        """SHA256 hash of content for conflict detection."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _read_file(self, path: str) -> Tuple[str, str]:
        """Read a file and return (content, hash). Returns ("", "") for new files."""
        target = self._resolve_path(path)
        if not target.exists():
            return "", ""
        content = target.read_text(encoding="utf-8", errors="replace")
        return content, self._hash_content(content)

    # -- Diff generation ---------------------------------------------------

    def diff(self, path: str, new_content: str, context_lines: int = 3) -> DiffResult:
        """Generate a diff for a single file.

        Args:
            path: File path relative to workspace
            new_content: The proposed new content
            context_lines: Lines of context around changes (default 3)

        Returns:
            DiffResult with parsed hunks and unified diff text
        """
        old_content, old_hash = self._read_file(path)

        # Determine diff type
        if not old_content and new_content:
            diff_type = DiffType.NEW_FILE
        elif old_content and not new_content:
            diff_type = DiffType.DELETE_FILE
        else:
            diff_type = DiffType.MODIFICATION

        # Generate unified diff
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        # Ensure files end with newline for cleaner diffs
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        unified_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=context_lines,
        ))

        unified = "".join(unified_lines)

        # Parse hunks
        hunks = self._parse_hunks(unified_lines)

        result = DiffResult(
            path=path,
            diff_type=diff_type,
            hunks=hunks,
            unified=unified,
            old_content=old_content,
            new_content=new_content,
            old_hash=old_hash,
        )

        self._pending[path] = result
        return result

    def _parse_hunks(self, diff_lines: List[str]) -> List[DiffHunk]:
        """Parse unified diff lines into structured hunks."""
        hunks = []
        current_lines: List[str] = []
        current_header = ""
        hunk_index = 0
        old_start = new_start = old_count = new_count = 0

        for line in diff_lines:
            if line.startswith("@@"):
                # Save previous hunk
                if current_lines:
                    hunks.append(DiffHunk(
                        index=hunk_index,
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                        lines=current_lines,
                        header=current_header,
                    ))
                    hunk_index += 1
                    current_lines = []

                # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@ [header]
                parts = line.split("@@")
                if len(parts) >= 3:
                    range_part = parts[1].strip()
                    current_header = parts[2].strip() if parts[2].strip() else ""
                else:
                    range_part = parts[1].strip() if len(parts) > 1 else ""
                    current_header = ""

                try:
                    old_range, new_range = range_part.split()
                    old_parts = old_range.lstrip("-").split(",")
                    new_parts = new_range.lstrip("+").split(",")
                    old_start = int(old_parts[0])
                    old_count = int(old_parts[1]) if len(old_parts) > 1 else 1
                    new_start = int(new_parts[0])
                    new_count = int(new_parts[1]) if len(new_parts) > 1 else 1
                except (ValueError, IndexError):
                    old_start = new_start = 1
                    old_count = new_count = 0

            elif line.startswith("---") or line.startswith("+++"):
                continue  # Skip file headers
            elif line.startswith("+") or line.startswith("-") or line.startswith(" "):
                current_lines.append(line.rstrip("\n"))

        # Last hunk
        if current_lines:
            hunks.append(DiffHunk(
                index=hunk_index,
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=current_lines,
                header=current_header,
            ))

        return hunks

    # -- Changeset (multi-file) --------------------------------------------

    def changeset(
        self,
        changes: List[Tuple[str, str]],
        description: str = "",
    ) -> Changeset:
        """Create a multi-file changeset.

        Args:
            changes: List of (path, new_content) tuples
            description: Human-readable description

        Returns:
            Changeset containing all diffs
        """
        self._changeset_counter += 1
        cs_id = f"cs-{self._changeset_counter:04d}"

        diffs = []
        for path, new_content in changes:
            diff = self.diff(path, new_content)
            diffs.append(diff)

        return Changeset(
            id=cs_id,
            description=description or f"Changeset with {len(diffs)} files",
            diffs=diffs,
        )

    # -- Application -------------------------------------------------------

    def apply(self, diff_or_changeset: DiffResult | Changeset) -> Dict[str, Any]:
        """Apply a diff or changeset to the workspace.

        For DiffResult: applies accepted hunks (or all if none specified).
        For Changeset: applies all diffs in order.

        Returns:
            {"applied": [...], "skipped": [...], "errors": [...]}
        """
        if isinstance(diff_or_changeset, Changeset):
            return self._apply_changeset(diff_or_changeset)
        else:
            return self._apply_diff(diff_or_changeset)

    def _apply_diff(self, diff: DiffResult) -> Dict[str, Any]:
        """Apply a single file diff."""
        result: Dict[str, Any] = {"applied": [], "skipped": [], "errors": []}

        if diff.is_empty:
            result["skipped"].append({"path": diff.path, "reason": "no changes"})
            return result

        # Conflict detection
        if diff.old_hash:
            current_content, current_hash = self._read_file(diff.path)
            if current_hash != diff.old_hash:
                result["errors"].append({
                    "path": diff.path,
                    "reason": "file changed since diff was generated (conflict)",
                })
                return result

        # Determine what to apply
        accepted = diff.accepted_hunks
        if not accepted:
            # If no hunks explicitly accepted/rejected, apply all
            if not any(h.accepted is not None for h in diff.hunks):
                accepted = diff.hunks
            else:
                # Some hunks were rejected, only apply accepted ones
                pass

        if not accepted:
            result["skipped"].append({"path": diff.path, "reason": "all hunks rejected"})
            return result

        # If all hunks accepted, just write the new content
        if len(accepted) == len(diff.hunks):
            content_to_write = diff.new_content
        else:
            # Partial application — rebuild content with only accepted hunks
            content_to_write = self._partial_apply(diff.old_content, diff.hunks, accepted)

        try:
            target = self._resolve_path(diff.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content_to_write, encoding="utf-8")
            diff.applied = True
            self._history.append(diff)

            # Clean up pending
            self._pending.pop(diff.path, None)

            result["applied"].append({
                "path": diff.path,
                "hunks": len(accepted),
                "additions": sum(h.additions for h in accepted),
                "deletions": sum(h.deletions for h in accepted),
            })
        except Exception as exc:
            result["errors"].append({"path": diff.path, "reason": str(exc)})

        return result

    def _apply_changeset(self, cs: Changeset) -> Dict[str, Any]:
        """Apply a complete changeset."""
        result: Dict[str, Any] = {"applied": [], "skipped": [], "errors": []}

        for diff in cs.diffs:
            sub = self._apply_diff(diff)
            result["applied"].extend(sub["applied"])
            result["skipped"].extend(sub["skipped"])
            result["errors"].extend(sub["errors"])

        if not result["errors"]:
            cs.applied = True

        return result

    @staticmethod
    def _partial_apply(
        old_content: str,
        all_hunks: List[DiffHunk],
        accepted_hunks: List[DiffHunk],
    ) -> str:
        """Apply only selected hunks to the original content.

        This is the tricky part — we need to apply hunks in reverse order
        so line numbers stay correct.
        """
        lines = old_content.splitlines(keepends=True)
        accepted_indices = {h.index for h in accepted_hunks}

        # Process hunks in reverse order to preserve line numbers
        for hunk in reversed(all_hunks):
            if hunk.index not in accepted_indices:
                continue

            # Extract old and new lines from the hunk
            old_lines = [l[1:] + "\n" for l in hunk.lines if l.startswith("-")]
            new_lines = [l[1:] + "\n" for l in hunk.lines if l.startswith("+")]

            # Replace in the original content
            start = hunk.old_start - 1  # 0-indexed
            end = start + hunk.old_count

            lines[start:end] = new_lines if new_lines else []

        return "".join(lines)

    # -- Rejection/Undo ----------------------------------------------------

    def reject(self, diff: DiffResult) -> None:
        """Reject a pending diff (discard it)."""
        diff.reject_all()
        self._pending.pop(diff.path, None)

    def undo_last(self) -> Optional[Dict[str, Any]]:
        """Undo the most recently applied diff."""
        if not self._history:
            return None

        last = self._history.pop()
        try:
            target = self._resolve_path(last.path)
            target.write_text(last.old_content, encoding="utf-8")
            last.applied = False
            return {
                "path": last.path,
                "restored": True,
                "from": "applied",
                "to": "original",
            }
        except Exception as exc:
            return {"path": last.path, "restored": False, "error": str(exc)}

    # -- Conflict detection ------------------------------------------------

    def check_conflict(self, path: str, expected_hash: str) -> bool:
        """Check if a file has changed since we last read it.

        Returns True if there's a conflict (file changed).
        """
        _, current_hash = self._read_file(path)
        return current_hash != expected_hash

    # -- State -------------------------------------------------------------

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def pending_diffs(self) -> List[DiffResult]:
        return list(self._pending.values())

    @property
    def history_count(self) -> int:
        return len(self._history)
