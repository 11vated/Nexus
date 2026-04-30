"""Tests for CLI utilities — startup animation, colorized output."""
import pytest
from unittest.mock import patch, MagicMock

from nexus.ui.cli_utils import (
    supports_color,
    is_windows_terminal,
    fmt_primary,
    fmt_user,
    fmt_tool,
    fmt_danger,
    fmt_muted,
    fmt_bold,
    fmt_dim,
    print_tool_call,
    print_success,
    print_error,
    play_startup_animation,
)


class TestColorFormatters:
    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    def test_fmt_primary(self, mock_supports):
        result = fmt_primary("hello")
        assert "\033[" in result
        assert "hello" in result

    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    def test_fmt_user(self, mock_supports):
        result = fmt_user("hello")
        assert "\033[" in result
        assert "hello" in result

    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    def test_fmt_tool(self, mock_supports):
        result = fmt_tool("hello")
        assert "\033[" in result

    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    def test_fmt_danger(self, mock_supports):
        result = fmt_danger("hello")
        assert "\033[" in result

    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    def test_fmt_muted(self, mock_supports):
        result = fmt_muted("hello")
        assert "\033[" in result

    @patch("nexus.ui.cli_utils.supports_color", return_value=False)
    def test_fmt_no_color(self, mock_supports):
        """When terminal doesn't support color, return plain text."""
        assert fmt_primary("hello") == "hello"
        assert fmt_user("hello") == "hello"
        assert fmt_tool("hello") == "hello"
        assert fmt_danger("hello") == "hello"
        assert fmt_muted("hello") == "hello"


class TestPlayStartupAnimation:
    @patch("nexus.ui.cli_utils.supports_color", return_value=False)
    @patch("sys.stdout")
    def test_animation_skipped_when_no_color(self, mock_stdout, mock_supports):
        play_startup_animation(version="0.6.0")
        # Should not write anything when color not supported
        mock_stdout.write.assert_not_called()

    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    @patch("sys.stdout")
    def test_animation_runs_with_color(self, mock_stdout, mock_supports):
        mock_stdout.fileno.return_value = 1
        mock_stdout.isatty.return_value = True
        play_startup_animation(version="0.6.0", quiet=False)
        # Should write something
        assert mock_stdout.write.called

    @patch("sys.stdout")
    def test_animation_skipped_when_quiet(self, mock_stdout):
        play_startup_animation(version="0.6.0", quiet=True)
        mock_stdout.write.assert_not_called()


class TestPrintHelpers:
    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    @patch("builtins.print")
    def test_print_tool_call(self, mock_print, mock_supports):
        print_tool_call("shell", "git status")
        mock_print.assert_called()

    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    @patch("builtins.print")
    def test_print_success(self, mock_print, mock_supports):
        print_success("Done", elapsed=2.3, files_changed=3)
        mock_print.assert_called()

    @patch("nexus.ui.cli_utils.supports_color", return_value=True)
    @patch("builtins.print")
    def test_print_error(self, mock_print, mock_supports):
        print_error("Failed", suggestion="Try again")
        mock_print.assert_called()
