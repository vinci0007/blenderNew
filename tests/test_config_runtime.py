import contextlib
import json
import shutil
import uuid
from pathlib import Path

import pytest

from vbf.config_runtime import (
    load_full_config,
    load_llm_section,
    load_project_paths,
    load_project_scene_config,
)
import vbf.llm.openai_compat as openai_compat
from vbf.llm.openai_compat import LLMError, OpenAICompatConfig, OpenAICompatLLM, load_openai_compat_config

_WORKSPACE_TMP = Path(".tmp_runtime_cfg")


def _toml_literal(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_literal(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML literal: {type(value).__name__}")


def _toml_key(key: str) -> str:
    if key and all(ch.isalnum() or ch in {"_", "-"} for ch in key):
        return key
    return json.dumps(key, ensure_ascii=False)


def _write_toml(path: Path, data):
    lines = []

    def _emit_table(prefix: str, mapping):
        if prefix:
            if lines:
                lines.append("")
            lines.append(f"[{prefix}]")
        scalars = []
        children = []
        for key, value in mapping.items():
            if isinstance(value, dict):
                children.append((key, value))
            else:
                scalars.append((key, value))
        for key, value in scalars:
            lines.append(f"{_toml_key(key)} = {_toml_literal(value)}")
        for key, value in children:
            child_key = _toml_key(key)
            child_prefix = f"{prefix}.{child_key}" if prefix else child_key
            _emit_table(child_prefix, value)

    _emit_table("", data)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@contextlib.contextmanager
def _workspace_temp_dir():
    _WORKSPACE_TMP.mkdir(parents=True, exist_ok=True)
    tmp_dir = _WORKSPACE_TMP / uuid.uuid4().hex
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_load_project_paths_from_vbf_config_path(monkeypatch):
    with _workspace_temp_dir() as tmp_dir:
        cfg = tmp_dir / "config.toml"
        cache_dir = tmp_dir / "cache_dir"
        logs_dir = tmp_dir / "logs_dir"
        llm_cache_dir = tmp_dir / "my_llm_cache"

        _write_toml(
            cfg,
            {
                "project": {
                    "paths": {
                        "cache_dir": str(cache_dir),
                        "logs_dir": str(logs_dir),
                        "task_state_file": str(cache_dir / "task_state.json"),
                        "last_gen_fail_file": str(cache_dir / "last_gen_fail.txt"),
                        "last_plan_fail_file": str(cache_dir / "last_plan_fail.txt"),
                        "last_plan_raw_file": str(cache_dir / "last_plan_raw.txt"),
                        "llm_cache_dir": str(llm_cache_dir),
                    }
                },
                "llm": {
                    "use_llm": True,
                    "base_url": "https://example.test",
                    "api_key": "key",
                    "model": "test-model",
                }
            },
        )

        monkeypatch.setenv("VBF_CONFIG_PATH", str(cfg))

        paths = load_project_paths()

        assert Path(paths["cache_dir"]) == cache_dir.resolve()
        assert Path(paths["logs_dir"]) == logs_dir.resolve()
        assert Path(paths["llm_cache_dir"]) == llm_cache_dir.resolve()
        assert cache_dir.exists()
        assert logs_dir.exists()
        assert llm_cache_dir.exists()


def test_load_llm_section_reads_nested_structure():
    with _workspace_temp_dir() as tmp_dir:
        cfg = tmp_dir / "config.toml"
        _write_toml(
            cfg,
            {
                "project": {"paths": {}},
                "llm": {
                    "use_llm": True,
                    "base_url": "https://example.test",
                    "api_key": "key",
                    "model": "m1",
                    "temperature": 0.2,
                },
            },
        )

        llm = load_llm_section(str(cfg))
        assert llm["base_url"] == "https://example.test"
        assert llm["model"] == "m1"


def test_load_full_config_defaults_llm_to_empty_dict():
    with _workspace_temp_dir() as tmp_dir:
        cfg = tmp_dir / "config.toml"
        _write_toml(cfg, {"project": {"paths": {}}})

        full = load_full_config(str(cfg))
        assert full["llm"] == {}


def test_load_project_scene_config_defaults_and_overrides():
    with _workspace_temp_dir() as tmp_dir:
        cfg = tmp_dir / "config.toml"
        _write_toml(
            cfg,
            {
                "project": {
                    "paths": {},
                    "scene": {
                        "task_scene_policy": "all",
                        "include_environment_objects": False,
                    },
                }
            },
        )

        scene = load_project_scene_config(str(cfg))

        assert scene["task_scene_policy"] == "all"
        assert scene["include_environment_objects"] is False


def test_load_openai_compat_config_does_not_fallback_to_legacy_filename(monkeypatch):
    with _workspace_temp_dir() as tmp_dir:
        legacy = tmp_dir / "llm_config.json"
        legacy.write_text(
            json.dumps(
                {
                    "base_url": "https://legacy.test",
                    "api_key": "legacy",
                    "model": "legacy-model",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("VBF_CONFIG_PATH", str(tmp_dir / "config.toml"))
        monkeypatch.delenv("VBF_LLM_BASE_URL", raising=False)
        monkeypatch.delenv("VBF_LLM_API_KEY", raising=False)
        monkeypatch.delenv("VBF_LLM_MODEL", raising=False)

        try:
            load_openai_compat_config()
        except LLMError:
            pass
        else:
            raise AssertionError("expected load_openai_compat_config to fail without config.toml")


def test_load_openai_compat_config_rejects_legacy_filename():
    with _workspace_temp_dir() as tmp_dir:
        legacy = tmp_dir / "llm_config.json"
        legacy.write_text(
            json.dumps(
                {
                    "base_url": "https://legacy.test",
                    "api_key": "legacy",
                    "model": "legacy-model",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with pytest.raises(LLMError, match="Legacy config filename"):
            load_openai_compat_config(str(legacy))


def test_load_full_config_rejects_legacy_filename():
    with _workspace_temp_dir() as tmp_dir:
        legacy = tmp_dir / "llm_config.json"
        legacy.write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError, match="Legacy config filename"):
            load_full_config(str(legacy))


def test_load_openai_compat_config_reads_request_headers():
    with _workspace_temp_dir() as tmp_dir:
        cfg = tmp_dir / "config.toml"
        _write_toml(
            cfg,
            {
                "project": {"paths": {}},
                "llm": {
                    "base_url": "https://example.test",
                    "api_key": "key",
                    "model": "m1",
                    "is_proxy_api": True,
                    "enable_extra_request_headers": True,
                    "use_curl_http_compat": True,
                    "llm_api_throttling": {
                        "call_timeout_seconds": 123
                    },
                    "request_headers": {
                        "User-Agent": "curl/8.8.0",
                        "X-Test": 123,
                        "": "ignored",
                    },
                },
            },
        )

        loaded = load_openai_compat_config(str(cfg))

        assert loaded is not None
        assert loaded.use_curl_http_compat is True
        assert loaded.http_timeout_seconds == 123
        assert loaded.request_headers == {
            "User-Agent": "curl/8.8.0",
            "X-Test": "123",
        }


def test_load_openai_compat_config_ignores_invalid_request_headers():
    with _workspace_temp_dir() as tmp_dir:
        cfg = tmp_dir / "config.toml"
        _write_toml(
            cfg,
            {
                "project": {"paths": {}},
                "llm": {
                    "base_url": "https://example.test",
                    "api_key": "key",
                    "model": "m1",
                    "is_proxy_api": True,
                    "enable_extra_request_headers": True,
                    "request_headers": ["bad"],
                },
            },
        )

        loaded = load_openai_compat_config(str(cfg))

        assert loaded is not None
        assert loaded.request_headers == {}


def test_load_openai_compat_config_ignores_request_headers_when_disabled():
    with _workspace_temp_dir() as tmp_dir:
        cfg = tmp_dir / "config.toml"
        _write_toml(
            cfg,
            {
                "project": {"paths": {}},
                "llm": {
                    "base_url": "https://example.test",
                    "api_key": "key",
                    "model": "m1",
                    "is_proxy_api": True,
                    "enable_extra_request_headers": False,
                    "request_headers": {
                        "User-Agent": "curl/8.8.0",
                    },
                },
            },
        )

        loaded = load_openai_compat_config(str(cfg))

        assert loaded is not None
        assert loaded.request_headers == {}


def test_load_openai_compat_config_filters_reserved_request_headers():
    with _workspace_temp_dir() as tmp_dir:
        cfg = tmp_dir / "config.toml"
        _write_toml(
            cfg,
            {
                "project": {"paths": {}},
                "llm": {
                    "base_url": "https://example.test",
                    "api_key": "key",
                    "model": "m1",
                    "is_proxy_api": True,
                    "enable_extra_request_headers": True,
                    "request_headers": {
                        "Authorization": "blocked",
                        "content-type": "blocked",
                        "HOST": "blocked",
                        "User-Agent": "curl/8.8.0",
                    },
                },
            },
        )

        loaded = load_openai_compat_config(str(cfg))

        assert loaded is not None
        assert loaded.request_headers == {"User-Agent": "curl/8.8.0"}


def test_load_full_config_rejects_legacy_json_filename():
    with _workspace_temp_dir() as tmp_dir:
        legacy = tmp_dir / "config.json"
        legacy.write_text("{}", encoding="utf-8")

        with pytest.raises(ValueError, match="Legacy config filename"):
            load_full_config(str(legacy))


def test_openai_compat_llm_passes_default_headers(monkeypatch):
    observed = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            observed.update(kwargs)

    monkeypatch.setattr(openai_compat, "OpenAI", _FakeOpenAI)

    OpenAICompatLLM(
        OpenAICompatConfig(
            base_url="https://example.test",
            api_key="key",
            model="model-test",
            request_headers={"User-Agent": "curl/8.8.0"},
        )
    )

    assert observed["default_headers"] == {"User-Agent": "curl/8.8.0"}
