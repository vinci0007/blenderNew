import pytest

from vbf.app.client import VBFClient


class _CompressionAdapter:
    def get_skill_description(self, skill_name: str):
        return skill_name.replace("_", " ")


@pytest.mark.asyncio
async def test_two_stage_planning_merges_and_reindexes_refs(monkeypatch):
    client = VBFClient()

    async def _fake_plan(prompt, allowed_skills, save_path):
        if "STAGE 1 / GEOMETRY ONLY" in prompt:
            return (
                {"vbf_version": "2.1", "plan_type": "skills_plan", "steps": []},
                [
                    {"step_id": "001", "skill": "create_primitive", "args": {"type": "cube"}},
                    {"step_id": "002", "skill": "create_primitive", "args": {"type": "cube"}},
                ],
            )
        if "STAGE 2 / PRESENTATION ONLY" in prompt:
            return (
                {"vbf_version": "2.1", "plan_type": "skills_plan", "steps": []},
                [
                    {"step_id": "001", "skill": "create_light", "args": {"light_type": "AREA"}},
                    {
                        "step_id": "002",
                        "skill": "set_parent",
                        "args": {"child_name": {"$ref": "step_001.data.object_name"}},
                    },
                ],
            )
        raise AssertionError("unexpected prompt")

    monkeypatch.setattr(client, "_plan_skill_task", _fake_plan)

    plan, steps = await client._plan_skill_task_two_stage(
        prompt="create futuristic phone and render shot",
        allowed_skills=[
            "create_primitive",
            "set_parent",
            "create_light",
            "set_render_resolution",
            "assign_material",
        ],
        save_path="vbf/cache/task_state.json",
    )

    assert plan["metadata"]["planning_mode"] == "two_stage"
    assert [s["step_id"] for s in steps] == ["001", "002", "003", "004"]
    assert steps[3]["args"]["child_name"]["$ref"] == "step_003.data.object_name"


def test_two_stage_planning_can_be_forced_off(monkeypatch):
    client = VBFClient()
    monkeypatch.setenv("VBF_TWO_STAGE_PLANNING", "never")
    assert client._should_use_two_stage_planning("x" * 4000, ["a"] * 500) is False


@pytest.mark.asyncio
async def test_requirement_assessment_failure_does_not_fallback_to_other_planning_modes(monkeypatch):
    client = VBFClient()

    async def _fail_adaptive(prompt, allowed_skills, save_path):
        raise RuntimeError("requirement_assessment_failed_no_local_fallback: timeout")

    async def _unexpected_single(prompt, allowed_skills, save_path):
        raise AssertionError("single-stage planning should not run after assessment failure")

    monkeypatch.setattr(client, "_plan_skill_task_adaptive_staged", _fail_adaptive)
    monkeypatch.setattr(client, "_plan_skill_task", _unexpected_single)
    monkeypatch.setattr("vbf.app.client.load_llm_section", lambda: {"planning_mode": "adaptive_staged"})

    with pytest.raises(RuntimeError, match="requirement_assessment_failed_no_local_fallback"):
        await client._plan_skill_task_auto(
            "Create a product model",
            ["create_primitive"],
            "vbf/cache/task_state.json",
        )


def test_capability_compression_keeps_required_skills_with_tiny_budget(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {
            "planning_context": {
                "compression_mode": "capability_coverage",
                "target_prompt_budget_chars": 1,
                "allow_full_skill_fallback": False,
            }
        },
    )
    allowed_skills = [
        "bake_animation",
        "cloth_add",
        "fluid_bake",
        "create_primitive",
        "create_beveled_box",
        "boolean_tool",
        "add_modifier_bevel",
        "set_parent",
        "create_collection",
        "link_to_collection",
        "move_object",
        "scale_object",
        "recalculate_normals",
        "remove_doubles",
    ]

    subset = client._derive_skill_subset(
        _CompressionAdapter(),
        "Create a hard surface smartphone chassis with USB-C cutouts and camera lens holes",
        allowed_skills,
        size=1,
    )

    assert "create_beveled_box" in subset
    assert "boolean_tool" in subset
    assert "set_parent" in subset
    assert "bake_animation" not in subset
    assert "cloth_add" not in subset


def test_capability_compression_removes_geometry_high_risk_from_uv_stage(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {
            "planning_context": {
                "compression_mode": "capability_coverage",
                "target_prompt_budget_chars": 1,
                "allow_full_skill_fallback": False,
            }
        },
    )
    allowed_skills = [
        "create_beveled_box",
        "boolean_tool",
        "add_modifier_boolean",
        "mark_seam",
        "unwrap_mesh",
        "pack_uv_islands",
        "create_material_pbr",
        "assign_material",
        "set_parent",
        "move_object",
    ]

    subset = client._derive_skill_subset(
        _CompressionAdapter(),
        "ADAPTIVE STAGE / UV TEXTURE MATERIAL. Add UV unwrap and PBR material",
        allowed_skills,
        size=1,
    )

    assert "mark_seam" in subset
    assert "unwrap_mesh" in subset
    assert "assign_material" in subset
    assert "boolean_tool" not in subset
    assert "add_modifier_boolean" not in subset


def test_capability_compression_reports_missing_required_capability(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {
            "planning_context": {
                "compression_mode": "capability_coverage",
                "target_prompt_budget_chars": 100,
                "allow_full_skill_fallback": False,
            }
        },
    )

    with pytest.raises(ValueError, match="planning_context_missing_required_capability"):
        client._derive_skill_subset(
            _CompressionAdapter(),
            "ADAPTIVE STAGE / ANIMATION. Animate a falling phone",
            ["create_primitive", "set_parent"],
            size=1,
        )


def test_adaptive_stage_prompt_lists_required_capability_boundaries():
    client = VBFClient()
    prompt = client._build_adaptive_stage_prompt(
        "Create a hard surface smartphone with USB-C cutouts",
        "geometry_modeling",
    )

    assert "Required capabilities for this stage" in prompt
    assert "primitive_creation" in prompt
    assert "mesh_cleanup" in prompt
    assert "beveled_chassis" not in prompt
    assert "boolean_cutouts" not in prompt
    assert "Keep compact schemas/argument names exact" in prompt


def test_required_capabilities_do_not_special_case_product_keywords():
    client = VBFClient()

    caps = client._required_capabilities_for_stage(
        "geometry_modeling",
        "Create a hard surface smartphone chassis with USB-C cutouts and camera lens holes",
    )

    assert caps == [
        "primitive_creation",
        "transform_alignment",
        "assembly_parenting",
        "mesh_cleanup",
    ]


def test_adaptive_stage_selection_for_cinematic_falling_phone():
    stages = VBFClient._select_adaptive_planning_stages(
        "Create a cinematic animation of a smartphone falling from the sky with materials, lighting, and render"
    )

    assert stages == [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "animation",
        "camera_render",
    ]


def test_adaptive_stage_selection_does_not_treat_phone_camera_as_render_camera():
    stages = VBFClient._select_adaptive_planning_stages(
        "Only create the model: hard surface smartphone with rear camera island and lens cutouts, focusing only on geometry"
    )

    assert stages == ["geometry_modeling"]


def test_adaptive_stage_selection_geometry_only_ignores_style_and_contract_terms():
    prompt = (
        "Current Blender scene state:\n"
        "- Cube\n\n"
        "--- USER REQUEST ---\n"
        "Create a photorealistic hard surface model with precise engineering details. "
        "Only create the model: hard surface smartphone focusing ONLY on geometry and clean topology.\n\n"
        "Planning constraints:\n"
        "- Generate coherent modeling steps.\n"
        f"{VBFClient._modeling_quality_contract()}"
    )

    assert VBFClient._select_adaptive_planning_stages(prompt) == ["geometry_modeling"]
    assert VBFClient._infer_planning_stage(prompt) == "geometry_modeling"


def test_adaptive_stage_selection_geometry_only_does_not_override_explicit_rendering():
    stages = VBFClient._select_adaptive_planning_stages(
        "Do not only create the model; also add PBR materials, lighting, animation, and render a cinematic shot"
    )

    assert stages == [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "animation",
        "camera_render",
    ]
    assert VBFClient._infer_planning_stage("geometry only, but add PBR materials") == "uv_texture_material"
    assert VBFClient._infer_planning_stage("geometry only, but render a cinematic shot") == "camera_render"


def test_stage_intent_respects_explicit_model_plus_material_scope():
    intent = VBFClient._analyze_stage_intent(
        "Only create the model and add clean PBR materials; no animation or final render"
    )

    assert intent.stages == ["geometry_modeling", "uv_texture_material"]
    assert intent.primary_stage == "uv_texture_material"
    assert intent.explicit_scope == "explicit_limited"
    assert intent.has_conflict is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Build geometry only, no materials or render",
        "Please just model the object, no texturing, lighting, or rendering",
        "只建模，不要材质和渲染",
        "仅做几何结构和拓扑",
    ],
)
def test_stage_intent_accepts_varied_geometry_only_phrasings(prompt):
    intent = VBFClient._analyze_stage_intent(prompt)

    assert intent.stages == ["geometry_modeling"]
    assert intent.primary_stage == "geometry_modeling"


def test_stage_intent_accepts_non_english_limited_material_scope():
    intent = VBFClient._analyze_stage_intent("只做模型，加基础材质，不要渲染")

    assert intent.stages == ["geometry_modeling", "uv_texture_material"]
    assert intent.primary_stage == "uv_texture_material"


def test_stage_intent_keeps_render_stage_when_scope_conflicts():
    intent = VBFClient._analyze_stage_intent(
        "Only create the model, but render a cinematic product shot to verify the silhouette"
    )

    assert intent.stages == [
        "geometry_modeling",
        "environment_lighting",
        "camera_render",
    ]
    assert intent.primary_stage == "camera_render"
    assert intent.has_conflict is True
    assert intent.confidence < 0.8


def test_stage_intent_inferrs_finished_visual_without_literal_render_word():
    intent = VBFClient._analyze_stage_intent(
        "Create a marketing-ready product visualization of a foldable phone"
    )

    assert intent.stages == [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "camera_render",
    ]
    assert intent.confidence < 0.8


def test_stage_intent_preserves_more_stages_for_ambiguous_polished_request():
    intent = VBFClient._analyze_stage_intent(
        "Create a complete polished sci-fi headset"
    )

    assert intent.stages == [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "camera_render",
    ]
    assert intent.explicit_scope == "ambiguous_preserved"
    assert intent.confidence < 0.6


def test_stage_intent_respects_explicit_exclusions_in_finished_visual_request():
    intent = VBFClient._analyze_stage_intent(
        "Create a final product visual of a smartwatch, but without animation or final render"
    )

    assert intent.stages == [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
    ]
    assert "camera_render" not in intent.stages
    assert "animation" not in intent.stages


def test_stage_intent_infers_showcase_stages_when_scope_is_not_explicit():
    intent = VBFClient._analyze_stage_intent(
        "Create a photorealistic smartphone showcase scene"
    )

    assert intent.stages == [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "camera_render",
    ]
    assert intent.explicit_scope == "explicit_multistage"


def test_adaptive_stage_selection_does_not_treat_generic_set_as_lighting():
    stages = VBFClient._select_adaptive_planning_stages(
        "Create a clean product model and set parent relationships between the chassis and buttons"
    )

    assert stages == ["geometry_modeling"]


def test_capability_compression_respects_requested_topk(monkeypatch):
    client = VBFClient()
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {
            "planning_context": {
                "compression_mode": "capability_coverage",
                "target_prompt_budget_chars": 18000,
                "allow_full_skill_fallback": False,
            }
        },
    )
    required = []
    for cap in (
        "primitive_creation",
        "beveled_chassis",
        "boolean_cutouts",
        "assembly_parenting",
        "transform_alignment",
        "mesh_cleanup",
    ):
        required.extend(VBFClient._capability_skill_map()[cap])
    allowed_skills = list(dict.fromkeys(required + [f"extra_skill_{idx}" for idx in range(160)]))

    subset = client._derive_skill_subset(
        _CompressionAdapter(),
        "Only create the model: smartphone geometry only with USB-C cutouts and camera lens holes",
        allowed_skills,
        size=60,
    )

    assert len(subset) == 60


def test_replan_stage_inference_prefers_failed_geometry_skill_over_quality_contract():
    prompt = (
        "REPLAN FROM CURRENT SCENE STATE\n"
        "Current skill: boolean_tool\n"
        f"{VBFClient._modeling_quality_contract()}"
    )

    assert VBFClient._infer_planning_stage(prompt) == "geometry_modeling"


@pytest.mark.asyncio
async def test_adaptive_staged_planning_runs_stage_specific_skill_sets(monkeypatch):
    client = VBFClient()
    calls = []

    async def _fake_plan(prompt, allowed_skills, save_path):
        calls.append({"prompt": prompt, "skills": list(allowed_skills)})
        return (
            {"vbf_version": "2.1", "plan_type": "skills_plan", "steps": []},
            [{"step_id": "001", "skill": allowed_skills[0], "args": {}}],
        )

    monkeypatch.setattr(client, "_plan_skill_task", _fake_plan)

    async def _fake_assess(prompt):
        return VBFClient._analyze_stage_intent(prompt)

    monkeypatch.setattr(client, "_assess_adaptive_stage_intent", _fake_assess)
    plan, steps = await client._plan_skill_task_adaptive_staged(
        prompt="Create a cinematic phone falling animation with materials and lighting render",
        allowed_skills=[
            "create_primitive",
            "boolean_tool",
            "assign_material",
            "mark_seam",
            "insert_keyframe",
            "set_frame_range",
            "create_light",
            "set_render_engine",
            "render_image",
            "set_parent",
        ],
        save_path="vbf/cache/task_state.json",
    )

    assert plan["metadata"]["planning_mode"] == "adaptive_staged"
    assert len(steps) == 5
    assert {step["adaptive_stage"] for step in steps} == {
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "animation",
        "camera_render",
    }
    assert any("ADAPTIVE STAGE / ANIMATION" in call["prompt"] for call in calls)
    animation_call = next(call for call in calls if "ADAPTIVE STAGE / ANIMATION" in call["prompt"])
    assert "insert_keyframe" in animation_call["skills"]
    assert "assign_material" not in animation_call["skills"]


@pytest.mark.asyncio
async def test_requirement_assessment_uses_llm_stage_decision(monkeypatch):
    client = VBFClient()

    class _Adapter:
        def format_messages(self, prompt, skills_subset=None):
            return [{"role": "user", "content": prompt}]

    async def _fake_adapter():
        return _Adapter()

    monkeypatch.setattr(client, "_ensure_adapter", _fake_adapter)

    async def _fake_call(messages):
        assert "Assess the user's Blender task requirements" in messages[1]["content"]
        assert "Local heuristic fallback" not in messages[1]["content"]
        return {
            "requested_stages": [
                "geometry_modeling",
                "uv_texture_material",
                "environment_lighting",
                "camera_render",
            ],
            "excluded_stages": [],
            "deliverable_level": "render_output",
            "explicit_scope": False,
            "confidence": 0.88,
            "reason": "User asks for a client-facing product visual.",
            "risks": [],
        }

    monkeypatch.setattr(client, "_adapter_call", _fake_call)
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {"requirement_assessment": {"mode": "always", "timeout_seconds": 5}},
    )

    intent = await client._assess_adaptive_stage_intent("Make it client-presentation quality")

    assert intent.stages == [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "camera_render",
    ]
    assert intent.explicit_scope == "llm_inferred"


@pytest.mark.asyncio
async def test_requirement_assessment_no_local_fallback_raises_on_llm_failure(monkeypatch):
    client = VBFClient()

    async def _fake_call(messages):
        raise TimeoutError("assessment timeout")

    monkeypatch.setattr(client, "_adapter_call", _fake_call)
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {
            "requirement_assessment": {
                "mode": "always",
                "timeout_seconds": 5,
                "enable_local_fallback": False,
            }
        },
    )

    with pytest.raises(RuntimeError, match="requirement_assessment_failed_no_local_fallback"):
        await client._assess_adaptive_stage_intent("Only create the model")


@pytest.mark.asyncio
async def test_requirement_assessment_local_fallback_can_be_enabled(monkeypatch):
    client = VBFClient()

    async def _fake_call(messages):
        raise AssertionError("LLM should be skipped when local fallback is explicitly enabled and confident")

    monkeypatch.setattr(client, "_adapter_call", _fake_call)
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {
            "requirement_assessment": {
                "mode": "auto",
                "enable_local_fallback": True,
                "use_llm_when_confidence_below": 0.95,
            }
        },
    )

    intent = await client._assess_adaptive_stage_intent("Only create the model")

    assert intent.stages == ["geometry_modeling"]
    assert intent.explicit_scope == "geometry_only"


@pytest.mark.asyncio
async def test_requirement_assessment_low_confidence_preserves_downstream_stages(monkeypatch):
    client = VBFClient()

    class _Adapter:
        def format_messages(self, prompt, skills_subset=None):
            return [{"role": "user", "content": prompt}]

    async def _fake_adapter():
        return _Adapter()

    monkeypatch.setattr(client, "_ensure_adapter", _fake_adapter)

    async def _fake_call(messages):
        return {
            "requested_stages": ["geometry_modeling"],
            "excluded_stages": [],
            "deliverable_level": "ambiguous",
            "explicit_scope": False,
            "confidence": 0.42,
            "reason": "Ambiguous deliverable.",
            "risks": ["User may expect final presentation."],
        }

    monkeypatch.setattr(client, "_adapter_call", _fake_call)
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {"requirement_assessment": {"mode": "always", "timeout_seconds": 5}},
    )

    intent = await client._assess_adaptive_stage_intent("Create a premium device concept")

    assert intent.stages == [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "camera_render",
    ]
    assert intent.explicit_scope == "llm_low_confidence_preserved"


@pytest.mark.asyncio
async def test_requirement_assessment_simple_model_request_prefers_geometry(monkeypatch):
    client = VBFClient()

    async def _fake_call(messages):
        return {
            "requested_stages": ["geometry_modeling", "uv_texture_material", "environment_lighting"],
            "excluded_stages": [],
            "deliverable_level": "ambiguous",
            "explicit_scope": False,
            "confidence": 0.82,
            "reason": "Over-preserved downstream stages.",
            "risks": [],
        }

    monkeypatch.setattr(client, "_adapter_call", _fake_call)
    monkeypatch.setattr(
        "vbf.app.client.load_llm_section",
        lambda: {
            "requirement_assessment": {
                "mode": "always",
                "timeout_seconds": 5,
                "prefer_geometry_for_simple_model_requests": True,
            }
        },
    )

    intent = await client._assess_adaptive_stage_intent("制作一个沙发3D模型")

    assert intent.stages == ["geometry_modeling"]
    assert intent.explicit_scope == "local_simple_model_guard"
