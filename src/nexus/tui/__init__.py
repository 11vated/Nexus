"""Nexus TUI — interactive terminal interfaces.

Two modes:
  - run_chat:       Collaborative chat TUI (the primary experience)
  - NexusDashboard: Agent progress dashboard (for autonomous runs)
"""

from nexus.tui.chat_ui import run_chat
from nexus.tui.dashboard import NexusDashboard

__all__ = ["run_chat", "NexusDashboard"]
