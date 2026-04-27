"""Tests for LLM rate limiter."""

import pytest
import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from vbf.llm.rate_limiter import (
    LLM_API_Throttle_Config,
    RateLimiter,
    LLMRateLimiter,
    load_throttle_config,
    call_llm_with_throttle,
)

_WORKSPACE_TMP = Path(".tmp_runtime_cfg")


def _toml_literal(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"Unsupported TOML literal: {type(value).__name__}")


def _write_toml(path, data):
    lines = []

    def _emit_table(prefix, mapping):
        if prefix:
            if lines:
                lines.append("")
            lines.append(f"[{prefix}]")
        for key, value in mapping.items():
            if isinstance(value, dict):
                child_prefix = f"{prefix}.{key}" if prefix else key
                _emit_table(child_prefix, value)
            else:
                lines.append(f"{key} = {_toml_literal(value)}")

    _emit_table("", data)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _workspace_config_path() -> Path:
    _WORKSPACE_TMP.mkdir(parents=True, exist_ok=True)
    return _WORKSPACE_TMP / f"{uuid.uuid4().hex}.toml"


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


def test_load_throttle_config_from_nested_llm_section(monkeypatch):
    cfg = _workspace_config_path()
    try:
        _write_toml(
            cfg,
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
                    },
                }
            },
        )
        monkeypatch.setenv("VBF_CONFIG_PATH", str(cfg))
        config = load_throttle_config()
        assert config is not None
        assert config.max_concurrent_calls == 7
        assert config.max_calls_per_minute == 11
        assert config.call_timeout_seconds == 123
    finally:
        cfg.unlink(missing_ok=True)
