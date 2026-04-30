"""Unit tests for security.sanitizer module."""
import pytest
from pathlib import Path
import tempfile

from nexus.security.sanitizer import (
    validate_model_name,
    validate_command_args,
    safe_path_join,
    sanitize_filename,
    sanitize_prompt,
    safe_subprocess_args,
    ALLOWED_MODELS,
)


class TestValidateModelName:
    """Test model name validation."""

    def test_valid_model_name(self):
        """Test valid model names pass validation."""
        assert validate_model_name("qwen2.5-coder:14b") == "qwen2.5-coder:14b"
        assert validate_model_name("deepseek-r1:7b") == "deepseek-r1:7b"
        assert validate_model_name("codellama") == "codellama"

    def test_invalid_model_name_not_in_whitelist(self):
        """Test invalid model names fail validation."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_model_name("evil_model")

    def test_empty_model_name(self):
        """Test empty model name raises error."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            validate_model_name("")

    def test_whitespace_model_name(self):
        """Test whitespace-only model name raises error."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            validate_model_name("   ")

    def test_none_model_name(self):
        """Test None model name raises error."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            validate_model_name(None)  # type: ignore


class TestValidateCommandArgs:
    """Test command argument validation."""

    def test_valid_args(self):
        """Test valid arguments pass."""
        result = validate_command_args("aider", ["--model", "test-model"])
        assert result == ["--model", "test-model"]

    def test_unsafe_arg_value(self):
        """Test unsafe argument values fail."""
        with pytest.raises(ValueError, match="Unsafe argument"):
            validate_command_args("aider", ["--model", "test; rm -rf /"])

    def test_disallowed_argument(self):
        """Test disallowed arguments fail."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_command_args("aider", ["--dangerous-option"])

    def test_empty_args(self):
        """Test empty args pass."""
        result = validate_command_args("aider", [])
        assert result == []


class TestSafePathJoin:
    """Test safe path joining."""

    def test_valid_relative_path(self):
        """Test valid relative path."""
        base = Path("/home/user/workspace")
        result = safe_path_join(base, "src/main.py")
        assert result == Path("/home/user/workspace/src/main.py")

    def test_path_traversal_blocked(self):
        """Test path traversal is blocked."""
        base = Path("/home/user/workspace")
        with pytest.raises(ValueError, match="escapes workspace"):
            safe_path_join(base, "../../../etc/passwd")

    def test_empty_path_raises(self):
        """Test empty path raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            safe_path_join(Path("/base"), "")

    def test_tilde_expansion(self):
        """Test tilde is expanded to home."""
        base = Path("/home/user/workspace")
        result = safe_path_join(base, "~/file.txt")
        assert "~" not in str(result)


class TestSanitizeFilename:
    """Test filename sanitization."""

    def test_normal_filename(self):
        """Test normal filename passes through."""
        assert sanitize_filename("main.py") == "main.py"
        assert sanitize_filename("test-file_123.py") == "test-file_123.py"

    def test_path_traversal_removed(self):
        """Test path traversal chars removed."""
        assert sanitize_filename("../etc/passwd") == "etcpasswd"
        assert sanitize_filename("foo/../bar") == "foo..bar"

    def test_special_chars_removed(self):
        """Test special characters removed."""
        assert sanitize_filename("file<>:?.txt") == "file.txt"


class TestSanitizePrompt:
    """Test prompt sanitization."""

    def test_normal_prompt(self):
        """Test normal prompt passes through."""
        result = sanitize_prompt("Write a hello world program")
        assert result == "Write a hello world program"

    def test_prompt_truncation(self):
        """Test long prompts are truncated."""
        long_prompt = "a" * 20000
        result = sanitize_prompt(long_prompt, max_length=1000)
        assert len(result) <= 1100
        assert "[truncated]" in result

    def test_null_bytes_removed(self):
        """Test null bytes are removed."""
        result = sanitize_prompt("test\x00 prompt")
        assert "\x00" not in result

    def test_eval_pattern_sanitized(self):
        """Test dangerous patterns are sanitized."""
        result = sanitize_prompt("Execute eval('malicious')")
        assert "[SANITIZED]" in result


class TestSafeSubprocessArgs:
    """Test subprocess argument validation."""

    def test_valid_args(self):
        """Test valid args pass."""
        result = safe_subprocess_args(["echo", "hello"])
        assert result == ["echo", "hello"]

    def test_null_byte_raises(self):
        """Test null byte raises error."""
        with pytest.raises(ValueError, match="Invalid characters"):
            safe_subprocess_args(["cmd\x00", "arg"])