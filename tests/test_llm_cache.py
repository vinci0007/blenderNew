"""Tests for LLM cache system."""

import pytest
import time
import tempfile
import shutil
from pathlib import Path

from vbf.llm.cache import (
    LLMCache,
    CacheEntry,
    get_cache,
    reset_cache,
)


class TestLLMCache:
    """Tests for LLMCache."""

    @pytest.fixture
    def cache_dir(self):
        """Create temporary cache directory."""
        tmp = tempfile.mkdtemp()
        yield tmp
        shutil.rmtree(tmp, ignore_errors=True)

    @pytest.fixture
    def cache(self, cache_dir):
        """Create fresh cache instance."""
        reset_cache()
        return LLMCache(
            memory_size=4,
            disk_cache_dir=cache_dir,
            default_ttl_seconds=1.0,  # 1 second for fast tests
        )

    def test_compute_key(self, cache):
        """Should compute consistent hash."""
        messages = [{"role": "user", "content": "hello"}]
        key1 = cache._compute_key(messages)
        key2 = cache._compute_key(messages)

        assert key1 == key2
        assert len(key1) == 64  # SHA256 hex

    def test_cache_miss(self, cache):
        """Should return None on cache miss."""
        messages = [{"role": "user", "content": "new message"}]
        result = cache.get(messages)
        assert result is None

    def test_cache_hit(self, cache):
        """Should return cached value on hit."""
        messages = [{"role": "user", "content": "test"}]
        response = {"ok": True, "data": "result"}

        cache.set(messages, response)
        cached = cache.get(messages)

        assert cached == response

    def test_expiration(self, cache):
        """Should expire after TTL."""
        messages = [{"role": "user", "content": "expire test"}]
        response = {"data": "value"}

        cache.set(messages, response)

        # Immediately should hit
        assert cache.get(messages) is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should miss after expiration
        assert cache.get(messages) is None

    def test_memory_limit(self, cache):
        """Should evict oldest when memory limit reached."""
        # Fill cache to capacity
        for i in range(5):
            messages = [{"role": "user", "content": f"msg {i}"}]
            cache.set(messages, {"data": i})

        # First message should be evicted (LRU)
        first_msg = [{"role": "user", "content": "msg 0"}]
        assert cache.get(first_msg) is None

        # Latest should still be in memory
        latest_msg = [{"role": "user", "content": "msg 4"}]
        assert cache.get(latest_msg) is not None

    def test_similarity(self, cache):
        """Should compute Jaccard similarity."""
        sim = cache._compute_similarity(
            "create a red cube",
            "create a blue cube"
        )
        assert 0 < sim < 1  # Some similarity

        exact = cache._compute_similarity(
            "same prompt",
            "same prompt"
        )
        assert exact == 1.0

    def test_stats(self, cache):
        """Should track statistics."""
        messages = [{"role": "user", "content": "stat test"}]

        # Miss
        cache.get(messages)

        # Set
        cache.set(messages, {"data": 1})

        # Hit
        cache.get(messages)

        stats = cache.get_stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 1
        assert stats["hit_ratio"] == 0.5

    def test_cleanup_expired(self, cache):
        """Should cleanup expired entries."""
        messages = [{"role": "user", "content": "cleanup"}]
        cache.set(messages, {"data": 1})

        time.sleep(1.5)

        removed = cache.cleanup_expired()
        assert removed == 1

    def test_clear(self, cache):
        """Should clear all entries."""
        for i in range(3):
            messages = [{"role": "user", "content": f"m{i}"}]
            cache.set(messages, {"data": i})

        cache.clear()
        stats = cache.get_stats()
        assert stats["memory_entries"] == 0


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_is_expired(self):
        """Should detect expiration."""
        entry = CacheEntry(
            key="test",
            response={},
            prompt="test prompt",
            created_at=time.time() - 10,  # 10 seconds ago
            ttl_seconds=5.0  # 5 second TTL
        )
        assert entry.is_expired()

        fresh = CacheEntry(
            key="test2",
            response={},
            prompt="test",
            created_at=time.time(),
            ttl_seconds=3600.0
        )
        assert not fresh.is_expired()

    def test_touch(self):
        """Should update access stats."""
        entry = CacheEntry(
            key="test",
            response={},
            prompt="test",
            created_at=time.time(),
            access_count=0
        )

        entry.touch()
        assert entry.access_count == 1
        assert entry.last_accessed > entry.created_at


class TestGlobalCache:
    """Tests for global cache singleton."""

    def test_get_cache_returns_same_instance(self):
        """Should return singleton instance."""
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2

    def test_reset_cache(self):
        """Should reset to None."""
        c1 = get_cache()
        reset_cache()
        c2 = get_cache()
        assert c1 is not c2


class TestFuzzyMatching:
    """Tests for fuzzy prompt matching."""

    def test_fuzzy_match(self, tmp_path):
        """Should find similar prompts."""
        cache = LLMCache(
            memory_size=100,
            disk_cache_dir=str(tmp_path),
            fuzzy_match_threshold=0.5,
            enable_fuzzy=True,
        )

        # Store a prompt
        original_messages = [{"role": "user", "content": "create a red cube"}]
        response = {"object": "cube"}
        cache.set(original_messages, response)

        # Query with slightly different prompt
        query_messages = [{"role": "user", "content": "create a red cube please"}]
        result = cache.get(query_messages)

        assert result == response

    def test_no_fuzzy_when_disabled(self, tmp_path):
        """Should not match when fuzzy is disabled."""
        cache = LLMCache(
            memory_size=100,
            disk_cache_dir=str(tmp_path),
            enable_fuzzy=False,
        )

        original_messages = [{"role": "user", "content": "create a red cube"}]
        cache.set(original_messages, {"result": 1})

        query_messages = [{"role": "user", "content": "create a red cube please"}]
        result = cache.get(query_messages)

        assert result is None  # No exact match


def test_default_disk_cache_dir_is_under_vbf_cache():
    cache = LLMCache(memory_size=4)
    try:
        disk_dir = str(cache._disk_dir).replace("\\", "/")
        assert disk_dir.endswith("/vbf/cache/llm_cache")
    finally:
        cache.clear()
