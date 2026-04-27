from __future__ import annotations

import copy
import os
import re
from typing import Any, Dict, List, Set, Tuple


def build_error_signature(error_text: Any) -> str:
    text = str(error_text or "").strip().lower()
    if not text:
        return "none"
    text = re.sub(r"\s+", " ", text)
    return text[:160]


def build_json_format_retry_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "FORMAT REQUIREMENT (must follow exactly):\n"
        "- Return plain JSON only (no markdown fences).\n"
        "- Output must be a single JSON object.\n"
        "- Keep the same user intent; do not change task semantics.\n"
        "- Include top-level `steps` array with executable Blender skills.\n"
        "- `steps` must be a non-empty JSON array.\n"
        "- Do NOT return `tool_calls`, `tool_results`, or `load_skill` helper payloads."
    )


def build_nonempty_steps_rescue_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "CRITICAL RECOVERY MODE:\n"
        "- Previous responses failed because `steps` was empty or non-executable.\n"
        "- You MUST return at least 3 executable Blender skill steps.\n"
        "- Return a single JSON object with top-level `steps` array.\n"
        "- Each step must include: step_id, skill, args.\n"
        "- Do NOT return tool_calls/tool_results/load_skill.\n"
        "- If uncertain, start from create_primitive and continue with valid follow-up steps."
    )


def has_nonempty_steps(payload: Any, extract_skills_plan_fn: Any) -> bool:
    extracted = extract_skills_plan_fn(payload)
    if not isinstance(extracted, dict):
        return False
    steps = extracted.get("steps")
    return isinstance(steps, list) and len(steps) > 0


def is_tool_calls_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return False
    return all(isinstance(call, dict) and "name" in call for call in tool_calls)


def tokenize_prompt_for_skills(prompt: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9_]+", (prompt or "").lower()))


def get_core_skills() -> Set[str]:
    return {
        "create_primitive",
        "create_beveled_box",
        "add_modifier_boolean",
        "boolean_tool",
        "add_modifier_bevel",
        "apply_modifier",
        "set_parent",
        "delete_object",
        "rename_object",
        "create_camera",
        "set_camera_active",
        "create_light",
        "set_light_properties",
        "assign_material",
        "create_material_pbr",
        "set_render_engine",
        "set_render_resolution",
        "set_cycles_samples",
        "render_image",
    }


def default_planning_context() -> Dict[str, Any]:
    return {
        "compression_mode": "capability_coverage",
        "target_prompt_budget_chars": 18000,
        "allow_budget_overflow_for_required_capabilities": True,
        "allow_full_skill_fallback": False,
        "include_compact_schema_for_required": True,
        "include_compact_schema_for_high_risk": True,
    }


def get_planning_context(load_llm_section_fn: Any) -> Dict[str, Any]:
    ctx = default_planning_context()
    try:
        raw_ctx = load_llm_section_fn().get("planning_context", {})
    except Exception:
        raw_ctx = {}
    if isinstance(raw_ctx, dict):
        ctx.update(raw_ctx)
    return ctx


def default_requirement_assessment_config() -> Dict[str, Any]:
    return {
        "mode": "auto",
        "timeout_seconds": 45,
        "enable_local_fallback": False,
        "use_llm_when_confidence_below": 1.0,
        "fallback_policy": "preserve_more_stages",
        "low_confidence_threshold": 0.7,
        "prefer_geometry_for_simple_model_requests": True,
    }


def get_requirement_assessment_config(load_llm_section_fn: Any) -> Dict[str, Any]:
    cfg = default_requirement_assessment_config()
    try:
        raw_cfg = load_llm_section_fn().get("requirement_assessment", {})
    except Exception:
        raw_cfg = {}
    if isinstance(raw_cfg, dict):
        cfg.update(raw_cfg)
    return cfg


def get_planning_mode(load_llm_section_fn: Any) -> str:
    env_mode = os.getenv("VBF_PLANNING_MODE")
    if env_mode:
        return env_mode.strip().lower()
    try:
        mode = load_llm_section_fn().get("planning_mode", "adaptive_staged")
    except Exception:
        mode = "adaptive_staged"
    return str(mode or "adaptive_staged").strip().lower()


def capability_skill_map() -> Dict[str, List[str]]:
    return {
        "primitive_creation": ["create_primitive", "create_beveled_box"],
        "beveled_chassis": ["create_beveled_box", "add_modifier_bevel", "apply_modifier"],
        "boolean_cutouts": ["boolean_tool", "add_modifier_boolean", "create_primitive", "apply_modifier"],
        "assembly_parenting": ["set_parent", "create_collection", "link_to_collection"],
        "transform_alignment": ["move_object", "scale_object", "apply_transform", "move_object_anchor_to_point"],
        "mesh_cleanup": ["recalculate_normals", "remove_doubles", "fill_holes", "inset_faces", "extrude_faces"],
        "uv_unwrap": ["add_uv_map", "set_active_uv_map", "mark_seam", "unwrap_mesh", "pack_uv_islands"],
        "pbr_materials": ["create_material_pbr", "assign_material", "import_image_texture", "add_normal_map"],
        "environment_lighting": ["create_light", "set_light_properties", "create_camera", "set_camera_properties"],
        "keyframe_animation": ["set_frame_range", "set_animation_fps", "set_current_frame", "insert_keyframe"],
        "camera_tracking": ["create_camera", "set_camera_properties", "set_camera_active"],
        "camera_render": [
            "create_camera",
            "set_camera_properties",
            "set_camera_active",
            "set_render_engine",
            "set_render_resolution",
            "render_image",
        ],
    }


def high_risk_skills() -> Set[str]:
    return {
        "boolean_tool",
        "add_modifier_boolean",
        "create_beveled_box",
        "create_primitive",
        "set_parent",
        "apply_modifier",
        "ops_invoke",
    }


def high_risk_skills_for_stage(stage: str) -> Set[str]:
    if stage == "geometry_modeling":
        return high_risk_skills()
    if stage == "uv_texture_material":
        return {
            "mark_seam",
            "unwrap_mesh",
            "pack_uv_islands",
            "create_material_pbr",
            "assign_material",
            "import_image_texture",
            "add_normal_map",
        }
    if stage == "animation":
        return {
            "set_frame_range",
            "set_animation_fps",
            "set_current_frame",
            "insert_keyframe",
            "set_camera_properties",
            "set_parent",
        }
    if stage == "environment_lighting":
        return {
            "create_light",
            "set_light_properties",
            "create_camera",
            "set_camera_properties",
        }
    if stage == "camera_render":
        return {
            "create_camera",
            "set_camera_properties",
            "set_camera_active",
            "set_render_engine",
            "set_render_resolution",
            "render_image",
        }
    return set()


def global_safety_skills() -> Set[str]:
    return {
        "create_collection",
        "link_to_collection",
        "set_parent",
        "rename_object",
        "delete_object",
        "object_select_all",
        "move_object",
        "scale_object",
        "apply_transform",
        "ops_search",
        "ops_introspect",
    }


def global_safety_skills_for_stage(stage: str) -> Set[str]:
    common = {
        "object_select_all",
        "rename_object",
        "set_parent",
        "move_object",
        "scale_object",
        "apply_transform",
        "ops_search",
        "ops_introspect",
    }
    if stage == "geometry_modeling":
        return common | {"create_collection", "link_to_collection", "delete_object"}
    if stage in {"uv_texture_material", "environment_lighting", "animation", "camera_render"}:
        return common
    return common


def required_capabilities_for_stage(stage: str, prompt: str) -> List[str]:
    _ = prompt
    caps: List[str] = []
    if stage == "geometry_modeling":
        caps.extend(
            [
                "primitive_creation",
                "transform_alignment",
                "assembly_parenting",
                "mesh_cleanup",
            ]
        )
    elif stage == "uv_texture_material":
        caps.extend(["uv_unwrap", "pbr_materials"])
    elif stage == "animation":
        caps.extend(["keyframe_animation", "transform_alignment", "camera_tracking"])
    elif stage in {"environment_lighting", "camera_render"}:
        caps.extend(["environment_lighting", "camera_render"])
    else:
        caps.extend(["primitive_creation", "transform_alignment"])

    deduped: List[str] = []
    for cap in caps:
        if cap not in deduped:
            deduped.append(cap)
    return deduped


def stage_irrelevant_skill(skill: str, stage: str) -> bool:
    if stage == "geometry_modeling":
        irrelevant_prefixes = (
            "bake_", "cloth_", "fluid_", "gpencil_", "paint_", "sequencer_",
            "insert_keyframe", "delete_keyframe", "nla_", "set_render_", "render_",
            "create_light", "set_light", "create_material", "assign_material",
            "compositor_", "add_compositor", "create_shader",
        )
        return skill.startswith(irrelevant_prefixes)
    if stage == "animation":
        irrelevant_prefixes = ("cloth_", "fluid_", "paint_", "sequencer_", "compositor_")
        return skill.startswith(irrelevant_prefixes)
    if stage in {"uv_texture_material", "environment_lighting", "camera_render"}:
        irrelevant_prefixes = ("armature_", "cloth_", "fluid_", "gpencil_", "sculpt_")
        return skill.startswith(irrelevant_prefixes)
    return False


def rank_skills_for_prompt(
    adapter: Any,
    prompt: str,
    allowed_skills: List[str],
) -> List[str]:
    tokens = tokenize_prompt_for_skills(prompt)
    core = get_core_skills()

    scored: List[Tuple[int, str]] = []
    for idx, skill in enumerate(allowed_skills):
        score = 0
        skill_tokens = set(re.findall(r"[a-z0-9_]+", skill.lower()))
        if skill in core:
            score += 60
        if skill_tokens & tokens:
            score += 40
        try:
            desc = adapter.get_skill_description(skill) or ""
        except Exception:
            desc = ""
        desc_tokens = set(re.findall(r"[a-z0-9_]+", desc.lower()))
        overlap = len(desc_tokens & tokens)
        score += min(overlap, 8) * 3
        scored.append((score * 1000 - idx, skill))

    scored.sort(reverse=True)
    ranked = [skill for _, skill in scored]
    for skill in allowed_skills:
        if skill in core and skill not in ranked:
            ranked.append(skill)
    return ranked


def derive_capability_covered_skill_subset(
    adapter: Any,
    prompt: str,
    allowed_skills: List[str],
    size: int,
    stage: str,
    context: Dict[str, Any],
) -> List[str]:
    allowed_set = set(allowed_skills)
    required_caps = required_capabilities_for_stage(stage, prompt)
    cap_map = capability_skill_map()

    required_skills: Set[str] = set()
    for cap in required_caps:
        candidates = [skill for skill in cap_map.get(cap, []) if skill in allowed_set]
        if candidates:
            required_skills.update(candidates)

    required_skills.update(skill for skill in high_risk_skills_for_stage(stage) if skill in allowed_set)
    required_skills.update(skill for skill in global_safety_skills_for_stage(stage) if skill in allowed_set)

    ranked = rank_skills_for_prompt(adapter, prompt, allowed_skills)
    budget_chars = int(context.get("target_prompt_budget_chars", 18000) or 18000)
    estimated_schema_chars = max(1, int(context.get("estimated_schema_chars_per_skill", 120) or 120))
    soft_skill_budget = max(len(required_skills), min(size, budget_chars // estimated_schema_chars))

    selected: Set[str] = set(required_skills)
    for skill in ranked:
        if skill in selected:
            continue
        if stage_irrelevant_skill(skill, stage):
            continue
        if len(selected) >= soft_skill_budget:
            break
        selected.add(skill)

    missing_caps = [
        cap for cap in required_caps
        if not any(skill in selected for skill in cap_map.get(cap, []))
    ]
    if missing_caps:
        raise ValueError(
            "planning_context_missing_required_capability: "
            + ", ".join(missing_caps)
        )

    print(
        "[VBF] planning_context "
        f"mode=capability_coverage stage={stage} "
        f"required_capabilities={len(required_caps)} "
        f"skills={len(selected)} budget_chars={budget_chars}"
    )
    return [skill for skill in allowed_skills if skill in selected]


def derive_skill_subset(
    adapter: Any,
    prompt: str,
    allowed_skills: List[str],
    size: int,
    stage: str,
    context: Dict[str, Any],
) -> List[str]:
    if context.get("compression_mode") == "capability_coverage":
        return derive_capability_covered_skill_subset(
            adapter,
            prompt,
            allowed_skills,
            size,
            stage,
            context,
        )

    if size >= len(allowed_skills):
        return list(allowed_skills)
    ranked = rank_skills_for_prompt(adapter, prompt, allowed_skills)
    picked = ranked[:size]
    core = get_core_skills()
    for skill in allowed_skills:
        if skill in core and skill not in picked:
            picked.append(skill)
    allowed_set = set(picked)
    return [s for s in allowed_skills if s in allowed_set]


def should_use_two_stage_planning(prompt: str, allowed_skills: List[str]) -> bool:
    mode = os.getenv("VBF_TWO_STAGE_PLANNING", "auto").strip().lower()
    if mode in {"1", "true", "on", "always"}:
        return True
    if mode in {"0", "false", "off", "never"}:
        return False
    return len(prompt) >= 700 or len(allowed_skills) >= 180


def classify_skills_for_two_stage(
    allowed_skills: List[str],
) -> Tuple[List[str], List[str]]:
    presentation_prefixes = (
        "create_camera",
        "set_camera",
        "camera_",
        "create_light",
        "set_light",
        "set_render",
        "set_cycles",
        "set_eevee",
        "render_",
        "create_material",
        "assign_material",
        "add_shader_",
        "set_material_",
        "add_texture",
        "attach_texture",
        "create_image_texture",
        "compositor_",
        "create_compositor",
        "set_compositor",
        "enable_pass",
    )
    presentation_exact = {
        "object_shade_smooth",
        "shade_smooth",
        "shade_flat",
        "object_shade_flat",
    }
    presentation: List[str] = []
    geometry: List[str] = []
    for skill in allowed_skills:
        if skill in presentation_exact or skill.startswith(presentation_prefixes):
            presentation.append(skill)
        else:
            geometry.append(skill)
    return geometry, presentation


def build_geometry_stage_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "PLANNING MODE: STAGE 1 / GEOMETRY ONLY.\n"
        "- Focus on topology, proportions, booleans, bevel/chamfer, assembly geometry.\n"
        "- Do not spend steps on final rendering polish.\n"
        "- Camera/light/material/compositor steps are allowed only if strictly required for geometry inspection.\n"
        "- Return executable VBF skills JSON only."
    )


def build_presentation_stage_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "PLANNING MODE: STAGE 2 / PRESENTATION ONLY.\n"
        "- Reuse existing geometry in scene.\n"
        "- Focus on camera, lights, materials, render, compositor.\n"
        "- Keep geometry edits minimal and local.\n"
        "- Do not use $ref to steps from stage 1. If relationships are needed, use existing object names "
        "or create local helper objects in this stage first.\n"
        "- Return executable VBF skills JSON only."
    )


def remap_ref_text(ref: str, id_map: Dict[str, str]) -> str:
    match = re.match(r"^(step_)?([A-Za-z0-9_-]+)(\..+)$", ref)
    if not match:
        return ref
    prefix, step_id, suffix = match.groups()
    mapped = id_map.get(step_id)
    if not mapped:
        return ref
    return f"{'step_' if prefix else ''}{mapped}{suffix}"


def remap_ref_value(value: Any, id_map: Dict[str, str]) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, nested in value.items():
            if key == "$ref" and isinstance(nested, str):
                out[key] = remap_ref_text(nested, id_map)
            else:
                out[key] = remap_ref_value(nested, id_map)
        return out
    if isinstance(value, list):
        return [remap_ref_value(item, id_map) for item in value]
    if isinstance(value, str) and value.startswith("$ref:"):
        ref = value[len("$ref:"):].strip()
        remapped = remap_ref_text(ref, id_map)
        return f"$ref: {remapped}"
    return value


def reindex_steps(
    steps: List[Dict[str, Any]],
    start_index: int,
) -> List[Dict[str, Any]]:
    remapped_steps = copy.deepcopy(steps)
    id_map: Dict[str, str] = {}
    for idx, step in enumerate(remapped_steps, start=start_index):
        old_id = step.get("step_id", f"{idx:03d}")
        old_id_str = str(old_id)
        normalized_old = old_id_str[len("step_"):] if old_id_str.startswith("step_") else old_id_str
        new_id = f"{idx:03d}"
        id_map[old_id_str] = new_id
        id_map[normalized_old] = new_id
        step["step_id"] = new_id

    for step in remapped_steps:
        for key, value in list(step.items()):
            step[key] = remap_ref_value(value, id_map)
    return remapped_steps


def merge_two_stage_plans(
    geom_plan: Dict[str, Any],
    geom_steps: List[Dict[str, Any]],
    pres_plan: Dict[str, Any],
    pres_steps: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    remapped_geom = reindex_steps(geom_steps, 1)
    remapped_pres = reindex_steps(pres_steps, len(remapped_geom) + 1)
    merged_steps = remapped_geom + remapped_pres

    merged_plan: Dict[str, Any] = {
        "vbf_version": geom_plan.get("vbf_version", pres_plan.get("vbf_version", "2.1")),
        "plan_type": "skills_plan",
        "steps": merged_steps,
        "execution": {
            "max_replans": max(
                int(geom_plan.get("execution", {}).get("max_replans", 5)),
                int(pres_plan.get("execution", {}).get("max_replans", 5)),
            )
        },
        "metadata": {
            "planning_mode": "two_stage",
            "geometry_steps": len(remapped_geom),
            "presentation_steps": len(remapped_pres),
        },
    }
    return merged_plan, merged_steps


def build_adaptive_stage_prompt(
    prompt: str,
    stage: str,
    modeling_quality_contract: str,
) -> str:
    stage_rules = {
        "geometry_modeling": (
            "PLANNING MODE: ADAPTIVE STAGE / GEOMETRY MODELING.\n"
            "- Build the required meshes, topology, booleans, bevels, proportions, and object relationships.\n"
            "- Do not spend steps on UVs, materials, environment, animation, or final render unless needed for geometry."
        ),
        "uv_texture_material": (
            "PLANNING MODE: ADAPTIVE STAGE / UV TEXTURE MATERIAL.\n"
            "- Work from existing geometry; create UVs, seams, texture slots, and material assignments.\n"
            "- Do not rebuild primary geometry unless the stage cannot succeed without a small local helper."
        ),
        "environment_lighting": (
            "PLANNING MODE: ADAPTIVE STAGE / ENVIRONMENT LIGHTING.\n"
            "- Work from existing objects; create lighting, environment, and scene setup.\n"
            "- Keep geometry edits minimal."
        ),
        "animation": (
            "PLANNING MODE: ADAPTIVE STAGE / ANIMATION.\n"
            "- Work from existing objects; set frame range, animation timing, keyframes, actions, and motion staging.\n"
            "- Do not rebuild geometry."
        ),
        "camera_render": (
            "PLANNING MODE: ADAPTIVE STAGE / CAMERA RENDER.\n"
            "- Work from existing objects; set camera, render engine, resolution, and render outputs.\n"
            "- Keep modeling edits minimal."
        ),
    }
    required_caps = required_capabilities_for_stage(stage, prompt)
    high_risk = sorted(high_risk_skills_for_stage(stage))
    capability_text = ", ".join(required_caps) if required_caps else "none"
    high_risk_text = ", ".join(high_risk[:16]) if high_risk else "none"
    contract_text = "" if "## Modeling Planning Contract" in prompt else f"{modeling_quality_contract}\n"
    return (
        f"{prompt}\n\n"
        f"{stage_rules.get(stage, stage_rules['geometry_modeling'])}\n"
        f"- Required capabilities for this stage: {capability_text}.\n"
        f"- Keep compact schemas/argument names exact for high-risk skills: {high_risk_text}.\n"
        "- Avoid skills outside this stage unless a required capability cannot be satisfied otherwise.\n"
        f"{contract_text}"
        "- Return executable VBF skills JSON only."
    )


def filter_skills_for_adaptive_stage(allowed_skills: List[str], stage: str) -> List[str]:
    presentation_prefixes = (
        "create_camera", "set_camera", "camera_", "create_light", "set_light",
        "set_render", "render_", "create_material", "assign_material",
        "import_image_texture", "add_normal_map", "compositor_", "add_compositor",
    )
    uv_prefixes = ("add_uv", "set_active_uv", "mark_seam", "unwrap", "pack_uv", "scale_uv", "arrange_uv")
    animation_prefixes = (
        "insert_keyframe", "delete_keyframe", "set_current_frame", "get_current_frame",
        "set_frame_range", "set_animation_fps", "clear_animation", "create_action",
        "set_action", "list_actions", "evaluate_fcurve", "nla_", "bake_animation",
    )
    camera_tracking_prefixes = ("create_camera", "set_camera", "camera_")
    always = {
        "object_select_all", "rename_object", "delete_object", "set_parent",
        "create_collection", "link_to_collection", "move_object", "scale_object",
        "apply_transform", "ops_search", "ops_introspect",
    }
    if stage == "geometry_modeling":
        return [
            skill for skill in allowed_skills
            if skill in always
            or not (
                skill.startswith(presentation_prefixes)
                or skill.startswith(uv_prefixes)
                or skill.startswith(animation_prefixes)
                or skill.startswith(("cloth_", "fluid_", "gpencil_", "paint_", "sequencer_", "sculpt_"))
            )
        ]
    if stage == "uv_texture_material":
        return [
            skill for skill in allowed_skills
            if skill in always or skill.startswith(uv_prefixes) or skill.startswith(("create_material", "assign_material", "import_image_texture", "add_normal_map"))
        ]
    if stage == "environment_lighting":
        return [
            skill for skill in allowed_skills
            if skill in always or skill.startswith(("create_light", "set_light", "create_camera", "set_camera", "set_render"))
        ]
    if stage == "animation":
        return [
            skill for skill in allowed_skills
            if skill in always
            or skill.startswith(animation_prefixes)
            or skill.startswith(camera_tracking_prefixes)
        ]
    if stage == "camera_render":
        return [
            skill for skill in allowed_skills
            if skill in always or skill.startswith(("create_camera", "set_camera", "set_render", "render_"))
        ]
    return list(allowed_skills)


def scene_to_prompt_text(scene: Any, max_objects: Any = None) -> str:
    try:
        return scene.to_prompt_text(max_objects=max_objects)
    except TypeError:
        return scene.to_prompt_text()
