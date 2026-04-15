"""LLM API throttling and concurrency control for VBF.

Manages concurrent LLM API calls and enforces rate limits to prevent
API throttling and manage costs.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque


@dataclass
class LLM_API_Throttle_Config:
    """Configuration for LLM API call throttling and concurrency control.

    This controls how many concurrent LLM API calls can be made,
    how many calls per minute are allowed, and retry behavior.
    """
    max_concurrent_calls: int = 3  # 同时最多N个LLM调用在进行
    max_calls_per_minute: int = 20  # 每分钟最多N个调用
    call_timeout_seconds: float = 60.0  # 单次LLM调用超时时间

    # 失败重试配置
    retry_on_failure: Dict[str, Any] = field(default_factory=lambda: {
        "max_attempts": 3,
        "delay_between_attempts_seconds": 1.0
    })

    @classmethod
    def from_config_dict(cls, config: Dict[str, Any]) -> "LLM_API_Throttle_Config":
        """Create config from dict loaded from vbf/config/llm.json.

        Looks for key: "llm_api_throttling"
        """
        throttle_config = config.get("llm_api_throttling", {})
        retry_config = throttle_config.get("retry_on_failure", {
            "max_attempts": 3,
            "delay_between_attempts_seconds": 1.0
        })

        return cls(
            max_concurrent_calls=throttle_config.get("max_concurrent_calls", 3),
            max_calls_per_minute=throttle_config.get("max_calls_per_minute", 20),
            call_timeout_seconds=throttle_config.get("call_timeout_seconds", 60.0),
            retry_on_failure=retry_config,
        )


class RateLimiter:
    """Token bucket + semaphore based rate limiter for LLM requests.

    Features:
    - Limits concurrent calls (semaphore)
    - Limits calls per minute (token bucket)
    - Automatic retry with exponential backoff
    - Request queueing with fair scheduling
    """

    def __init__(self, config: Optional[LLM_API_Throttle_Config] = None):
        self.config = config or LLM_API_Throttle_Config()

        # Semaphore for concurrent call control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_calls)

        # Token bucket for rate control
        self._max_calls = self.config.max_calls_per_minute
        self._call_timestamps: deque = deque(maxlen=self._max_calls * 2)
        self._rate_lock = asyncio.Lock()

        # Statistics
        self._total_calls: int = 0
        self._throttled_calls: int = 0
        self._failed_calls: int = 0

    async def acquire(self) -> None:
        """Acquire permission to make an LLM API call."""
        # First check rate limit
        async with self._rate_lock:
            await self._wait_for_rate_limit()

        # Then acquire semaphore
        await self._semaphore.acquire()

    def release(self) -> None:
        """Release permit after call completes."""
        self._semaphore.release()

    async def _wait_for_rate_limit(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()
        one_minute_ago = now - 60.0

        # Remove calls older than 1 minute
        while self._call_timestamps and self._call_timestamps[0] < one_minute_ago:
            self._call_timestamps.popleft()

        # Check if at limit
        if len(self._call_timestamps) >= self._max_calls:
            # Wait until oldest call is outside window
            wait_time = 60.0 - (now - self._call_timestamps[0]) + 0.1
            if wait_time > 0:
                self._throttled_calls += 1
                await asyncio.sleep(wait_time)

        # Record this call
        self._call_timestamps.append(time.time())
        self._total_calls += 1

    async def execute_with_throttle(
        self,
        coro_factory: callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute a coroutine with throttling and retry logic.

        Args:
            coro_factory: Async function to call (e.g., llm.chat_json)
            *args: Positional arguments for coro_factory
            **kwargs: Keyword arguments for coro_factory

        Returns:
            Result of coro_factory

        Raises:
            Exception: After all retries exhausted
        """
        await self.acquire()
        try:
            max_attempts = self.config.retry_on_failure.get("max_attempts", 3)
            delay_base = self.config.retry_on_failure.get("delay_between_attempts_seconds", 1.0)

            for attempt in range(max_attempts + 1):
                try:
                    # Execute with timeout
                    return await asyncio.wait_for(
                        coro_factory(*args, **kwargs),
                        timeout=self.config.call_timeout_seconds
                    )
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    # TimeoutError: asyncio.wait_for timed out -> model slow/processing
                    # CancelledError: BaseException (not caught by 'except Exception')
                    #   from asyncio.to_thread cancellation after timeout fires.
                    # Both mean the model needs more time: retry with backoff.
                    self._failed_calls += 1
                    if attempt < max_attempts:
                        delay = delay_base * (2 ** attempt)
                        print(f"[VBF] Timeout/cancelled. Retrying in {delay}s... (attempt {attempt + 1}/{max_attempts})")
                        await asyncio.sleep(delay)
                    else:
                        raise TimeoutError(
                            f"LLM call timed out after {self.config.call_timeout_seconds}s. "
                            "Consider increasing call_timeout_seconds in llm_config.json."
                        ) from None
                except Exception as e:
                    # Other errors: check if retryable (rate limit / server errors)
                    error_str = str(e).lower()
                    is_rate_limit = (
                        isinstance(e, RuntimeError)
                        and (
                            "429" in error_str
                            or "rate limit" in error_str
                            or "too many request" in error_str
                        )
                    )
                    is_server_error = (
                        isinstance(e, RuntimeError)
                        and any(code in error_str for code in ["500", "502", "503"])
                    )
                    if is_rate_limit or is_server_error:
                        self._failed_calls += 1
                        if attempt < max_attempts:
                            delay = delay_base * (2 ** attempt) * 2
                            print(f"[VBF] Retryable error: {e}. Retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_attempts})")
                            await asyncio.sleep(delay)
                        else:
                            raise
                    else:
                        # Non-retryable (parse errors, 400 bad request, etc.)
                        raise
        finally:
            self.release()

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        current_calls = len(self._call_timestamps)
        return {
            "total_calls": self._total_calls,
            "throttled_calls": self._throttled_calls,
            "failed_calls": self._failed_calls,
            "current_window_calls": current_calls,
            "available_capacity": self._max_calls - current_calls,
            "semaphore_available": self._semaphore._value,
        }

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()


class LLMRateLimiter:
    """Singleton-style rate limiter for LLM operations.

    Loads configuration from vbf/config/llm.json and provides
global rate limiting across all LLM calls.
    """

    _instance: Optional["LLMRateLimiter"] = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern - only one rate limiter per process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[LLM_API_Throttle_Config] = None):
        if not hasattr(self, "_initialized"):
            self._limiter = RateLimiter(config)
            self._initialized = True

    @classmethod
    async def get_instance(cls) -> "LLMRateLimiter":
        """Get or create singleton instance."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    async def execute(self, coro_factory: callable, *args, **kwargs) -> Any:
        """Execute LLM request with throttling."""
        return await self._limiter.execute_with_throttle(coro_factory, *args, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return self._limiter.get_stats()


def load_throttle_config() -> Optional[LLM_API_Throttle_Config]:
    """Load throttle configuration from config file.

    Returns:
        LLM_API_Throttle_Config or None if file not found
    """
    import json
    import os

    config_paths = [
        os.path.join(os.path.dirname(__file__), "config", "llm_config.json"),
        os.path.join("vbf", "config", "llm_config.json"),
    ]

    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "llm_api_throttling" in config:
                        return LLM_API_Throttle_Config.from_config_dict(config)
            except (json.JSONDecodeError, IOError):
                continue

    # Return default config
    return LLM_API_Throttle_Config()


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or initialize global rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        config = load_throttle_config()
        _rate_limiter = RateLimiter(config)
    return _rate_limiter


async def call_llm_with_throttle(coro_factory: callable, *args, **kwargs) -> Any:
    """Convenience function to call LLM with throttling.

    Usage:
        from vbf.llm_rate_limiter import call_llm_with_throttle

        response = await call_llm_with_throttle(
            llm.chat_json,
            messages
        )
    """
    limiter = get_rate_limiter()
    return await limiter.execute_with_throttle(coro_factory, *args, **kwargs)
