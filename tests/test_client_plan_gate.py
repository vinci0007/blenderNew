import pytest
from unittest.mock import AsyncMock

from vbf.app.client import VBFClient
from vbf.app.plan_gate import (
    build_prior_object_table,
    matches_expected_type,
    validate_and_repair_parent_refs,
)
from vbf.core.plan_normalization import normalize_plan


class _SchemaAdapter:
    def format_messages(self, prompt: str, skills_subset=None):
        return [{"role": "user", "content": prompt}]

    def get_skill_description(self, skill_name: str):
        return skill_name

    def get_skill_params(self, skill_name: str):
        if skill_name == "create_primitive":
            return {
                "primitive_type": {"required": True, "type": "str", "default": None},
                "name": {"required": False, "type": "str", "default": None},
                "location": {"required": False, "type": "list", "default": None},
                "rotation_euler": {"required": False, "type": "list", "default": None},
                "scale": {"required": False, "type": "list", "default": None},
                "size": {"required": False, "type": "list", "default": None},
                "radius": {"required": False, "type": "float", "default": None},
                "height": {"required": False, "type": "float", "default": None},
            }
        if skill_name == "create_beveled_box":
            return {
                "name": {"required": True, "type": "str", "default": None},
                "size": {"required": True, "type": "list", "default": None},
                "location": {"required": True, "type": "list", "default": None},
            }
        if skill_name == "create_panel":
            return {
                "name": {"required": True, "type": "str", "default": None},
                "size": {"required": True, "type": "list", "default": None},
                "location": {"required": True, "type": "list", "default": None},
            }
        if skill_name == "create_transformable_panel":
            return {
                "name": {"required": True, "type": "str", "default": None},
                "size": {"required": True, "type": "list", "default": None},
                "location": {"required": True, "type": "list", "default": None},
                "rotation_euler": {"required": False, "type": "list", "default": None},
            }
        if skill_name == "apply_transform":
            return {
                "object_name": {"required": True, "type": "str", "default": None},
                "rotation_euler": {"required": False, "type": "list", "default": None},
                "scale": {"required": False, "type": "list", "default": None},
                "location": {"required": False, "type": "list", "default": None},
            }
        if skill_name == "mark_edge_crease":
            return {
                "object_name": {"required": True, "type": "str", "default": None},
                "edges": {"required": True, "type": "list", "default": None},
                "crease_value": {"required": False, "type": "float", "default": 1.0},
            }
        if skill_name == "set_cycles_denoise":
            return {
                "enable": {"required": False, "type": "bool", "default": True},
            }
        if skill_name == "set_camera_properties":
            return {
                "camera_name": {"required": True, "type": "str", "default": None},
                "focal_length": {"required": False, "type": "float", "default": None},
                "clip_start": {"required": False, "type": "float", "default": None},
                "clip_end": {"required": False, "type": "float", "default": None},
            }
        if skill_name == "create_light":
            return {
                "light_type": {"required": True, "type": "str", "default": None},
                "name": {"required": True, "type": "str", "default": None},
                "location": {"required": True, "type": "list", "default": None},
                "rotation_euler": {"required": False, "type": "list", "default": None},
            }
        if skill_name == "create_material_simple":
            return {
                "name": {"required": True, "type": "str", "default": None},
                "base_color": {"required": True, "type": "list", "default": None},
                "roughness": {"required": False, "type": "float", "default": 0.4},
                "metallic": {"required": False, "type": "float", "default": 0.0},
            }
        return {}


def test_plan_gate_rejects_unknown_args():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"primitive_type": "cube", "bad_arg": 1},
            }
        ]
    }
    with pytest.raises(ValueError, match="plan_gate_unknown_args"):
        client._validate_plan_with_skill_schemas(plan, adapter, ["create_primitive"])


def test_plan_gate_rejects_missing_required():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"name": "cube"},
            }
        ]
    }
    with pytest.raises(ValueError, match="plan_gate_missing_required"):
        client._validate_plan_with_skill_schemas(plan, adapter, ["create_primitive"])


def test_plan_gate_autofix_drops_mark_edge_crease_without_edges():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"primitive_type": "cube"},
            },
            {
                "step_id": "002",
                "skill": "mark_edge_crease",
                "args": {"object_name": {"$ref": "step_001.data.object_name"}},
            },
        ]
    }
    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_primitive", "mark_edge_crease"],
    )

    assert len(steps) == 1
    assert steps[0]["skill"] == "create_primitive"
    assert len(plan["steps"]) == 1


def test_plan_gate_autofix_fill_create_primitive_and_drop_unknown_args():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"bad_arg": 1},
            }
        ]
    }
    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_primitive"],
    )

    assert len(steps) == 1
    assert steps[0]["args"]["primitive_type"] == "cube"
    assert "bad_arg" not in steps[0]["args"]


def test_plan_gate_list_hint_rejects_scalar_float():
    assert matches_expected_type("List[float] | None", [1.0, 2.0, 3.0])
    assert not matches_expected_type("List[float] | None", 1.0)


def test_plan_gate_autofix_create_primitive_numeric_cube_size():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {"primitive_type": "cube", "name": "Root", "size": 1.0},
            }
        ]
    }
    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_primitive"],
    )

    assert steps[0]["args"]["size"] == [1.0, 1.0, 1.0]


def test_normalize_plan_converts_create_primitive_numeric_size():
    plan = normalize_plan(
        {
            "steps": [
                {
                    "step_id": "001",
                    "skill": "create_primitive",
                    "args": {"primitive_type": "cube", "size": 1.0},
                }
            ]
        }
    )

    assert plan["steps"][0]["args"]["size"] == [1.0, 1.0, 1.0]


def test_prior_object_table_and_parent_name_repair():
    prior = build_prior_object_table(
        [
            {
                "created_objects": [
                    {
                        "step_id": "003",
                        "skill": "create_primitive",
                        "planned_name": "GEO_Turntable_Rotation_Control",
                        "object_name": "GEO_Turntable_Rotation_Control",
                    }
                ]
            }
        ]
    )
    plan = {
        "steps": [
            {
                "step_id": "014",
                "skill": "set_parent",
                "args": {
                    "child_name": {"$ref": "step_013.data.object_name"},
                    "parent_name": "Hypercar_Turntable_Control",
                    "keep_transform": True,
                },
            }
        ]
    }

    repaired = validate_and_repair_parent_refs(plan, prior)

    assert repaired == 1
    assert plan["steps"][0]["args"]["parent_name"] == "GEO_Turntable_Rotation_Control"


def test_parent_name_without_unique_match_fails_plan_gate():
    prior = [
        {"object_name": "GEO_Left_Wheel_Control"},
        {"object_name": "GEO_Right_Wheel_Control"},
    ]
    plan = {
        "steps": [
            {
                "step_id": "014",
                "skill": "set_parent",
                "args": {"child_name": "GEO_New", "parent_name": "Wheel_Control"},
            }
        ]
    }

    with pytest.raises(ValueError, match="plan_gate_unknown_parent_object"):
        validate_and_repair_parent_refs(plan, prior)


def test_plan_gate_autofix_fill_create_material_simple_base_color():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_material_simple",
                "args": {"name": "MAT_Sofa_Fabric"},
            }
        ]
    }
    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_material_simple"],
    )

    assert steps[0]["args"]["base_color"] == [0.55, 0.48, 0.40]


def test_plan_gate_autofix_create_beveled_box_dimensions_to_size():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_beveled_box",
                "args": {
                    "name": "cutout",
                    "location": [0, 0, 0],
                    "dimensions": [1.0, 2.0, 3.0],
                },
            }
        ]
    }

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_beveled_box"],
    )

    assert len(steps) == 1
    assert steps[0]["args"]["size"] == [1.0, 2.0, 3.0]
    assert "dimensions" not in steps[0]["args"]


def test_plan_gate_autofix_create_beveled_box_object_name_to_name():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_beveled_box",
                "args": {
                    "object_name": "Volume_Up_Button",
                    "size": [0.08, 0.02, 0.35],
                    "location": [-3.7, 0.0, 0.25],
                },
            }
        ]
    }

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_beveled_box"],
    )

    assert steps[0]["args"]["name"] == "Volume_Up_Button"
    assert "object_name" not in steps[0]["args"]


def test_plan_gate_splits_unsupported_rotation_to_apply_transform():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = normalize_plan(
        {
            "steps": [
                {
                    "step_id": "013",
                    "stage": "geometry_modeling",
                    "skill": "create_beveled_box",
                    "args": {
                        "object_name": "GEO_Hood_Vent",
                        "dimensions": [0.42, 0.095, 0.018],
                        "location": [0.69, 0.205, 0.435],
                        "rotation": [0.0, -0.08, 0.0],
                    },
                }
            ]
        }
    )

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_beveled_box", "apply_transform"],
    )

    assert len(steps) == 2
    assert steps[0]["skill"] == "create_beveled_box"
    assert steps[0]["args"]["name"] == "GEO_Hood_Vent"
    assert steps[0]["args"]["size"] == [0.42, 0.095, 0.018]
    assert "rotation" not in steps[0]["args"]
    assert steps[1]["skill"] == "apply_transform"
    assert steps[1]["args"]["object_name"] == {"$ref": "step_013.data.object_name"}
    assert steps[1]["args"]["rotation_euler"] == [0.0, -0.08, 0.0]


def test_plan_gate_splits_transform_args_for_generic_creation_skill():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "panel",
                "skill": "create_panel",
                "args": {
                    "name": "GEO_Generic_Panel",
                    "size": [1.0, 0.2, 0.05],
                    "location": [0.0, 0.0, 0.0],
                    "rotation_euler": [0.0, 0.0, 0.2],
                },
            }
        ]
    }

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_panel", "apply_transform"],
    )

    assert [step["skill"] for step in steps] == ["create_panel", "apply_transform"]
    assert "rotation_euler" not in steps[0]["args"]
    assert steps[1]["args"] == {
        "object_name": {"$ref": "step_panel.data.object_name"},
        "rotation_euler": [0.0, 0.0, 0.2],
    }


def test_plan_gate_schema_aliases_are_generic_for_supported_signatures():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "panel",
                "skill": "create_transformable_panel",
                "args": {
                    "object_name": "GEO_Generic_Panel",
                    "dimensions": [1.0, 0.2, 0.05],
                    "position": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.2],
                },
            }
        ]
    }

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_transformable_panel"],
    )

    assert steps[0]["args"] == {
        "name": "GEO_Generic_Panel",
        "size": [1.0, 0.2, 0.05],
        "location": [0.0, 0.0, 0.0],
        "rotation_euler": [0.0, 0.0, 0.2],
    }


def test_plan_gate_schema_aliases_name_to_object_name_when_signature_requires_target():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "transform",
                "skill": "apply_transform",
                "args": {
                    "name": "GEO_Generic_Panel",
                    "rotation_euler": [0.0, 0.0, 0.2],
                },
            }
        ]
    }

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["apply_transform"],
    )

    assert steps[0]["args"] == {
        "object_name": "GEO_Generic_Panel",
        "rotation_euler": [0.0, 0.0, 0.2],
    }


def test_plan_gate_autofix_aliases_stage2_parameter_names():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "set_cycles_denoise",
                "args": {"enabled": True},
            },
            {
                "step_id": "002",
                "skill": "set_camera_properties",
                "args": {"camera_name": "Camera", "lens": 85, "clip_start": 0.01},
            },
            {
                "step_id": "003",
                "skill": "create_light",
                "args": {
                    "light_type": "AREA",
                    "name": "KeyArea",
                    "location": [0, 0, 1],
                    "rotation": [0.0, 0.0, 0.0],
                },
            },
        ]
    }

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["set_cycles_denoise", "set_camera_properties", "create_light"],
    )

    assert steps[0]["args"]["enable"] is True
    assert "enabled" not in steps[0]["args"]
    assert steps[1]["args"]["focal_length"] == 85
    assert "lens" not in steps[1]["args"]
    assert steps[2]["args"]["rotation_euler"] == [0.0, 0.0, 0.0]
    assert "rotation" not in steps[2]["args"]


def test_plan_gate_autofix_handles_more_than_four_repairs():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {"step_id": "001", "skill": "set_cycles_denoise", "args": {"enabled": True}},
            {"step_id": "002", "skill": "set_cycles_denoise", "args": {"enabled": False}},
            {
                "step_id": "003",
                "skill": "set_camera_properties",
                "args": {"camera_name": "Camera", "lens": 50},
            },
            {
                "step_id": "004",
                "skill": "create_light",
                "args": {
                    "light_type": "AREA",
                    "name": "LightA",
                    "location": [0, 0, 1],
                    "rotation": [0.0, 0.0, 0.0],
                },
            },
            {
                "step_id": "005",
                "skill": "create_light",
                "args": {
                    "light_type": "AREA",
                    "name": "LightB",
                    "location": [1, 0, 1],
                    "rotation": [0.1, 0.0, 0.0],
                },
            },
        ]
    }

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["set_cycles_denoise", "set_camera_properties", "create_light"],
    )

    assert len(steps) == 5
    assert steps[0]["args"]["enable"] is True
    assert steps[1]["args"]["enable"] is False
    assert steps[2]["args"]["focal_length"] == 50
    assert steps[3]["args"]["rotation_euler"] == [0.0, 0.0, 0.0]
    assert steps[4]["args"]["rotation_euler"] == [0.1, 0.0, 0.0]


def test_plan_gate_accepts_normalized_primitive_skill_alias():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = normalize_plan(
        {
            "steps": [
                {
                    "step_id": "001",
                    "skill": "create_cylinder",
                    "args": {
                        "name": "GEO_Display_Turntable",
                        "location": [0.0, 0.0, -0.06],
                        "radius": 1.55,
                        "depth": 0.08,
                    },
                }
            ]
        }
    )

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_primitive"],
    )

    assert steps[0]["skill"] == "create_primitive"
    assert steps[0]["args"]["primitive_type"] == "cylinder"
    assert steps[0]["args"]["height"] == 0.08


def test_plan_gate_autofix_replaces_unsupported_torus_primitive():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {
                    "primitive_type": "torus",
                    "name": "GEO_Left_Front_Tire",
                    "location": [0.8, -0.5, 0.2],
                    "radius": 0.2,
                    "height": 0.08,
                },
            }
        ]
    }

    steps = client._validate_plan_with_schema_autofix(
        plan,
        adapter,
        ["create_primitive"],
    )

    assert steps[0]["args"]["primitive_type"] == "cylinder"


def test_plan_gate_rejects_unknown_primitive_type():
    client = VBFClient()
    adapter = _SchemaAdapter()
    plan = {
        "steps": [
            {
                "step_id": "001",
                "skill": "create_primitive",
                "args": {
                    "primitive_type": "plane",
                    "name": "GEO_Panel",
                    "location": [0, 0, 0],
                },
            }
        ]
    }

    with pytest.raises(ValueError, match="plan_gate_invalid_primitive_type"):
        client._validate_plan_with_schema_autofix(
            plan,
            adapter,
            ["create_primitive"],
        )


@pytest.mark.asyncio
async def test_plan_skill_task_expands_subset_on_plan_gate_error(monkeypatch):
    client = VBFClient()
    adapter = _SchemaAdapter()
    monkeypatch.setattr(client, "_ensure_adapter", AsyncMock(return_value=adapter))
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {
            "planning_context": {
                "compression_mode": "ranked",
                "allow_full_skill_fallback": False,
            }
        },
    )

    subsets = []

    async def _fake_call(adapter_obj, prompt, skills_subset=None):
        subsets.append(list(skills_subset or []))
        if len(subsets) <= 2:
            return {
                "steps": [
                    {
                        "step_id": "001",
                        "skill": "unknown_skill",
                        "args": {},
                    }
                ]
            }
        return {
            "steps": [
                {
                    "step_id": "001",
                    "skill": "create_primitive",
                    "args": {"primitive_type": "cube"},
                }
            ]
        }

    monkeypatch.setattr(client, "_call_plan_with_format_retry", _fake_call)

    allowed_skills = ["create_primitive"] + [f"skill_{i:03d}" for i in range(180)]
    plan, steps = await client._plan_skill_task(
        prompt="create a precise phone with bevels",
        allowed_skills=allowed_skills,
        save_path="vbf/cache/task_state.json",
    )

    assert steps[0]["skill"] == "create_primitive"
    assert steps[0]["args"]["primitive_type"] == "cube"
    assert len(subsets) == 3
    assert len(subsets[0]) < len(allowed_skills)
    assert len(subsets[-1]) > len(subsets[0])
    assert len(subsets[-1]) < len(allowed_skills)
