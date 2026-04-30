"""Tests for Tool Fallback Chains."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexus.tools.fallback import (
    FallbackAttempt,
    FallbackManager,
    FallbackResult,
    FailureType,
    ToolFallbackChain,
    classify_failure,
)


class TestClassifyFailure:
    def test_transient_timeout(self):
        assert classify_failure("Connection timeout after 30s") == FailureType.TRANSIENT

    def test_transient_rate_limit(self):
        assert classify_failure("Rate limit exceeded") == FailureType.TRANSIENT

    def test_permission_denied(self):
        assert classify_failure("Permission denied: /etc/passwd") == FailureType.PERMISSION

    def test_not_found(self):
        assert classify_failure("File not found: missing.py") == FailureType.NOT_FOUND

    def test_validation_error(self):
        assert classify_failure("Invalid JSON format") == FailureType.VALIDATION

    def test_fatal(self):
        assert classify_failure("Unexpected internal error") == FailureType.FATAL


class TestToolFallbackChain:
    @pytest.fixture
    def chain(self):
        return ToolFallbackChain("file_write")

    @pytest.fixture
    def tools(self):
        mock_tool = AsyncMock()
        mock_tool.name = "shell"
        mock_tool.execute = AsyncMock(return_value="success via shell")
        return {"shell": mock_tool}

    def test_add_fallback(self, chain):
        chain.add_fallback("shell")
        assert len(chain._fallbacks) == 1

    def test_add_fallback_with_transform(self, chain):
        transform = lambda x: {"cmd": x["content"]}  # noqa: E731
        chain.add_fallback("shell", transform)
        name, fn = chain._fallbacks[0]
        assert name == "shell"
        assert fn({"content": "hello"}) == {"cmd": "hello"}

    @pytest.mark.asyncio
    async def test_primary_succeeds(self, chain, tools):
        mock_tool = AsyncMock()
        mock_tool.name = "file_write"
        mock_tool.execute = AsyncMock(return_value="Written 100 chars")

        result = await chain.execute(mock_tool, {"path": "test.txt", "content": "hello"}, tools)
        assert result.success
        assert result.result == "Written 100 chars"
        assert len(result.attempts) == 1

    @pytest.mark.asyncio
    async def test_primary_fails_transient_retries(self, chain, tools):
        mock_tool = AsyncMock()
        mock_tool.name = "file_write"
        # Fail twice, succeed on third try
        mock_tool.execute = AsyncMock(
            side_effect=["Error: Connection timeout", "Error: Connection timeout", "Written 100 chars"]
        )
        chain.set_retry_policy(count=3, delay=0.01)

        result = await chain.execute(mock_tool, {"path": "test.txt", "content": "hello"}, tools)
        assert result.success
        assert result.result == "Written 100 chars"

    @pytest.mark.asyncio
    async def test_primary_falls_back(self, chain, tools):
        mock_tool = AsyncMock()
        mock_tool.name = "file_write"
        mock_tool.execute = AsyncMock(return_value="Error: Permission denied")

        chain.add_fallback("shell")
        result = await chain.execute(mock_tool, {"path": "test.txt", "content": "hello"}, tools)
        # Should fall back to shell
        assert len(result.attempts) >= 1
        # Shell should have been called
        tools["shell"].execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_fallbacks_fail(self, chain):
        mock_tool = AsyncMock()
        mock_tool.name = "file_write"
        mock_tool.execute = AsyncMock(return_value="Error: Permission denied")

        chain.add_fallback("shell")
        result = await chain.execute(mock_tool, {"path": "test.txt", "content": "hello"}, {})
        assert not result.success
        assert len(result.attempts) >= 1  # At least the primary attempt


class TestFallbackManager:
    def test_default_chains(self):
        manager = FallbackManager()
        assert manager.get_chain("file_write") is not None
        assert manager.get_chain("file_read") is not None
        assert manager.get_chain("shell") is not None
        assert manager.get_chain("search") is not None

    def test_get_stats(self):
        manager = FallbackManager()
        stats = manager.get_stats()
        assert stats["chain_count"] >= 4
        assert "file_write" in stats["registered_chains"]

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        manager = FallbackManager()
        result = await manager.execute_with_fallback(
            "nonexistent_tool", {"arg": "val"}, {}
        )
        assert not result.success
        assert result.failure_type == FailureType.NOT_FOUND

    @pytest.mark.asyncio
    async def test_execute_no_chain(self):
        manager = FallbackManager()
        mock_tool = AsyncMock()
        mock_tool.name = "custom"
        mock_tool.execute = AsyncMock(return_value="custom result")

        result = await manager.execute_with_fallback(
            "custom", {"arg": "val"}, {"custom": mock_tool}
        )
        assert result.success
        assert result.result == "custom result"

    def test_add_custom_chain(self):
        manager = FallbackManager()
        chain = ToolFallbackChain("custom_tool")
        manager.add_chain("custom_tool", chain)
        assert manager.get_chain("custom_tool") is chain
