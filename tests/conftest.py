"""Pytest configuration and fixtures."""
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def mock_config():
    """Mock configuration."""
    from unittest.mock import Mock
    config = Mock()
    config.workspace_root = Path("/test/workspace")
    config.ollama_url = "http://localhost:11434"
    config.default_model = "qwen2.5-coder:14b"
    config.model_timeout_seconds = 120
    return config


@pytest.fixture
def sample_prompt():
    """Sample prompts for testing."""
    return "Write a hello world program in Python"


@pytest.fixture
def sample_code():
    """Sample code for testing."""
    return '''def hello():
    print("Hello, World!")

if __name__ == "__main__":
    hello()
'''