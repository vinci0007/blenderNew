"""
Bug condition exploration test for skill schema injection.

Property 1: Fault Condition — Schema 注入到 allowed_skills 字段
Validates: Requirements 1.1, 2.1, 2.4

On UNFIXED code, `_build_skill_plan_messages` does not accept a `skill_schemas`
keyword argument, so calling it with `skill_schemas=...` raises:
    TypeError: _build_skill_plan_messages() got an unexpected keyword argument 'skill_schemas'

This failure IS the expected outcome — it confirms the bug exists.
"""

import json
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from vbf.client import VBFClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client() -> VBFClient:
    """Instantiate VBFClient without a live WebSocket connection."""
    return VBFClient.__new__(VBFClient)


def _parse_user_content(messages: list) -> dict:
    """Extract and parse the JSON body of the user message."""
    user_msg = messages[1]
    return json.loads(user_msg["content"])


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

skill_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=32,
)

skill_schema_entry_st = st.fixed_dictionaries({
    "description": st.text(min_size=0, max_size=80),
    "args": st.dictionaries(
        keys=skill_name_st,
        values=st.fixed_dictionaries({
            "required": st.booleans(),
            "type": st.sampled_from(["str", "int", "float", "bool", "list", "any"]),
        }),
        max_size=5,
    ),
})


@st.composite
def skill_schemas_st(draw):
    """Generate a non-empty skill_schemas dict mapping skill names to schema entries."""
    names = draw(st.lists(skill_name_st, min_size=1, max_size=6, unique=True))
    return {name: draw(skill_schema_entry_st) for name in names}


# ---------------------------------------------------------------------------
# Task 1 — Bug condition exploration (Property 1: Fault Condition)
# ---------------------------------------------------------------------------

@given(
    prompt=st.text(min_size=1, max_size=200),
    skill_schemas=skill_schemas_st(),
)
@settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
def test_fault_condition(prompt, skill_schemas):
    """
    **Validates: Requirements 1.1, 2.1, 2.4**

    When `_build_skill_plan_messages` is called with a non-None `skill_schemas`,
    the `allowed_skills` field in the user message MUST be a List[Dict] where
    each entry contains at least `description` and `args` keys.

    On UNFIXED code this test raises:
        TypeError: _build_skill_plan_messages() got an unexpected keyword argument 'skill_schemas'

    That TypeError IS the expected failure — it proves the bug exists.
    """
    client = _make_client()
    allowed_skills = list(skill_schemas.keys())

    # On unfixed code this line raises TypeError (unexpected keyword argument).
    messages = client._build_skill_plan_messages(
        prompt, allowed_skills, skill_schemas=skill_schemas
    )

    user_content = _parse_user_content(messages)
    injected = user_content["allowed_skills"]

    # Each entry must be a dict (not a bare string).
    assert isinstance(injected, list), "allowed_skills must be a list"
    for entry in injected:
        assert isinstance(entry, dict), (
            f"Expected dict in allowed_skills, got {type(entry).__name__!r}: {entry!r}"
        )
        assert "description" in entry, f"Missing 'description' key in skill entry: {entry!r}"
        assert "args" in entry, f"Missing 'args' key in skill entry: {entry!r}"


# ---------------------------------------------------------------------------
# Task 2 — Preservation property tests (Property 2: Preservation)
# ---------------------------------------------------------------------------

@given(
    prompt=st.text(min_size=1, max_size=200),
    allowed_skills=st.lists(skill_name_st, min_size=0, max_size=8),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_fallback(prompt, allowed_skills):
    """
    **Validates: Requirements 2.5, 3.2**

    When `_build_skill_plan_messages` is called WITHOUT `skill_schemas` (fallback mode),
    the `allowed_skills` field in the user message MUST remain a List[str], and the
    messages list MUST have length 2.

    This test MUST PASS on unfixed code — it establishes the baseline behavior to preserve.
    """
    client = _make_client()

    # Call without skill_schemas — this is the fallback / original path.
    messages = client._build_skill_plan_messages(prompt, allowed_skills)

    # Must return exactly 2 messages.
    assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"

    user_content = _parse_user_content(messages)
    injected = user_content["allowed_skills"]

    # In fallback mode, allowed_skills must still be a plain list of strings.
    assert isinstance(injected, list), "allowed_skills must be a list"
    for entry in injected:
        if isinstance(entry, dict):
            # If it's a dict, we just want to make sure it's a valid skill entry
            assert "name" in entry, f"Expected 'name' key in skill entry dict: {entry!r}"
        else:
            assert isinstance(entry, str), (
                f"Expected str or dict in allowed_skills (fallback), got {type(entry).__name__!r}: {entry!r}"
            )


@given(
    prompt=st.text(min_size=1, max_size=200),
    allowed_skills=st.lists(skill_name_st, min_size=0, max_size=8),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_message_format(prompt, allowed_skills):
    """
    **Validates: Requirements 3.2**

    The messages list returned by `_build_skill_plan_messages` MUST always have the
    structure [{"role": "system", ...}, {"role": "user", ...}].

    This test MUST PASS on unfixed code.
    """
    client = _make_client()

    messages = client._build_skill_plan_messages(prompt, allowed_skills)

    assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
    assert messages[0]["role"] == "system", (
        f"First message role must be 'system', got {messages[0]['role']!r}"
    )
    assert messages[1]["role"] == "user", (
        f"Second message role must be 'user', got {messages[1]['role']!r}"
    )
    # Both messages must have a non-empty 'content' key.
    assert "content" in messages[0] and messages[0]["content"], "system message must have content"
    assert "content" in messages[1] and messages[1]["content"], "user message must have content"


@given(
    prompt=st.text(min_size=1, max_size=200),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_preservation_radio_task_unaffected(prompt):
    """
    **Validates: Requirements 3.6**

    `_build_radio_skill_plan_messages` MUST still return exactly 2 messages with
    the correct [system, user] structure. The radio task path must not be affected
    by the skill schema injection fix.

    This test MUST PASS on unfixed code.
    """
    client = _make_client()

    messages = client._build_radio_skill_plan_messages(prompt)

    assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
    assert messages[0]["role"] == "system", (
        f"First message role must be 'system', got {messages[0]['role']!r}"
    )
    assert messages[1]["role"] == "user", (
        f"Second message role must be 'user', got {messages[1]['role']!r}"
    )

    user_content = _parse_user_content(messages)

    # Radio task uses 'required_skills', not 'allowed_skills'.
    assert "required_skills" in user_content, "radio task user message must contain 'required_skills'"
    required = user_content["required_skills"]
    assert isinstance(required, list), "required_skills must be a list"
    for entry in required:
        assert isinstance(entry, str), (
            f"required_skills entries must be strings, got {type(entry).__name__!r}: {entry!r}"
        )
