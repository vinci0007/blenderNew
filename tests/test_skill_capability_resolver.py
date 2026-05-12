from vbf.app.skill_capability_resolver import (
    format_skill_capability_resolution,
    parse_plan_gate_issue,
    resolve_skill_capability_issue,
)


class _Adapter:
    def __init__(self, skills):
        self.skills = skills

    def get_skill_params(self, skill_name):
        skill = self.skills.get(skill_name) or {}
        return skill.get("args")

    def get_skill_description(self, skill_name):
        skill = self.skills.get(skill_name) or {}
        return skill.get("description", "")


def _arg(required=False, type_name="Any"):
    return {"required": required, "type": type_name}


def test_parse_plan_gate_unknown_args():
    issue = parse_plan_gate_issue(
        "plan_gate_unknown_args: step[2] skill=create_box unknown=['rotation_euler']"
    )

    assert issue == {
        "kind": "unknown_args",
        "step_index": 2,
        "skill": "create_box",
        "args": ["rotation_euler"],
    }


def test_resolver_finds_registered_skill_that_supports_unknown_arg():
    adapter = _Adapter(
        {
            "create_box": {
                "description": "Create an axis-aligned box.",
                "args": {
                    "name": _arg(True, "str"),
                    "size": _arg(True, "list"),
                    "location": _arg(True, "list"),
                },
            },
            "apply_transform": {
                "description": "Apply transform values such as rotation_euler to an object.",
                "args": {
                    "object_name": _arg(True, "str"),
                    "rotation_euler": _arg(False, "list"),
                    "location": _arg(False, "list"),
                },
            },
        }
    )
    plan = {
        "steps": [
            {
                "step_id": "s1",
                "skill": "create_box",
                "args": {
                    "name": "Body",
                    "size": [1, 1, 1],
                    "location": [0, 0, 0],
                    "rotation_euler": [0, 0, 1],
                },
            }
        ]
    }

    resolution = resolve_skill_capability_issue(
        adapter=adapter,
        allowed_skills=["create_box", "apply_transform"],
        plan=plan,
        error_message=(
            "plan_gate_unknown_args: step[0] skill=create_box "
            "unknown=['rotation_euler']"
        ),
    )

    assert resolution["classification"] == "better_registered_skill_found"
    assert resolution["candidate_registered_skills"][0]["skill"] == "apply_transform"
    assert resolution["candidate_registered_skills"][0]["supports_issue_args"] == ["rotation_euler"]


def test_resolver_marks_visible_schema_violation_when_no_candidate_or_gateway():
    adapter = _Adapter(
        {
            "create_box": {
                "description": "Create an axis-aligned box.",
                "args": {
                    "name": _arg(True, "str"),
                    "size": _arg(True, "list"),
                    "location": _arg(True, "list"),
                },
            }
        }
    )
    plan = {
        "steps": [
            {
                "step_id": "s1",
                "skill": "create_box",
                "args": {"name": "Body", "size": [1, 1, 1], "location": [0, 0, 0], "bevel_mode": "wide"},
            }
        ]
    }

    resolution = resolve_skill_capability_issue(
        adapter=adapter,
        allowed_skills=["create_box"],
        plan=plan,
        error_message="plan_gate_unknown_args: step[0] skill=create_box unknown=['bevel_mode']",
    )

    assert resolution["classification"] == "current_skill_schema_violation"
    assert resolution["current_skill_schema_visible"] is True
    assert resolution["candidate_registered_skills"] == []


def test_resolver_allows_gateway_discovery_only_when_registered():
    adapter = _Adapter(
        {
            "create_box": {
                "description": "Create an axis-aligned box.",
                "args": {"name": _arg(True, "str")},
            },
            "ops_search": {"description": "Search Blender operators.", "args": {"query": _arg(True, "str")}},
            "ops_introspect": {
                "description": "Return operator signature.",
                "args": {"operator_id": _arg(True, "str")},
            },
            "ops_invoke": {"description": "Invoke operator.", "args": {"operator_id": _arg(True, "str")}},
        }
    )
    plan = {"steps": [{"step_id": "s1", "skill": "create_box", "args": {"name": "Body", "unknown": 1}}]}

    resolution = resolve_skill_capability_issue(
        adapter=adapter,
        allowed_skills=["create_box", "ops_search", "ops_introspect", "ops_invoke"],
        plan=plan,
        error_message="plan_gate_unknown_args: step[0] skill=create_box unknown=['unknown']",
    )

    assert resolution["classification"] == "no_high_level_registered_match_gateway_available"
    assert resolution["gateway"]["discovery_available"] is True
    formatted = format_skill_capability_resolution(resolution)
    assert "ops_search" in formatted
    assert "ops_introspect" in formatted
    assert "inventing a new skill" in formatted


def test_resolver_does_not_label_unparsed_gate_error_as_schema_visibility():
    adapter = _Adapter(
        {
            "create_box": {
                "description": "Create an axis-aligned box.",
                "args": {"name": _arg(True, "str")},
            }
        }
    )

    resolution = resolve_skill_capability_issue(
        adapter=adapter,
        allowed_skills=["create_box"],
        plan={"steps": [{"step_id": "s1", "skill": "create_box", "args": {"name": "Body"}}]},
        error_message="plan_gate_autofix_exhausted",
    )

    assert resolution["classification"] == "local_autofix_exhausted"
    assert resolution["current_skill_schema_visible"] is False
