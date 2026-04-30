"""Live diff preview — see changes before they happen.

Nexus shows you exactly what will change BEFORE writing files.
Accept, reject, or edit diffs interactively.
"""

from nexus.diff.engine import DiffEngine, DiffHunk, DiffResult, DiffType
from nexus.diff.renderer import DiffRenderer

__all__ = [
    "DiffEngine",
    "DiffHunk",
    "DiffResult",
    "DiffType",
    "DiffRenderer",
]
