"""Nexus TUI — interactive terminal interfaces.

Three modes:
  - run_textual_chat: Cognitive coding TUI with Textual (next-gen, recommended)
  - run_chat:         Rich-based collaborative chat TUI (classic)
  - NexusDashboard:   Agent progress dashboard (for autonomous runs)
"""

from nexus.tui.chat_ui import run_chat
from nexus.tui.dashboard import NexusDashboard

# Textual TUI is optional — only available when textual is installed
try:
    from nexus.tui.textual_ui import run_textual_chat, NexusApp
    __all__ = ["run_chat", "run_textual_chat", "NexusApp", "NexusDashboard"]
except ImportError:
    __all__ = ["run_chat", "NexusDashboard"]
