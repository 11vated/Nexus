"""Unit tests for caching utilities."""
import pytest
import time
from unittest.mock import MagicMock, patch

from nexus.utils.cache import OllamaCache, PersistentCache, ollama_cache


class TestOllamaCache:
    """Test OllamaCache."""

    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = OllamaCache(max_size=10, ttl_seconds=60)
        result = cache.get("model", "prompt")
        assert result is None

    def test_cache_hit(self):
        """Test cache hit returns stored response."""
        cache = OllamaCache(max_size=10, ttl_seconds=60)
        cache.set("model", "prompt", "response")
        result = cache.get("model", "prompt")
        assert result == "response"

    def test_cache_expires(self):
        """Test cache entry expires after TTL."""
        cache = OllamaCache(max_size=10, ttl_seconds=0.01)
        cache.set("model", "prompt", "response")
        
        time.sleep(0.02)
        result = cache.get("model", "prompt")
        assert result is None

    def test_cache_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = OllamaCache(max_size=2, ttl_seconds=60)
        
        cache.set("model1", "prompt1", "response1")
        cache.set("model2", "prompt2", "response2")
        cache.set("model3", "prompt3", "response3")
        
        # First entry should be evicted
        assert cache.get("model1", "prompt1") is None
        assert cache.get("model2", "prompt2") == "response2"
        assert cache.get("model3", "prompt3") == "response3"

    def test_cache_invalidate_by_model(self):
        """Test invalidating cache by model."""
        cache = OllamaCache(max_size=10, ttl_seconds=60)
        
        cache.set("model1", "prompt", "response1")
        cache.set("model2", "prompt", "response2")
        
        cache.invalidate(model="model1")
        
        assert cache.get("model1", "prompt") is None
        assert cache.get("model2", "prompt") == "response2"

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = OllamaCache(max_size=10, ttl_seconds=60)
        
        cache.set("model", "prompt1", "response")
        cache.get("model", "prompt1")
        cache.get("model", "prompt2")  # Miss
        
        stats = cache.get_stats()
        
        assert stats["size"] == 1
        assert stats["total_hits"] == 1

    def test_cache_clear(self):
        """Test clearing cache."""
        cache = OllamaCache(max_size=10, ttl_seconds=60)
        
        cache.set("model", "prompt", "response")
        cache.clear()
        
        assert cache.get("model", "prompt") is None


class TestPersistentCache:
    """Test PersistentCache."""

    def test_persistent_cache_miss(self, tmp_path):
        """Test persistent cache miss."""
        cache = PersistentCache(cache_dir=tmp_path)
        result = cache.get("key1")
        assert result is None

    def test_persistent_cache_set_and_get(self, tmp_path):
        """Test setting and getting from persistent cache."""
        cache = PersistentCache(cache_dir=tmp_path, max_size=10)
        
        cache.set("key1", {"data": "value"}, ttl=60)
        result = cache.get("key1")
        
        assert result is not None
        assert result["data"] == "value"

    def test_persistent_cache_expiry(self, tmp_path):
        """Test persistent cache expiry."""
        cache = PersistentCache(cache_dir=tmp_path, max_size=10)
        
        cache.set("key1", {"data": "value"}, ttl=0.01)
        
        time.sleep(0.02)
        result = cache.get("key1")
        
        assert result is None

    def test_persistent_cache_clear(self, tmp_path):
        """Test clearing persistent cache."""
        cache = PersistentCache(cache_dir=tmp_path, max_size=10)
        
        cache.set("key1", {"data": "value"}, ttl=60)
        cache.clear()
        
        result = cache.get("key1")
        assert result is None


class TestGlobalCache:
    """Test global cache instance."""

    def test_global_cache_exists(self):
        """Test global cache is available."""
        assert ollama_cache is not None
        assert isinstance(ollama_cache, OllamaCache)