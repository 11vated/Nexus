"""Retry utilities with exponential backoff and circuit breaker."""
import asyncio
import functools
import logging
import time
from typing import Callable, Type, Tuple, Optional, TypeVar

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryCallState,
)
from tenacity.before_sleep import before_sleep_log
from tenacity.after import after_log

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_on_exception(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 10,
    logger_instance: logging.Logger = None
):
    """Decorator for retrying with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger_instance or logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True
    )


def async_retry_on_exception(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_attempts: int = 3,
    min_wait: float = 1,
    max_wait: float = 10,
):
    """Async decorator for retrying with exponential backoff."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )


class CircuitBreaker:
    """Simple circuit breaker implementation."""
    
    def __init__(
        self,
        fail_max: int = 5,
        reset_timeout: float = 60,
        excluded_exceptions: Tuple[Type[Exception], ...] = ()
    ):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.excluded_exceptions = excluded_exceptions
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.reset_timeout:
                self.state = "half-open"
                logger.info("Circuit breaker entering half-open state")
            else:
                raise RuntimeError("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.reset()
            return result
        except self.excluded_exceptions:
            raise
        except Exception as e:
            self.record_failure()
            raise
    
    def record_failure(self):
        """Record a failure and possibly open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.fail_max:
            self.state = "open"
            logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
    
    def reset(self):
        """Reset the circuit breaker."""
        self.failure_count = 0
        self.state = "closed"
        logger.info("Circuit breaker CLOSED")


async def async_with_timeout(coro, timeout_seconds: float):
    """Run coroutine with timeout."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {timeout_seconds}s")
        raise