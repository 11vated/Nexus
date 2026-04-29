"""Terminal-aware dynamic UI layout."""
import os
import signal
import sys
from shutil import get_terminal_size
from typing import Optional, Callable
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
import asyncio


class TerminalAwareUI:
    """UI that adapts to terminal size."""
    
    def __init__(self):
        self.console = Console()
        self._signal_handlers = []
        self._setup_resize_handler()
    
    def _setup_resize_handler(self):
        """Set up SIGWINCH handler for resize events."""
        if sys.platform != "win32":
            def handle_resize(signum, frame):
                self._terminal_width, self._terminal_height = get_terminal_size()
                self.on_resize()
            
            signal.signal(signal.SIGWINCH, handle_resize)
        
        # Also handle SIGWINCH on Windows
        if sys.platform == "win32":
            try:
                import msvcrt
                def check_resize():
                    while msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b'\x00':  # Special keys
                            key = msvcrt.getch()
                            if key == b'H':  # Up arrow (resize signal)
                                self._terminal_width, self._terminal_height = get_terminal_size()
                                self.on_resize()
                self._resize_checker = check_resize
            except ImportError:
                pass
    
    def on_resize(self):
        """Called when terminal is resized."""
        self.console.clear()
    
    @property
    def terminal_width(self) -> int:
        """Get current terminal width."""
        return get_terminal_size().columns
    
    @property
    def terminal_height(self) -> int:
        """Get current terminal height."""
        return get_terminal_size().lines
    
    def responsive_padding(self, padding: Optional[tuple] = None) -> tuple:
        """Calculate padding based on terminal width."""
        width = self.terminal_width
        
        if width < 80:
            return (0, 0)
        elif width < 120:
            return (0, 1)
        else:
            return (0, 2)
    
    def calculate_pane_sizes(self) -> dict:
        """Calculate dynamic pane sizes based on terminal."""
        w, h = self.terminal_width, self.terminal_height
        
        agent_width = max(20, int(w * 0.25))
        log_width = w - agent_width - 3  # Account for borders
        
        return {
            "agent_pane": agent_width,
            "log_pane": log_width,
            "header_height": 3,
            "footer_height": 3,
            "footer_width": w
        }
    
    def create_dynamic_layout(self, 
                            agents: dict,
                            logs: list,
                            models: dict) -> Layout:
        """Create a layout that adapts to terminal size."""
        sizes = self.calculate_pane_sizes()
        w = self.terminal_width
        h = self.terminal_height
        agent_width = sizes["agent_pane"]
        
        # Calculate log lines that fit
        min_log_lines = max(10, h - 20)
        
        # Create agent status table
        agent_table = Table(show_header=False, box=None, padding=self.responsive_padding())
        for name, status in agents.items():
            icon = "●" if status == "active" else "○"
            color = "yellow" if status == "active" else "bright_black"
            agent_table.add_row(Text(f"{icon} {name}", style=color))
        
        agent_panel = Panel(
            agent_table,
            title="Agents",
            border_style="blue",
            padding=self.responsive_padding()
        )
        
        # Create model status
        model_table = Table(show_header=False, box=None)
        for name, status in models.items():
            status_icon = "✓" if status == "ready" else "○"
            color = "green" if status == "ready" else "red"
            model_table.add_row(Text(f"{name}: {status_icon}", style=color))
        
        model_panel = Panel(
            model_table,
            title="Models",
            border_style="cyan",
            padding=self.responsive_padding()
        )
        
        # Create left sidebar
        sidebar = Layout([agent_panel, model_panel])
        
        # Create log panel (scrollable)
        log_lines = "\n".join(logs[-min_log_lines:]) if logs else "No logs yet"
        
        # Handle text wrapping
        log_text = Text.from_markup(
            log_lines,
            overflow="ellipsis",
            word_wrap=True
        )
        
        log_panel = Panel(
            log_text,
            title="Activity Log",
            border_style="green",
            padding=(0, 1),
            height=h - 10
        )
        
        # Create header
        header = Panel(
            f"[bold cyan]Nexus AI Workstation[/bold cyan] | {w}x{h}",
            style="on blue",
            height=3
        )
        
        # Create footer
        footer_text = f"[cyan]Commands:[/cyan] run | status | models | quit | [dim]Terminal: {w}x{h}[/]"
        footer = Panel(
            footer_text,
            style="on cyan",
            height=3
        )
        
        # Combine into main layout
        layout = Layout()
        layout.split_column(
            Layout(header, size=3),
            Layout(sidebar, log_panel),
            Layout(footer, size=3)
        )
        layout[""].split_row(
            Layout(sidebar, size=agent_width),
            Layout(log_panel)
        )
        
        return layout
    
    def render_with_live(self, 
                         state_fn: Callable,
                         update_interval: float = 0.5):
        """Render UI with live updates."""
        with Live(
            self.create_dynamic_layout(*state_fn()),
            refresh_per_second=int(1/update_interval),
            screen=True,
            transient=False
        ) as live:
            while True:
                try:
                    layout = self.create_dynamic_layout(*state_fn())
                    live.update(layout)
                    asyncio.sleep(update_interval)
                except KeyboardInterrupt:
                    break
    
    def truncate_text(self, text: str, max_width: int) -> str:
        """Truncate text to fit width."""
        if len(text) <= max_width:
            return text
        return text[:max_width-3] + "..."
    
    def wrap_text(self, text: str, width: int) -> list:
        """Wrap text to fit width."""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            if current_length + word_length + 1 <= width:
                current_line.append(word)
                current_length += word_length + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines
    
    def is_interactive(self) -> bool:
        """Check if running in interactive terminal."""
        return sys.stdin.isatty() and sys.stdout.isatty()
    
    def fallback_to_plain(self, logs: list):
        """Fallback to plain scrolling log for non-ANSI terminals."""
        if not self.is_interactive():
            for line in logs:
                print(line)
            return True
        return False


# Global instance
terminal_ui = TerminalAwareUI()