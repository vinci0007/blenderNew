import json
from pathlib import Path

import pytest

from vbf.config_runtime import load_full_config, load_llm_section, load_project_paths
from vbf.llm.openai_compat import LLMError, load_openai_compat_config


def test_load_project_paths_from_vbf_config_path(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cache_dir = tmp_path / "cache_dir"
    logs_dir = tmp_path / "logs_dir"
    llm_cache_dir = tmp_path / "my_llm_cache"

    cfg.write_text(
        json.dumps(
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
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("VBF_CONFIG_PATH", str(cfg))

    paths = load_project_paths()

    assert Path(paths["cache_dir"]) == cache_dir
    assert Path(paths["logs_dir"]) == logs_dir
    assert Path(paths["llm_cache_dir"]) == llm_cache_dir
    assert cache_dir.exists()
    assert logs_dir.exists()
    assert llm_cache_dir.exists()


def test_load_llm_section_reads_nested_structure(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
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
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    llm = load_llm_section(str(cfg))
    assert llm["base_url"] == "https://example.test"
    assert llm["model"] == "m1"


def test_load_full_config_defaults_llm_to_empty_dict(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"project": {"paths": {}}}, ensure_ascii=False), encoding="utf-8")

    full = load_full_config(str(cfg))
    assert full["llm"] == {}


def test_load_openai_compat_config_does_not_fallback_to_legacy_filename(tmp_path, monkeypatch):
    legacy = tmp_path / "llm_config.json"
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

    monkeypatch.setenv("VBF_CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.delenv("VBF_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("VBF_LLM_API_KEY", raising=False)
    monkeypatch.delenv("VBF_LLM_MODEL", raising=False)

    try:
        load_openai_compat_config()
    except LLMError:
        pass
    else:
        raise AssertionError("expected load_openai_compat_config to fail without config.json")


def test_load_openai_compat_config_rejects_legacy_filename(tmp_path):
    legacy = tmp_path / "llm_config.json"
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


def test_load_full_config_rejects_legacy_filename(tmp_path):
    legacy = tmp_path / "llm_config.json"
    legacy.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Legacy config filename"):
        load_full_config(str(legacy))
