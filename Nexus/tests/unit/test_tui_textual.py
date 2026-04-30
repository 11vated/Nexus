"""Tests for the Textual TUI module.

Since Textual apps require a terminal, we test the non-UI logic:
data models, message widgets, slash command routing, sidebar builders,
and state management.
"""

import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Test the data models and helpers that don't require Textual runtime
from nexus.tui.textual_ui import (
    ChatMessage,
    SidebarTab,
    TEXTUAL_AVAILABLE,
)


class TestChatMessage:
    def test_user_message(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.icon == "👤"

    def test_assistant_message(self):
        msg = ChatMessage(role="assistant", content="hi")
        assert msg.icon == "🤖"

    def test_system_message(self):
        msg = ChatMessage(role="system", content="info")
        assert msg.icon == "⚙️"

    def test_tool_message(self):
        msg = ChatMessage(role="tool", content="result", event_type="tool")
        assert msg.icon == "🔧"

    def test_cognitive_message(self):
        msg = ChatMessage(role="cognitive", content="thinking", event_type="cognitive")
        assert msg.icon == "🧠"

    def test_verification_message(self):
        msg = ChatMessage(role="cognitive", content="check", event_type="verification")
        assert msg.icon == "⚡"

    def test_error_message(self):
        msg = ChatMessage(role="system", content="oops", event_type="error")
        assert msg.icon == "❌"

    def test_unknown_role(self):
        msg = ChatMessage(role="unknown", content="x")
        assert msg.icon == "•"

    def test_timestamp_auto_set(self):
        before = time.time()
        msg = ChatMessage(role="user", content="x")
        assert msg.timestamp >= before

    def test_data_field(self):
        msg = ChatMessage(
            role="tool", content="x",
            data={"tool": "shell", "args": {"cmd": "ls"}},
        )
        assert msg.data["tool"] == "shell"


class TestSidebarTab:
    def test_tab_values(self):
        assert SidebarTab.PLAN == "plan"
        assert SidebarTab.TRACE == "trace"
        assert SidebarTab.KNOWLEDGE == "knowledge"
        assert SidebarTab.MEMORY == "memory"
        assert SidebarTab.TOOLS == "tools"

    def test_all_tabs(self):
        assert len(SidebarTab) == 5


class TestTextualAvailability:
    def test_textual_flag_set(self):
        # TEXTUAL_AVAILABLE should be True or False based on import
        assert isinstance(TEXTUAL_AVAILABLE, bool)


# ── Textual widget tests (only run if Textual is installed) ────────────────

@pytest.mark.skipif(not TEXTUAL_AVAILABLE, reason="Textual not installed")
class TestTextualWidgets:
    """Tests that require Textual to be installed."""

    def test_message_widget_creates(self):
        from nexus.tui.textual_ui import MessageWidget
        msg = ChatMessage(role="user", content="test message")
        widget = MessageWidget(msg)
        assert widget is not None

    def test_streaming_message_creates(self):
        from nexus.tui.textual_ui import StreamingMessage
        widget = StreamingMessage()
        assert widget is not None

    def test_streaming_message_append(self):
        from nexus.tui.textual_ui import StreamingMessage
        widget = StreamingMessage()
        widget.append_text("hello")
        widget.append_text(" world")
        full = widget.current_text
        assert full == "hello world"

    def test_streaming_message_finish(self):
        from nexus.tui.textual_ui import StreamingMessage
        widget = StreamingMessage()
        widget.append_text("test")
        widget.finish()
        assert widget.is_done is True

    def test_plan_card_creates(self):
        from nexus.tui.textual_ui import PlanCard
        card = PlanCard()
        assert card is not None
        assert card.steps == []

    def test_plan_card_with_steps(self):
        from nexus.tui.textual_ui import PlanCard
        steps = [
            {"description": "Step one", "status": "done"},
            {"description": "Step two", "status": "pending"},
        ]
        card = PlanCard(plan_steps=steps)
        assert len(card.steps) == 2

    def test_plan_card_update(self):
        from nexus.tui.textual_ui import PlanCard
        card = PlanCard()
        card.update_plan([{"description": "new step", "status": "running"}])
        assert len(card.steps) == 1

    def test_cognitive_indicator_creates(self):
        from nexus.tui.textual_ui import CognitiveIndicator
        indicator = CognitiveIndicator()
        assert indicator is not None
        assert indicator.stance == "neutral"
        assert indicator.mode == "chat"

    def test_help_screen_creates(self):
        from nexus.tui.textual_ui import HelpScreen
        screen = HelpScreen()
        assert screen is not None

    def test_nexus_app_creates(self):
        from nexus.tui.textual_ui import NexusApp
        from nexus.agent.models import AgentConfig
        from nexus.agent.chat import ChatSession

        config = AgentConfig()
        session = ChatSession(config=config, workspace="/tmp", model="test:latest")
        app = NexusApp(session=session)
        assert app is not None
        assert app.session is session

    def test_nexus_app_bindings(self):
        """Test that NexusApp has expected keybindings."""
        from nexus.tui.textual_ui import NexusApp
        from nexus.agent.models import AgentConfig
        from nexus.agent.chat import ChatSession

        config = AgentConfig()
        session = ChatSession(config=config, workspace="/tmp", model="test:latest")
        app = NexusApp(session=session)
        # BINDINGS is a list of tuples: (key, action, description)
        binding_keys = [b[0] for b in app.BINDINGS]
        assert "f1" in binding_keys
        assert "escape" in binding_keys
        assert any("ctrl+s" in k for k in binding_keys)

    def test_nexus_app_has_css(self):
        """Test that NexusApp has CSS styling defined."""
        from nexus.tui.textual_ui import NexusApp
        # DEFAULT_CSS should be defined (even if empty string is acceptable)
        assert hasattr(NexusApp, "DEFAULT_CSS")

    def test_nexus_app_reactives(self):
        """Test that NexusApp has reactive state."""
        from nexus.tui.textual_ui import NexusApp
        from nexus.agent.models import AgentConfig
        from nexus.agent.chat import ChatSession

        config = AgentConfig()
        session = ChatSession(config=config, workspace="/tmp", model="test:latest")
        app = NexusApp(session=session)
        assert hasattr(app, "current_sidebar_tab")
        assert hasattr(app, "cognitive_mode")
