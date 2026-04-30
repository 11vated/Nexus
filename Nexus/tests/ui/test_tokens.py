"""Tests for design tokens and theme system."""
import pytest

from nexus.ui.tokens import (
    DARK_THEME,
    LIGHT_THEME,
    ALL_THEMES,
    ANSI_MAP,
    get_ansi_style,
    get_theme,
    get_css_variables,
    get_token,
    print_theme_sample,
    SPACING,
    ANIMATION,
    RADIUS,
    FONTS,
)


class TestThemes:
    def test_dark_theme_exists(self):
        assert DARK_THEME.name == "dark"
        assert DARK_THEME.primary == "#00D4FF"
        assert DARK_THEME.user == "#00FF88"
        assert DARK_THEME.tool == "#FFB800"
        assert DARK_THEME.danger == "#FF3366"
        assert DARK_THEME.muted == "#888888"
        assert DARK_THEME.bg == "#0A0E14"
        assert DARK_THEME.surface == "#141A24"
        assert DARK_THEME.border == "#2A3342"

    def test_light_theme_exists(self):
        assert LIGHT_THEME.name == "light"
        assert LIGHT_THEME.primary == "#007ACC"
        assert LIGHT_THEME.user == "#00875A"
        assert LIGHT_THEME.tool == "#D48C00"
        assert LIGHT_THEME.danger == "#D42E5B"
        assert LIGHT_THEME.muted == "#6B6B6B"
        assert LIGHT_THEME.bg == "#F5F7FA"
        assert LIGHT_THEME.surface == "#FFFFFF"
        assert LIGHT_THEME.border == "#D0D7DE"

    def test_all_themes_registered(self):
        assert "dark" in ALL_THEMES
        assert "light" in ALL_THEMES
        assert len(ALL_THEMES) == 2

    def test_theme_immutable(self):
        """Themes are frozen dataclasses."""
        with pytest.raises(Exception):  # FrozenInstanceError
            DARK_THEME.primary = "#FF0000"


class TestAnsiStyles:
    def test_ansi_map_dark(self):
        assert "dark" in ANSI_MAP
        assert "primary" in ANSI_MAP["dark"]
        assert "reset" in ANSI_MAP["dark"]

    def test_ansi_map_light(self):
        assert "light" in ANSI_MAP

    def test_get_ansi_style_primary_dark(self):
        code = get_ansi_style("primary", "dark")
        assert "\033[" in code

    def test_get_ansi_style_user_dark(self):
        code = get_ansi_style("user", "dark")
        assert "\033[" in code

    def test_get_ansi_style_danger(self):
        code = get_ansi_style("danger", "dark")
        assert "\033[" in code

    def test_get_ansi_style_tool(self):
        code = get_ansi_style("tool", "dark")
        assert "\033[" in code

    def test_get_ansi_style_muted(self):
        code = get_ansi_style("muted", "dark")
        assert "\033[" in code

    def test_get_ansi_style_reset(self):
        code = get_ansi_style("reset", "dark")
        assert "\033[" in code

    def test_get_ansi_style_unknown(self):
        code = get_ansi_style("nonexistent", "dark")
        # Should return reset code for unknown roles
        assert code == ANSI_MAP["dark"]["reset"]

    def test_get_ansi_style_light_theme(self):
        code = get_ansi_style("primary", "light")
        assert "\033[" in code
        # Light theme uses different ANSI codes
        assert code != get_ansi_style("primary", "dark")

    def test_ansi_roundtrip(self):
        """ANSI codes should be valid escape sequences."""
        for role in ["primary", "user", "tool", "danger", "muted", "reset"]:
            dark_code = get_ansi_style(role, "dark")
            light_code = get_ansi_style(role, "light")
            assert dark_code.startswith("\033[")
            assert light_code.startswith("\033[")


class TestThemeFunctions:
    def test_get_theme_dark(self):
        theme = get_theme("dark")
        assert theme == DARK_THEME

    def test_get_theme_light(self):
        theme = get_theme("light")
        assert theme == LIGHT_THEME

    def test_get_theme_default(self):
        theme = get_theme()
        assert theme == DARK_THEME

    def test_get_theme_unknown(self):
        theme = get_theme("nonexistent")
        assert theme == DARK_THEME  # Falls back to dark

    def test_get_css_variables_dark(self):
        css = get_css_variables("dark")
        assert "--nexus-primary: #00D4FF" in css
        assert "--nexus-user: #00FF88" in css
        assert "--nexus-danger: #FF3366" in css

    def test_get_css_variables_light(self):
        css = get_css_variables("light")
        assert "--nexus-primary: #007ACC" in css
        assert "--nexus-user: #00875A" in css
        assert "--nexus-danger: #D42E5B" in css

    def test_print_theme_sample(self):
        sample = print_theme_sample("dark")
        assert "Nexus Theme: dark" in sample
        assert "\033[" in sample  # Contains ANSI codes

    def test_print_theme_sample_light(self):
        sample = print_theme_sample("light")
        assert "Nexus Theme: light" in sample


class TestTokens:
    def test_spacing_scale(self):
        assert SPACING["1"] == 4
        assert SPACING["2"] == 8
        assert SPACING["4"] == 16
        assert SPACING["8"] == 64

    def test_animation_durations(self):
        assert ANIMATION["fast"] == 150
        assert ANIMATION["medium"] == 300
        assert ANIMATION["slow"] == 800
        assert ANIMATION["instant"] == 0

    def test_radius_values(self):
        assert RADIUS["sm"] == "4px"
        assert RADIUS["md"] == "8px"
        assert RADIUS["lg"] == "12px"
        assert RADIUS["full"] == "9999px"

    def test_font_families(self):
        assert "JetBrains Mono" in FONTS["mono"]
        assert "Inter" in FONTS["sans"]

    def test_font_sizes(self):
        assert FONTS["sizes"]["base"] == "14px"
        assert FONTS["sizes"]["xl"] == "18px"

    def test_get_token_spacing(self):
        assert get_token("4", "spacing") == 16

    def test_get_token_animation(self):
        assert get_token("fast", "animation") == 150

    def test_get_token_radius(self):
        assert get_token("md", "radius") == "8px"

    def test_get_token_font_sizes(self):
        assert get_token("base", "font_sizes") == "14px"

    def test_get_token_unknown_section(self):
        assert get_token("x", "nonexistent") == ""

    def test_get_token_unknown_key(self):
        assert get_token("nonexistent", "spacing") == ""


class TestThemeConsistency:
    def test_all_themes_have_same_keys(self):
        """Both themes should have identical attribute sets."""
        dark_keys = set(DARK_THEME.__dataclass_fields__.keys())
        light_keys = set(LIGHT_THEME.__dataclass_fields__.keys())
        assert dark_keys == light_keys

    def test_ansi_map_has_all_roles(self):
        """ANSI maps should have the same role keys."""
        dark_roles = set(ANSI_MAP["dark"].keys())
        light_roles = set(ANSI_MAP["light"].keys())
        assert dark_roles == light_roles

    def test_theme_hex_format(self):
        """All hex colours should be valid #RRGGBB format."""
        import re
        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for theme in ALL_THEMES.values():
            for attr in ["primary", "user", "tool", "danger", "muted", "bg", "surface", "border"]:
                value = getattr(theme, attr)
                assert hex_pattern.match(value), f"{theme.name}.{attr} = {value} is not valid hex"
