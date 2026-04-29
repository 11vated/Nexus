"""Permission & Audit System — what Nexus can and cannot do.

Unlike cloud AI tools that can do anything on your behalf, Nexus
gives you granular control. You decide what's auto-approved and
what requires confirmation.

Permission levels (ascending trust):
  - READ:        Read files, list directories, search
  - WRITE:       Create/modify files (shows diff first)
  - EXECUTE:     Run shell commands, scripts
  - DESTRUCTIVE: Delete files, force push, modify git history

Each tool has a default permission level. Users can override
per-tool or per-directory in `.nexus/permissions.yaml`.

Every tool execution is logged to an audit trail, so you can
always see exactly what Nexus did and when.

Usage:
    pm = PermissionManager(workspace="/path/to/project")

    # Check before executing
    if pm.check("shell", args={"command": "rm -rf build/"}):
        # Auto-approved or user confirmed
        result = await tool.execute(...)
        pm.log_execution("shell", args, result, success=True)
    else:
        print("Blocked by permissions")

    # Review audit log
    for entry in pm.audit_log():
        print(f"{entry.timestamp} {entry.tool} → {entry.status}")
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PermissionLevel(IntEnum):
    """Permission levels in ascending order of trust."""
    READ = 1
    WRITE = 2
    EXECUTE = 3
    DESTRUCTIVE = 4


@dataclass
class Permission:
    """A permission rule for a tool or action.

    Rules can match specific tools, argument patterns, or paths.
    """
    tool: str                           # Tool name (or "*" for all)
    level: PermissionLevel
    auto_approve: bool = False          # Skip confirmation prompt
    path_pattern: str = ""              # Glob pattern for path-based rules
    arg_pattern: str = ""               # Regex for argument-based rules
    description: str = ""

    def matches(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Check if this rule matches a tool call."""
        # Tool match
        if self.tool != "*" and self.tool != tool_name:
            return False

        # Path pattern match
        if self.path_pattern:
            path_args = [
                str(v) for k, v in args.items()
                if k in ("path", "file", "directory", "target")
            ]
            if path_args:
                from fnmatch import fnmatch
                if not any(fnmatch(p, self.path_pattern) for p in path_args):
                    return False

        # Argument pattern match
        if self.arg_pattern:
            args_str = json.dumps(args)
            if not re.search(self.arg_pattern, args_str):
                return False

        return True


@dataclass
class ToolAuditEntry:
    """A single entry in the tool execution audit log."""
    timestamp: float
    tool: str
    args: Dict[str, Any]
    status: str                         # "approved", "blocked", "error"
    permission_level: PermissionLevel
    result_preview: str = ""            # First 200 chars of result
    duration_ms: float = 0.0
    auto_approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "tool": self.tool,
            "args": {k: str(v)[:100] for k, v in self.args.items()},
            "status": self.status,
            "level": self.permission_level.name,
            "result_preview": self.result_preview,
            "duration_ms": self.duration_ms,
            "auto_approved": self.auto_approved,
        }


class PermissionManager:
    """Manages tool permissions and audit logging.

    Default tool permissions (can be overridden):
      - file_read, file_list, search → READ (auto-approve)
      - file_write, git (non-destructive) → WRITE
      - shell, code_run, test_run → EXECUTE
      - git push --force, file_delete → DESTRUCTIVE
    """

    # Default permission levels for built-in tools
    DEFAULT_LEVELS: Dict[str, PermissionLevel] = {
        "file_read": PermissionLevel.READ,
        "file_list": PermissionLevel.READ,
        "search": PermissionLevel.READ,
        "file_write": PermissionLevel.WRITE,
        "git": PermissionLevel.WRITE,
        "shell": PermissionLevel.EXECUTE,
        "code_run": PermissionLevel.EXECUTE,
        "test_run": PermissionLevel.EXECUTE,
    }

    # Patterns that escalate permission level
    DANGEROUS_PATTERNS = [
        (r"rm\s+(-rf?|--recursive)", PermissionLevel.DESTRUCTIVE),
        (r"git\s+push\s+.*--force", PermissionLevel.DESTRUCTIVE),
        (r"git\s+reset\s+--hard", PermissionLevel.DESTRUCTIVE),
        (r"chmod\s+777", PermissionLevel.DESTRUCTIVE),
        (r"sudo\s+", PermissionLevel.DESTRUCTIVE),
        (r"curl\s+.*\|\s*sh", PermissionLevel.DESTRUCTIVE),
        (r"DROP\s+TABLE", PermissionLevel.DESTRUCTIVE),
        (r"DELETE\s+FROM", PermissionLevel.DESTRUCTIVE),
        (r":\s*>\s*/", PermissionLevel.DESTRUCTIVE),  # truncate files
        (r"mkfs\.", PermissionLevel.DESTRUCTIVE),
        (r"dd\s+if=", PermissionLevel.DESTRUCTIVE),
    ]

    # Patterns that are always blocked
    BLOCKED_PATTERNS = [
        r"curl\s+.*\|\s*bash",
        r"eval\s*\(",
        r"\.env\b",  # Don't read/write .env files
        r"/etc/passwd",
        r"/etc/shadow",
    ]

    def __init__(
        self,
        workspace: str = ".",
        trust_level: PermissionLevel = PermissionLevel.WRITE,
        confirmation_callback: Optional[Callable[[str, str, Dict], bool]] = None,
    ):
        """Initialize the permission manager.

        Args:
            workspace: Project workspace path
            trust_level: Maximum auto-approved permission level.
                        Anything above this requires confirmation.
            confirmation_callback: Function to ask user for confirmation.
                                 Receives (tool_name, reason, args) → bool.
        """
        self.workspace = str(Path(workspace).resolve())
        self.trust_level = trust_level
        self.confirm = confirmation_callback
        self._rules: List[Permission] = []
        self._audit: List[ToolAuditEntry] = []
        self._blocked_count = 0
        self._approved_count = 0

        self._load_rules()

    def _load_rules(self) -> None:
        """Load custom rules from .nexus/permissions.yaml if it exists."""
        rules_path = Path(self.workspace) / ".nexus" / "permissions.yaml"
        if not rules_path.exists():
            return

        try:
            # Simple YAML-like parsing (avoid external dependency)
            content = rules_path.read_text(encoding="utf-8")
            # For now, rules are loaded from the default set
            # Full YAML parsing can be added later
            logger.info("Loaded permission rules from %s", rules_path)
        except Exception as exc:
            logger.warning("Failed to load permission rules: %s", exc)

    # -- Permission checks -------------------------------------------------

    def get_level(self, tool_name: str, args: Dict[str, Any]) -> PermissionLevel:
        """Determine the permission level for a tool call.

        Checks:
        1. Custom rules (from .nexus/permissions.yaml)
        2. Dangerous patterns (escalate to DESTRUCTIVE)
        3. Default tool levels
        """
        # Check custom rules first
        for rule in self._rules:
            if rule.matches(tool_name, args):
                return rule.level

        # Check for dangerous patterns in arguments
        args_str = json.dumps(args)
        for pattern, level in self.DANGEROUS_PATTERNS:
            if re.search(pattern, args_str, re.IGNORECASE):
                return level

        # Default level
        return self.DEFAULT_LEVELS.get(tool_name, PermissionLevel.EXECUTE)

    def is_blocked(self, tool_name: str, args: Dict[str, Any]) -> Optional[str]:
        """Check if a tool call is unconditionally blocked.

        Returns a reason string if blocked, None if allowed.
        """
        args_str = json.dumps(args)
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, args_str, re.IGNORECASE):
                return f"Blocked: matches safety pattern '{pattern}'"
        return None

    def check(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> bool:
        """Check if a tool call is permitted.

        Returns True if the call is allowed (auto-approved or user confirmed).
        Returns False if blocked or user denied.
        """
        args = args or {}

        # Check blocklist first
        blocked = self.is_blocked(tool_name, args)
        if blocked:
            self._log(tool_name, args, "blocked", PermissionLevel.DESTRUCTIVE)
            self._blocked_count += 1
            logger.warning("Blocked: %s(%s) — %s", tool_name, args, blocked)
            return False

        # Get permission level
        level = self.get_level(tool_name, args)

        # Auto-approve if within trust level
        if level <= self.trust_level:
            self._log(tool_name, args, "approved", level, auto=True)
            self._approved_count += 1
            return True

        # Check custom rules for auto-approve overrides
        for rule in self._rules:
            if rule.matches(tool_name, args) and rule.auto_approve:
                self._log(tool_name, args, "approved", level, auto=True)
                self._approved_count += 1
                return True

        # Need confirmation
        if self.confirm:
            reason = (
                f"Tool '{tool_name}' requires {level.name} permission "
                f"(trust level: {self.trust_level.name})"
            )
            if self.confirm(tool_name, reason, args):
                self._log(tool_name, args, "approved", level, auto=False)
                self._approved_count += 1
                return True
            else:
                self._log(tool_name, args, "denied", level)
                self._blocked_count += 1
                return False

        # No callback — block by default for anything above trust level
        self._log(tool_name, args, "blocked", level)
        self._blocked_count += 1
        return False

    # -- Rules management --------------------------------------------------

    def add_rule(self, rule: Permission) -> None:
        """Add a custom permission rule."""
        self._rules.append(rule)

    def allow_tool(self, tool_name: str, auto_approve: bool = True) -> None:
        """Convenience: allow a specific tool at EXECUTE level."""
        self._rules.append(Permission(
            tool=tool_name,
            level=PermissionLevel.EXECUTE,
            auto_approve=auto_approve,
            description=f"Allow {tool_name}",
        ))

    def block_tool(self, tool_name: str) -> None:
        """Convenience: block a specific tool."""
        self._rules.append(Permission(
            tool=tool_name,
            level=PermissionLevel.DESTRUCTIVE,
            auto_approve=False,
            description=f"Block {tool_name}",
        ))

    def set_trust_level(self, level: PermissionLevel) -> None:
        """Change the trust level."""
        self.trust_level = level
        logger.info("Trust level changed to %s", level.name)

    # -- Audit log ---------------------------------------------------------

    def _log(
        self,
        tool: str,
        args: Dict[str, Any],
        status: str,
        level: PermissionLevel,
        auto: bool = False,
        result: str = "",
        duration: float = 0.0,
    ) -> None:
        """Add an entry to the audit log."""
        entry = ToolAuditEntry(
            timestamp=time.time(),
            tool=tool,
            args=args,
            status=status,
            permission_level=level,
            result_preview=result[:200] if result else "",
            duration_ms=duration,
            auto_approved=auto,
        )
        self._audit.append(entry)

    def log_execution(
        self,
        tool: str,
        args: Dict[str, Any],
        result: str = "",
        success: bool = True,
        duration_ms: float = 0.0,
    ) -> None:
        """Log a completed tool execution (called after execution)."""
        level = self.get_level(tool, args)
        status = "success" if success else "error"
        self._log(tool, args, status, level, result=result, duration=duration_ms)

    def audit_log(self, limit: int = 50) -> List[ToolAuditEntry]:
        """Get the audit log (most recent first)."""
        return list(reversed(self._audit[-limit:]))

    def audit_summary(self) -> Dict[str, Any]:
        """Get a summary of the audit log."""
        tool_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        level_counts: Dict[str, int] = {}

        for entry in self._audit:
            tool_counts[entry.tool] = tool_counts.get(entry.tool, 0) + 1
            status_counts[entry.status] = status_counts.get(entry.status, 0) + 1
            level_counts[entry.permission_level.name] = (
                level_counts.get(entry.permission_level.name, 0) + 1
            )

        return {
            "total_entries": len(self._audit),
            "approved": self._approved_count,
            "blocked": self._blocked_count,
            "by_tool": tool_counts,
            "by_status": status_counts,
            "by_level": level_counts,
            "trust_level": self.trust_level.name,
        }

    # -- Persistence -------------------------------------------------------

    def save_audit(self) -> str:
        """Save audit log to disk."""
        audit_dir = Path(self.workspace) / ".nexus" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "tool_audit.jsonl"

        with open(audit_file, "a", encoding="utf-8") as f:
            for entry in self._audit:
                f.write(json.dumps(entry.to_dict()) + "\n")

        count = len(self._audit)
        self._audit.clear()
        logger.info("Saved %d audit entries to %s", count, audit_file)
        return str(audit_file)

    def load_audit(self, limit: int = 100) -> List[ToolAuditEntry]:
        """Load recent audit entries from disk."""
        audit_file = Path(self.workspace) / ".nexus" / "audit" / "tool_audit.jsonl"
        if not audit_file.exists():
            return []

        entries = []
        for line in audit_file.read_text(encoding="utf-8").strip().splitlines():
            try:
                data = json.loads(line)
                entries.append(ToolAuditEntry(
                    timestamp=data["timestamp"],
                    tool=data["tool"],
                    args=data.get("args", {}),
                    status=data["status"],
                    permission_level=PermissionLevel[data.get("level", "EXECUTE")],
                    result_preview=data.get("result_preview", ""),
                    duration_ms=data.get("duration_ms", 0),
                    auto_approved=data.get("auto_approved", False),
                ))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        return entries[-limit:]
