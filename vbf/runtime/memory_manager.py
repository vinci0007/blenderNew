"""Memory management utilities for VBF.

Provides memory monitoring, optimization hooks, and automatic cleanup
to prevent OOM in long-running modeling tasks.
"""

import gc
import os
import sys
import warnings
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class MemoryStats:
    """Snapshot of memory statistics."""
    step_count: int = 0
    step_results_size: int = 0  # bytes
    scene_state_objects: int = 0
    llm_cache_hits: int = 0
    llm_cache_misses: int = 0
    peak_memory_mb: float = 0.0
    current_memory_mb: float = 0.0


class MemoryManager:
    """Manages memory usage for VBF operations.

    Features:
    - Monitors memory usage during task execution
    - Triggers garbage collection when thresholds are exceeded
    - Enforces limits on step_results history size
    - Provides memory stats for debugging
    """

    # Default thresholds (can be overridden via environment variables)
    DEFAULT_STEP_RESULTS_LIMIT = int(os.getenv("VBF_MAX_STEP_RESULTS", "100"))
    DEFAULT_MEMORY_THRESHOLD_MB = int(os.getenv("VBF_MEMORY_THRESHOLD_MB", "512"))
    DEFAULT_GC_INTERVAL_STEPS = int(os.getenv("VBF_GC_INTERVAL_STEPS", "10"))

    def __init__(
        self,
        step_results_limit: int = DEFAULT_STEP_RESULTS_LIMIT,
        memory_threshold_mb: float = DEFAULT_MEMORY_THRESHOLD_MB,
        gc_interval: int = DEFAULT_GC_INTERVAL_STEPS,
        auto_cleanup: bool = True,
    ):
        self.step_results_limit = step_results_limit
        self.memory_threshold_mb = memory_threshold_mb
        self.gc_interval = gc_interval
        self.auto_cleanup = auto_cleanup

        # Track state
        self._step_count: int = 0
        self._gc_trigger_count: int = 0
        self._last_gc_step: int = 0
        self._peak_memory_mb: float = 0.0

        # Optional: track object references for manual cleanup
        self._registered_objects: Set[int] = set()

    def record_step(self) -> None:
        """Call after each step to track progress and trigger cleanup if needed."""
        self._step_count += 1

        if not self.auto_cleanup:
            return

        # Periodic GC
        if self._step_count - self._last_gc_step >= self.gc_interval:
            self._trigger_gc()

        # Check memory threshold
        current_mb = self._get_current_memory_mb()
        self._peak_memory_mb = max(self._peak_memory_mb, current_mb)

        if current_mb > self.memory_threshold_mb:
            self._trigger_gc()
            # Still over threshold? Warn user
            if self._get_current_memory_mb() > self.memory_threshold_mb:
                warnings.warn(
                    f"Memory usage ({current_mb:.1f}MB) exceeds threshold "
                    f"({self.memory_threshold_mb}MB). Consider reducing task complexity.",
                    MemoryWarning,
                    stacklevel=2
                )

    def _trigger_gc(self) -> None:
        """Trigger garbage collection and update stats."""
        gc.collect()
        self._gc_trigger_count += 1
        self._last_gc_step = self._step_count

    def limit_step_results(self, step_results: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce limit on step_results dict size.

        If over limit, keeps only the most recent entries.
        Returns the trimmed dict (may be same object if under limit).
        """
        if len(step_results) <= self.step_results_limit:
            return step_results

        # Keep only the most recent results
        # Convert to list, sort by some heuristic (here just dict order), trim
        items = list(step_results.items())

        # Strategy: Keep first half and last quarter for context
        # This preserves beginning and recent history while dropping middle
        keep_count = self.step_results_limit // 2
        recent_count = self.step_results_limit - keep_count

        # Actually, better strategy: LRU - keep most recently accessed
        # But we don't have access timestamps, so keep first N and last M
        keep_items = items[:keep_count // 2] + items[-recent_count:]

        new_results = dict(keep_items)

        # Force GC on the old dict
        del items
        self._trigger_gc()

        return new_results

    def estimate_object_size(self, obj: Any) -> int:
        """Estimate memory size of an object in bytes."""
        try:
            import sys
            return sys.getsizeof(obj)
        except (TypeError, AttributeError):
            return 0

    def get_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()

        return MemoryStats(
            step_count=self._step_count,
            peak_memory_mb=self._peak_memory_mb,
            current_memory_mb=mem_info.rss / (1024 * 1024),
        )

    def _get_current_memory_mb(self) -> float:
        """Get current process memory in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0

    def cleanup(self) -> None:
        """Force cleanup of all tracked objects and GC."""
        # Clear registered object references
        self._registered_objects.clear()

        # Force full GC
        gc.collect()
        gc.collect()  # Second pass for cyclic refs

        self._gc_trigger_count += 1

    def __enter__(self) -> "MemoryManager":
        return self

    def __exit__(self, *args) -> None:
        self.cleanup()


class MemoryWarning(UserWarning):
    """Warning for memory-related issues."""
    pass


def memory_aware(threshold_mb: float = 512, gc_interval: int = 10):
    """Decorator to make a function memory-aware.

    Automatically triggers GC and warns on high memory usage.
    """
    def decorator(func: Callable) -> Callable:
        manager = MemoryManager(
            memory_threshold_mb=threshold_mb,
            gc_interval=gc_interval,
        )

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            manager.record_step()
            try:
                return await func(*args, **kwargs)
            finally:
                if manager._step_count % gc_interval == 0:
                    manager.cleanup()

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            manager.record_step()
            try:
                return func(*args, **kwargs)
            finally:
                if manager._step_count % gc_interval == 0:
                    manager.cleanup()

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Import here to avoid circular import at module level
import asyncio