"""Safety & Permissions — trust but verify.

Controls what Nexus can do, logs what it did, and asks before
doing anything dangerous.
"""

from nexus.safety.permissions import (
    Permission,
    PermissionLevel,
    PermissionManager,
    ToolAuditEntry,
)

__all__ = [
    "Permission",
    "PermissionLevel",
    "PermissionManager",
    "ToolAuditEntry",
]
