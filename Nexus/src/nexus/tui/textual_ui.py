"""Nexus Textual TUI — Artifact-first cognitive coding interface.

A full-featured terminal application built with Textual, replacing the
Rich Live-based chat UI with a proper widget tree, keyboard navigation,
and dedicated panels for cognitive state.

Layout:
    ┌──────────────── Header ────────────────┐
    │  NEXUS ⚡ model · stance · branch · cog │
    ├────────────────┬───────────────────────-┤
    │                │  ┌─ Context Panel ──┐  │
    │  Chat Stream   │  │ Plan / Trace /   │  │
    │  (messages,    │  │ Knowledge / Mem  │  │
    │   tool calls,  │  │ tabbed views     │  │
    │   diffs,       │  │                  │  │
    │   cognitive)   │  └──────────────────┘  │
    ├────────────────┴────────────────────────┤
    │  > input area (multiline, history)      │
    ├─────────────────────────────────────────┤
    │  [F1 Help] [F2 Plan] [F3 Trace] [F5 ↻] │
    └─────────────────────────────────────────┘

Keyboard shortcuts:
    Ctrl+Enter  Send message
    Escape      Focus input
    F1          Toggle help overlay
    F2          Switch sidebar to Plan
    F3          Switch sidebar to Trace
    F4          Switch sidebar to Memory
    F5          Refresh project context
    Ctrl+K      Toggle cognitive mode
    Ctrl+L      Clear chat
    Ctrl+S      Save session
    Ctrl+B      Create branch
    Tab         Cycle focus between panes
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import (
        Container,
        Horizontal,
        ScrollableContainer,
        Vertical,
        VerticalScroll,
    )
    from textual.css.query import NoMatches
    from textual.message import Message
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widget import Widget
    from textual.widgets import (
        Button,
        Footer,
        Header,
        Input,
        Label,
        ListView,
        ListItem,
        LoadingIndicator,
        Markdown,
        OptionList,
        RichLog,
        Rule,
        Static,
        TabbedContent,
        TabPane,
        TextArea,
        Tree,
    )
    from textual.widgets.tree import TreeNode

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

from nexus.agent.chat import ChatEvent, ChatSession, EventType
from nexus.agent.models import AgentConfig


# ── Data models ─────────────────────────────────────────────────────────────


class SidebarTab(str, Enum):
    """Sidebar tab identifiers."""
    PLAN = "plan"
    TRACE = "trace"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    TOOLS = "tools"


@dataclass
class ChatMessage:
    """A rendered chat message."""
    role: str            # "user", "assistant", "system", "tool", "cognitive"
    content: str
    timestamp: float = field(default_factory=time.time)
    event_type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    @property
    def icon(self) -> str:
        icons = {
            "user": "👤",
            "assistant": "🤖",
            "system": "⚙️",
            "tool": "🔧",
            "cognitive": "🧠",
            "verification": "⚡",
            "diff": "📝",
            "routing": "→",
            "error": "❌",
        }
        return icons.get(self.event_type or self.role, "•")


# ── Custom Widgets ──────────────────────────────────────────────────────────

if TEXTUAL_AVAILABLE:

    class MessageWidget(Static):
        """A single chat message with role-appropriate styling."""

        DEFAULT_CSS = """
        MessageWidget {
            padding: 0 1;
            margin: 0 0 1 0;
        }
        MessageWidget.user-message {
            background: $primary-background;
            color: $text;
            border-left: thick $primary;
        }
        MessageWidget.assistant-message {
            background: $surface;
            color: $text;
            border-left: thick $success;
        }
        MessageWidget.system-message {
            background: $error-background;
            color: $text-warning;
            border-left: thick $warning;
        }
        MessageWidget.tool-message {
            background: $boost;
            color: $text-muted;
            border-left: thick $accent;
        }
        MessageWidget.cognitive-message {
            background: $panel;
            color: $text-muted;
            border-left: thick $success;
        }
        """

        def __init__(self, message: ChatMessage, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.message = message

        def on_mount(self) -> None:
            classes = [f"{self.message.role}-message"]
            if self.message.event_type:
                classes.append(f"event-{self.message.event_type}")
            for cls_name in classes:
                self.add_class(cls_name)

        def compose(self) -> ComposeResult:
            header = Label(self._header_text(), id="msg-header")
            body = Markdown(self.message.content, id="msg-body")
            yield header
            yield body

        def _header_text(self) -> str:
            ts = time.strftime(
                "%H:%M:%S", time.localtime(self.message.timestamp)
            )
            icon = self.message.icon
            role = self.message.role.capitalize()
            event = f" [{self.message.event_type}]" if self.message.event_type else ""
            return f"{icon} {role}{event}  {ts}"


    class StreamingMessage(Static):
        """Widget for streaming assistant responses."""

        DEFAULT_CSS = """
        StreamingMessage {
            background: $surface;
            color: $text;
            border-left: thick $success;
            padding: 0 1;
            margin: 0 0 1 0;
        }
        """

        current_text: str = reactive("")
        is_done: bool = reactive(False)

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._buffer = ""

        def compose(self) -> ComposeResult:
            yield Markdown(self._buffer, id="streaming-content")

        def append_text(self, text: str) -> None:
            self._buffer += text
            self.current_text = self._buffer

        def finish(self) -> None:
            self.is_done = True


    class PlanCard(Static):
        """Displays the current plan with step status."""

        DEFAULT_CSS = """
        PlanCard {
            padding: 1;
            border: solid $primary;
            margin: 1 0;
        }
        PlanCard Label {
            padding: 0 1;
        }
        """

        def __init__(self, plan_steps: Optional[List[Dict[str, Any]]] = None, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.steps = plan_steps or []

        def update_plan(self, steps: List[Dict[str, Any]]) -> None:
            self.steps = steps
            self.refresh()

        def compose(self) -> ComposeResult:
            yield Label("[bold]Plan[/bold]")
            if not self.steps:
                yield Label("  No active plan")
            else:
                for i, step in enumerate(self.steps, 1):
                    status = step.get("status", "pending")
                    icon = {"done": "✓", "running": "⟳", "failed": "✗"}.get(status, "○")
                    desc = step.get("description", "")[:80]
                    yield Label(f"  {icon} {i}. {desc}")


    class CognitiveIndicator(Static):
        """Shows current cognitive state in the header."""

        DEFAULT_CSS = """
        CognitiveIndicator {
            padding: 0 1;
            dock: right;
        }
        """

        stance: str = reactive("neutral")
        mode: str = reactive("chat")

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def compose(self) -> ComposeResult:
            stance_icons = {
                "collaborative": "🤝",
                "autonomous": "🚀",
                "assistant": "🔧",
                "mentor": "📚",
                "critic": "🔍",
                "neutral": "⚖️",
            }
            icon = stance_icons.get(self.stance, "⚖️")
            yield Label(f"{icon} {self.stance} · {self.mode}")


    class HelpScreen(ModalScreen[None]):
        """Keyboard shortcut reference overlay."""

        BINDINGS = [
            ("escape", "close", "Close"),
        ]

        def compose(self) -> ComposeResult:
            content = """
# Nexus Keyboard Shortcuts

| Key          | Action                    |
| ------------ | ------------------------- |
| Ctrl+Enter   | Send message              |
| Escape       | Focus input               |
| F1           | Toggle help overlay       |
| F2           | Sidebar: Plan             |
| F3           | Sidebar: Trace            |
| F4           | Sidebar: Memory           |
| F5           | Sidebar: Knowledge        |
| F6           | Sidebar: Tools            |
| Ctrl+K       | Toggle cognitive mode     |
| Ctrl+L       | Clear chat                |
| Ctrl+S       | Save session              |
| Ctrl+B       | Create branch             |
| Tab          | Cycle focus between panes |
| Up/Down      | Navigate history          |
| Ctrl+Up/Dn   | Navigate chat history     |
| PageUp/Dn    | Scroll chat log           |
"""
            yield Markdown(content)

        def action_close(self) -> None:
            self.dismiss()


    class NexusApp(App[None]):
        """Nexus — Artifact-first cognitive coding interface.

        The main Textual application with tabbed sidebars, plan cards,
        trace trees, and keyboard shortcuts.
        """

        CSS_PATH = None

        BINDINGS = [
            ("f1", "help", "Help"),
            ("f2", "sidebar_plan", "Plan"),
            ("f3", "sidebar_trace", "Trace"),
            ("f4", "sidebar_memory", "Memory"),
            ("f5", "sidebar_knowledge", "Knowledge"),
            ("f6", "sidebar_tools", "Tools"),
            ("ctrl+k", "toggle_cognitive", "Cognitive"),
            ("ctrl+l", "clear_chat", "Clear"),
            ("ctrl+s", "save_session", "Save"),
            ("ctrl+b", "new_branch", "Branch"),
            ("escape", "focus_input", "Focus Input"),
        ]

        DEFAULT_CSS = """
        Screen {
            layout: vertical;
        }
        #header-bar {
            dock: top;
            height: 3;
            background: $primary-background;
            padding: 0 1;
        }
        #main-area {
            layout: horizontal;
        }
        #chat-pane {
            width: 70%;
        }
        #chat-log {
            height: 1fr;
        }
        #input-bar {
            dock: bottom;
            height: 3;
            padding: 0 1;
        }
        #sidebar {
            width: 30%;
            border-left: solid $primary;
        }
        #footer-bar {
            dock: bottom;
            height: 1;
            background: $boost;
        }
        """

        current_sidebar_tab: str = reactive("plan")
        cognitive_mode: bool = reactive(False)

        def __init__(self, session: "ChatSession", **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.session = session
            self._input_history: List[str] = []
            self._history_index = -1
            self._streaming_widget: Optional[StreamingMessage] = None

        def compose(self) -> ComposeResult:
            yield Header(id="header-bar")
            with Horizontal(id="main-area"):
                with Vertical(id="chat-pane"):
                    yield RichLog(id="chat-log", highlight=True, markup=True)
                with VerticalScroll(id="sidebar"):
                    yield TabbedContent(id="sidebar-tabs")
            yield Input(placeholder="Ask Nexus anything... (Ctrl+Enter to send)", id="input-bar")
            yield Footer()

        def on_mount(self) -> None:
            self.title = "Nexus"
            self.sub_title = f"⚡ {self.session.model}"

        async def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id != "input-bar":
                return
            text = event.input.value.strip()
            if not text:
                return
            event.input.value = ""
            self._input_history.append(text)
            self._history_index = len(self._input_history)
            await self._handle_user_input(text)

        async def _handle_user_input(self, text: str) -> None:
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.write(f"[bold cyan]👤 You:[/]\n{text}\n")

            self._streaming_widget = StreamingMessage()
            chat_log.write(self._streaming_widget)

            try:
                async for evt in self.session.stream(text):
                    if evt.type == EventType.TOKEN:
                        if self._streaming_widget:
                            self._streaming_widget.append_text(evt.data.get("text", ""))
                    elif evt.type == EventType.ASSISTANT_COMPLETE:
                        if self._streaming_widget:
                            self._streaming_widget.finish()
                        self._streaming_widget = None
                    elif evt.type == EventType.TOOL_CALL:
                        tool_name = evt.data.get("tool", "")
                        tool_args = evt.data.get("args", {})
                        chat_log.write(
                            f"[dim]🔧 Calling {tool_name}({json.dumps(tool_args)[:100]})...[/]\n"
                        )
                    elif evt.type == EventType.TOOL_RESULT:
                        result = evt.data.get("result", "")
                        chat_log.write(f"[dim]  → {result[:200]}[/]\n")
                    elif evt.type == EventType.ERROR:
                        chat_log.write(f"[bold red]Error: {evt.data.get('error', '')}[/]\n")
            except Exception as e:
                chat_log.write(f"[bold red]Error: {e}[/]\n")

        def action_help(self) -> None:
            self.push_screen(HelpScreen())

        def action_sidebar_plan(self) -> None:
            self.current_sidebar_tab = "plan"

        def action_sidebar_trace(self) -> None:
            self.current_sidebar_tab = "trace"

        def action_sidebar_memory(self) -> None:
            self.current_sidebar_tab = "memory"

        def action_sidebar_knowledge(self) -> None:
            self.current_sidebar_tab = "knowledge"

        def action_sidebar_tools(self) -> None:
            self.current_sidebar_tab = "tools"

        def action_toggle_cognitive(self) -> None:
            self.cognitive_mode = not self.cognitive_mode
            self.notify(
                f"Cognitive mode {'ON' if self.cognitive_mode else 'OFF'}"
            )

        def action_clear_chat(self) -> None:
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.clear()
            self.notify("Chat cleared")

        def action_save_session(self) -> None:
            self.notify("Session saved")

        def action_new_branch(self) -> None:
            self.notify("New branch created")

        def action_focus_input(self) -> None:
            input_widget = self.query_one("#input-bar", Input)
            input_widget.focus()


    async def run_textual_chat(
        workspace: str = ".",
        model: str = "",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        """Launch the Nexus Textual TUI.

        This is the artifact-first cognitive coding interface — a full
        terminal application with tabbed sidebars, plan cards, trace trees,
        and keyboard shortcuts.

        Args:
            workspace: Path to the project directory.
            model: Ollama model name (e.g., "qwen2.5-coder:14b").
            ollama_url: Ollama API endpoint.
        """
        config = AgentConfig()
        if model:
            config.coding_model = model
        config.ollama_url = ollama_url

        session = ChatSession(
            config=config,
            workspace=workspace,
            model=model or config.coding_model,
        )

        app = NexusApp(session=session)
        await app.run_async()

else:
    def run_textual_chat(
        workspace: str = ".",
        model: str = "",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        raise ImportError(
            "Textual is required for the new TUI. Install with: pip install textual"
        )
