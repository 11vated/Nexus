"""Rate limiting and resource quota utilities."""
import time
import threading
from collections import deque
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging


logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_calls: int = 30
    window_seconds: float = 60.0
    block_duration: float = 0.0


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, max_calls: int = 30, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: deque = deque()
        self._lock = threading.Lock()
    
    def _cleanup_old_calls(self):
        """Remove calls outside the window."""
        now = time.time()
        cutoff = now - self.window_seconds
        
        while self.calls and self.calls[0] < cutoff:
            self.calls.popleft()
    
    def can_call(self) -> bool:
        """Check if a call can be made."""
        with self._lock:
            self._cleanup_old_calls()
            return len(self.calls) < self.max_calls
    
    def record_call(self) -> bool:
        """Record a call and return success."""
        with self._lock:
            self._cleanup_old_calls()
            
            if len(self.calls) >= self.max_calls:
                return False
            
            self.calls.append(time.time())
            return True
    
    def time_until_next_available(self) -> float:
        """Get seconds until next call is allowed."""
        with self._lock:
            self._cleanup_old_calls()
            
            if len(self.calls) < self.max_calls:
                return 0.0
            
            oldest = self.calls[0]
            return (oldest + self.window_seconds) - time.time()
    
    def reset(self):
        """Reset the rate limiter."""
        with self._lock:
            self.calls.clear()


class SlidingWindowRateLimiter:
    """Sliding window rate limiter with finer granularity."""
    
    def __init__(self, max_calls: int = 30, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: Dict[str, deque] = {}
        self._lock = threading.Lock()
    
    def _get_user_calls(self, user_id: str) -> deque:
        """Get or create user's call history."""
        if user_id not in self.calls:
            self.calls[user_id] = deque()
        return self.calls[user_id]
    
    def can_call(self, user_id: str = "default") -> bool:
        """Check if user can make a call."""
        with self._lock:
            user_calls = self._get_user_calls(user_id)
            self._cleanup_user_calls(user_calls)
            return len(user_calls) < self.max_calls
    
    def _cleanup_user_calls(self, calls: deque):
        """Remove old calls from user's history."""
        now = time.time()
        cutoff = now - self.window_seconds
        
        while calls and calls[0] < cutoff:
            calls.popleft()
    
    def record_call(self, user_id: str = "default") -> bool:
        """Record a call for user."""
        with self._lock:
            user_calls = self._get_user_calls(user_id)
            self._cleanup_user_calls(user_calls)
            
            if len(user_calls) >= self.max_calls:
                logger.warning(f"Rate limit exceeded for user: {user_id}")
                return False
            
            user_calls.append(time.time())
            return True
    
    def get_remaining_calls(self, user_id: str = "default") -> int:
        """Get remaining calls for user."""
        with self._lock:
            user_calls = self._get_user_calls(user_id)
            self._cleanup_user_calls(user_calls)
            return max(0, self.max_calls - len(user_calls))
    
    def reset(self, user_id: Optional[str] = None):
        """Reset rate limits."""
        with self._lock:
            if user_id:
                self.calls.pop(user_id, None)
            else:
                self.calls.clear()


class TokenBucket:
    """Token bucket for rate limiting with bursts."""
    
    def __init__(self, capacity: int = 10, refill_rate: float = 1.0):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def _refill(self):
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill
        
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens."""
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """Get wait time until tokens are available."""
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                return 0.0
            
            needed = tokens - self.tokens
            return needed / self.refill_rate


class ResourceQuota:
    """Track and enforce resource quotas."""
    
    def __init__(self, max_memory_mb: int = 4096, max_cpu_percent: int = 80):
        self.max_memory_mb = max_memory_mb
        self.max_cpu_percent = max_cpu_percent
        self.allocations: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def allocate(self, resource_id: str, memory_mb: int, cpu_percent: int) -> bool:
        """Allocate resources to a resource ID."""
        with self._lock:
            current = self._get_current_usage()
            
            new_memory = current["memory"] + memory_mb
            new_cpu = current["cpu"] + cpu_percent
            
            if new_memory > self.max_memory_mb:
                logger.warning(f"Memory quota exceeded: {new_memory}/{self.max_memory_mb}MB")
                return False
            
            if new_cpu > self.max_cpu_percent:
                logger.warning(f"CPU quota exceeded: {new_cpu}/{self.max_cpu_percent}%")
                return False
            
            self.allocations[resource_id] = {
                "memory_mb": memory_mb,
                "cpu_percent": cpu_percent,
                "allocated_at": time.time()
            }
            return True
    
    def release(self, resource_id: str):
        """Release resources for a resource ID."""
        with self._lock:
            self.allocations.pop(resource_id, None)
    
    def _get_current_usage(self) -> Dict[str, int]:
        """Get current resource usage."""
        total_memory = sum(a["memory_mb"] for a in self.allocations.values())
        total_cpu = sum(a["cpu_percent"] for a in self.allocations.values())
        return {"memory": total_memory, "cpu": total_cpu}
    
    def get_usage(self) -> Dict[str, int]:
        """Get current resource usage."""
        with self._lock:
            return self._get_current_usage()


# Global rate limiter for tool calls
default_rate_limiter = RateLimiter(max_calls=30, window_seconds=60)