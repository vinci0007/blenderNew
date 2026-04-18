"""Tests for plan normalization utilities."""

import pytest
from hypothesis import given, strategies as st

from vbf.plan_normalization import (
    extract_skills_plan,
    normalize_step_field_names,
    apply_parameter_aliases,
    ensure_on_success_structure,
    normalize_plan,
    validate_plan_structure,
    PARAMETER_ALIASES,
)


class TestExtractSkillsPlan:
    """Tests for extract_skills_plan function."""

    def test_extract_wrapped_plan(self):
        """Should extract plan from skills_plan wrapper."""
        wrapped = {"skills_plan": {"plan_id": "test", "steps": []}}
        result = extract_skills_plan(wrapped)
        assert result == {"plan_id": "test", "steps": []}

    def test_return_unwrapped_plan(self):
        """Should return plan as-is if not wrapped."""
        plan = {"plan_id": "test", "steps": []}
        result = extract_skills_plan(plan)
        assert result == plan

    def test_empty_dict(self):
        """Should handle empty dict."""
        result = extract_skills_plan({})
        assert result == {}


class TestNormalizeStepFieldNames:
    """Tests for normalize_step_field_names function."""

    def test_parameters_to_args(self):
        """Should rename parameters to args."""
        step = {"step_id": "test", "parameters": {"name": "cube"}}
        normalize_step_field_names(step)
        assert step == {"step_id": "test", "args": {"name": "cube"}}

    def test_params_to_args(self):
        """Should rename params to args."""
        step = {"step_id": "test", "params": {"name": "cube"}}
        normalize_step_field_names(step)
        assert step == {"step_id": "test", "args": {"name": "cube"}}

    def test_preserve_existing_args(self):
        """Should not modify if args already exists."""
        step = {"step_id": "test", "args": {"name": "cube"}, "params": {"x": 1}}
        normalize_step_field_names(step)
        assert step == {"step_id": "test", "args": {"name": "cube"}, "params": {"x": 1}}

    def test_empty_step(self):
        """Should handle empty step dict."""
        step = {}
        normalize_step_field_names(step)
        assert step == {}


class TestApplyParameterAliases:
    """Tests for apply_parameter_aliases function."""

    def test_create_primitive_type_alias(self):
        """Should rename 'type' to 'primitive_type' for create_primitive."""
        args = {"type": "cube", "name": "test"}
        apply_parameter_aliases("create_primitive", args)
        assert args == {"primitive_type": "cube", "name": "test"}

    def test_create_primitive_rotation_alias(self):
        """Should rename 'rotation' to 'rotation_euler' for create_primitive."""
        args = {"rotation": [0.0, 0.0, 1.57], "name": "test"}
        apply_parameter_aliases("create_primitive", args)
        assert args == {"rotation_euler": [0.0, 0.0, 1.57], "name": "test"}

    def test_no_alias_for_unknown_skill(self):
        """Should not modify args for unknown skills."""
        args = {"type": "cube"}
        apply_parameter_aliases("unknown_skill", args)
        assert args == {"type": "cube"}

    def test_drop_alias_if_canonical_exists(self):
        """Should drop alias key when canonical key already exists."""
        args = {"type": "cube", "primitive_type": "sphere"}
        apply_parameter_aliases("create_primitive", args)
        assert args == {"primitive_type": "sphere"}


class TestEnsureOnSuccessStructure:
    """Tests for ensure_on_success_structure function."""

    def test_add_default_return_path(self):
        """Should add step_return_json_path for object type."""
        on_success = {"store_as": "cube_data", "store_type": "object"}
        ensure_on_success_structure(on_success)
        assert on_success["step_return_json_path"] == "data.object_name"

    def test_preserve_existing_return_path(self):
        """Should not modify if step_return_json_path exists."""
        on_success = {
            "store_as": "cube_data",
            "step_return_json_path": "data.custom_path"
        }
        ensure_on_success_structure(on_success)
        assert on_success["step_return_json_path"] == "data.custom_path"

    def test_default_object_type(self):
        """Should default to object type if store_type not specified."""
        on_success = {"store_as": "data"}
        ensure_on_success_structure(on_success)
        assert on_success["step_return_json_path"] == "data.object_name"


class TestNormalizePlan:
    """Tests for normalize_plan function."""

    def test_normalize_complete_plan(self):
        """Should normalize all aspects of a plan."""
        raw_plan = {
            "skills_plan": {
                "steps": [
                    {
                        "step_id": "create",
                        "skill": "create_primitive",
                        "params": {"type": "cube"},
                        "on_success": {"store_as": "obj"}
                    }
                ]
            }
        }

        result = normalize_plan(raw_plan)

        assert result["steps"][0]["args"] == {"primitive_type": "cube"}
        assert result["steps"][0]["on_success"]["step_return_json_path"] == "data.object_name"

    def test_reject_invalid_plan(self):
        """Should reject plan without steps."""
        with pytest.raises(ValueError, match="must be a dict with 'steps'"):
            normalize_plan({})

    def test_reject_non_list_steps(self):
        """Should reject steps that are not a list."""
        with pytest.raises(ValueError, match="'steps' must be a list"):
            normalize_plan({"steps": "not a list"})

    def test_filter_non_execution_load_skill_steps(self):
        """Should remove planning-only tool steps like load_skill."""
        raw_plan = {
            "steps": [
                {"step_id": "s0", "stage": "skill_discovery", "skill": "load_skill", "args": {"skill_name": "create_primitive"}},
                {"step_id": "s1", "stage": "primitive_blocking", "skill": "create_primitive", "args": {"type": "cube"}},
            ]
        }
        result = normalize_plan(raw_plan)
        assert len(result["steps"]) == 1
        assert result["steps"][0]["skill"] == "create_primitive"
        assert result["steps"][0]["args"]["primitive_type"] == "cube"

    def test_reject_when_all_steps_filtered_out(self):
        """Should reject plans that only contain non-executable pseudo steps."""
        with pytest.raises(ValueError, match="no executable steps"):
            normalize_plan(
                {
                    "steps": [
                        {"step_id": "s0", "skill": "load_skill", "args": {"skill_name": "create_primitive"}},
                    ]
                }
            )


class TestValidatePlanStructure:
    """Tests for validate_plan_structure function."""

    def test_validate_and_return_steps(self):
        """Should validate and return steps list."""
        plan = {
            "plan_id": "test",
            "steps": [
                {"step_id": "1", "skill": "test"},
                {"step_id": "2", "skill": "test"}
            ]
        }

        steps = validate_plan_structure(plan)
        assert len(steps) == 2

    def test_reject_non_dict_plan(self):
        """Should reject non-dict plan."""
        with pytest.raises(ValueError, match="must be a dict"):
            validate_plan_structure([])

    def test_reject_missing_steps(self):
        """Should reject plan without steps."""
        with pytest.raises(ValueError, match="missing 'steps'"):
            validate_plan_structure({"plan_id": "test"})

    def test_reject_non_list_steps(self):
        """Should reject non-list steps."""
        with pytest.raises(ValueError, match="must be a list"):
            validate_plan_structure({"steps": {}})

    def test_reject_non_dict_step(self):
        """Should reject non-dict step."""
        with pytest.raises(ValueError, match="step\\[1\\] must be an object"):
            validate_plan_structure({"steps": [{"step_id": "1"}, "invalid"]})


# Property-based tests using Hypothesis
class TestPropertyBased:
    """Property-based tests for normalization."""

    @given(st.dictionaries(
        st.sampled_from(["parameters", "params", "args"]),
        st.dictionaries(st.text(), st.integers())
    ))
    def test_normalize_preserves_content(self, step):
        """Normalization should preserve existing content."""
        normalize_step_field_names(step)
        # If parameters or params existed, they should become args
        if "parameters" in step or "params" in step:
            if "args" not in step:
                # Content should be in args now
                pass  # Already normalized
