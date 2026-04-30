"""Diff Renderer — beautiful, interactive diff display in the terminal.

This is what makes Nexus's diff preview feel premium. Instead of raw
unified diffs, you get color-coded, syntax-aware diff display with
hunk-level accept/reject controls.

Rendering modes:
  1. Unified   — classic +/- format with colors
  2. Side-by-side — old and new content side by side
  3. Inline    — changes highlighted within lines (word-level)
  4. Summary   — just the stats (for changesets)

All renderers produce Rich renderables for the TUI.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

from nexus.diff.engine import Changeset, DiffHunk, DiffResult, DiffType


class DiffRenderer:
    """Renders diffs as Rich elements for terminal display."""

    # File extension → Rich syntax lexer
    LEXER_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "jsx",
        ".tsx": "tsx",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
        ".sh": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".sql": "sql",
        ".dockerfile": "dockerfile",
    }

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def _detect_lexer(self, path: str) -> str:
        """Detect syntax highlighter from file extension."""
        for ext, lexer in self.LEXER_MAP.items():
            if path.endswith(ext):
                return lexer
        return "text"

    # -- Unified diff rendering --------------------------------------------

    def render_unified(self, diff: DiffResult) -> Panel:
        """Render a unified diff with color coding.

        + lines in green, - lines in red, context in dim.
        Each hunk has a header showing its status.
        """
        lines = Text()

        # File header
        type_label = {
            DiffType.NEW_FILE: "✨ NEW FILE",
            DiffType.DELETE_FILE: "🗑  DELETED",
            DiffType.MODIFICATION: "✏️  MODIFIED",
            DiffType.ADDITION: "➕ ADDED",
            DiffType.DELETION: "➖ REMOVED",
            DiffType.RENAME: "📝 RENAMED",
        }
        label = type_label.get(diff.diff_type, "CHANGED")
        stats = diff.stats
        lines.append(f"  {label}  ", style="bold")
        lines.append(f"+{stats['additions']} ", style="green")
        lines.append(f"-{stats['deletions']} ", style="red")
        lines.append(f"({stats['hunks']} hunks)\n\n", style="dim")

        for hunk in diff.hunks:
            # Hunk header
            status = ""
            if hunk.accepted is True:
                status = " ✅ accepted"
            elif hunk.accepted is False:
                status = " ❌ rejected"
            else:
                status = " ⏳ pending"

            lines.append(
                f"  @@ -{hunk.old_start},{hunk.old_count} "
                f"+{hunk.new_start},{hunk.new_count} @@",
                style="cyan",
            )
            if hunk.header:
                lines.append(f" {hunk.header}", style="dim cyan")
            lines.append(f"{status}\n", style="dim")

            # Diff lines
            for line in hunk.lines:
                if line.startswith("+"):
                    lines.append(f"  {line}\n", style="green")
                elif line.startswith("-"):
                    lines.append(f"  {line}\n", style="red")
                else:
                    lines.append(f"  {line}\n", style="dim")

            lines.append("\n")

        return Panel(
            lines,
            title=f"[bold]{diff.path}[/bold]",
            border_style="yellow",
            padding=(0, 1),
        )

    # -- Side-by-side rendering --------------------------------------------

    def render_side_by_side(self, diff: DiffResult, width: int = 80) -> Panel:
        """Render a side-by-side diff with old and new content.

        Two columns showing the before and after.
        """
        table = Table(show_header=True, expand=True, padding=(0, 1))
        half_width = width // 2
        table.add_column("Before", style="red", ratio=1)
        table.add_column("After", style="green", ratio=1)

        for hunk in diff.hunks:
            old_lines = [l[1:] for l in hunk.lines if l.startswith("-")]
            new_lines = [l[1:] for l in hunk.lines if l.startswith("+")]
            ctx_lines = [l[1:] for l in hunk.lines if l.startswith(" ")]

            # Pair up old and new lines
            max_len = max(len(old_lines), len(new_lines))
            for i in range(max_len):
                old = old_lines[i] if i < len(old_lines) else ""
                new = new_lines[i] if i < len(new_lines) else ""
                old_text = Text(old[:half_width], style="red" if old else "dim")
                new_text = Text(new[:half_width], style="green" if new else "dim")
                table.add_row(old_text, new_text)

        return Panel(
            table,
            title=f"[bold]{diff.path}[/bold] (side by side)",
            border_style="yellow",
        )

    # -- Inline word-level diff --------------------------------------------

    def render_inline(self, diff: DiffResult) -> Panel:
        """Render an inline diff with word-level highlighting.

        Shows changed words highlighted within lines, not just whole lines.
        """
        import difflib

        lines = Text()

        for hunk in diff.hunks:
            old_lines = [l[1:] for l in hunk.lines if l.startswith("-")]
            new_lines = [l[1:] for l in hunk.lines if l.startswith("+")]

            # Word-level diff using SequenceMatcher
            old_text = "\n".join(old_lines)
            new_text = "\n".join(new_lines)

            matcher = difflib.SequenceMatcher(None, old_text, new_text)
            for op, i1, i2, j1, j2 in matcher.get_opcodes():
                if op == "equal":
                    lines.append(new_text[j1:j2], style="dim")
                elif op == "insert":
                    lines.append(new_text[j1:j2], style="green bold")
                elif op == "delete":
                    lines.append(old_text[i1:i2], style="red strike")
                elif op == "replace":
                    lines.append(old_text[i1:i2], style="red strike")
                    lines.append(new_text[j1:j2], style="green bold")

            lines.append("\n")

        return Panel(
            lines,
            title=f"[bold]{diff.path}[/bold] (inline)",
            border_style="yellow",
        )

    # -- Summary rendering -------------------------------------------------

    def render_summary(self, diff_or_changeset: DiffResult | Changeset) -> Panel:
        """Render a stats summary for a diff or changeset."""
        if isinstance(diff_or_changeset, Changeset):
            return self._render_changeset_summary(diff_or_changeset)
        else:
            return self._render_diff_summary(diff_or_changeset)

    def _render_diff_summary(self, diff: DiffResult) -> Panel:
        """Summary for a single file diff."""
        stats = diff.stats
        text = Text()
        text.append(f"  {diff.path}\n", style="bold")
        text.append(f"  +{stats['additions']} ", style="green")
        text.append(f"-{stats['deletions']} ", style="red")
        text.append(f"(net: {stats['net']:+d})", style="dim")
        return Panel(text, title="Diff Summary", border_style="yellow")

    def _render_changeset_summary(self, cs: Changeset) -> Panel:
        """Summary for a multi-file changeset."""
        table = Table(show_header=True, expand=True, padding=(0, 1))
        table.add_column("File", ratio=3)
        table.add_column("Type", width=10)
        table.add_column("+", style="green", width=6, justify="right")
        table.add_column("-", style="red", width=6, justify="right")
        table.add_column("Net", width=6, justify="right")

        for diff in cs.diffs:
            type_label = diff.diff_type.value
            stats = diff.stats
            net_style = "green" if stats["net"] > 0 else "red" if stats["net"] < 0 else "dim"
            table.add_row(
                Text(diff.path, style="bold"),
                Text(type_label, style="dim"),
                str(stats["additions"]),
                str(stats["deletions"]),
                Text(f"{stats['net']:+d}", style=net_style),
            )

        # Totals
        total = cs.stats
        table.add_row(
            Text(f"{total['files']} files", style="bold"),
            Text("", style="dim"),
            Text(str(total["additions"]), style="green bold"),
            Text(str(total["deletions"]), style="red bold"),
            Text(f"{total['net']:+d}", style="bold"),
        )

        return Panel(
            table,
            title=f"[bold]{cs.description}[/bold]",
            subtitle=f"[dim]{cs.id}[/dim]",
            border_style="yellow",
        )

    # -- Hunk selector (for interactive mode) ------------------------------

    def render_hunk_selector(self, diff: DiffResult) -> Panel:
        """Render hunks with selection controls for interactive review."""
        lines = Text()
        lines.append(f"  {diff.path} — {len(diff.hunks)} hunks\n\n", style="bold")

        for hunk in diff.hunks:
            # Status indicator
            if hunk.accepted is True:
                icon = "✅"
            elif hunk.accepted is False:
                icon = "❌"
            else:
                icon = "⬜"

            lines.append(
                f"  {icon} Hunk #{hunk.index}  "
                f"+{hunk.additions} -{hunk.deletions}  "
                f"@@ lines {hunk.old_start}-{hunk.old_start + hunk.old_count}\n",
                style="bold" if hunk.accepted is None else "dim",
            )

            # Show first few lines of the hunk
            preview_lines = hunk.lines[:5]
            for line in preview_lines:
                if line.startswith("+"):
                    lines.append(f"    {line}\n", style="green")
                elif line.startswith("-"):
                    lines.append(f"    {line}\n", style="red")
                else:
                    lines.append(f"    {line}\n", style="dim")

            if len(hunk.lines) > 5:
                lines.append(f"    ... +{len(hunk.lines) - 5} more lines\n", style="dim")

            lines.append("\n")

        lines.append(
            "  Commands: [a]ccept all  [r]eject all  "
            "[1-9] toggle hunk  [Enter] apply accepted\n",
            style="dim cyan",
        )

        return Panel(
            lines,
            title="[bold]Review Changes[/bold]",
            border_style="yellow",
        )

    # -- Convenience methods -----------------------------------------------

    def print_diff(self, diff: DiffResult, mode: str = "unified") -> None:
        """Print a diff to the console."""
        if mode == "unified":
            self.console.print(self.render_unified(diff))
        elif mode == "side_by_side":
            self.console.print(self.render_side_by_side(diff))
        elif mode == "inline":
            self.console.print(self.render_inline(diff))
        elif mode == "summary":
            self.console.print(self.render_summary(diff))

    def print_changeset(self, cs: Changeset, mode: str = "summary") -> None:
        """Print a changeset to the console."""
        if mode == "summary":
            self.console.print(self.render_summary(cs))
        else:
            for diff in cs.diffs:
                self.print_diff(diff, mode=mode)
