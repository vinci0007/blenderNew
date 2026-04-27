from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Dict

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parent
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "vbf" / "config" / "config.toml"
_LEGACY_CONFIG_FILENAMES = {"llm_config.json", "config.json"}


def _assert_supported_config_name(cfg_path: Path) -> None:
    if cfg_path.name.lower() in _LEGACY_CONFIG_FILENAMES:
        raise ValueError(
            f"Legacy config filename '{cfg_path.name}' is no longer supported. "
            "Use 'config.toml' instead."
        )
    if cfg_path.suffix.lower() != ".toml":
        raise ValueError(
            f"Unsupported config format '{cfg_path.suffix or cfg_path.name}'. "
            "Use a TOML config file such as 'config.toml'."
        )


def _default_project_paths() -> Dict[str, str]:
    cache_dir = _REPO_ROOT / "vbf" / "cache"
    logs_dir = _REPO_ROOT / "vbf" / "logs"
    return {
        "cache_dir": str(cache_dir),
        "logs_dir": str(logs_dir),
        "task_state_file": str(cache_dir / "task_state.json"),
        "last_gen_fail_file": str(cache_dir / "last_gen_fail.txt"),
        "last_plan_fail_file": str(cache_dir / "last_plan_fail.txt"),
        "last_plan_raw_file": str(cache_dir / "last_plan_raw.txt"),
        "llm_cache_dir": str(cache_dir / "llm_cache"),
    }


def _resolve_runtime_path(path_value: str, fallback: Path) -> str:
    if not path_value:
        return str(fallback)
    raw = Path(path_value)
    if raw.is_absolute():
        return str(raw)
    return str((_REPO_ROOT / raw).resolve())


def _normalize_project_paths(raw_paths: Dict[str, Any] | None) -> Dict[str, str]:
    defaults = _default_project_paths()
    raw_paths = raw_paths or {}

    cache_dir = Path(_resolve_runtime_path(str(raw_paths.get("cache_dir", "")), Path(defaults["cache_dir"])))
    logs_dir = Path(_resolve_runtime_path(str(raw_paths.get("logs_dir", "")), Path(defaults["logs_dir"])))

    normalized = {
        "cache_dir": str(cache_dir),
        "logs_dir": str(logs_dir),
        "task_state_file": _resolve_runtime_path(
            str(raw_paths.get("task_state_file", "")),
            cache_dir / "task_state.json",
        ),
        "last_gen_fail_file": _resolve_runtime_path(
            str(raw_paths.get("last_gen_fail_file", "")),
            cache_dir / "last_gen_fail.txt",
        ),
        "last_plan_fail_file": _resolve_runtime_path(
            str(raw_paths.get("last_plan_fail_file", "")),
            cache_dir / "last_plan_fail.txt",
        ),
        "last_plan_raw_file": _resolve_runtime_path(
            str(raw_paths.get("last_plan_raw_file", "")),
            cache_dir / "last_plan_raw.txt",
        ),
        "llm_cache_dir": _resolve_runtime_path(
            str(raw_paths.get("llm_cache_dir", "")),
            cache_dir / "llm_cache",
        ),
    }

    return normalized


def _ensure_runtime_dirs(paths: Dict[str, str]) -> None:
    required_dirs = {
        Path(paths["cache_dir"]),
        Path(paths["logs_dir"]),
        Path(paths["llm_cache_dir"]),
        Path(paths["task_state_file"]).parent,
        Path(paths["last_gen_fail_file"]).parent,
        Path(paths["last_plan_fail_file"]).parent,
        Path(paths["last_plan_raw_file"]).parent,
    }
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)


def get_default_config_path() -> str:
    return str(_DEFAULT_CONFIG_PATH)


def load_full_config(config_path: str | None = None) -> Dict[str, Any]:
    cfg_path = Path(config_path or os.getenv("VBF_CONFIG_PATH") or _DEFAULT_CONFIG_PATH)
    _assert_supported_config_name(cfg_path)
    raw: Dict[str, Any] = {}

    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8-sig") as f:
            loaded = tomllib.loads(f.read())
            if isinstance(loaded, dict):
                raw = loaded

    project_raw = raw.get("project") if isinstance(raw.get("project"), dict) else {}
    paths_raw = project_raw.get("paths") if isinstance(project_raw.get("paths"), dict) else {}
    scene_raw = project_raw.get("scene") if isinstance(project_raw.get("scene"), dict) else {}
    paths = _normalize_project_paths(paths_raw)
    _ensure_runtime_dirs(paths)

    llm = raw.get("llm") if isinstance(raw.get("llm"), dict) else {}

    return {
        "project": {
            "paths": paths,
            "scene": {
                "task_scene_policy": str(scene_raw.get("task_scene_policy", "isolate")),
                "include_environment_objects": bool(scene_raw.get("include_environment_objects", True)),
            },
        },
        "llm": llm,
    }


def load_project_paths(config_path: str | None = None) -> Dict[str, str]:
    full = load_full_config(config_path)
    return full["project"]["paths"]


def load_project_scene_config(config_path: str | None = None) -> Dict[str, Any]:
    full = load_full_config(config_path)
    return full["project"]["scene"]


def load_llm_section(config_path: str | None = None) -> Dict[str, Any]:
    full = load_full_config(config_path)
    return full.get("llm", {})
