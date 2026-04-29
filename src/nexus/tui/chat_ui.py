"""Chat TUI — a three-pane terminal interface for collaborative coding.

This is the primary Nexus experience. Not a boring input-and-print chat
window, but a full Rich-powered dashboard:

    ┌────────── Header ──────────┐
    │  Nexus Chat ⚡ coder mode  │
    ├──────────────┬─────────────┤
    │              │  Tools/Ctx  │
    │  Chat Pane   │  - tools    │
    │  (scrolling  │  - project  │
    │   messages)  │  - routing  │
    │              │  - diffs    │
    │              │  - branch   │
    │              │  - audit    │
    ├──────────────┴─────────────┤
    │  > your message here       │
    └────────────────────────────┘

The chat pane scrolls and supports:
  - Markdown rendering in messages
  - Syntax highlighting in code blocks
  - Tool call/result display with icons
  - Diff preview panels (unified, side-by-side, inline)
  - Branch context indicator
  - Streaming tokens (word by word)

Slash commands let you control the session without leaving the chat:
  /help            Show this help
  /plan <x>        Ask for a plan
  /tools           List available tools
  /stance [name]   Set or show stance
  /project         Show project intelligence
  /route           Show model routing history
  /save [name]     Save session
  /load            Load a session
  /clear           Clear history
  /stats           Show session stats
  /diff [mode]     Show pending diffs (unified|side|inline|summary)
  /branch <name>   Create a new branch
  /branches        List branches
  /switch <name>   Switch to a branch
  /compare <a> <b> Compare two branches
  /merge <src>     Merge a branch into current
  /tree            Show branch tree
  /accept [path]   Accept pending diff
  /reject [path]   Reject pending diff
  /undo            Undo last applied change
  /audit [n]       Show audit log
  /trust [level]   Show/set trust level
  /hooks           List registered hooks
  /watch           Show watcher status
  /quit            Exit
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

from nexus.agent.chat import ChatEvent, ChatSession, EventType
from nexus.agent.models import AgentConfig


def _make_layout() -> Layout:
    """Build the three-pane layout skeleton."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="chat", ratio=3, minimum_size=40),
        Layout(name="sidebar", ratio=1, minimum_size=20),
    )
    return layout


def _header_panel(session: ChatSession) -> Panel:
    """Render the header bar with model + stance + branch info."""
    stance_info = ""
    if session._stances:
        cfg = session._stances.current_config
        stance_info = f"  {cfg.emoji} {cfg.display_name}"

    branch_info = ""
    if session._branch_tree and session._branch_tree.branch_count > 1:
        branch_info = f"  🌿 {session.current_branch}"
    elif session._branch_tree:
        branch_info = "  🌿 main"

    trust_info = ""
    if session._permissions:
        trust_info = f"  🔒 {session.get_trust_level()}"

    diff_info = ""
    if session._diff_engine and session._diff_engine.pending_count > 0:
        diff_info = f"  📋 {session._diff_engine.pending_count} pending diffs"

    return Panel(
        Text.assemble(
            ("Nexus Chat", "bold cyan"),
            ("  ⚡ ", "yellow"),
            (session.model, "dim"),
            (stance_info, "magenta"),
            (branch_info, "green"),
            (trust_info, "yellow"),
            (diff_info, "blue"),
        ),
        style="cyan",
    )


def _footer_panel() -> Panel:
    """Render the input prompt footer."""
    return Panel(
        Text.assemble(
            (" > ", "bold green"),
            ("Type a message or /help for commands", "dim"),
        ),
        style="green",
    )


def _chat_panel(messages: list[dict]) -> Panel:
    """Render the chat pane (scrolling message list)."""
    lines = Text()

    for msg in messages[-50:]:  # Scrollback limit
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Skip internal tool-result forwarding messages
        if content.startswith("[Tool results — do not repeat"):
            continue

        if role == "user":
            lines.append("  You  ", style="bold green")
            lines.append(content[:500] + ("\n" if len(content) <= 500 else "…\n"))
        elif role == "assistant":
            lines.append("  Nexus  ", style="bold cyan")
            # Truncate very long responses for display
            display = content[:2000]
            lines.append(display + "\n")
        elif role == "system":
            lines.append(f"  ⚙ {content}\n", style="dim")

        lines.append("\n")

    if not messages:
        lines.append("  Start chatting! Send a message or type /help.\n", style="dim")

    return Panel(lines, title="[bold]Chat[/bold]", border_style="cyan")


def _sidebar_panel(session: ChatSession, activity: list[str]) -> Panel:
    """Render the sidebar with tools, project context, branch, diff, and audit info."""
    text = Text()

    # Model & Routing
    text.append("  🧠 Model\n", style="bold cyan")
    text.append(f"   {session.model}\n", style="dim")
    if session._router:
        stats = session.get_routing_stats()
        if stats.get("total_routed", 0) > 0:
            text.append(f"   Routed: {stats['total_routed']}\n", style="dim")
    text.append("\n")

    # Stance
    if session._stances:
        cfg = session._stances.current_config
        text.append("  🎭 Stance\n", style="bold cyan")
        text.append(f"   {cfg.emoji} {cfg.display_name}\n", style="dim")
        text.append("\n")

    # Branch info
    if session._branch_tree:
        text.append("  🌿 Branch\n", style="bold cyan")
        text.append(f"   {session.current_branch}", style="green")
        if session._branch_tree.branch_count > 1:
            text.append(f" (+{session._branch_tree.branch_count - 1})", style="dim")
        text.append("\n\n")

    # Diff info
    if session._diff_engine:
        text.append("  📋 Diffs\n", style="bold cyan")
        pending = session._diff_engine.pending_count
        history = session._diff_engine.history_count
        if pending > 0:
            text.append(f"   ⏳ {pending} pending\n", style="yellow")
        text.append(f"   ✅ {history} applied\n", style="dim")
        text.append("\n")

    # Safety/Trust
    if session._permissions:
        text.append("  🔒 Safety\n", style="bold cyan")
        text.append(f"   Trust: {session.get_trust_level()}\n", style="dim")
        summary = session.get_audit_summary()
        if summary:
            text.append(f"   Approved: {summary.get('approved', 0)}\n", style="dim green")
            text.append(f"   Blocked: {summary.get('blocked', 0)}\n", style="dim red")
        text.append("\n")

    # Hooks
    if session._hooks:
        hooks = session.get_hooks()
        if hooks:
            text.append("  🪝 Hooks\n", style="bold cyan")
            text.append(f"   {len(hooks)} registered\n", style="dim")
            text.append("\n")

    # Project info
    if session._project_map:
        summary = session.get_project_summary()
        if summary:
            text.append("  📁 Project\n", style="bold cyan")
            text.append(f"   {summary.get('name', '?')}\n", style="dim")
            text.append(f"   {summary.get('file_count', 0)} files\n", style="dim")
            text.append("\n")

    # Recent activity
    if activity:
        text.append("  ⚡ Activity\n", style="bold cyan")
        for line in activity[-8:]:
            text.append(f"   {line}\n", style="dim")

    return Panel(text, title="[bold]Context[/bold]", border_style="yellow")


# ---------------------------------------------------------------------------
# Command handling — the slash command engine
# ---------------------------------------------------------------------------

async def _handle_command(cmd: str, session: ChatSession, console: Console) -> Optional[str]:
    """Handle a slash command.

    Returns a string to display as system feedback, or None to
    indicate the session should quit.
    """
    parts = cmd.strip().split(maxsplit=2)
    command = parts[0].lower()
    arg1 = parts[1] if len(parts) > 1 else ""
    arg2 = parts[2] if len(parts) > 2 else ""

    # -- Session management -----------------------------------------------

    if command == "/help":
        return (
            "╭─── Nexus Chat Commands ───────────────────────────╮\n"
            "│                                                   │\n"
            "│  💬 Chat                                          │\n"
            "│  /plan <x>      Ask for a plan                    │\n"
            "│  /tools         List available tools               │\n"
            "│  /clear         Clear conversation history         │\n"
            "│                                                   │\n"
            "│  🧠 Intelligence                                  │\n"
            "│  /stance [name] Show or set stance                │\n"
            "│  /project       Show project intelligence          │\n"
            "│  /route         Show model routing info            │\n"
            "│  /stats         Show session statistics            │\n"
            "│                                                   │\n"
            "│  💾 Sessions                                      │\n"
            "│  /save [name]   Save current session              │\n"
            "│  /load          Load a saved session              │\n"
            "│                                                   │\n"
            "│  📋 Diffs                                         │\n"
            "│  /diff [mode]   Show pending diffs                │\n"
            "│  /accept [path] Accept pending diff(s)            │\n"
            "│  /reject [path] Reject pending diff(s)            │\n"
            "│  /undo          Undo last applied change          │\n"
            "│                                                   │\n"
            "│  🌿 Branching                                     │\n"
            "│  /branch <name> Create a new branch               │\n"
            "│  /branches      List all branches                 │\n"
            "│  /switch <name> Switch to a branch                │\n"
            "│  /compare <a> <b> Compare two branches            │\n"
            "│  /merge <src>   Merge branch into current         │\n"
            "│  /tree          Show branch tree visualization    │\n"
            "│                                                   │\n"
            "│  🔒 Safety                                        │\n"
            "│  /trust [level] Show or set trust level           │\n"
            "│  /audit [n]     Show audit log                    │\n"
            "│                                                   │\n"
            "│  🪝 Hooks & Watchers                              │\n"
            "│  /hooks         List registered hooks              │\n"
            "│  /watch         Show watcher status               │\n"
            "│                                                   │\n"
            "│  /quit          Exit chat                         │\n"
            "╰───────────────────────────────────────────────────╯"
        )

    if command in ("/quit", "/exit", "/q"):
        session.save_session()
        return None  # Signal to quit

    if command == "/clear":
        session.clear_history()
        return "🗑 Conversation cleared."

    if command == "/tools":
        tools = session._tools
        lines = ["Available tools:"]
        for name, tool in sorted(tools.items()):
            desc = getattr(tool, "description", "")[:60]
            lines.append(f"  • {name} — {desc}")
        return "\n".join(lines)

    if command == "/plan":
        if not arg1:
            return "Usage: /plan <what to plan>"
        # Forward to the LLM as a planning request
        return f"SEND:Create a detailed step-by-step plan for: {arg1} {arg2}".strip()

    # -- Intelligence layer -----------------------------------------------

    if command == "/stance":
        if not arg1:
            stances = session.list_stances()
            if stances:
                lines = ["Available stances:"]
                for s in stances:
                    active = " ← active" if s.get("active") else ""
                    lines.append(f"  {s.get('emoji', '?')} {s.get('name', '?')}{active}")
                return "\n".join(lines)
            return "Stances not available."

        result = session.set_stance(arg1)
        if result:
            return f"Stance: {result}"
        return f"Unknown stance '{arg1}'. Use /stance to see options."

    if command == "/project":
        summary = session.get_project_summary()
        if not summary:
            return "Project intelligence not available. Run with a workspace."
        lines = [
            f"Project: {summary.get('name', '?')}",
            f"Type: {summary.get('project_type', '?')}",
            f"Files: {summary.get('file_count', 0)}",
            f"Languages: {', '.join(summary.get('languages', []))}",
        ]
        dirs = summary.get('key_directories', [])
        if dirs:
            lines.append(f"Key dirs: {', '.join(dirs[:8])}")
        return "\n".join(lines)

    if command == "/route":
        stats = session.get_routing_stats()
        if not stats:
            return "Model routing not available."
        lines = [
            f"Total routed: {stats.get('total_routed', 0)}",
            "By model:",
        ]
        for model, count in stats.get("by_model", {}).items():
            lines.append(f"  {model}: {count}")
        lines.append("By intent:")
        for intent, count in stats.get("by_intent", {}).items():
            lines.append(f"  {intent}: {count}")
        return "\n".join(lines)

    if command == "/stats":
        s = session.stats()
        lines = [
            f"Turns: {s.get('turns', 0)}",
            f"Messages: {s.get('messages', 0)}",
            f"Tool calls: {s.get('tool_calls', 0)}",
            f"Duration: {s.get('duration_seconds', 0)}s",
            f"Model: {s.get('model', '?')}",
        ]
        if "stance" in s:
            lines.append(f"Stance: {s['stance']}")
        if "branch" in s:
            lines.append(f"Branch: {s['branch']} ({s.get('branches', 1)} total)")
        if "pending_diffs" in s:
            lines.append(f"Pending diffs: {s['pending_diffs']}")
            lines.append(f"Diff history: {s.get('diff_history', 0)}")
        if "audit" in s:
            a = s["audit"]
            lines.append(f"Audit: {a.get('approved', 0)} approved, {a.get('blocked', 0)} blocked (trust: {a.get('trust_level', '?')})")
        if "hooks" in s:
            lines.append(f"Hooks: {s['hooks']} registered")
        if "routing" in s:
            lines.append(f"Routing: {s['routing'].get('total_routed', 0)} routed")
        return "\n".join(lines)

    # -- Session persistence -----------------------------------------------

    if command == "/save":
        title = f"{arg1} {arg2}".strip() if arg1 else None
        sid = session.save_session(title=title)
        if sid:
            return f"💾 Session saved: {sid}"
        return "Session save failed."

    if command == "/load":
        sessions = session.list_sessions()
        if not sessions:
            return "No saved sessions."

        if arg1:
            # Load by ID or index
            try:
                idx = int(arg1) - 1
                if 0 <= idx < len(sessions):
                    sid = sessions[idx]["id"]
                else:
                    sid = arg1
            except ValueError:
                sid = arg1

            if session.load_session(sid):
                return f"📂 Loaded session: {sid}"
            return f"Failed to load session '{sid}'."

        # List sessions
        lines = ["Saved sessions:"]
        for i, s in enumerate(sessions[:20], 1):
            lines.append(
                f"  {i}. [{s['id'][:8]}] {s.get('title', 'Untitled')} "
                f"({s.get('messages', 0)} msgs, {s.get('when', '?')})"
            )
        lines.append("\nUse /load <number> or /load <id> to restore.")
        return "\n".join(lines)

    # ====================================================================
    # Diff commands
    # ====================================================================

    if command == "/diff":
        pending = session.get_pending_diffs()
        if not pending:
            stats = session.get_diff_stats()
            return (
                f"No pending diffs.\n"
                f"Applied: {stats.get('history', 0)} | "
                f"Auto-apply: {'on' if stats.get('auto_apply') else 'off'} | "
                f"Mode: {stats.get('mode', 'unified')}"
            )

        mode = arg1 if arg1 in ("unified", "side", "inline", "summary") else "unified"
        lines = [f"📋 {len(pending)} pending diff(s) (mode: {mode}):\n"]
        for diff in pending:
            lines.append(f"  {diff.path} — +{diff.additions} -{diff.deletions} ({len(diff.hunks)} hunks)")
            if mode == "summary":
                continue
            # Show the unified diff content
            lines.append("")
            for hline in diff.unified.splitlines()[:30]:
                lines.append(f"    {hline}")
            if len(diff.unified.splitlines()) > 30:
                lines.append(f"    ... +{len(diff.unified.splitlines()) - 30} more lines")
            lines.append("")

        lines.append("Commands: /accept [path] | /reject [path] | /undo")
        return "\n".join(lines)

    if command == "/accept":
        path = arg1 if arg1 else None
        result = session.accept_diff(path)
        if "error" in result:
            return f"❌ {result['error']}"
        if "message" in result:
            return result["message"]
        applied = result.get("applied", [])
        if applied:
            names = [a["path"] for a in applied]
            return f"✅ Applied: {', '.join(names)}"
        return "Nothing to apply."

    if command == "/reject":
        path = arg1 if arg1 else None
        result = session.reject_diff(path)
        if "error" in result:
            return f"❌ {result['error']}"
        if "message" in result:
            return result["message"]
        rejected = result.get("rejected", [])
        return f"❌ Rejected: {', '.join(rejected)}" if rejected else "Nothing to reject."

    if command == "/undo":
        result = session.undo_last_change()
        if "error" in result:
            return f"❌ {result['error']}"
        if "message" in result:
            return result["message"]
        if result.get("restored"):
            return f"↩ Undone: {result['path']} restored to previous state"
        return f"Undo failed: {result.get('error', 'unknown')}"

    # ====================================================================
    # Branch commands
    # ====================================================================

    if command == "/branch":
        if not arg1:
            return "Usage: /branch <name> [description]"
        desc = arg2 if arg2 else ""
        result = session.create_branch(arg1, description=desc)
        return f"🌿 {result}"

    if command == "/branches":
        branches = session.list_branches()
        if not branches:
            return "Branching not available."
        lines = ["🌿 Conversation branches:"]
        for b in branches:
            active = " ← active" if b.get("active") else ""
            lines.append(
                f"  {'*' if b.get('active') else ' '} {b['name']} "
                f"({b.get('messages', 0)} msgs, {b.get('own_messages', 0)} own)"
                f"{active}"
            )
        return "\n".join(lines)

    if command == "/switch":
        if not arg1:
            return "Usage: /switch <branch-name>"
        result = session.switch_branch(arg1)
        return f"🌿 {result}"

    if command == "/compare":
        if not arg1 or not arg2:
            return "Usage: /compare <branch-a> <branch-b>"
        result = session.compare_branches(arg1, arg2)
        if "error" in result:
            return f"❌ {result['error']}"
        lines = [
            f"🔀 Comparing '{result['branch_a']}' vs '{result['branch_b']}':",
            f"  Fork point: message #{result['fork_point']}",
            f"  Shared: {result['shared_messages']} messages",
            f"  {result['branch_a']}: +{result['unique_a']} unique ({result.get('a_tool_calls', 0)} tool calls)",
            f"  {result['branch_b']}: +{result['unique_b']} unique ({result.get('b_tool_calls', 0)} tool calls)",
        ]
        if result.get("a_summary"):
            lines.append(f"  A: {result['a_summary']}")
        if result.get("b_summary"):
            lines.append(f"  B: {result['b_summary']}")
        return "\n".join(lines)

    if command == "/merge":
        if not arg1:
            return "Usage: /merge <source-branch> [strategy: append|replace]"
        strategy = arg2 if arg2 in ("append", "replace") else "append"
        result = session.merge_branch(arg1, strategy=strategy)
        if "error" in result:
            return f"❌ {result['error']}"
        return (
            f"🔀 Merged {result.get('merged', 0)} messages from "
            f"'{result.get('source', '?')}' into '{result.get('target', '?')}' "
            f"(strategy: {result.get('strategy', '?')})"
        )

    if command == "/tree":
        tree = session.get_branch_tree()
        return f"🌿 Branch Tree:\n{tree}"

    # ====================================================================
    # Safety commands
    # ====================================================================

    if command == "/trust":
        if not arg1:
            level = session.get_trust_level()
            return (
                f"🔒 Current trust level: {level}\n"
                f"   Levels: read < write < execute < destructive\n"
                f"   Set with: /trust <level>"
            )
        result = session.set_trust_level(arg1)
        return f"🔒 {result}"

    if command == "/audit":
        limit = 20
        if arg1:
            try:
                limit = int(arg1)
            except ValueError:
                pass

        entries = session.get_audit_log(limit=limit)
        if not entries:
            summary = session.get_audit_summary()
            if summary:
                return (
                    f"🔍 No audit entries yet.\n"
                    f"   Trust level: {summary.get('trust_level', '?')}\n"
                    f"   Approved: {summary.get('approved', 0)} | Blocked: {summary.get('blocked', 0)}"
                )
            return "Audit log not available."

        lines = [f"🔍 Audit log (last {len(entries)}):"]
        for e in entries[:limit]:
            status_icon = {
                "approved": "✅",
                "blocked": "⛔",
                "denied": "🚫",
                "success": "✅",
                "error": "❌",
            }.get(e.get("status", ""), "❓")
            auto = " (auto)" if e.get("auto_approved") else ""
            lines.append(
                f"  {status_icon} {e.get('tool', '?')} [{e.get('level', '?')}]{auto}"
            )
        summary = session.get_audit_summary()
        if summary:
            lines.append(
                f"\n  Total: {summary.get('total_entries', 0)} | "
                f"Approved: {summary.get('approved', 0)} | "
                f"Blocked: {summary.get('blocked', 0)}"
            )
        return "\n".join(lines)

    # ====================================================================
    # Hooks & Watchers
    # ====================================================================

    if command == "/hooks":
        hooks = session.get_hooks()
        if not hooks:
            return "🪝 No hooks registered."
        lines = ["🪝 Registered hooks:"]
        for h in hooks:
            enabled = "✅" if h.get("enabled") else "❌"
            lines.append(
                f"  {enabled} {h.get('name', '?')} "
                f"({h.get('phase', '?')}, priority={h.get('priority', '?')})"
                f" → {', '.join(h.get('tools', []))}"
            )
            if h.get("description"):
                lines.append(f"     {h['description']}")

        # Show recent hook history
        history = session.get_hook_history()
        if history:
            lines.append(f"\n  Recent activity ({len(history)}):")
            for hr in history[-5:]:
                icon = "✅" if hr.get("success") else "⛔"
                lines.append(
                    f"    {icon} {hr.get('name', '?')} "
                    f"({hr.get('phase', '?')}) {hr.get('message', '')}"
                )

        return "\n".join(lines)

    if command == "/watch":
        status = session.get_watcher_status()
        if not status:
            return "👁 File watchers not available."

        watchers = status.get("watchers", [])
        events = status.get("recent_events", [])

        lines = ["👁 File Watchers:"]
        if watchers:
            for w in watchers:
                enabled = "✅" if w.get("enabled") else "❌"
                lines.append(
                    f"  {enabled} {w.get('name', '?')} — "
                    f"{', '.join(w.get('patterns', []))}"
                )
        else:
            lines.append("  No watchers registered.")

        if events:
            lines.append(f"\n  Recent events ({len(events)}):")
            for e in events[-5:]:
                lines.append(f"    {e.get('type', '?')}: {e.get('path', '?')}")

        return "\n".join(lines)

    return f"Unknown command: {command}. Type /help for available commands."


# ---------------------------------------------------------------------------
# Main run_chat — the async entry point
# ---------------------------------------------------------------------------

async def run_chat(
    workspace: str = ".",
    model: Optional[str] = None,
    config: Optional[AgentConfig] = None,
):
    """Run the interactive chat TUI.

    This is what `nexus chat` launches — a full-screen Rich interface
    with three panes, slash commands, and intelligence features.
    """
    console = Console()
    session = ChatSession(workspace=workspace, config=config, model=model)
    session.load_project_rules()

    # Activity log for sidebar
    activity: list[str] = []

    def log_activity(msg: str) -> None:
        activity.append(msg)
        if len(activity) > 50:
            activity.pop(0)

    layout = _make_layout()

    console.print()
    console.print(Panel(
        Text.assemble(
            ("🚀 Nexus Chat", "bold cyan"),
            (" — collaborative coding partner\n\n", "dim"),
            ("Type a message to start coding together.\n", ""),
            ("Use ", "dim"), ("/help", "cyan"), (" for commands, ", "dim"),
            ("/quit", "cyan"), (" to exit.", "dim"),
        ),
        border_style="cyan",
    ))
    console.print()

    try:
        while True:
            # Update layout panels
            layout["header"].update(_header_panel(session))
            layout["chat"].update(_chat_panel(session.history))
            layout["sidebar"].update(_sidebar_panel(session, activity))
            layout["footer"].update(_footer_panel())

            # Get user input
            try:
                user_input = console.input("[bold green] > [/bold green]")
            except (EOFError, KeyboardInterrupt):
                session.save_session()
                console.print("\n[dim]Session saved. Goodbye![/dim]")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                result = await _handle_command(user_input, session, console)

                if result is None:
                    # Quit signal
                    console.print("[dim]Session saved. Goodbye![/dim]")
                    break

                if result.startswith("SEND:"):
                    # Forward to LLM
                    user_input = result[5:]
                else:
                    # Display command output
                    console.print(Panel(
                        result,
                        border_style="yellow",
                        padding=(0, 1),
                    ))
                    log_activity(f"/{user_input.split()[0][1:]} executed")
                    continue

            # Send to LLM and display response
            console.print(f"[bold green]  You  [/bold green]{user_input}")
            log_activity(f"User: {user_input[:40]}...")

            response_text = ""
            tool_count = 0

            async for event in session.send(user_input):
                if event.type == EventType.TOKEN:
                    response_text = event.content
                    # Display will happen after all events

                elif event.type == EventType.THINKING:
                    console.print(f"[dim italic]  💭 {event.content[:200]}[/dim italic]")

                elif event.type == EventType.PLAN:
                    console.print(Panel(
                        event.content,
                        title="[bold]📋 Plan[/bold]",
                        border_style="cyan",
                    ))
                    response_text = ""  # Already displayed

                elif event.type == EventType.ROUTING:
                    console.print(f"[dim]  🧠 Routed to {event.data.get('model', '?')} ({event.data.get('intent', '?')})[/dim]")
                    log_activity(f"→ {event.data.get('model', '?')}")

                elif event.type == EventType.STANCE_CHANGE:
                    console.print(f"[dim]  🎭 {event.content}[/dim]")
                    log_activity(f"Stance: {event.content}")

                elif event.type == EventType.DIFF_PREVIEW:
                    diff_data = event.data
                    stats = diff_data.get("stats", {})
                    console.print(Panel(
                        event.content[:3000] if event.content else "(empty diff)",
                        title=f"[bold]📋 Diff: {diff_data.get('path', '?')}[/bold]  +{stats.get('additions', 0)} -{stats.get('deletions', 0)}",
                        border_style="yellow",
                    ))
                    log_activity(f"Diff: {diff_data.get('path', '?')}")

                elif event.type == EventType.PERMISSION:
                    status = event.data.get("status", "?")
                    icon = "✅" if status == "approved" else "⛔"
                    console.print(f"[dim]  🔒 {icon} {event.content}[/dim]")
                    log_activity(f"Perm: {event.content}")

                elif event.type == EventType.HOOK:
                    phase = event.data.get("phase", "?")
                    console.print(f"[dim]  🪝 [{phase}] {event.content}[/dim]")
                    log_activity(f"Hook: {event.content}")

                elif event.type == EventType.BRANCH:
                    console.print(f"[dim]  🌿 {event.content}[/dim]")
                    log_activity(f"Branch: {event.content}")

                elif event.type == EventType.TOOL_CALL:
                    tool_name = event.data.get("tool", "?")
                    console.print(f"  [cyan]⚡ {tool_name}[/cyan]", end="")
                    tool_count += 1

                elif event.type == EventType.TOOL_RESULT:
                    success = event.data.get("success", True)
                    icon = "✓" if success else "✗"
                    style = "green" if success else "red"
                    preview = event.content[:200].replace("\n", " ")
                    console.print(f" [{style}]{icon}[/{style}] [dim]{preview}[/dim]")
                    log_activity(f"Tool: {event.data.get('tool', '?')} {'✓' if success else '✗'}")

                elif event.type == EventType.ERROR:
                    console.print(f"  [red]❌ {event.content}[/red]")
                    log_activity(f"Error: {event.content[:40]}")

                elif event.type == EventType.DONE:
                    pass

            # Display the final response text (if not already shown as plan)
            if response_text:
                console.print(f"[bold cyan]  Nexus  [/bold cyan]{response_text}")

            if tool_count:
                log_activity(f"Turn: {tool_count} tool calls")

            console.print()

    except Exception as exc:
        console.print(f"\n[red]Fatal error: {exc}[/red]")
        session.save_session()
        raise
