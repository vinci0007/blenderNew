"""Tests for LLM rate limiter."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock

from vbf.llm.rate_limiter import (
    LLM_API_Throttle_Config,
    RateLimiter,
    LLMRateLimiter,
    load_throttle_config,
    call_llm_with_throttle,
)


class TestThrottleConfig:
    """Tests for LLM_API_Throttle_Config."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = LLM_API_Throttle_Config()
        assert config.max_concurrent_calls == 3
        assert config.max_calls_per_minute == 20
        assert config.call_timeout_seconds == 60.0
        assert config.retry_on_failure["max_attempts"] == 3

    def test_from_dict(self):
        """Should load from config dict."""
        data = {
            "llm_api_throttling": {
                "max_concurrent_calls": 5,
                "max_calls_per_minute": 30,
                "call_timeout_seconds": 90.0,
                "retry_on_failure": {
                    "max_attempts": 5,
                    "delay_between_attempts_seconds": 2.0
                }
            }
        }
        config = LLM_API_Throttle_Config.from_config_dict(data)
        assert config.max_concurrent_calls == 5
        assert config.max_calls_per_minute == 30
        assert config.retry_on_failure["max_attempts"] == 5


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_initialization(self):
        """Should initialize with config."""
        config = LLM_API_Throttle_Config(max_concurrent_calls=2)
        limiter = RateLimiter(config)
        assert limiter.config.max_concurrent_calls == 2

    @pytest.mark.asyncio
    async def test_stats_initially_zero(self):
        """Stats should start at zero."""
        config = LLM_API_Throttle_Config()
        limiter = RateLimiter(config)
        stats = limiter.get_stats()
        assert stats["total_calls"] == 0
        assert stats["throttled_calls"] == 0


def test_load_throttle_config_from_nested_llm_section(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "project": {"paths": {}},
                "llm": {
                    "llm_api_throttling": {
                        "max_concurrent_calls": 7,
                        "max_calls_per_minute": 11,
                        "call_timeout_seconds": 123,
                        "retry_on_failure": {
                            "max_attempts": 4,
                            "delay_between_attempts_seconds": 1.5,
                        },
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VBF_CONFIG_PATH", str(cfg))
    config = load_throttle_config()
    assert config is not None
    assert config.max_concurrent_calls == 7
    assert config.max_calls_per_minute == 11
    assert config.call_timeout_seconds == 123
