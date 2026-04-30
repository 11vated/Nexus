"""Edge case handling utilities for robustness."""
import asyncio
import logging
import os
import signal
import sys
from contextlib import contextmanager
from typing import Any, Callable, Optional, TypeVar
import functools


logger = logging.getLogger(__name__)

T = TypeVar('T')


class NexusError(Exception):
    """Base exception for Nexus."""
    pass


class ConfigurationError(NexusError):
    """Configuration related errors."""
    pass


class ToolNotFoundError(NexusError):
    """Tool not found error."""
    pass


class ModelNotAvailableError(NexusError):
    """Model not available error."""
    pass


class WorkspaceError(NexusError):
    """Workspace related errors."""
    pass


class TimeoutError(NexusError):
    """Timeout errors."""
    pass


def handle_sigint():
    """Handle Ctrl+C gracefully."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            stop_event = asyncio.Event()
            
            def signal_handler(sig, frame):
                logger.warning("Interrupt received, shutting down gracefully...")
                stop_event.set()
            
            old_handler = signal.signal(signal.SIGINT, signal_handler)
            
            try:
                return func(*args, **kwargs)
            finally:
                signal.signal(signal.SIGINT, old_handler)
        
        return wrapper
    return decorator


@contextmanager
def ignore_exceptions(*exceptions, logger=None):
    """Context manager to ignore specific exceptions."""
    try:
        yield
    except exceptions as e:
        if logger:
            logger.debug(f"Ignored exception: {e}")


@contextmanager
def exception_to_warning(logger, message: str = "Operation failed"):
    """Convert exceptions to warnings."""
    try:
        yield
    except Exception as e:
        logger.warning(f"{message}: {e}")


def retry_on_failure(func: Callable = None, max_attempts: int = 3, delay: float = 1.0):
    """Decorator to retry on failure."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying...")
                        import time
                        time.sleep(delay * (attempt + 1))
            raise last_exception
        return wrapper
    
    if func:
        return decorator(func)
    return decorator


class SafeDict(dict):
    """Dictionary that returns default value for missing keys."""
    
    def __init__(self, *args, default=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.default = default
    
    def __getitem__(self, key):
        return self.get(key, self.default)
    
    def __missing__(self, key):
        return self.default


class ResourceGuard:
    """Guard resource allocation and cleanup."""
    
    def __init__(self):
        self.resources = []
        self.lock = asyncio.Lock()
    
    async def acquire(self, resource, cleanup_fn=None):
        """Acquire a resource."""
        async with self.lock:
            self.resources.append((resource, cleanup_fn))
            return resource
    
    async def release_all(self):
        """Release all resources."""
        async with self.lock:
            for resource, cleanup_fn in reversed(self.resources):
                try:
                    if cleanup_fn:
                        if asyncio.iscoroutinefunction(cleanup_fn):
                            await cleanup_fn(resource)
                        else:
                            cleanup_fn(resource)
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
            
            self.resources.clear()


def robust_json_loads(data: str, default: Any = None) -> Any:
    """Robust JSON parsing with fallback."""
    import json
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


def ensure_directory(path) -> bool:
    """Ensure directory exists, create if not."""
    try:
        path = path if hasattr(path, 'mkdir') else type('Path', (), {'mkdir': lambda self, **k: os.makedirs(self, **k)})(path)
        if hasattr(path, 'exists'):
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.warning(f"Failed to create directory {path}: {e}")
        return False


def get_safe_input(prompt: str, default: str = None, validator: Callable = None) -> str:
    """Get safe user input with validation."""
    while True:
        try:
            value = input(prompt).strip()
            
            if not value and default:
                value = default
            
            if validator and value:
                if validator(value):
                    return value
                else:
                    print("Invalid input, please try again.")
            elif value:
                return value
                    
        except (KeyboardInterrupt, EOFError):
            print("\nInput cancelled")
            return default or ""


class CircularBuffer:
    """Fixed-size buffer that overwrites oldest entries."""
    
    def __init__(self, max_size: int):
        self.buffer = []
        self.max_size = max_size
    
    def append(self, item):
        if len(self.buffer) >= self.max_size:
            self.buffer.pop(0)
        self.buffer.append(item)
    
    def get_all(self):
        return list(self.buffer)
    
    def clear(self):
        self.buffer.clear()


class AsyncBatcher:
    """Batch async operations."""
    
    def __init__(self, batch_size: int = 10, timeout: float = 1.0):
        self.batch_size = batch_size
        self.timeout = timeout
        self.queue = []
        self._lock = asyncio.Lock()
    
    async def add(self, item):
        """Add item to batch."""
        async with self._lock:
            self.queue.append(item)
            
            if len(self.queue) >= self.batch_size:
                return await self._process_batch()
        
        # Schedule delayed processing
        asyncio.create_task(self._delayed_process())
        return None
    
    async def _delayed_process(self):
        """Process batch after timeout."""
        await asyncio.sleep(self.timeout)
        
        async with self._lock:
            if self.queue:
                return await self._process_batch()
    
    async def _process_batch(self):
        """Process accumulated batch."""
        if not self.queue:
            return []
        
        batch = self.queue[:self.batch_size]
        self.queue = self.queue[self.batch_size:]
        return batch


def format_bytes(bytes_count: int) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024
    return f"{bytes_count:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format seconds to human readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def is_interactive_terminal() -> bool:
    """Check if running in interactive terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def get_terminal_size() -> tuple:
    """Get terminal size (columns, lines)."""
    try:
        return os.get_terminal_size().columns, os.get_terminal_size().lines
    except OSError:
        return 80, 24