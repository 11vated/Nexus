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
        background: $surface;
        color: $text-muted;
        border-left: thick $warning;
    }
    MessageWidget.tool-message {
        background: $surface;
        color: $text-muted;
        border-left: thick $accent;
    }
    MessageWidget.cognitive-message {
        background: $boost;
        color: $text;
        border-left: thick $secondary;
    }
    MessageWidget.error-message {
        background: $error 10%;
        color: $error;
        border-left: thick $error;
    }
    """

    def __init__(self, msg: ChatMessage, **kwargs) -> None:
        role_class = f"{msg.event_type or msg.role}-message"
        if msg.event_type in ("verification", "diff", "routing"):
            role_class = "cognitive-message"
        elif msg.event_type == "error":
            role_class = "error-message"
        elif msg.role == "tool":
            role_class = "tool-message"

        display_text = f"{msg.icon}  {msg.content}"
        super().__init__(display_text, classes=role_class, **kwargs)


class StreamingMessage(Static):
    """A message being actively streamed — tokens append in real time."""

    DEFAULT_CSS = """
    StreamingMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        background: $surface;
        color: $text;
        border-left: thick $success;
    }
    """

    content_text: reactive[str] = reactive("🤖  ", layout=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tokens: list[str] = []

    def append_token(self, token: str) -> None:
        self._tokens.append(token)
        self.content_text = "🤖  " + "".join(self._tokens)

    def finalize(self) -> str:
        full = "".join(self._tokens)
        self._tokens.clear()
        return full

    def watch_content_text(self, value: str) -> None:
        self.update(value)


class PlanCard(Static):
    """A single plan step rendered as an interactive card."""

    DEFAULT_CSS = """
    PlanCard {
        padding: 1;
        margin: 0 0 1 0;
        border: round $primary;
        height: auto;
    }
    PlanCard.completed {
        border: round $success;
        opacity: 0.7;
    }
    PlanCard.failed {
        border: round $error;
    }
    PlanCard.active {
        border: double $warning;
        background: $warning 10%;
    }
    """

    def __init__(self, step_id: str, title: str, status: str = "pending",
                 risk: str = "low", description: str = "", **kwargs) -> None:
        self.step_id = step_id
        self.step_title = title
        self.status = status
        self.risk = risk
        self.description = description

        status_icons = {
            "pending": "⬜",
            "active": "🔄",
            "completed": "✅",
            "failed": "❌",
            "skipped": "⏭️",
        }
        risk_colors = {"low": "🟢", "medium": "🟡", "high": "🔴"}

        icon = status_icons.get(status, "⬜")
        risk_icon = risk_colors.get(risk, "⬜")

        text = f"{icon} {title}  {risk_icon}\n"
        if description:
            text += f"  {description[:120]}"

        super().__init__(text, classes=status, **kwargs)


class CognitiveIndicator(Static):
    """Compact cognitive mode indicator for the header."""

    DEFAULT_CSS = """
    CognitiveIndicator {
        dock: right;
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }
    CognitiveIndicator.mode-passive {
        color: $success;
    }
    CognitiveIndicator.mode-guided {
        color: $warning;
    }
    CognitiveIndicator.mode-autonomous {
        color: $error;
    }
    """

    mode: reactive[str] = reactive("passive")

    def watch_mode(self, value: str) -> None:
        mode_display = {
            "off": "COG:OFF",
            "passive": "🧠 PASSIVE",
            "guided": "🧠 GUIDED",
            "autonomous": "🧠 AUTO",
        }
        self.update(mode_display.get(value, f"COG:{value.upper()}"))
        self.set_class(value != "off", f"mode-{value}")

    def render(self) -> str:
        mode_display = {
            "off": "COG:OFF",
            "passive": "🧠 PASSIVE",
            "guided": "🧠 GUIDED",
            "autonomous": "🧠 AUTO",
        }
        return mode_display.get(self.mode, f"COG:{self.mode.upper()}")


# ── Help Overlay ────────────────────────────────────────────────────────────


class HelpScreen(ModalScreen[None]):
    """Modal help screen with keybinding reference."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Container {
        width: 72;
        height: 36;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close"),
        Binding("f1", "dismiss(None)", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(
                "╭─── NEXUS KEYBOARD SHORTCUTS ───────────────────╮\n"
                "│                                                 │\n"
                "│  ⌨️  Navigation                                 │\n"
                "│  Tab          Cycle focus between panes         │\n"
                "│  Escape       Focus input                       │\n"
                "│  F1           Toggle this help                  │\n"
                "│  F2           Sidebar → Plan                    │\n"
                "│  F3           Sidebar → Trace                   │\n"
                "│  F4           Sidebar → Memory                  │\n"
                "│  F5           Refresh project context            │\n"
                "│                                                 │\n"
                "│  ✏️  Input                                       │\n"
                "│  Enter        Send message                      │\n"
                "│  Shift+Enter  New line in input                 │\n"
                "│  Up/Down      Scroll input history               │\n"
                "│                                                 │\n"
                "│  ⚡ Actions                                      │\n"
                "│  Ctrl+K       Cycle cognitive mode               │\n"
                "│  Ctrl+L       Clear chat                        │\n"
                "│  Ctrl+S       Save session                      │\n"
                "│  Ctrl+B       Create conversation branch        │\n"
                "│  Ctrl+Q       Quit                              │\n"
                "│                                                 │\n"
                "│  💬 Slash Commands                               │\n"
                "│  /help /plan /tools /stance /project /route      │\n"
                "│  /save /load /clear /stats /diff /branch         │\n"
                "│  /cognitive /trace /knowledge /memory            │\n"
                "│  /learn <text> /remember <text> /quit            │\n"
                "╰─────────────────────────────────────────────────╯"
            )


# ── Main Application ────────────────────────────────────────────────────────


class NexusApp(App[None]):
    """The Nexus Textual TUI application."""

    TITLE = "NEXUS"
    SUB_TITLE = "Cognitive Coding Partner"

    CSS = """
    /* ── Global ────────────────────────────────── */
    Screen {
        background: $background;
    }

    /* ── Layout ────────────────────────────────── */
    #main-container {
        height: 1fr;
    }
    #chat-column {
        width: 3fr;
        min-width: 40;
    }
    #sidebar-column {
        width: 1fr;
        min-width: 24;
        max-width: 50;
        border-left: tall $primary-background;
    }

    /* ── Chat Pane ─────────────────────────────── */
    #chat-scroll {
        height: 1fr;
        scrollbar-gutter: stable;
    }
    #chat-messages {
        padding: 0 1;
    }

    /* ── Input Area ────────────────────────────── */
    #input-area {
        dock: bottom;
        height: auto;
        max-height: 8;
        padding: 0 1;
        border-top: tall $primary-background;
    }
    #message-input {
        width: 1fr;
    }
    #send-button {
        width: 8;
        min-width: 8;
    }

    /* ── Sidebar ───────────────────────────────── */
    #sidebar-tabs {
        height: 1fr;
    }
    .sidebar-content {
        padding: 1;
        height: 1fr;
    }

    /* ── Status Bar ────────────────────────────── */
    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary-background;
        color: $text-muted;
        padding: 0 1;
    }

    /* ── Header Info ───────────────────────────── */
    #header-info {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }

    /* ── Loading ───────────────────────────────── */
    #thinking-indicator {
        height: 1;
        display: none;
        color: $warning;
        padding: 0 1;
    }
    #thinking-indicator.visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("f1", "toggle_help", "Help", show=True),
        Binding("f2", "sidebar_plan", "Plan", show=True),
        Binding("f3", "sidebar_trace", "Trace", show=True),
        Binding("f4", "sidebar_memory", "Memory", show=True),
        Binding("f5", "refresh_context", "Refresh", show=True),
        Binding("ctrl+k", "cycle_cognitive", "Cog Mode", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
        Binding("ctrl+s", "save_session", "Save", show=False),
        Binding("ctrl+b", "create_branch", "Branch", show=False),
        Binding("ctrl+q", "quit_app", "Quit", show=True),
        Binding("escape", "focus_input", "Focus Input", show=False),
    ]

    # Reactive state
    is_streaming: reactive[bool] = reactive(False)
    message_count: reactive[int] = reactive(0)
    current_model: reactive[str] = reactive("")
    current_stance: reactive[str] = reactive("")
    current_branch: reactive[str] = reactive("main")
    cognitive_mode: reactive[str] = reactive("passive")

    def __init__(
        self,
        session: ChatSession,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.session = session
        self._input_history: list[str] = []
        self._history_idx: int = -1
        self._streaming_widget: Optional[StreamingMessage] = None
        self._plan_cards: list[PlanCard] = []

        # Set initial reactive values from session
        self.current_model = session.model or ""
        if session._stances:
            cfg = session._stances.current_config
            self.current_stance = f"{cfg.emoji} {cfg.display_name}"

    def compose(self) -> ComposeResult:
        """Build the widget tree."""
        # Header
        yield Static(self._build_header_text(), id="header-info")

        # Main content area
        with Horizontal(id="main-container"):
            # Chat column
            with Vertical(id="chat-column"):
                with VerticalScroll(id="chat-scroll"):
                    yield Vertical(id="chat-messages")
                yield Static("", id="thinking-indicator")

            # Sidebar column
            with Vertical(id="sidebar-column"):
                with TabbedContent(id="sidebar-tabs"):
                    with TabPane("Plan", id="tab-plan"):
                        yield VerticalScroll(
                            Static("No active plan.", id="plan-empty"),
                            id="plan-scroll",
                            classes="sidebar-content",
                        )
                    with TabPane("Trace", id="tab-trace"):
                        yield VerticalScroll(
                            Static("No reasoning trace yet.", id="trace-content"),
                            id="trace-scroll",
                            classes="sidebar-content",
                        )
                    with TabPane("Know", id="tab-knowledge"):
                        yield VerticalScroll(
                            Static("No knowledge stored.", id="knowledge-content"),
                            id="knowledge-scroll",
                            classes="sidebar-content",
                        )
                    with TabPane("Mem", id="tab-memory"):
                        yield VerticalScroll(
                            Static("No memories yet.", id="memory-content"),
                            id="memory-scroll",
                            classes="sidebar-content",
                        )
                    with TabPane("Tools", id="tab-tools"):
                        yield VerticalScroll(
                            Static(self._build_tools_text(), id="tools-content"),
                            id="tools-scroll",
                            classes="sidebar-content",
                        )

        # Input area
        with Horizontal(id="input-area"):
            yield Input(
                placeholder="Message Nexus... (Enter to send, Shift+Enter for newline)",
                id="message-input",
            )
            yield Button("Send", id="send-button", variant="primary")

        # Status bar
        yield Static(self._build_status_text(), id="status-bar")

        # Footer with keybindings
        yield Footer()

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#message-input", Input).focus()
        self._add_system_message(
            "Welcome to Nexus 🧠 Type a message or use /help for commands.\n"
            f"Model: {self.session.model}  •  Cognitive: {self.cognitive_mode}"
        )

    # ── Header/Status builders ──────────────────────────────────────────

    def _build_header_text(self) -> str:
        parts = ["⚡ NEXUS"]
        if self.current_model:
            parts.append(f"📡 {self.current_model}")
        if self.current_stance:
            parts.append(self.current_stance)
        parts.append(f"🌿 {self.current_branch}")

        mode_icons = {
            "off": "COG:OFF",
            "passive": "🧠 PASSIVE",
            "guided": "🧠 GUIDED",
            "autonomous": "🧠 AUTO",
        }
        parts.append(mode_icons.get(self.cognitive_mode, "🧠"))
        return "  │  ".join(parts)

    def _build_status_text(self) -> str:
        stats = self.session.stats()
        turns = stats.get("turns", 0)
        tools = stats.get("tool_calls", 0)
        return f"  Turns: {turns}  │  Tools: {tools}  │  Messages: {self.message_count}"

    def _build_tools_text(self) -> str:
        tools = list(self.session._tools.keys()) if self.session._tools else []
        if not tools:
            return "No tools registered."
        lines = ["Available Tools:", ""]
        for t in sorted(tools):
            lines.append(f"  🔧 {t}")
        return "\n".join(lines)

    # ── Reactive watchers ───────────────────────────────────────────────

    def watch_is_streaming(self, streaming: bool) -> None:
        try:
            indicator = self.query_one("#thinking-indicator", Static)
            if streaming:
                indicator.update("⏳ Nexus is thinking...")
                indicator.add_class("visible")
            else:
                indicator.remove_class("visible")
                indicator.update("")
        except NoMatches:
            pass

    def watch_message_count(self, count: int) -> None:
        try:
            self.query_one("#status-bar", Static).update(self._build_status_text())
        except NoMatches:
            pass

    def watch_cognitive_mode(self, mode: str) -> None:
        try:
            self.query_one("#header-info", Static).update(self._build_header_text())
        except NoMatches:
            pass

    # ── Message display ─────────────────────────────────────────────────

    def _add_message(self, msg: ChatMessage) -> None:
        """Add a message widget to the chat pane."""
        container = self.query_one("#chat-messages", Vertical)
        widget = MessageWidget(msg)
        container.mount(widget)
        self.message_count += 1
        # Auto-scroll to bottom
        scroll = self.query_one("#chat-scroll", VerticalScroll)
        scroll.scroll_end(animate=False)

    def _add_system_message(self, text: str) -> None:
        self._add_message(ChatMessage(role="system", content=text, event_type="system"))

    def _start_streaming(self) -> StreamingMessage:
        """Create a streaming message widget."""
        container = self.query_one("#chat-messages", Vertical)
        widget = StreamingMessage()
        container.mount(widget)
        self._streaming_widget = widget
        self.is_streaming = True
        return widget

    def _finish_streaming(self) -> Optional[str]:
        """Finalize the streaming widget."""
        if self._streaming_widget:
            full = self._streaming_widget.finalize()
            self._streaming_widget = None
            self.is_streaming = False
            self.message_count += 1
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.scroll_end(animate=False)
            return full
        self.is_streaming = False
        return None

    # ── Sidebar updates ─────────────────────────────────────────────────

    def _update_plan_panel(self) -> None:
        """Refresh the plan panel from cognitive state."""
        if not self.session._cognitive:
            return
        try:
            plan_scroll = self.query_one("#plan-scroll", VerticalScroll)
        except NoMatches:
            return

        # Get plan steps from SharedState
        cog = self.session._cognitive
        steps = []
        if hasattr(cog, '_loop') and cog._loop and hasattr(cog._loop, '_state'):
            state = cog._loop._state
            if hasattr(state, 'plan_steps'):
                steps = state.plan_steps

        # Remove old plan-empty message
        try:
            plan_scroll.query_one("#plan-empty", Static).remove()
        except NoMatches:
            pass

        # Remove old plan cards
        for card in self._plan_cards:
            try:
                card.remove()
            except Exception:
                pass
        self._plan_cards.clear()

        if not steps:
            plan_scroll.mount(Static("No active plan steps.", id="plan-empty"))
            return

        for step in steps:
            card = PlanCard(
                step_id=getattr(step, 'id', ''),
                title=getattr(step, 'title', str(step)),
                status=getattr(step, 'status', 'pending'),
                risk=getattr(step, 'risk', 'low'),
                description=getattr(step, 'description', ''),
            )
            plan_scroll.mount(card)
            self._plan_cards.append(card)

    def _update_trace_panel(self) -> None:
        """Refresh the trace panel."""
        if not self.session._cognitive:
            return
        try:
            content = self.query_one("#trace-content", Static)
        except NoMatches:
            return
        summary = self.session.get_reasoning_trace()
        content.update(summary or "No reasoning trace yet.")

    def _update_knowledge_panel(self) -> None:
        """Refresh the knowledge panel."""
        if not self.session._cognitive:
            return
        try:
            content = self.query_one("#knowledge-content", Static)
        except NoMatches:
            return
        summary = self.session.get_knowledge_summary()
        content.update(summary or "No knowledge stored.")

    def _update_memory_panel(self) -> None:
        """Refresh the memory panel."""
        if not self.session._cognitive:
            return
        try:
            content = self.query_one("#memory-content", Static)
        except NoMatches:
            return
        summary = self.session.get_memory_summary()
        content.update(summary or "No memories yet.")

    def _refresh_all_sidebars(self) -> None:
        """Update all sidebar panels."""
        self._update_plan_panel()
        self._update_trace_panel()
        self._update_knowledge_panel()
        self._update_memory_panel()

    # ── Input handling ──────────────────────────────────────────────────

    @on(Input.Submitted, "#message-input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in the input field."""
        await self._send_input()

    @on(Button.Pressed, "#send-button")
    async def on_send_pressed(self, event: Button.Pressed) -> None:
        """Handle Send button click."""
        await self._send_input()

    async def _send_input(self) -> None:
        """Process the current input value."""
        inp = self.query_one("#message-input", Input)
        text = inp.value.strip()
        if not text:
            return

        inp.value = ""
        inp.focus()

        # Save to input history
        if not self._input_history or self._input_history[-1] != text:
            self._input_history.append(text)
        self._history_idx = -1

        # Handle slash commands
        if text.startswith("/"):
            await self._handle_slash_command(text)
            return

        # Regular message
        self._add_message(ChatMessage(role="user", content=text))
        await self._send_to_session(text)

    async def _handle_slash_command(self, cmd: str) -> None:
        """Route slash commands."""
        parts = cmd.strip().split(maxsplit=2)
        command = parts[0].lower()
        arg1 = parts[1] if len(parts) > 1 else ""
        arg2 = parts[2] if len(parts) > 2 else ""

        if command in ("/quit", "/exit", "/q"):
            self.exit()
            return

        if command == "/help":
            self.action_toggle_help()
            return

        if command == "/clear":
            self.action_clear_chat()
            return

        if command in ("/cognitive", "/cog"):
            if arg1:
                result = self.session.set_cognitive_mode(arg1)
                self.cognitive_mode = self.session.get_cognitive_mode()
                self._add_system_message(result)
            else:
                mode = self.session.get_cognitive_mode()
                self._add_system_message(f"Cognitive mode: {mode}")
            return

        if command == "/trace":
            self._update_trace_panel()
            # Also switch sidebar to trace tab
            try:
                tabs = self.query_one("#sidebar-tabs", TabbedContent)
                tabs.active = "tab-trace"
            except NoMatches:
                pass
            summary = self.session.get_reasoning_trace()
            self._add_system_message(summary or "No trace available.")
            return

        if command == "/knowledge":
            self._update_knowledge_panel()
            try:
                tabs = self.query_one("#sidebar-tabs", TabbedContent)
                tabs.active = "tab-knowledge"
            except NoMatches:
                pass
            summary = self.session.get_knowledge_summary()
            self._add_system_message(summary or "No knowledge stored.")
            return

        if command == "/memory":
            self._update_memory_panel()
            try:
                tabs = self.query_one("#sidebar-tabs", TabbedContent)
                tabs.active = "tab-memory"
            except NoMatches:
                pass
            summary = self.session.get_memory_summary()
            self._add_system_message(summary or "No memories yet.")
            return

        if command == "/learn":
            text = " ".join(parts[1:]) if len(parts) > 1 else ""
            if text:
                result = self.session.cognitive_learn(text)
                self._add_system_message(f"Learned: {result}")
                self._update_knowledge_panel()
            else:
                self._add_system_message("Usage: /learn <knowledge text>")
            return

        if command == "/remember":
            text = " ".join(parts[1:]) if len(parts) > 1 else ""
            if text:
                result = self.session.cognitive_remember(text)
                self._add_system_message(f"Remembered: {result}")
                self._update_memory_panel()
            else:
                self._add_system_message("Usage: /remember <memory text>")
            return

        if command == "/tools":
            try:
                tabs = self.query_one("#sidebar-tabs", TabbedContent)
                tabs.active = "tab-tools"
            except NoMatches:
                pass
            self._add_system_message(self._build_tools_text())
            return

        if command == "/stats":
            stats = self.session.stats()
            lines = ["Session Statistics:", ""]
            for k, v in stats.items():
                if isinstance(v, dict):
                    lines.append(f"  {k}:")
                    for kk, vv in v.items():
                        lines.append(f"    {kk}: {vv}")
                else:
                    lines.append(f"  {k}: {v}")
            self._add_system_message("\n".join(lines))
            return

        if command == "/stance":
            if not self.session._stances:
                self._add_system_message("Stances not available.")
                return
            if arg1:
                try:
                    self.session._stances.set_stance(arg1)
                    cfg = self.session._stances.current_config
                    self.current_stance = f"{cfg.emoji} {cfg.display_name}"
                    self._add_system_message(f"Stance: {cfg.emoji} {cfg.display_name}")
                except Exception as e:
                    self._add_system_message(f"Error setting stance: {e}")
            else:
                cfg = self.session._stances.current_config
                self._add_system_message(
                    f"Current stance: {cfg.emoji} {cfg.display_name}\n"
                    f"Available: architect, pair_programmer, debugger, reviewer, teacher"
                )
            return

        if command == "/project":
            if self.session._project_map:
                summary = self.session._project_map.summary()
                self._add_system_message(str(summary))
            else:
                self._add_system_message("Project map not available.")
            return

        if command == "/route":
            if self.session._router and self.session._router.history:
                lines = ["Model Routing History:", ""]
                for d in self.session._router.history[-5:]:
                    lines.append(f"  {d.intent.value} → {d.model} ({d.confidence:.0%})")
                self._add_system_message("\n".join(lines))
            else:
                self._add_system_message("No routing history.")
            return

        if command == "/save":
            name = arg1 or None
            if self.session._session_store:
                sid = self.session._session_store.save(
                    self.session.history,
                    metadata={"name": name} if name else {},
                )
                self._add_system_message(f"Session saved: {sid}")
            else:
                self._add_system_message("Session store not available.")
            return

        if command == "/branch":
            if not arg1:
                self._add_system_message("Usage: /branch <name>")
                return
            try:
                self.session.create_branch(arg1)
                self.current_branch = arg1
                self._add_system_message(f"Created branch: {arg1}")
            except Exception as e:
                self._add_system_message(f"Error: {e}")
            return

        if command == "/branches":
            if self.session._branch_tree:
                branches = self.session._branch_tree.list_branches()
                current = self.session.current_branch
                lines = ["Conversation Branches:", ""]
                for b in branches:
                    marker = " ← current" if b == current else ""
                    lines.append(f"  🌿 {b}{marker}")
                self._add_system_message("\n".join(lines))
            else:
                self._add_system_message("No branches.")
            return

        if command == "/switch":
            if arg1 and self.session._branch_tree:
                try:
                    self.session._branch_tree.switch_to(arg1)
                    self.current_branch = arg1
                    self._add_system_message(f"Switched to branch: {arg1}")
                except Exception as e:
                    self._add_system_message(f"Error: {e}")
            else:
                self._add_system_message("Usage: /switch <branch>")
            return

        if command == "/diff":
            mode = arg1 or "summary"
            self._add_system_message(f"Diff mode: {mode} (display in sidebar coming soon)")
            return

        if command == "/plan":
            text = " ".join(parts[1:]) if len(parts) > 1 else ""
            if text:
                # Send as a plan request to the session
                self._add_message(ChatMessage(role="user", content=f"/plan {text}"))
                await self._send_to_session(f"Please create a detailed plan for: {text}")
            else:
                self._update_plan_panel()
                try:
                    tabs = self.query_one("#sidebar-tabs", TabbedContent)
                    tabs.active = "tab-plan"
                except NoMatches:
                    pass
                self._add_system_message("Plan panel updated. Use /plan <task> to request a plan.")
            return

        if command == "/audit":
            n = int(arg1) if arg1.isdigit() else 10
            if self.session._permissions:
                log = self.session._permissions.get_audit_log(last_n=n)
                if log:
                    lines = [f"Last {len(log)} audit entries:", ""]
                    for entry in log:
                        lines.append(f"  {entry}")
                    self._add_system_message("\n".join(lines))
                else:
                    self._add_system_message("No audit entries.")
            else:
                self._add_system_message("Permissions not available.")
            return

        if command == "/hooks":
            if self.session._hooks:
                hooks = self.session._hooks.list_hooks()
                if hooks:
                    lines = ["Registered Hooks:", ""]
                    for h in hooks:
                        lines.append(f"  🪝 {h}")
                    self._add_system_message("\n".join(lines))
                else:
                    self._add_system_message("No hooks registered.")
            else:
                self._add_system_message("Hook engine not available.")
            return

        # Unknown command
        self._add_system_message(f"Unknown command: {command}. Try /help")

    # ── Session communication ───────────────────────────────────────────

    @work(thread=True, exclusive=True, name="send_message")
    async def _send_to_session(self, text: str) -> None:
        """Send a message to the ChatSession and process events."""
        self.is_streaming = True
        streaming_widget = None

        try:
            async for event in self.session.send_streaming(text):
                if event.type == EventType.TOKEN:
                    if streaming_widget is None:
                        streaming_widget = self.call_from_thread(self._start_streaming)
                    self.call_from_thread(streaming_widget.append_token, event.content)

                elif event.type == EventType.TOOL_CALL:
                    # Finalize any streaming before showing tool call
                    if streaming_widget is not None:
                        self.call_from_thread(self._finish_streaming)
                        streaming_widget = None
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="tool",
                            content=f"Calling: {event.content}",
                            event_type="tool",
                            data=event.data,
                        ),
                    )

                elif event.type == EventType.TOOL_RESULT:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="tool",
                            content=event.content[:500],
                            event_type="tool",
                            data=event.data,
                        ),
                    )

                elif event.type == EventType.ROUTING:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="system",
                            content=f"Routed to: {event.content}",
                            event_type="routing",
                            data=event.data,
                        ),
                    )
                    if event.data and "model" in event.data:
                        self.current_model = event.data["model"]

                elif event.type == EventType.STANCE_CHANGE:
                    self.current_stance = event.content
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="system",
                            content=f"Stance: {event.content}",
                            event_type="system",
                        ),
                    )

                elif event.type == EventType.DIFF_PREVIEW:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="system",
                            content=f"Diff preview:\n{event.content[:300]}",
                            event_type="diff",
                            data=event.data,
                        ),
                    )

                elif event.type == EventType.AMBIGUITY:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="cognitive",
                            content=event.content,
                            event_type="cognitive",
                            data=event.data,
                        ),
                    )

                elif event.type == EventType.KNOWLEDGE:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="cognitive",
                            content=event.content,
                            event_type="cognitive",
                            data=event.data,
                        ),
                    )
                    self.call_from_thread(self._update_knowledge_panel)

                elif event.type == EventType.MEMORY:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="cognitive",
                            content=event.content,
                            event_type="cognitive",
                            data=event.data,
                        ),
                    )
                    self.call_from_thread(self._update_memory_panel)

                elif event.type == EventType.VERIFICATION:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="cognitive",
                            content=event.content,
                            event_type="verification",
                            data=event.data,
                        ),
                    )

                elif event.type == EventType.COGNITIVE:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="cognitive",
                            content=event.content,
                            event_type="cognitive",
                            data=event.data,
                        ),
                    )

                elif event.type == EventType.ERROR:
                    self.call_from_thread(
                        self._add_message,
                        ChatMessage(
                            role="system",
                            content=event.content,
                            event_type="error",
                        ),
                    )

                elif event.type == EventType.DONE:
                    break

        except Exception as exc:
            self.call_from_thread(
                self._add_message,
                ChatMessage(
                    role="system",
                    content=f"Error: {exc}",
                    event_type="error",
                ),
            )
        finally:
            if streaming_widget is not None:
                self.call_from_thread(self._finish_streaming)
            self.is_streaming = False
            # Refresh sidebars after each turn
            self.call_from_thread(self._refresh_all_sidebars)
            self.call_from_thread(self._update_header)

    def _update_header(self) -> None:
        try:
            self.query_one("#header-info", Static).update(self._build_header_text())
            self.query_one("#status-bar", Static).update(self._build_status_text())
        except NoMatches:
            pass

    # ── Actions (keybindings) ───────────────────────────────────────────

    def action_toggle_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_sidebar_plan(self) -> None:
        self._update_plan_panel()
        try:
            self.query_one("#sidebar-tabs", TabbedContent).active = "tab-plan"
        except NoMatches:
            pass

    def action_sidebar_trace(self) -> None:
        self._update_trace_panel()
        try:
            self.query_one("#sidebar-tabs", TabbedContent).active = "tab-trace"
        except NoMatches:
            pass

    def action_sidebar_memory(self) -> None:
        self._update_memory_panel()
        try:
            self.query_one("#sidebar-tabs", TabbedContent).active = "tab-memory"
        except NoMatches:
            pass

    def action_refresh_context(self) -> None:
        self._refresh_all_sidebars()
        self._add_system_message("Context refreshed.")

    def action_cycle_cognitive(self) -> None:
        modes = ["off", "passive", "guided", "autonomous"]
        current = self.session.get_cognitive_mode()
        try:
            idx = modes.index(current)
            next_mode = modes[(idx + 1) % len(modes)]
        except ValueError:
            next_mode = "passive"
        result = self.session.set_cognitive_mode(next_mode)
        self.cognitive_mode = self.session.get_cognitive_mode()
        self._add_system_message(f"Cognitive mode: {self.cognitive_mode}")

    def action_clear_chat(self) -> None:
        container = self.query_one("#chat-messages", Vertical)
        container.remove_children()
        self.message_count = 0
        self._add_system_message("Chat cleared. History preserved in session.")

    def action_save_session(self) -> None:
        if self.session._session_store:
            sid = self.session._session_store.save(self.session.history)
            self._add_system_message(f"Session saved: {sid}")
        else:
            self._add_system_message("Session store not available.")

    def action_create_branch(self) -> None:
        self._add_system_message("Use /branch <name> to create a branch.")

    def action_focus_input(self) -> None:
        self.query_one("#message-input", Input).focus()

    def action_quit_app(self) -> None:
        self.exit()


# ── Entry point ─────────────────────────────────────────────────────────────


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
    if not TEXTUAL_AVAILABLE:
        raise ImportError(
            "Textual is required for the new TUI. Install with: pip install textual"
        )

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
