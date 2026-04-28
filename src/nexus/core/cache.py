"""Response caching for LLM calls."""
import hashlib
import time
from typing import Any, Dict, Optional
from functools import lru_cache
import logging


logger = logging.getLogger(__name__)


class ResponseCache:
    """LRU cache for LLM responses."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def _make_key(self, model: str, prompt: str) -> str:
        """Create cache key from model and prompt."""
        data = f"{model}:{prompt}".encode()
        return hashlib.blake2b(data, digest_size=16).hexdigest()
    
    def get(self, model: str, prompt: str) -> Optional[str]:
        """Get cached response."""
        key = self._make_key(model, prompt)
        
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["time"] < self.ttl:
                logger.debug(f"Cache hit for {model}")
                return entry["response"]
            else:
                del self._cache[key]
        
        return None
    
    def set(self, model: str, prompt: str, response: str) -> None:
        """Cache a response."""
        key = self._make_key(model, prompt)
        
        if len(self._cache) >= self.max_size:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k]["time"]
            )
            del self._cache[oldest_key]
        
        self._cache[key] = {
            "response": response,
            "time": time.time()
        }
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
    
    def stats(self) -> Dict[str, int]:
        """Get cache stats."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl": self.ttl
        }


_global_cache = ResponseCache()


def get_global_cache() -> ResponseCache:
    """Get global cache instance."""
    return _global_cache