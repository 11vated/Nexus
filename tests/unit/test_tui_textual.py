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
        widget.append_token("hello")
        widget.append_token(" world")
        full = widget.finalize()
        assert full == "hello world"

    def test_streaming_message_finalize_clears(self):
        from nexus.tui.textual_ui import StreamingMessage
        widget = StreamingMessage()
        widget.append_token("test")
        widget.finalize()
        # Second finalize should return empty
        assert widget.finalize() == ""

    def test_plan_card_creates(self):
        from nexus.tui.textual_ui import PlanCard
        card = PlanCard(
            step_id="step-1",
            title="Implement feature",
            status="pending",
            risk="low",
            description="Add the new endpoint",
        )
        assert card.step_id == "step-1"
        assert card.step_title == "Implement feature"

    def test_plan_card_statuses(self):
        from nexus.tui.textual_ui import PlanCard
        for status in ["pending", "active", "completed", "failed", "skipped"]:
            card = PlanCard(
                step_id=f"s-{status}",
                title=f"Step {status}",
                status=status,
            )
            assert card is not None

    def test_cognitive_indicator_creates(self):
        from nexus.tui.textual_ui import CognitiveIndicator
        indicator = CognitiveIndicator()
        assert indicator is not None

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
        # Check bindings are defined
        binding_keys = [b.key for b in app.BINDINGS]
        assert "f1" in binding_keys
        assert "ctrl+q" in binding_keys
        assert "escape" in binding_keys

    def test_nexus_app_css_defined(self):
        """Test that NexusApp has CSS styling."""
        from nexus.tui.textual_ui import NexusApp
        assert NexusApp.CSS is not None
        assert "#chat-scroll" in NexusApp.CSS
        assert "#sidebar-column" in NexusApp.CSS

    def test_nexus_app_tools_text(self):
        from nexus.tui.textual_ui import NexusApp
        from nexus.agent.models import AgentConfig
        from nexus.agent.chat import ChatSession

        config = AgentConfig()
        session = ChatSession(config=config, workspace="/tmp", model="test:latest")
        app = NexusApp(session=session)
        tools = app._build_tools_text()
        # Session should have tools registered
        assert "tool" in tools.lower() or "Tool" in tools
