"""Caching utilities for Ollama responses."""
import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Any, Dict
from dataclasses import dataclass, asdict
import threading
import logging


logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached response."""
    key: str
    model: str
    prompt: str
    response: str
    created_at: float
    ttl: float
    hits: int = 0


class OllamaCache:
    """LRU cache for Ollama model responses."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
    
    def _make_key(self, model: str, prompt: str) -> str:
        """Generate cache key from model and prompt."""
        combined = f"{model}:{prompt}"
        return hashlib.blake2b(combined.encode(), digest_size=16).hexdigest()
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if entry has expired."""
        return time.time() - entry.created_at > entry.ttl
    
    def get(self, model: str, prompt: str) -> Optional[str]:
        """Get cached response if available and not expired."""
        key = self._make_key(model, prompt)
        
        with self._lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            
            if self._is_expired(entry):
                del self.cache[key]
                return None
            
            entry.hits += 1
            logger.debug(f"Cache hit for key: {key[:8]}... (hits: {entry.hits})")
            return entry.response
    
    def set(self, model: str, prompt: str, response: str, ttl: Optional[float] = None):
        """Store response in cache."""
        key = self._make_key(model, prompt)
        ttl = ttl or self.ttl_seconds
        
        with self._lock:
            if len(self.cache) >= self.max_size:
                self._evict_oldest()
            
            entry = CacheEntry(
                key=key,
                model=model,
                prompt=prompt,
                response=response,
                created_at=time.time(),
                ttl=ttl
            )
            self.cache[key] = entry
            logger.debug(f"Cached response for key: {key[:8]}...")
    
    def _evict_oldest(self):
        """Evict the oldest/least used entry."""
        if not self.cache:
            return
        
        # Evict oldest by creation time
        oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k].created_at)
        del self.cache[oldest_key]
        logger.debug(f"Evicted cache entry: {oldest_key[:8]}...")
    
    def invalidate(self, model: Optional[str] = None, pattern: Optional[str] = None):
        """Invalidate cache entries."""
        with self._lock:
            if model:
                keys_to_delete = [
                    k for k, v in self.cache.items() 
                    if v.model == model
                ]
                for key in keys_to_delete:
                    del self.cache[key]
            
            if pattern:
                keys_to_delete = [
                    k for k, v in self.cache.items() 
                    if pattern.lower() in v.prompt.lower()
                ]
                for key in keys_to_delete:
                    del self.cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_hits = sum(e.hits for e in self.cache.values())
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "total_hits": total_hits,
                "ttl_seconds": self.ttl_seconds,
            }
    
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self.cache.clear()
            logger.info("Cache cleared")


class PersistentCache:
    """File-based persistent cache."""
    
    def __init__(self, cache_dir: Path = None, max_size: int = 1000):
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "nexus")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size
        self._memory_cache = {}
    
    def _get_cache_file(self, key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{key}.json"
    
    def get(self, key: str) -> Optional[Dict]:
        """Get cached data."""
        if key in self._memory_cache:
            return self._memory_cache[key]
        
        cache_file = self._get_cache_file(key)
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            if time.time() > data.get("expires_at", 0):
                cache_file.unlink()
                return None
            
            self._memory_cache[key] = data
            return data
        except (json.JSONDecodeError, IOError):
            return None
    
    def set(self, key: str, data: Dict, ttl: float = 3600):
        """Store data in cache."""
        cache_file = self._get_cache_file(key)
        
        cache_data = {
            **data,
            "created_at": time.time(),
            "expires_at": time.time() + ttl
        }
        
        self._memory_cache[key] = cache_data
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
        except IOError as e:
            logger.warning(f"Failed to persist cache: {e}")
    
    def clear(self):
        """Clear all cached data."""
        self._memory_cache.clear()
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
            except IOError:
                pass


# Global cache instance
ollama_cache = OllamaCache(max_size=1000, ttl_seconds=3600)