"""CLI utilities — startup animation, colorized output, theme integration.

All CLI visual polish lives here, powered by design tokens.
"""
from __future__ import annotations

import sys
import time

from nexus.ui.tokens import get_ansi_style, get_theme, print_theme_sample


# ---------------------------------------------------------------------------
# Terminal capability detection
# ---------------------------------------------------------------------------

def supports_color() -> bool:
    """Detect if the current terminal supports ANSI colours."""
    if not hasattr(sys.stdout, "fileno"):
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def is_windows_terminal() -> bool:
    """Detect if running in Windows terminal (needs special encoding)."""
    return sys.platform == "win32"


def enable_ansi_windows():
    """Enable ANSI support on Windows terminals."""
    if is_windows_terminal():
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return False


# ---------------------------------------------------------------------------
# Startup animation
# ---------------------------------------------------------------------------

def play_startup_animation(version: str = "0.6.0", quiet: bool = False) -> None:
    """Play the Nexus startup animation.

    Shows: "Nexus v0.6.0 ■■■■■■■■□□" filling over 800ms.
    If quiet=True, skips animation entirely.
    """
    if quiet or not supports_color():
        return

    enable_ansi_windows()

    primary = get_ansi_style("primary")
    muted = get_ansi_style("muted")
    reset = get_ansi_style("reset")
    bold = get_ansi_style("bold")

    bar_length = 10
    duration = 0.8  # seconds
    steps = 10
    step_duration = duration / steps

    sys.stdout.write("\n")

    for i in range(steps + 1):
        filled = i
        empty = bar_length - i
        bar = f"{filled * '■'}{empty * '□'}"

        line = f"\r  {bold}{primary}Nexus v{version}{reset} {bar}"

        sys.stdout.write(line)
        sys.stdout.flush()

        if i < steps:
            time.sleep(step_duration)

    # Fade out
    sys.stdout.write("\n\n")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Colorized message helpers
# ---------------------------------------------------------------------------

def fmt_primary(text: str) -> str:
    """Format text in primary (cyan) colour."""
    if not supports_color():
        return text
    return f"{get_ansi_style('primary')}{text}{get_ansi_style('reset')}"


def fmt_user(text: str) -> str:
    """Format text in user (green) colour."""
    if not supports_color():
        return text
    return f"{get_ansi_style('user')}{text}{get_ansi_style('reset')}"


def fmt_tool(text: str) -> str:
    """Format text in tool (yellow) colour."""
    if not supports_color():
        return text
    return f"{get_ansi_style('tool')}{text}{get_ansi_style('reset')}"


def fmt_danger(text: str) -> str:
    """Format text in danger (red) colour."""
    if not supports_color():
        return text
    return f"{get_ansi_style('danger')}{text}{get_ansi_style('reset')}"


def fmt_muted(text: str) -> str:
    """Format text in muted (gray) colour."""
    if not supports_color():
        return text
    return f"{get_ansi_style('muted')}{text}{get_ansi_style('reset')}"


def fmt_bold(text: str) -> str:
    """Format text in bold."""
    if not supports_color():
        return text
    return f"{get_ansi_style('bold')}{text}{get_ansi_style('reset')}"


def fmt_dim(text: str) -> str:
    """Format text in dim."""
    if not supports_color():
        return text
    return f"{get_ansi_style('dim')}{text}{get_ansi_style('reset')}"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def print_prompt() -> None:
    """Print the Nexus prompt symbol in primary colour."""
    if supports_color():
        print(f"{get_ansi_style('primary')}>{get_ansi_style('reset')} ", end="")
    else:
        print("> ", end="")
    sys.stdout.flush()


def print_thinking() -> None:
    """Print the 'thinking' indicator with animation."""
    if not supports_color():
        print("Nexus is thinking...")
        return

    import threading
    import itertools

    indicator = fmt_dim("Nexus") + " "
    dots = ["   ", ".  ", ".. ", "..."]
    cycle = itertools.cycle(dots)

    stop_event = threading.Event()

    def _animate():
        while not stop_event.is_set():
            sys.stdout.write(f"\r{indicator}{get_ansi_style('dim')}{next(cycle)}{get_ansi_style('reset')}")
            sys.stdout.flush()
            time.sleep(0.4)

    thread = threading.Thread(target=_animate, daemon=True)
    thread.start()
    return stop_event


def stop_thinking(stop_event: threading.Event | None) -> None:
    """Stop the thinking animation."""
    if stop_event:
        stop_event.set()
        time.sleep(0.1)
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Step display
# ---------------------------------------------------------------------------

def print_step(icon: str, text: str, colour: str = "primary") -> None:
    """Print a step line with icon and coloured text."""
    if supports_color():
        c = get_ansi_style(colour)
        r = get_ansi_style("reset")
        print(f"  {icon} {c}{text}{r}")
    else:
        print(f"  {icon} {text}")


def print_tool_call(tool_name: str, args: str = "") -> None:
    """Print a tool call in yellow."""
    line = f"  🔧 {tool_name}"
    if args:
        line += f": {args}"
    if supports_color():
        print(f"{get_ansi_style('tool')}{line}{get_ansi_style('reset')}")
    else:
        print(line)


def print_success(text: str, elapsed: float = 0, files_changed: int = 0) -> None:
    """Print a success line."""
    parts = [f"  ✓ {text}"]
    if elapsed > 0:
        parts.append(f"({elapsed:.1f}s)")
    if files_changed > 0:
        parts.append(f"{files_changed} file(s) changed")
    line = " ".join(parts)
    if supports_color():
        print(f"{get_ansi_style('user')}{line}{get_ansi_style('reset')}")
    else:
        print(line)


def print_error(text: str, suggestion: str | None = None) -> None:
    """Print an error line with optional suggestion."""
    if supports_color():
        print(f"{get_ansi_style('danger')}  ✗ {text}{get_ansi_style('reset')}")
        if suggestion:
            print(f"  {get_ansi_style('muted')}  Hint: {suggestion}{get_ansi_style('reset')}")
    else:
        print(f"  ✗ {text}")
        if suggestion:
            print(f"  Hint: {suggestion}")


# ---------------------------------------------------------------------------
# Import for threading.Event type hint
# ---------------------------------------------------------------------------

import threading
