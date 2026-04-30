"""Design tokens — single source of truth for colours, typography, spacing, animations.

All Nexus surfaces (CLI, TUI, Web, IDE) consume these tokens.
CLI maps to ANSI codes; TUI/Web map to CSS variables.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any


# ---------------------------------------------------------------------------
# Colour themes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Theme:
    """A named colour palette."""
    name: str
    primary: str      # Accent / links / highlights
    user: str         # User messages
    tool: str         # Tool call indicators
    danger: str       # Errors / warnings
    muted: str        # Secondary text
    bg: str           # Background
    surface: str      # Cards / panels
    border: str       # Dividers


DARK_THEME = Theme(
    name="dark",
    primary="#00D4FF",
    user="#00FF88",
    tool="#FFB800",
    danger="#FF3366",
    muted="#888888",
    bg="#0A0E14",
    surface="#141A24",
    border="#2A3342",
)

LIGHT_THEME = Theme(
    name="light",
    primary="#007ACC",
    user="#00875A",
    tool="#D48C00",
    danger="#D42E5B",
    muted="#6B6B6B",
    bg="#F5F7FA",
    surface="#FFFFFF",
    border="#D0D7DE",
)

ALL_THEMES: Dict[str, Theme] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
}


# ---------------------------------------------------------------------------
# ANSI mapping for CLI (maps theme roles to ANSI codes)
# ---------------------------------------------------------------------------

# Standard 256-colour ANSI codes that best match our palette
ANSI_MAP: Dict[str, Dict[str, str]] = {
    "dark": {
        "primary": "\033[38;5;45m",     # Bright cyan
        "user": "\033[38;5;46m",        # Bright green
        "tool": "\033[38;5;220m",       # Yellow
        "danger": "\033[38;5;197m",     # Bright red
        "muted": "\033[38;5;244m",      # Gray
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "underline": "\033[4m",
        "bg_dark": "\033[48;5;232m",    # Near black
        "bg_surface": "\033[48;5;234m", # Dark surface
    },
    "light": {
        "primary": "\033[38;5;32m",     # Blue
        "user": "\033[38;5;35m",        # Green
        "tool": "\033[38;5;172m",       # Dark yellow
        "danger": "\033[38;5;161m",     # Dark red
        "muted": "\033[38;5;242m",      # Medium gray
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "underline": "\033[4m",
        "bg_dark": "\033[48;5;254m",    # Light gray bg
        "bg_surface": "\033[48;5;255m", # White
    },
}


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

FONTS = {
    "mono": "JetBrains Mono, Fira Code, 'Cascadia Code', monospace",
    "sans": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "sizes": {
        "xs": "11px",
        "sm": "12px",
        "base": "14px",
        "lg": "16px",
        "xl": "18px",
        "2xl": "24px",
        "3xl": "32px",
    },
    "line_height": {
        "tight": "1.25",
        "normal": "1.5",
        "relaxed": "1.75",
    },
}


# ---------------------------------------------------------------------------
# Spacing scale (pixels)
# ---------------------------------------------------------------------------

SPACING = {
    "1": 4,
    "2": 8,
    "3": 12,
    "4": 16,
    "5": 24,
    "6": 32,
    "7": 48,
    "8": 64,
}


# ---------------------------------------------------------------------------
# Animation durations (milliseconds)
# ---------------------------------------------------------------------------

ANIMATION = {
    "instant": 0,
    "fast": 150,
    "medium": 300,
    "slow": 800,
    "pulse": 1200,
}

EASING = {
    "linear": "linear",
    "ease_out": "cubic-bezier(0.22, 1, 0.36, 1)",
    "spring": "cubic-bezier(0.34, 1.56, 0.64, 1)",
    "technical": "linear",
}


# ---------------------------------------------------------------------------
# Border radius
# ---------------------------------------------------------------------------

RADIUS = {
    "sm": "4px",
    "md": "8px",
    "lg": "12px",
    "full": "9999px",
}


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def get_ansi_style(role: str, theme: str = "dark") -> str:
    """Get the ANSI escape code for a role and theme.

    Args:
        role: 'primary', 'user', 'tool', 'danger', 'muted', 'reset',
              'bold', 'dim', 'underline', 'bg_dark', 'bg_surface'.
        theme: 'dark' or 'light'.

    Returns:
        ANSI escape code string.
    """
    theme_map = ANSI_MAP.get(theme, ANSI_MAP["dark"])
    return theme_map.get(role, theme_map.get("reset", ""))


def get_theme(name: str = "dark") -> Theme:
    """Get a theme by name."""
    return ALL_THEMES.get(name, DARK_THEME)


def get_css_variables(theme: str = "dark") -> str:
    """Generate CSS custom properties string for a theme.

    Returns a string like:
    --nexus-primary: #00D4FF;
    --nexus-user: #00FF88;
    ...
    """
    t = get_theme(theme)
    lines = [
        f"  --nexus-primary: {t.primary};",
        f"  --nexus-user: {t.user};",
        f"  --nexus-tool: {t.tool};",
        f"  --nexus-danger: {t.danger};",
        f"  --nexus-muted: {t.muted};",
        f"  --nexus-bg: {t.bg};",
        f"  --nexus-surface: {t.surface};",
        f"  --nexus-border: {t.border};",
    ]
    return "\n".join(lines)


def get_token(key: str, section: str = "spacing") -> Any:
    """Get a design token by key and section.

    Args:
        key: Token key (e.g., "4", "md", "fast").
        section: 'spacing', 'animation', 'radius', or 'font_sizes'.

    Returns:
        Token value.
    """
    section_map = {
        "spacing": SPACING,
        "animation": ANIMATION,
        "radius": RADIUS,
        "font_sizes": FONTS["sizes"],
        "line_height": FONTS["line_height"],
        "easing": EASING,
    }
    tokens = section_map.get(section, {})
    return tokens.get(key, "")


def print_theme_sample(theme_name: str = "dark") -> str:
    """Print a visual sample of a theme using ANSI codes."""
    t = get_theme(theme_name)
    a = ANSI_MAP[theme_name]
    reset = a["reset"]
    bold = a["bold"]
    dim = a["dim"]

    lines = [
        f"{bold}{a['primary']}Nexus Theme: {t.name}{reset}",
        f"{a['primary']}■■■■■■ Primary: {t.primary}{reset}",
        f"{a['user']}■■■■■■ User: {t.user}{reset}",
        f"{a['tool']}■■■■■■ Tool: {t.tool}{reset}",
        f"{a['danger']}■■■■■■ Danger: {t.danger}{reset}",
        f"{a['muted']}■■■■■■ Muted: {t.muted}{reset}",
        f"{dim}{t.bg} Background | {t.surface} Surface | {t.border} Border{reset}",
    ]
    return "\n".join(lines)
