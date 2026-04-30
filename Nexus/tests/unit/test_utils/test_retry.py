"""Unit tests for retry utilities."""
import pytest
import asyncio
import time
from unittest.mock import Mock, patch

from nexus.utils.retry_utils import (
    retry_on_exception,
    async_retry_on_exception,
    CircuitBreaker,
    async_with_timeout,
)


class TestRetryOnException:
    """Test retry decorator."""

    def test_succeeds_on_first_try(self):
        """Test function succeeds without retry."""
        call_count = 0
        
        @retry_on_exception(max_attempts=3)
        def succeed_once():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = succeed_once()
        assert result == "success"
        assert call_count == 1

    def test_retries_on_failure(self):
        """Test function retries on failure."""
        call_count = 0
        
        @retry_on_exception(max_attempts=3, min_wait=0.01, max_wait=0.05)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = fail_twice()
        assert result == "success"
        assert call_count == 3

    def test_raises_after_max_attempts(self):
        """Test raises after max attempts."""
        call_count = 0
        
        @retry_on_exception(max_attempts=2, min_wait=0.01, max_wait=0.02)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")
        
        with pytest.raises(ConnectionError):
            always_fail()
        
        assert call_count == 2


class TestCircuitBreaker:
    """Test circuit breaker."""

    def test_closed_state_allows_calls(self):
        """Test circuit allows calls in closed state."""
        cb = CircuitBreaker(fail_max=3)
        
        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == "closed"

    def test_opens_after_max_failures(self):
        """Test circuit opens after max failures."""
        cb = CircuitBreaker(fail_max=2, reset_timeout=60)
        
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        assert cb.state == "open"
        
        with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
            cb.call(lambda: "should not run")

    def test_half_open_after_timeout(self):
        """Test circuit enters half-open after timeout."""
        cb = CircuitBreaker(fail_max=1, reset_timeout=0.01)
        
        with pytest.raises(Exception):
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        assert cb.state == "open"
        
        time.sleep(0.02)
        result = cb.call(lambda: "success")
        
        assert result == "success"
        assert cb.state == "closed"

    def test_resets_on_success_in_half_open(self):
        """Test circuit resets after success in half-open."""
        cb = CircuitBreaker(fail_max=1, reset_timeout=0.01)
        
        with pytest.raises(Exception):
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        time.sleep(0.02)
        cb.call(lambda: "success")
        
        assert cb.failure_count == 0
        assert cb.state == "closed"

    def test_excluded_exceptions_not_counted(self):
        """Test excluded exceptions don't count as failures."""
        cb = CircuitBreaker(fail_max=1, excluded_exceptions=(ValueError,))
        
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("excluded")))
        
        assert cb.state == "closed"


class TestAsyncWithTimeout:
    """Test async timeout utility."""

    @pytest.mark.asyncio
    async def test_completes_before_timeout(self):
        """Test completes before timeout."""
        async def slow_task():
            await asyncio.sleep(0.01)
            return "done"
        
        result = await async_with_timeout(slow_task(), timeout_seconds=1)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self):
        """Test raises on timeout."""
        async def long_task():
            await asyncio.sleep(10)
            return "done"
        
        with pytest.raises(asyncio.TimeoutError):
            await async_with_timeout(long_task(), timeout_seconds=0.01)