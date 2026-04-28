"""Additional security tests for edge cases."""
import pytest
import re
from pathlib import Path

from nexus.security.sanitizer import (
    validate_model_name,
    validate_command_args,
    safe_path_join,
    sanitize_filename,
    sanitize_prompt,
    ALLOWED_MODELS,
)


class TestPathTraversalEdgeCases:
    """Test path traversal edge cases."""

    def test_double_dots_with_intermediate_dirs(self):
        """Test path traversal with intermediate directories."""
        base = Path("/home/user/workspace")
        
        with pytest.raises(ValueError, match="escapes workspace"):
            safe_path_join(base, "src/../../../etc/passwd")

    def test_encoded_traversal(self):
        """Test URL-encoded traversal attempts."""
        base = Path("/home/user/workspace")
        
        # %2e%2e should be stripped
        result = safe_path_join(base, "src%2f%2e%2e%2f%2e%2e")
        assert ".." not in str(result)

    def test_symlink_outside_workspace(self):
        """Test symlink pointing outside workspace."""
        base = Path("/home/user/workspace")
        
        # Even if symlink resolves, we check against base
        with pytest.raises(ValueError, match="escapes workspace"):
            safe_path_join(base, "link_to_escape")

    def test_case_mixing_traversal(self):
        """Test case-mixing traversal attempts."""
        base = Path("/home/user/workspace")
        
        with pytest.raises(ValueError, match="escapes workspace"):
            safe_path_join(base, "SRC/../..")

    def test_trailing_dot_after_traversal(self):
        """Test trailing dot after traversal."""
        base = Path("/home/user/workspace")
        
        with pytest.raises(ValueError, match="escapes workspace"):
            safe_path_join(base, "../..")


class TestCommandInjectionEdgeCases:
    """Test command injection edge cases."""

    def test_newline_injection(self):
        """Test newline injection in command args."""
        with pytest.raises(ValueError, match="Unsafe argument"):
            validate_command_args("aider", ["--model", "test\nrm -rf /"])

    def test_semicolon_injection(self):
        """Test semicolon injection."""
        with pytest.raises(ValueError, match="Unsafe argument"):
            validate_command_args("aider", ["--model", "test; echo hacked"])

    def test_pipe_injection(self):
        """Test pipe injection."""
        with pytest.raises(ValueError, match="Unsafe argument"):
            validate_command_args("aider", ["--model", "test | cat /etc/passwd"])

    def test_backtick_injection(self):
        """Test backtick command substitution."""
        with pytest.raises(ValueError, match="Unsafe argument"):
            validate_command_args("aider", ["--model", "test`whoami`"])

    def test_dollar_paren_injection(self):
        """Test $(command) substitution."""
        with pytest.raises(ValueError, match="Unsafe argument"):
            validate_command_args("aider", ["--model", "$(whoami)"])

    def test_null_byte_injection(self):
        """Test null byte injection."""
        with pytest.raises(ValueError, match="Invalid characters"):
            validate_command_args("aider", ["--model", "test\x00"])


class TestModelNameEdgeCases:
    """Test model name validation edge cases."""

    def test_case_sensitivity(self):
        """Test model names are case-sensitive."""
        assert validate_model_name("qwen2.5-coder:14b") == "qwen2.5-coder:14b"
        
        with pytest.raises(ValueError):
            validate_model_name("QWEN2.5-CODER:14B")

    def test_whitespace_variations(self):
        """Test whitespace handling."""
        with pytest.raises(ValueError):
            validate_model_name("  qwen2.5-coder:14b")

    def test_special_chars_in_model(self):
        """Test special characters are not allowed."""
        with pytest.raises(ValueError):
            validate_model_name("model\nwith\nnewlines")

    def test_unicode_model_name(self):
        """Test unicode in model names is rejected."""
        with pytest.raises(ValueError):
            validate_model_name("model\u2022name")

    def test_all_allowed_models_work(self):
        """Test all models in ALLOWED_MODELS pass validation."""
        for model in ALLOWED_MODELS:
            result = validate_model_name(model)
            assert result == model


class TestPromptInjectionEdgeCases:
    """Test prompt injection edge cases."""

    def test_very_long_prompt(self):
        """Test very long prompt is truncated."""
        long_prompt = "x" * 100000
        result = sanitize_prompt(long_prompt, max_length=5000)
        
        assert len(result) < len(long_prompt)
        assert "[truncated]" in result

    def test_multiple_dangerous_patterns(self):
        """Test multiple dangerous patterns are sanitized."""
        prompt = "eval('test') and exec('test') and __import__('os')"
        result = sanitize_prompt(prompt)
        
        # Patterns should be replaced
        assert "eval" not in result.lower() or "[SANITIZED]" in result

    def test_carriage_return_handling(self):
        """Test carriage returns are handled."""
        result = sanitize_prompt("line1\r\nline2\r\nline3")
        
        # Should not cause issues
        assert len(result) > 0

    def test_bidirectional_override(self):
        """Test bidirectional unicode is sanitized."""
        # LRE/PDF and RLE characters
        dangerous = "Hello\u202A\u202CWorld"
        result = sanitize_prompt(dangerous)
        
        # Should be sanitized
        assert "\u202A" not in result or "[SANITIZED]" in result


class TestFilenameEdgeCases:
    """Test filename sanitization edge cases."""

    def test_empty_filename(self):
        """Test empty filename returns empty."""
        result = sanitize_filename("")
        assert result == ""

    def test_only_special_chars(self):
        """Test filename with only special chars."""
        result = sanitize_filename("<>:?|/*")
        assert len(result) > 0

    def test_long_filename(self):
        """Test very long filename is handled."""
        long_name = "a" * 1000 + ".txt"
        result = sanitize_filename(long_name)
        
        # Should not crash
        assert len(result) <= len(long_name)

    def test_nul_in_filename(self):
        """Test null in filename."""
        result = sanitize_filename("file\x00name.txt")
        assert "\x00" not in result


class TestAllowedModels:
    """Test ALLOWED_MODELS configuration."""

    def test_models_not_empty(self):
        """Test ALLOWED_MODELS is not empty."""
        assert len(ALLOWED_MODELS) > 0

    def test_models_are_strings(self):
        """Test all models are strings."""
        assert all(isinstance(m, str) for m in ALLOWED_MODELS)

    def test_models_contain_mainstream(self):
        """Test mainstream models are included."""
        assert "qwen2.5-coder:14b" in ALLOWED_MODELS
        assert "deepseek-r1:7b" in ALLOWED_MODELS
        assert "codellama" in ALLOWED_MODELS