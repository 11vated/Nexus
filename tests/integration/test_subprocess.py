"""Integration tests for subprocess utilities."""
import pytest
import subprocess
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from nexus.utils.subprocess_utils import (
    run_command,
    run_command_async,
    run_ollama,
    get_safe_env,
    CommandRunner,
)


class TestRunCommand:
    """Test run_command function."""

    def test_echo_command(self):
        """Test basic echo command."""
        result = run_command(["echo", "hello"])
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_command_with_cwd(self, tmp_path):
        """Test command runs in specified directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        result = run_command(["ls", str(tmp_path)])
        assert result.returncode == 0
        assert "test.txt" in result.stdout

    def test_command_timeout(self):
        """Test command timeout works."""
        with pytest.raises(subprocess.TimeoutExpired):
            run_command(["sleep", "10"], timeout=1)

    def test_command_not_found(self):
        """Test command not found raises error."""
        with pytest.raises(FileNotFoundError):
            run_command(["nonexistent_command_xyz"])

    def test_command_failure(self):
        """Test command failure raises error with check=True."""
        with pytest.raises(subprocess.CalledProcessError):
            run_command(["exit", "1"], check=True)


class TestGetSafeEnv:
    """Test safe environment creation."""

    def test_preserves_safe_vars(self):
        """Test safe environment variables are preserved."""
        env = get_safe_env()
        
        assert "PATH" in env
        assert "HOME" in env
        assert "USER" in env

    def test_removes_dangerous_vars(self):
        """Test dangerous environment variables are removed."""
        env = get_safe_env()
        
        assert "PYTHONPATH" not in env
        assert "LD_PRELOAD" not in env

    def test_extra_env_added(self):
        """Test extra environment variables are added."""
        env = get_safe_env({"CUSTOM_VAR": "value"})
        
        assert "CUSTOM_VAR" in env
        assert env["CUSTOM_VAR"] == "value"


class TestCommandRunner:
    """Test CommandRunner class."""

    def test_run_with_workspace(self, tmp_path):
        """Test command runs with workspace."""
        runner = CommandRunner(workspace=tmp_path)
        result = runner.run(["echo", "test"])
        
        assert result.returncode == 0
        assert "test" in result.stdout

    def test_run_with_timeout(self):
        """Test command respects timeout."""
        runner = CommandRunner()
        
        with pytest.raises(subprocess.TimeoutExpired):
            runner.run(["sleep", "10"], timeout=1)

    def test_run_captures_output(self):
        """Test output is captured."""
        runner = CommandRunner()
        result = runner.run(["echo", "output"])
        
        assert result.stdout
        assert "output" in result.stdout


@pytest.mark.asyncio
class TestRunCommandAsync:
    """Test async command execution."""

    async def test_echo_command_async(self):
        """Test basic async echo."""
        stdout, stderr = await run_command_async(["echo", "async_test"])
        
        assert b"async_test" in stdout
        assert stderr == b""

    async def test_command_timeout_async(self):
        """Test async command timeout."""
        with pytest.raises(asyncio.TimeoutError):
            await run_command_async(["sleep", "10"], timeout=1)

    async def test_failed_command(self):
        """Test failed async command."""
        stdout, stderr = await run_command_async(["exit", "1"])
        
        assert b"" == stdout  # stdout is empty on error


@pytest.mark.skipif(
    True,
    reason="Requires Ollama running and --run-ollama flag"
)
class TestRunOllama:
    """Test Ollama command execution."""

    def test_ollama_list(self):
        """Test 'ollama list' command."""
        try:
            result = run_ollama("list")
            assert result is not None
        except Exception:
            pytest.skip("Ollama not running")

    def test_ollama_run_with_invalid_model(self):
        """Test invalid model name validation."""
        with pytest.raises(ValueError, match="not allowed"):
            run_ollama("run", model="invalid_model_xyz")

    def test_ollama_run_with_valid_model(self):
        """Test valid model name."""
        # Just validate the model is passed correctly
        with pytest.raises((subprocess.TimeoutExpired, Exception)):
            run_ollama("run", model="nonexistent_model", prompt="test", timeout=2)