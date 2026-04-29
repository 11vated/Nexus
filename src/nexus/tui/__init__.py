"""Nexus TUI — interactive terminal interfaces.

Two modes:
  - NexusChatTUI:   Collaborative chat (the primary experience)
  - NexusDashboard: Agent progress dashboard (for autonomous runs)
"""

from nexus.tui.chat_ui import NexusChatTUI
from nexus.tui.dashboard import NexusDashboard

__all__ = ["NexusChatTUI", "NexusDashboard"]
