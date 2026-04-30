"""Unit tests for config module."""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from nexus.config.settings import NexusConfig


class TestNexusConfig:
    """Test Nexus configuration."""

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            config = NexusConfig()
            
            assert config.default_model == "qwen2.5-coder:14b"
            assert config.ollama_url == "http://localhost:11434"
            assert config.model_timeout_seconds == 120
            assert config.log_level == "INFO"
            assert config.max_concurrent_tools == 4
            assert config.enable_telemetry is False

    def test_env_override(self):
        """Test environment variables override defaults."""
        with patch.dict(os.environ, {
            "DEFAULT_MODEL": "deepseek-r1:7b",
            "OLLAMA_URL": "http://custom:11434",
            "LOG_LEVEL": "DEBUG"
        }, clear=False):
            config = NexusConfig()
            
            assert config.default_model == "deepseek-r1:7b"
            assert config.ollama_url == "http://custom:11434"
            assert config.log_level == "DEBUG"

    def test_env_file_loading(self, tmp_path):
        """Test loading from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
DEFAULT_MODEL=codellama
OLLAMA_URL=http://localhost:11435
LOG_LEVEL=WARNING
""")
        
        with patch.dict(os.environ, {"NEXUS_CONFIG": str(env_file)}, clear=False):
            config = NexusConfig(_env_file=str(env_file))
            assert config.default_model == "codellama"
            assert config.ollama_url == "http://localhost:11435"

    def test_workspace_path_conversion(self):
        """Test workspace path is converted to Path object."""
        with patch.dict(os.environ, {
            "WORKSPACE_ROOT": "/test/workspace"
        }, clear=True):
            config = NexusConfig()
            assert isinstance(config.workspace_root, Path)
            assert str(config.workspace_root) == "/test/workspace"

    def test_find_tool_not_found(self):
        """Test find_tool returns None when tool not found."""
        config = NexusConfig()
        result = config.find_tool("nonexistent_tool_xyz")
        assert result is None

    def test_find_tool_in_path(self):
        """Test find_tool searches PATH."""
        with patch.dict(os.environ, {"PATH": os.environ.get("PATH", "")}, clear=False):
            config = NexusConfig()
            # Python should be available in PATH
            result = config.find_tool("python")
            assert result is not None
            assert "python" in str(result).lower()

    def test_log_level_validation(self):
        """Test invalid log level raises error."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}, clear=False):
            with pytest.raises(ValueError):
                NexusConfig()

    def test_type_validation(self):
        """Test type validation for settings."""
        with patch.dict(os.environ, {
            "MODEL_TIMEOUT_SECONDS": "not_a_number"
        }, clear=False):
            with pytest.raises(ValueError):
                NexusConfig()


class TestNexusConfigPaths:
    """Test path configuration."""

    def test_default_workspace_is_cwd(self):
        """Test default workspace is cwd/workspace."""
        with patch.dict(os.environ, {}, clear=True):
            config = NexusConfig()
            expected = Path.cwd() / "workspace"
            assert config.workspace_root == expected

    def test_custom_workspace(self):
        """Test custom workspace path."""
        with patch.dict(os.environ, {
            "WORKSPACE_ROOT": "/custom/workspace"
        }, clear=True):
            config = NexusConfig()
            assert config.workspace_root == Path("/custom/workspace")