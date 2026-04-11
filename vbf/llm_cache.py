"""LLM response caching system for VBF.

Provides two-level caching (memory + disk) to reduce API costs
on repeated or similar prompts. Uses SHA256 hashing for cache keys
and supports fuzzy matching.
"""

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict


@dataclass
class CacheEntry:
    """A single cached LLM response."""
    key: str
    response: Dict[str, Any]
    prompt: str
    created_at: float
    ttl_seconds: float = 3600.0  # Default 1 hour
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return time.time() - self.created_at > self.ttl_seconds

    def touch(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = time.time()


class LLMCache:
    """Two-level cache for LLM responses.

    Level 1: In-memory LRU cache (fast)
    Level 2: Disk cache (persistent, JSON files)

    Features:
    - SHA256 hash keys for fast lookup
    - TTL-based expiration
    - Fuzzy matching for similar prompts (>0.9 similarity)
    - LRU eviction when memory limit reached

    Example usage:
        cache = LLMCache()

        # Try cache first
        cached = cache.get(prompt_hash)
        if cached:
            return cached

        # Miss: call LLM and cache response
        response = await llm.chat_json(...)
        cache.set(prompt_hash, response, prompt_text)
    """

    def __init__(
        self,
        memory_size: int = 128,  # Max 128 cached responses in memory
        disk_cache_dir: Optional[str] = None,
        default_ttl_seconds: float = 7200.0,  # 2 hours default
        fuzzy_match_threshold: float = 0.9,
        enable_fuzzy: bool = True,
    ):
        self.memory_size = memory_size
        self.default_ttl = default_ttl_seconds
        self.fuzzy_threshold = fuzzy_match_threshold
        self.enable_fuzzy = enable_fuzzy

        # Memory cache: OrderedDict for LRU eviction
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Disk cache directory
        if disk_cache_dir is None:
            try:
                base_path = Path(__file__).parent
            except NameError:
                # __file__ not available (e.g., frozen/embedded), fallback to cwd
                base_path = Path.cwd()
            disk_cache_dir = base_path / "config" / "llm_cache"
        self._disk_dir = Path(disk_cache_dir)
        self._disk_dir.mkdir(parents=True, exist_ok=True)

        # Statistics
        self._hits = 0
        self._misses = 0
        self._disk_hits = 0

    def _compute_key(self, messages: List[Dict[str, str]]) -> str:
        """Compute SHA256 hash of messages for cache key.

        Args:
            messages: List of message dicts from build_skill_plan_messages

        Returns:
            SHA256 hex digest (64 characters)
        """
        # Canonical JSON representation for consistent hashing
        content = json.dumps(messages, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _normalize_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Normalize messages for comparison."""
        # Sort system messages first, then user messages
        normalized = []
        for msg in sorted(messages, key=lambda m: m.get('role', '')):
            normalized.append({
                'role': msg.get('role', ''),
                'content': msg.get('content', '')[:1000]  # Truncate long content
            })
        return normalized

    def _compute_similarity(self, prompt_a: str, prompt_b: str) -> float:
        """Compute Jaccard similarity between two prompts.

        Returns float 0.0-1.0, where 1.0 means identical.
        """
        if not prompt_a or not prompt_b:
            return 0.0

        # Simple word-based Jaccard similarity
        words_a = set(prompt_a.lower().split())
        words_b = set(prompt_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b

        return len(intersection) / len(union)

    def get(self, messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """Try to get cached response for messages.

        Args:
            messages: Chat messages (will be hashed)

        Returns:
            Cached response dict or None if not found/expired
        """
        key = self._compute_key(messages)

        # Level 1: Memory cache
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if not entry.is_expired():
                entry.touch()
                # Move to end (most recently used)
                self._memory_cache.move_to_end(key)
                self._hits += 1
                return entry.response
            else:
                # Expired, remove
                del self._memory_cache[key]

        # Level 2: Disk cache
        disk_entry = self._load_from_disk(key)
        if disk_entry and not disk_entry.is_expired():
            # Promote to memory
            self._store_in_memory(disk_entry)
            self._disk_hits += 1
            self._hits += 1
            return disk_entry.response

        # Fuzzy match: look for similar prompts
        if self.enable_fuzzy and key not in self._memory_cache:
            current_prompt = json.dumps(messages)

            for entry in self._memory_cache.values():
                similarity = self._compute_similarity(current_prompt, entry.prompt)
                if similarity >= self.fuzzy_threshold and not entry.is_expired():
                    entry.touch()
                    self._memory_cache.move_to_end(entry.key)
                    self._hits += 1
                    return entry.response

        self._misses += 1
        return None

    def set(
        self,
        messages: List[Dict[str, str]],
        response: Dict[str, Any],
        ttl: Optional[float] = None
    ) -> None:
        """Cache a response.

        Args:
            messages: Chat messages
            response: LLM response to cache
            ttl: Time-to-live in seconds (optional, uses default if None)
        """
        key = self._compute_key(messages)
        prompt = json.dumps(messages, ensure_ascii=False)

        entry = CacheEntry(
            key=key,
            response=response,
            prompt=prompt,
            created_at=time.time(),
            ttl_seconds=ttl or self.default_ttl,
        )

        # Store in memory (with eviction if needed)
        self._store_in_memory(entry)

        # Also save to disk asynchronously, but only if event loop is running
        try:
            asyncio.get_running_loop()
            asyncio.create_task(self._save_to_disk(entry))
        except RuntimeError:
            # No running event loop, skip background save
            # This happens in synchronous unit tests
            pass

    def _store_in_memory(self, entry: CacheEntry) -> None:
        """Store entry in memory cache, evicting LRU if needed."""
        # Evict oldest if at capacity
        while len(self._memory_cache) >= self.memory_size:
            self._memory_cache.popitem(last=False)

        self._memory_cache[entry.key] = entry
        self._memory_cache.move_to_end(entry.key)

    async def _save_to_disk(self, entry: CacheEntry) -> None:
        """Save entry to disk cache."""
        file_path = self._disk_dir / f"{entry.key}.json"

        data = {
            "key": entry.key,
            "response": entry.response,
            "prompt": entry.prompt,
            "created_at": entry.created_at,
            "ttl_seconds": entry.ttl_seconds,
            "access_count": entry.access_count,
            "last_accessed": entry.last_accessed,
        }

        try:
            # Run disk I/O in thread to not block event loop
            await asyncio.to_thread(self._write_json, file_path, data)
        except Exception:
            # Disk errors are non-fatal, just skip caching
            pass

    def _write_json(self, path: Path, data: Dict) -> None:
        """Synchronously write JSON to file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_from_disk(self, key: str) -> Optional[CacheEntry]:
        """Load entry from disk cache."""
        file_path = self._disk_dir / f"{key}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entry = CacheEntry(
                key=data["key"],
                response=data["response"],
                prompt=data["prompt"],
                created_at=data["created_at"],
                ttl_seconds=data["ttl_seconds"],
                access_count=data.get("access_count", 0),
                last_accessed=data.get("last_accessed", data["created_at"]),
            )
            return entry
        except (json.JSONDecodeError, KeyError, IOError):
            # Corrupted or missing file, delete it
            try:
                file_path.unlink()
            except OSError:
                pass
            return None

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "memory_entries": len(self._memory_cache),
            "hits": self._hits,
            "misses": self._misses,
            "disk_hits": self._disk_hits,
            "hit_ratio": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0.0,
        }

    def clear(self) -> None:
        """Clear all cached entries."""
        self._memory_cache.clear()

        # Clear disk cache
        try:
            for file_path in self._disk_dir.glob("*.json"):
                file_path.unlink()
        except OSError:
            pass

    def cleanup_expired(self) -> int:
        """Remove expired entries from memory cache.

        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._memory_cache.items()
            if entry.is_expired()
        ]

        for key in expired_keys:
            del self._memory_cache[key]

        return len(expired_keys)


# Global cache instance
_global_cache: Optional[LLMCache] = None


def get_cache() -> LLMCache:
    """Get or initialize global LLM cache."""
    global _global_cache
    if _global_cache is None:
        _global_cache = LLMCache()
    return _global_cache


def reset_cache() -> None:
    """Reset global cache (for testing)."""
    global _global_cache
    _global_cache = None
