"""Conversation Branching — git for your coding conversations.

This is Nexus's most creative feature. Just like git lets you branch
code, Nexus lets you branch CONVERSATIONS:

  "Let me try approach A" → branch
  "Actually, try approach B" → another branch
  Compare results → pick the best → merge back

Why this matters:
  - You can explore multiple design approaches simultaneously
  - If an approach fails, just switch branches — nothing is lost
  - Compare how different models handled the same task
  - Like undo on steroids — branch history is a tree, not a stack

Mental model:
  main ─── "Build auth" ─── "Use JWT" ─── "Add middleware" ──→
                └── "Use sessions" ─── "Add Redis" ──→
                         └── "Use cookies" ──→

Usage:
    tree = ConversationTree()

    # Start on 'main' branch
    tree.add_message("user", "Build auth system")
    tree.add_message("assistant", "I'll use JWT...")

    # Branch to try a different approach
    tree.create_branch("sessions-approach")
    tree.add_message("assistant", "Actually, let's try sessions...")

    # Switch back to see what was on main
    tree.switch_branch("main")

    # Compare branches
    diff = tree.compare("main", "sessions-approach")
"""

from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BranchMessage:
    """A message in a conversation branch."""
    role: str                           # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BranchMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Branch:
    """A conversation branch — a named sequence of messages.

    Branches share a common prefix (fork point) and diverge from there.
    """
    name: str
    fork_point: int                     # Index in parent's messages where this branched
    parent_branch: Optional[str]        # Name of the parent branch (None for main)
    messages: List[BranchMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    description: str = ""
    archived: bool = False

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_turns(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "fork_point": self.fork_point,
            "parent_branch": self.parent_branch,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "description": self.description,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Branch":
        return cls(
            name=data["name"],
            fork_point=data["fork_point"],
            parent_branch=data.get("parent_branch"),
            messages=[BranchMessage.from_dict(m) for m in data.get("messages", [])],
            created_at=data.get("created_at", 0),
            description=data.get("description", ""),
            archived=data.get("archived", False),
        )


@dataclass
class BranchComparison:
    """Result of comparing two conversation branches."""
    branch_a: str
    branch_b: str
    fork_point: int                     # Where the branches diverged
    shared_messages: int                # Messages in common
    unique_a: int                       # Messages only in branch A
    unique_b: int                       # Messages only in branch B
    a_summary: str                      # Brief summary of branch A's direction
    b_summary: str                      # Brief summary of branch B's direction
    a_tool_calls: int                   # Tool calls in branch A
    b_tool_calls: int                   # Tool calls in branch B


class ConversationTree:
    """Git-like branching for conversations.

    Manages a tree of conversation branches with fork, switch,
    compare, and merge operations.
    """

    def __init__(self, workspace: str = "."):
        self.workspace = str(Path(workspace).resolve())
        self._branches: Dict[str, Branch] = {
            "main": Branch(name="main", fork_point=0, parent_branch=None),
        }
        self._current_branch = "main"
        self._save_path = Path(self.workspace) / ".nexus" / "branches"

    @property
    def current_branch(self) -> str:
        return self._current_branch

    @property
    def current(self) -> Branch:
        return self._branches[self._current_branch]

    @property
    def branch_names(self) -> List[str]:
        return list(self._branches.keys())

    @property
    def branch_count(self) -> int:
        return len(self._branches)

    # -- Message operations ------------------------------------------------

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BranchMessage:
        """Add a message to the current branch."""
        msg = BranchMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.current.messages.append(msg)
        return msg

    def get_messages(self, branch_name: Optional[str] = None) -> List[BranchMessage]:
        """Get all messages for a branch (including inherited from parent).

        Messages include the parent's messages up to the fork point,
        plus the branch's own messages.
        """
        name = branch_name or self._current_branch
        branch = self._branches.get(name)
        if not branch:
            return []

        # Build the full message chain by walking up the parent tree
        chain: List[BranchMessage] = []
        self._collect_messages(branch, chain)
        return chain

    def _collect_messages(self, branch: Branch, result: List[BranchMessage]) -> None:
        """Recursively collect messages from branch and its parents."""
        if branch.parent_branch and branch.parent_branch in self._branches:
            parent = self._branches[branch.parent_branch]
            # Get parent's messages up to the fork point
            self._collect_messages_up_to(parent, branch.fork_point, result)

        # Add this branch's own messages
        result.extend(branch.messages)

    def _collect_messages_up_to(
        self,
        branch: Branch,
        up_to: int,
        result: List[BranchMessage],
    ) -> None:
        """Collect messages from a branch up to a certain index."""
        if branch.parent_branch and branch.parent_branch in self._branches:
            parent = self._branches[branch.parent_branch]
            parent_msgs = len(parent.messages)
            if branch.fork_point <= parent_msgs:
                self._collect_messages_up_to(parent, branch.fork_point, result)
            else:
                self._collect_messages(parent, result)

        limit = min(up_to, len(branch.messages))
        result.extend(branch.messages[:limit])

    def get_history_dicts(self, branch_name: Optional[str] = None) -> List[Dict[str, str]]:
        """Get messages as simple dicts for the ChatSession."""
        return [
            {"role": m.role, "content": m.content}
            for m in self.get_messages(branch_name)
        ]

    # -- Branch operations -------------------------------------------------

    def create_branch(
        self,
        name: str,
        description: str = "",
        switch: bool = True,
    ) -> Branch:
        """Create a new branch from the current position.

        The new branch forks from the current branch at the current
        message count — everything up to now is shared.
        """
        if name in self._branches:
            raise ValueError(f"Branch '{name}' already exists")

        # Validate name
        if not name or not name.replace("-", "").replace("_", "").replace("/", "").isalnum():
            raise ValueError(
                f"Invalid branch name: '{name}'. "
                "Use letters, numbers, hyphens, underscores, or slashes."
            )

        branch = Branch(
            name=name,
            fork_point=len(self.current.messages),
            parent_branch=self._current_branch,
            description=description or f"Branched from {self._current_branch}",
        )
        self._branches[name] = branch

        if switch:
            self._current_branch = name

        logger.info(
            "Created branch '%s' from '%s' at message %d",
            name, branch.parent_branch, branch.fork_point,
        )
        return branch

    def switch_branch(self, name: str) -> Branch:
        """Switch to a different branch."""
        if name not in self._branches:
            raise ValueError(f"Branch '{name}' not found")

        self._current_branch = name
        logger.info("Switched to branch '%s'", name)
        return self._branches[name]

    def delete_branch(self, name: str) -> bool:
        """Delete a branch (cannot delete 'main' or current branch)."""
        if name == "main":
            raise ValueError("Cannot delete the 'main' branch")
        if name == self._current_branch:
            raise ValueError("Cannot delete the current branch. Switch first.")
        if name not in self._branches:
            return False

        # Check if any other branches depend on this one
        children = [
            b.name for b in self._branches.values()
            if b.parent_branch == name
        ]
        if children:
            raise ValueError(
                f"Cannot delete: branches {children} depend on '{name}'"
            )

        del self._branches[name]
        return True

    # -- Comparison --------------------------------------------------------

    def compare(self, branch_a: str, branch_b: str) -> BranchComparison:
        """Compare two branches.

        Shows where they diverged and how each one progressed.
        """
        if branch_a not in self._branches:
            raise ValueError(f"Branch '{branch_a}' not found")
        if branch_b not in self._branches:
            raise ValueError(f"Branch '{branch_b}' not found")

        msgs_a = self.get_messages(branch_a)
        msgs_b = self.get_messages(branch_b)

        # Find the common prefix (shared messages)
        shared = 0
        for i, (ma, mb) in enumerate(zip(msgs_a, msgs_b)):
            if ma.role == mb.role and ma.content == mb.content:
                shared = i + 1
            else:
                break

        unique_a = len(msgs_a) - shared
        unique_b = len(msgs_b) - shared

        # Generate summaries from divergent messages
        def summarize(messages: List[BranchMessage], start: int) -> str:
            divergent = messages[start:]
            user_msgs = [m.content for m in divergent if m.role == "user"]
            if user_msgs:
                first = user_msgs[0][:100]
                return f"{first}{'...' if len(first) >= 100 else ''} ({len(user_msgs)} user turns)"
            return f"{len(divergent)} messages"

        def count_tool_calls(messages: List[BranchMessage], start: int) -> int:
            return sum(
                1 for m in messages[start:]
                if m.role == "assistant" and "```tool" in m.content
            )

        return BranchComparison(
            branch_a=branch_a,
            branch_b=branch_b,
            fork_point=shared,
            shared_messages=shared,
            unique_a=unique_a,
            unique_b=unique_b,
            a_summary=summarize(msgs_a, shared),
            b_summary=summarize(msgs_b, shared),
            a_tool_calls=count_tool_calls(msgs_a, shared),
            b_tool_calls=count_tool_calls(msgs_b, shared),
        )

    # -- Merge -------------------------------------------------------------

    def merge(
        self,
        source: str,
        target: Optional[str] = None,
        strategy: str = "append",
    ) -> int:
        """Merge one branch into another.

        Strategies:
          - "append": add source's unique messages to target
          - "replace": replace target's divergent messages with source's

        Args:
            source: Branch to merge FROM
            target: Branch to merge INTO (default: current branch)
            strategy: Merge strategy

        Returns:
            Number of messages merged
        """
        target = target or self._current_branch

        if source not in self._branches:
            raise ValueError(f"Branch '{source}' not found")
        if target not in self._branches:
            raise ValueError(f"Branch '{target}' not found")

        source_msgs = self.get_messages(source)
        target_msgs = self.get_messages(target)

        # Find common prefix
        shared = 0
        for i, (ms, mt) in enumerate(zip(source_msgs, target_msgs)):
            if ms.role == mt.role and ms.content == mt.content:
                shared = i + 1
            else:
                break

        source_unique = source_msgs[shared:]
        target_branch = self._branches[target]

        if strategy == "append":
            # Add a merge marker and then source's unique messages
            target_branch.messages.append(BranchMessage(
                role="system",
                content=f"[Merged from branch '{source}': {len(source_unique)} messages]",
                metadata={"merge_from": source, "strategy": strategy},
            ))
            for msg in source_unique:
                merged = BranchMessage(
                    role=msg.role,
                    content=msg.content,
                    metadata={**msg.metadata, "merged_from": source},
                )
                target_branch.messages.append(merged)
            return len(source_unique)

        elif strategy == "replace":
            # Remove target's divergent messages, add source's
            target_unique_count = len(target_branch.messages) - shared
            if target_unique_count > 0:
                target_branch.messages = target_branch.messages[:shared]

            for msg in source_unique:
                target_branch.messages.append(BranchMessage(
                    role=msg.role,
                    content=msg.content,
                    metadata={**msg.metadata, "merged_from": source},
                ))
            return len(source_unique)

        else:
            raise ValueError(f"Unknown merge strategy: {strategy}")

    # -- Listing and info --------------------------------------------------

    def list_branches(self) -> List[Dict[str, Any]]:
        """List all branches with metadata."""
        result = []
        for name, branch in self._branches.items():
            total_msgs = len(self.get_messages(name))
            result.append({
                "name": name,
                "active": name == self._current_branch,
                "messages": total_msgs,
                "own_messages": branch.message_count,
                "parent": branch.parent_branch,
                "fork_point": branch.fork_point,
                "description": branch.description,
                "created_at": branch.created_at,
                "archived": branch.archived,
            })
        return result

    def tree_display(self) -> str:
        """Generate a text-based tree visualization.

        Returns something like:
        * main (5 messages) ← active
        ├── feature-a (3 messages)
        │   └── feature-a-v2 (2 messages)
        └── experiment (1 message)
        """
        lines = []
        self._tree_display_recursive("main", "", True, lines)
        return "\n".join(lines)

    def _tree_display_recursive(
        self,
        branch_name: str,
        prefix: str,
        is_last: bool,
        lines: List[str],
    ) -> None:
        """Recursively build the tree display."""
        branch = self._branches.get(branch_name)
        if not branch:
            return

        # Connector
        if branch_name == "main":
            connector = "* "
        elif is_last:
            connector = "└── "
        else:
            connector = "├── "

        # Active marker
        active = " ← active" if branch_name == self._current_branch else ""
        total = len(self.get_messages(branch_name))

        lines.append(
            f"{prefix}{connector}{branch_name} "
            f"({total} msgs, {branch.user_turns} turns){active}"
        )

        # Find children
        children = [
            b.name for b in self._branches.values()
            if b.parent_branch == branch_name
        ]

        # Recurse into children
        child_prefix = prefix + ("    " if is_last or branch_name == "main" else "│   ")
        for i, child_name in enumerate(children):
            child_is_last = (i == len(children) - 1)
            self._tree_display_recursive(child_name, child_prefix, child_is_last, lines)

    # -- Persistence -------------------------------------------------------

    def save(self) -> str:
        """Save the conversation tree to disk.

        Returns the save path.
        """
        self._save_path.mkdir(parents=True, exist_ok=True)
        save_file = self._save_path / "tree.json"

        data = {
            "current_branch": self._current_branch,
            "branches": {
                name: branch.to_dict()
                for name, branch in self._branches.items()
            },
            "saved_at": time.time(),
        }

        save_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Saved conversation tree to %s", save_file)
        return str(save_file)

    def load(self) -> bool:
        """Load the conversation tree from disk.

        Returns True if successful.
        """
        save_file = self._save_path / "tree.json"
        if not save_file.exists():
            return False

        try:
            data = json.loads(save_file.read_text(encoding="utf-8"))
            self._branches = {
                name: Branch.from_dict(bdata)
                for name, bdata in data.get("branches", {}).items()
            }
            self._current_branch = data.get("current_branch", "main")

            # Ensure main exists
            if "main" not in self._branches:
                self._branches["main"] = Branch(
                    name="main", fork_point=0, parent_branch=None
                )
                self._current_branch = "main"

            logger.info(
                "Loaded conversation tree: %d branches, active=%s",
                len(self._branches), self._current_branch,
            )
            return True
        except Exception as exc:
            logger.error("Failed to load conversation tree: %s", exc)
            return False

    # -- Utilities ---------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Get a summary of the conversation tree."""
        return {
            "current_branch": self._current_branch,
            "total_branches": len(self._branches),
            "branches": self.list_branches(),
            "tree": self.tree_display(),
        }
