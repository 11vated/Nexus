"""Interactive chat TUI — the collaborative Nexus experience.

This is the primary user-facing interface.  It provides a full-screen
terminal UI with:
  - Chat pane:   streaming LLM responses
  - Tool pane:   live activity log of tool calls and results
  - Input pane:  user text entry with history
  - Status bar:  model, workspace, stance, routing info

Layout:
┌──────────────────────────────────────────────┐
│  NEXUS CHAT — model · workspace  🏗 Arch  │
├────────────────────────────┬─────────────────┤
│                            │  Tool Activity   │
│   Chat history +           │  ─────────────── │
│   streaming response       │  ✓ file_read ... │
│                            │  ⚡ shell ...    │
│                            │  ✓ file_write .. │
├────────────────────────────┴─────────────────┤
│  > your message here...                      │
└──────────────────────────────────────────────┘

Use: nexus chat
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.spinner import Spinner

from nexus.agent.chat import ChatSession, ChatEvent, EventType
from nexus.agent.models import AgentConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WELCOME_MESSAGE = """\
Welcome to *Nexus Chat* — your collaborative AI coding partner.

I can help you:
• Plan and build features step-by-step
• Read, write, and modify code in your project
• Run commands, tests, and debug issues
• Search your codebase and explain code

*Intelligence features active:*
• 🧠 Multi-model routing — best model for each task
• 🔄 Adaptive stances — behavior shifts to match your need
• 🗺  Project map — I already understand your codebase
• 💾 Session save/resume — pick up where you left off

Type your request below. I'll propose a plan before making changes.
Type `/help` for commands, `/quit` to exit.
"""

HELP_TEXT = """\
*Commands:*
  /help        — Show this help
  /quit        — Exit the chat
  /clear       — Clear conversation history
  /stats       — Show session statistics
  /model [m]   — Show or change the active model
  /tools       — List available tools
  /plan <desc> — Ask Nexus to plan without executing
  /rules       — Show loaded project rules (.nexus/rules.md)
  /stance [s]  — Show or set stance (architect|pair_programmer|debugger|reviewer|teacher|explorer)
  /project     — Show project intelligence summary
  /route       — Show model routing history
  /save [name] — Save current session
  /load        — List and load saved sessions
  /sessions    — List saved sessions
"""


# ---------------------------------------------------------------------------
# Chat TUI
# ---------------------------------------------------------------------------

class NexusChatTUI:
    """Full-screen interactive chat interface.

    Renders a three-pane layout with live streaming and tool activity.
    """

    def __init__(
        self,
        workspace: str = ".",
        config: Optional[AgentConfig] = None,
        model: Optional[str] = None,
    ):
        self.console = Console()
        self.workspace = str(Path(workspace).resolve())
        self.config = config or AgentConfig(workspace_path=self.workspace)
        self.model = model
        self.session: Optional[ChatSession] = None

        # Display state
        self.chat_messages: List[Dict[str, str]] = []
        self.tool_log: List[Dict[str, Any]] = []
        self.current_response: str = ""
        self.is_streaming: bool = False
        self.is_thinking: bool = False

    def _init_session(self) -> ChatSession:
        """Create and configure the chat session."""
        session = ChatSession(
            workspace=self.workspace,
            config=self.config,
            model=self.model,
        )
        session.load_project_rules()
        return session

    # -- layout & rendering --------------------------------------------------

    def _make_layout(self) -> Layout:
        """Create the three-pane layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="chat", ratio=3),
            Layout(name="tools", ratio=1, minimum_size=30),
        )
        return layout

    def _render_header(self) -> Panel:
        """Render the status bar."""
        model_name = self.model or self.config.coding_model
        stats = self.session.stats() if self.session else {}
        turns = stats.get("turns", 0)
        tool_calls = stats.get("tool_calls", 0)
        duration = stats.get("duration_seconds", 0)
        stance = stats.get("stance", "default")

        left = Text(f"  NEXUS CHAT — {model_name}", style="bold cyan")
        mid = Text(f"  {self.workspace}", style="dim")

        # Stance indicator
        stance_display = ""
        if stance != "default" and self.session and self.session._stances:
            cfg = self.session._stances.current_config
            stance_display = f"  {cfg.emoji} {cfg.display_name}"

        right = Text(
            f"{stance_display}  turns:{turns}  tools:{tool_calls}  {duration:.0f}s  ",
            style="dim",
        )

        header_text = Text()
        header_text.append_text(left)
        header_text.append_text(mid)
        header_text.append("  ")
        header_text.append_text(right)

        return Panel(header_text, style="cyan", height=3)

    def _render_chat(self) -> Panel:
        """Render the chat history pane."""
        lines = Text()

        for msg in self.chat_messages:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                lines.append("  You: ", style="bold green")
                lines.append(content + "\n\n")
            elif role == "assistant":
                lines.append("  Nexus: ", style="bold cyan")
                lines.append(content + "\n\n")
            elif role == "plan":
                lines.append("  📋 Plan:\n", style="bold yellow")
                lines.append(content + "\n\n")
            elif role == "system":
                lines.append(f"  ℹ {content}\n", style="dim")
            elif role == "routing":
                lines.append(f"  🧠 {content}\n", style="dim magenta")
            elif role == "stance":
                lines.append(f"  {content}\n", style="dim yellow")

        # Current streaming response
        if self.is_streaming and self.current_response:
            lines.append("  Nexus: ", style="bold cyan")
            lines.append(self.current_response)
            lines.append(" █", style="blink bold cyan")
        elif self.is_thinking:
            lines.append("  ", style="dim")
            lines.append("Nexus is thinking...", style="dim italic")

        if not self.chat_messages and not self.is_streaming:
            lines = Text()
            for line in WELCOME_MESSAGE.split("\n"):
                lines.append(f"  {line}\n", style="dim")

        return Panel(
            lines,
            title="[bold]Chat[/bold]",
            border_style="cyan",
            padding=(1, 1),
        )

    def _render_tools(self) -> Panel:
        """Render the tool activity sidebar."""
        table = Table(show_header=False, expand=True, padding=(0, 1))
        table.add_column("Status", width=2)
        table.add_column("Tool", ratio=1)

        if not self.tool_log:
            table.add_row("", Text("No tool activity yet", style="dim"))
        else:
            # Show last 20 tool events
            for entry in self.tool_log[-20:]:
                status = entry.get("status", "")
                name = entry.get("tool", "")
                detail = entry.get("detail", "")

                if status == "calling":
                    icon = Text("⚡", style="yellow")
                    desc = Text(f"{name}", style="yellow")
                elif status == "success":
                    icon = Text("✓", style="green")
                    desc = Text(f"{name}", style="green")
                    if detail:
                        desc.append(f"\n  {detail[:60]}", style="dim")
                elif status == "error":
                    icon = Text("✗", style="red")
                    desc = Text(f"{name}", style="red")
                    if detail:
                        desc.append(f"\n  {detail[:60]}", style="dim red")
                elif status == "routing":
                    icon = Text("🧠", style="magenta")
                    desc = Text(f"{name}", style="magenta")
                elif status == "stance":
                    icon = Text("🔄", style="yellow")
                    desc = Text(f"{name}", style="yellow")
                else:
                    icon = Text("·")
                    desc = Text(name)

                table.add_row(icon, desc)

        return Panel(
            table,
            title="[bold]Activity[/bold]",
            border_style="blue",
        )

    def _render_footer(self) -> Panel:
        """Render the input prompt area."""
        if self.is_streaming:
            prompt_text = Text("  ⏳ Nexus is responding...", style="dim italic")
        else:
            prompt_text = Text("  > Type your message (Enter to send, /help for commands)", style="dim")
        return Panel(prompt_text, style="green", height=3)

    def _render(self, layout: Layout) -> Layout:
        """Update all layout panes."""
        layout["header"].update(self._render_header())
        layout["chat"].update(self._render_chat())
        layout["tools"].update(self._render_tools())
        layout["footer"].update(self._render_footer())
        return layout

    # -- command handling ----------------------------------------------------

    def _handle_command(self, cmd: str) -> Optional[str]:
        """Handle slash commands. Returns response text or None."""
        parts = cmd.strip().split(None, 1)
        command = parts[0].lower()

        if command in ("/quit", "/exit", "/q"):
            return "__QUIT__"

        elif command == "/help":
            return HELP_TEXT

        elif command == "/clear":
            self.chat_messages.clear()
            self.tool_log.clear()
            if self.session:
                self.session.clear_history()
            return "Conversation cleared."

        elif command == "/stats":
            if self.session:
                stats = self.session.stats()
                lines = [
                    f"Turns: {stats['turns']} | Messages: {stats['messages']} | Tool calls: {stats['tool_calls']}",
                    f"Duration: {stats['duration_seconds']}s | Model: {stats['model']}",
                ]
                if "stance" in stats:
                    lines.append(f"Stance: {stats['stance']}")
                if "routing" in stats:
                    r = stats["routing"]
                    lines.append(f"Routing: {r.get('total_routes', 0)} decisions, avg confidence: {r.get('avg_confidence', 0):.0%}")
                if "project" in stats:
                    p = stats["project"]
                    lines.append(f"Project: {p.get('type', '?')} ({p.get('files', 0)} files)")
                return "\n".join(lines)
            return "No active session."

        elif command == "/tools":
            if self.session:
                tools = list(self.session._tools.keys())
                return "Available tools: " + ", ".join(tools)
            return "No active session."

        elif command == "/model":
            if len(parts) > 1:
                new_model = parts[1].strip()
                self.model = new_model
                if self.session:
                    self.session.model = new_model
                return f"Model changed to: {new_model}"
            return f"Current model: {self.model or self.config.coding_model}"

        elif command == "/rules":
            if self.session and self.session.project_rules:
                return f"Project rules:\n{self.session.project_rules}"
            return "No project rules loaded. Create .nexus/rules.md in your workspace."

        elif command == "/plan":
            if len(parts) > 1:
                return None  # Pass to LLM with plan prefix
            return "Usage: /plan <description of what you want>"

        elif command == "/stance":
            if not self.session:
                return "No active session."
            if len(parts) > 1:
                result = self.session.set_stance(parts[1])
                if result:
                    return f"Stance set to: {result}"
                else:
                    stances = [s["name"] for s in self.session.list_stances()]
                    return f"Unknown stance. Available: {', '.join(stances)}"
            else:
                stances = self.session.list_stances()
                lines = ["Available stances:"]
                for s in stances:
                    marker = " ← active" if s.get("active") else ""
                    lines.append(f"  {s['display']}: {s['description']}{marker}")
                return "\n".join(lines)

        elif command == "/project":
            if not self.session:
                return "No active session."
            summary = self.session.get_project_summary()
            if not summary:
                return "Project not scanned. Intelligence layer may not be available."
            lines = [
                f"Project: {summary.get('name', '?')}",
                f"Type: {summary.get('type', '?')}",
                f"Frameworks: {', '.join(summary.get('frameworks', [])) or 'none detected'}",
                f"Total files: {summary.get('total_files', 0)}",
                f"Languages: {summary.get('languages', {})}",
            ]
            top = summary.get("top_files", [])
            if top:
                lines.append("Top files:")
                for path, score in top:
                    lines.append(f"  {score:.2f}  {path}")
            return "\n".join(lines)

        elif command == "/route":
            if not self.session:
                return "No active session."
            stats = self.session.get_routing_stats()
            if not stats or stats.get("total_routes", 0) == 0:
                return "No routing decisions yet."
            lines = [
                f"Total routing decisions: {stats['total_routes']}",
                f"Avg confidence: {stats.get('avg_confidence', 0):.0%}",
                f"Intent distribution: {stats.get('intent_distribution', {})}",
                f"Model distribution: {stats.get('model_distribution', {})}",
            ]
            return "\n".join(lines)

        elif command == "/save":
            if not self.session:
                return "No active session."
            title = parts[1] if len(parts) > 1 else None
            sid = self.session.save_session(title=title)
            if sid:
                return f"Session saved: {sid}"
            return "Failed to save session."

        elif command in ("/load", "/sessions"):
            if not self.session:
                return "No active session."
            sessions = self.session.list_sessions()
            if not sessions:
                return "No saved sessions."
            if command == "/load" and len(parts) > 1:
                # Load by ID
                sid = parts[1].strip()
                if self.session.load_session(sid):
                    return f"Session loaded: {sid} ({len(self.session.history)} messages)"
                return f"Session not found: {sid}"
            lines = ["Saved sessions:"]
            for s in sessions:
                lines.append(f"  {s['id']}  {s['title']}  ({s['messages']} msgs, {s['when']})")
            if command == "/load":
                lines.append("\nUsage: /load <session_id>")
            return "\n".join(lines)

        return None

    # -- main loop -----------------------------------------------------------

    async def _process_message(self, user_input: str) -> None:
        """Process a single user message through the chat session."""
        if not self.session:
            return

        # Add user message to display
        self.chat_messages.append({"role": "user", "content": user_input})

        # Handle /plan prefix
        if user_input.startswith("/plan "):
            user_input = (
                f"I want you to create a detailed plan for the following. "
                f"Do NOT execute anything yet, just outline the steps:\n\n"
                f"{user_input[6:]}"
            )

        # Stream response
        self.is_streaming = True
        self.current_response = ""

        try:
            async for event in self.session.send(user_input):
                if event.type == EventType.TOKEN:
                    self.current_response += event.content

                elif event.type == EventType.THINKING:
                    self.is_thinking = True
                    self.chat_messages.append({
                        "role": "system",
                        "content": event.content[:200],
                    })
                    self.is_thinking = False

                elif event.type == EventType.ROUTING:
                    self.chat_messages.append({
                        "role": "routing",
                        "content": f"Routed: {event.data.get('reasoning', event.content)}",
                    })
                    self.tool_log.append({
                        "status": "routing",
                        "tool": event.content,
                        "detail": event.data.get("intent", ""),
                    })

                elif event.type == EventType.STANCE_CHANGE:
                    self.chat_messages.append({
                        "role": "stance",
                        "content": f"Mode: {event.content}",
                    })
                    self.tool_log.append({
                        "status": "stance",
                        "tool": event.content,
                    })

                elif event.type == EventType.TOOL_CALL:
                    tool_name = event.data.get("tool", "?")
                    self.tool_log.append({
                        "status": "calling",
                        "tool": tool_name,
                        "detail": str(event.data.get("args", {}))[:80],
                    })

                elif event.type == EventType.TOOL_RESULT:
                    tool_name = event.data.get("tool", "?")
                    success = event.data.get("success", False)
                    self.tool_log.append({
                        "status": "success" if success else "error",
                        "tool": tool_name,
                        "detail": event.content[:80],
                    })

                elif event.type == EventType.PLAN:
                    self.chat_messages.append({
                        "role": "plan",
                        "content": event.content,
                    })

                elif event.type == EventType.ERROR:
                    self.chat_messages.append({
                        "role": "system",
                        "content": f"⚠ {event.content}",
                    })

                elif event.type == EventType.DONE:
                    if self.current_response:
                        self.chat_messages.append({
                            "role": "assistant",
                            "content": self.current_response,
                        })
                    self.current_response = ""
                    self.is_streaming = False

        except Exception as exc:
            self.chat_messages.append({
                "role": "system",
                "content": f"⚠ Error: {exc}",
            })
        finally:
            self.is_streaming = False
            self.current_response = ""

    async def run(self) -> None:
        """Run the interactive chat TUI.

        This is the main entry point that renders the layout,
        handles input, and processes messages.
        """
        self.session = self._init_session()
        layout = self._make_layout()

        self.console.clear()

        # Print welcome with intelligence info
        rules_loaded = " (rules loaded)" if self.session.project_rules else ""
        model_name = self.model or self.config.coding_model
        project_info = ""
        if self.session._project_map and self.session._project_map._scanned:
            pm = self.session._project_map
            project_info = f" · project: [yellow]{pm.project_type}[/yellow] ({len(pm.files)} files)"

        self.console.print(
            Panel(
                f"[bold cyan]NEXUS CHAT[/bold cyan] — "
                f"model: [green]{model_name}[/green] · "
                f"workspace: [dim]{self.workspace}[/dim]{project_info}{rules_loaded}\n\n"
                f"[dim]Intelligence: 🧠 multi-model routing · "
                f"🔄 adaptive stances · "
                f"🗺  project map · "
                f"💾 session persistence[/dim]",
                border_style="cyan",
            )
        )
        self.console.print()

        # Show welcome
        for line in WELCOME_MESSAGE.strip().split("\n"):
            self.console.print(f"  [dim]{line}[/dim]")
        self.console.print()

        # Main input loop
        while True:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: input("  \033[32m>\033[0m "),
                )
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n  [dim]Goodbye![/dim]")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                result = self._handle_command(user_input)
                if result == "__QUIT__":
                    # Auto-save on exit
                    if self.session and self.session.turn_count > 0:
                        sid = self.session.save_session()
                        if sid:
                            self.console.print(f"  [dim]Session auto-saved: {sid}[/dim]")
                    self.console.print("  [dim]Goodbye![/dim]")
                    break
                elif result is not None:
                    self.console.print(f"\n  [dim]{result}[/dim]\n")
                    continue
                # /plan falls through to message processing

            # Process the message
            self.console.print(f"\n  [bold green]You:[/bold green] {user_input}\n")

            # Stream response with live display
            self.console.print("  [bold cyan]Nexus:[/bold cyan] ", end="")

            response_text = ""
            tool_count = 0

            try:
                async for event in self.session.send(user_input):
                    if event.type == EventType.TOKEN:
                        # Print full response at once (non-streaming mode)
                        response_text = event.content

                    elif event.type == EventType.THINKING:
                        self.console.print(
                            f"\n  [dim italic]{event.content[:200]}[/dim italic]"
                        )

                    elif event.type == EventType.ROUTING:
                        self.console.print(
                            f"\n  [dim magenta]🧠 {event.data.get('reasoning', event.content)}[/dim magenta]"
                        )

                    elif event.type == EventType.STANCE_CHANGE:
                        self.console.print(
                            f"  [dim yellow]Mode: {event.content}[/dim yellow]"
                        )

                    elif event.type == EventType.TOOL_CALL:
                        tool_name = event.data.get("tool", "?")
                        tool_args = event.data.get("args", {})
                        tool_count += 1
                        self.console.print(
                            f"\n  [yellow]⚡ {tool_name}[/yellow]"
                            f"[dim]({', '.join(f'{k}={str(v)[:40]}' for k, v in tool_args.items())})[/dim]"
                        )

                    elif event.type == EventType.TOOL_RESULT:
                        success = event.data.get("success", False)
                        icon = "[green]✓[/green]" if success else "[red]✗[/red]"
                        preview = event.content[:120].replace("\n", " ")
                        self.console.print(f"  {icon} [dim]{preview}[/dim]")

                    elif event.type == EventType.PLAN:
                        response_text = event.content

                    elif event.type == EventType.ERROR:
                        self.console.print(f"\n  [red]⚠ {event.content}[/red]")

                    elif event.type == EventType.DONE:
                        pass

            except Exception as exc:
                self.console.print(f"\n  [red]Error: {exc}[/red]")

            # Print the final response
            if response_text:
                self.console.print(response_text)

            self.console.print()  # blank line between turns

        # Cleanup
        if self.session:
            await self.session.llm.close()


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

async def run_chat(
    workspace: str = ".",
    model: Optional[str] = None,
    config: Optional[AgentConfig] = None,
) -> None:
    """Launch the chat TUI."""
    tui = NexusChatTUI(workspace=workspace, config=config, model=model)
    await tui.run()
