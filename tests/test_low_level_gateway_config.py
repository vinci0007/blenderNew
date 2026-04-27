"""Property tests for low-level gateway config and repair prompt wiring."""

import contextlib
import json
import os
import uuid
from pathlib import Path
from unittest.mock import patch

from hypothesis import given, strategies as st

from vbf.llm.integration import build_skill_repair_messages
from vbf.llm.openai_compat import _parse_bool_field, load_openai_compat_config

_WORKSPACE_TMP = Path(".tmp_runtime_cfg")


def _toml_literal(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"Unsupported TOML literal: {type(value).__name__}")


def _write_toml(path: Path, data):
    lines = []

    def _emit_table(prefix: str, mapping):
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


@contextlib.contextmanager
def _workspace_temp_config_path():
    _WORKSPACE_TMP.mkdir(parents=True, exist_ok=True)
    cfg_path = _WORKSPACE_TMP / f"{uuid.uuid4().hex}.toml"
    try:
        yield cfg_path
    finally:
        cfg_path.unlink(missing_ok=True)


@given(default=st.booleans())
def test_parse_bool_field_missing_key_uses_default(default):
    assert _parse_bool_field({}, "allow_low_level_gateway", default) is default


@given(value=st.booleans())
def test_parse_bool_field_keeps_bool_value(value):
    data = {"allow_low_level_gateway": value}
    assert _parse_bool_field(data, "allow_low_level_gateway", not value) is value


@given(value=st.integers(min_value=-10_000, max_value=10_000))
def test_parse_bool_field_casts_int_to_bool(value):
    data = {"allow_low_level_gateway": value}
    assert _parse_bool_field(data, "allow_low_level_gateway", False) is bool(value)


@given(
    default=st.booleans(),
    value=st.one_of(
        st.none(),
        st.text(max_size=32),
        st.floats(allow_nan=False, allow_infinity=False),
        st.lists(st.integers(), max_size=5),
        st.dictionaries(st.text(max_size=8), st.integers(), max_size=3),
    ),
)
def test_parse_bool_field_unexpected_type_falls_back_to_default(default, value):
    data = {"allow_low_level_gateway": value}
    assert _parse_bool_field(data, "allow_low_level_gateway", default) is default


@given(
    base_url=st.text(
        alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters=["\n", "\r", "\t"]),
        min_size=1,
        max_size=40,
    ),
    api_key=st.text(
        alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters=["\n", "\r", "\t"]),
        min_size=1,
        max_size=40,
    ),
    model=st.text(
        alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters=["\n", "\r", "\t"]),
        min_size=1,
        max_size=40,
    ),
)
def test_json_config_defaults_low_level_flags(base_url, api_key, model):
    with _workspace_temp_config_path() as cfg_path:
        _write_toml(
            cfg_path,
            {
                "project": {"paths": {}},
                "llm": {
                    "base_url": base_url,
                    "api_key": api_key,
                    "model": model,
                    "temperature": 0.2,
                },
            },
        )
        cfg = load_openai_compat_config(str(cfg_path))
    assert cfg is not None
    assert cfg.allow_low_level_gateway is False
    assert cfg.auto_allow_low_level_gateway is True


@given(
    allow_raw=st.sampled_from(["0", "1", "2", "true", "false", "", "YES"]),
    auto_raw=st.sampled_from(["0", "1", "2", "true", "false", "", "NO"]),
)
def test_env_config_parses_low_level_flags(allow_raw, auto_raw):
    env = {
        "VBF_LLM_BASE_URL": "https://example.test",
        "VBF_LLM_API_KEY": "key-test",
        "VBF_LLM_MODEL": "model-test",
        "VBF_ALLOW_LOW_LEVEL_GATEWAY": allow_raw,
        "VBF_AUTO_ALLOW_LOW_LEVEL_GATEWAY": auto_raw,
    }
    with patch.dict(os.environ, env, clear=False):
        cfg = load_openai_compat_config()
    assert cfg is not None
    assert cfg.allow_low_level_gateway is (allow_raw == "1")
    assert cfg.auto_allow_low_level_gateway is (auto_raw == "1")


@given(failed_step_id=st.text(min_size=1, max_size=24))
def test_repair_prompt_keeps_failed_step_id(failed_step_id):
    messages = build_skill_repair_messages(
        prompt="fix plan",
        failed_step_id=failed_step_id,
        error_message="blocked by policy",
        error_traceback="trace",
        original_plan={"plan_id": "p1", "steps": []},
        step_results={},
        allowed_skills=["create_primitive"],
    )
    user = json.loads(messages[1]["content"])
    assert user["failed_step_id"] == failed_step_id
    assert user["repair_plan_schema"]["repair"]["replace_from_step_id"] == "string"


def test_repair_prompt_includes_low_level_hint_and_blocked_entry():
    step_results = {
        "s3": {
            "ok": False,
            "error": {
                "kind": "blocked_low_level_gateway",
                "message": "py_call requires explicit allow flag",
            },
        }
    }
    messages = build_skill_repair_messages(
        prompt="repair this task",
        failed_step_id="s3",
        error_message="blocked",
        error_traceback="trace",
        original_plan={"plan_id": "p1", "steps": []},
        step_results=step_results,
        allowed_skills=["create_primitive", "py_call", "py_set"],
        skill_schemas={
            "py_call": {"description": "Low-level callable bridge", "args": {"callable_path_steps": "list"}},
            "py_set": {"description": "Low-level setter bridge", "args": {"path_steps": "list"}},
        },
        low_level_gateway_hint=True,
    )

    user = json.loads(messages[1]["content"])
    instructions = " ".join(user["instructions"])
    assert "py_call and py_set are now available as low-level gateway skills" in instructions
    assert user["executed_step_outputs"]["s3"]["error"]["kind"] == "blocked_low_level_gateway"
    assert isinstance(user["allowed_skills"], list)
    assert isinstance(user["allowed_skills"][0], dict)
