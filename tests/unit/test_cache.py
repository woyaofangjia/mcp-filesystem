"""缓存模块单元测试"""
import time
import pytest
from src.mcp_project.services.cache import LRUCache, FileCacheManager


class TestLRUCache:
    def test_set_get(self):
        cache = LRUCache(max_items=10)
        cache.set("key1", "value1", mtime=100.0)
        assert cache.get("key1") == "value1"

    def test_miss(self):
        cache = LRUCache(max_items=10)
        assert cache.get("nonexistent") is None

    def test_lru_eviction(self):
        cache = LRUCache(max_items=2)
        cache.set("k1", "v1", mtime=1.0)
        cache.set("k2", "v2", mtime=2.0)
        cache.get("k1")  # make k1 recently used
        cache.set("k3", "v3", mtime=3.0)  # should evict k2
        assert cache.get("k1") == "v1"
        assert cache.get("k2") is None

    def test_mtime_invalidation(self):
        cache = LRUCache(max_items=10)
        cache.set("key", "value", mtime=100.0)
        assert cache.get("key", current_mtime=100.0) == "value"
        assert cache.get("key", current_mtime=200.0) is None

    def test_ttl_expiration(self):
        cache = LRUCache(max_items=10, default_ttl=0.1)
        cache.set("key", "value", mtime=100.0)
        assert cache.get("key") == "value"
        time.sleep(0.15)
        assert cache.get("key") is None

    def test_stats(self):
        cache = LRUCache(max_items=10)
        cache.set("k1", "v1", mtime=1.0)
        cache.get("k1")  # hit
        cache.get("k2")  # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_invalidate(self):
        cache = LRUCache(max_items=10)
        cache.set("k1", "v1", mtime=1.0)
        assert cache.invalidate("k1") is True
        assert cache.get("k1") is None
        assert cache.invalidate("k1") is False

    def test_clear(self):
        cache = LRUCache(max_items=10)
        cache.set("k1", "v1", mtime=1.0)
        cache.clear()
        assert cache.stats()["items"] == 0
