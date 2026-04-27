from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .stage_intent_patterns import (
    ANIMATION_DIRECT_PATTERNS,
    BROAD_REQUEST_PATTERNS,
    CAMERA_DIRECT_PATTERNS,
    CONTRAST_SCOPE_PATTERNS,
    GEOMETRY_ONLY_PATTERNS,
    LIGHTING_DIRECT_PATTERNS,
    MATERIAL_DELIVERABLE_PATTERNS,
    NEGATED_GEOMETRY_ONLY_PATTERNS,
    NO_ANIMATION_PATTERNS,
    NO_LIGHTING_PATTERNS,
    NO_RENDER_PATTERNS,
    NO_UV_PATTERNS,
    PRESENTATION_DELIVERABLE_PATTERNS,
    RENDER_DIRECT_PATTERNS,
    UV_DIRECT_PATTERNS,
)


@dataclass(frozen=True)
class StageIntent:
    stages: List[str]
    primary_stage: str
    confidence: float
    explicit_scope: str
    has_conflict: bool = False


def extract_stage_selection_text(prompt: str) -> str:
    text = (prompt or "").lower()
    marker = "--- user request ---"
    if marker in text:
        text = text.split(marker, 1)[1]
        for stop in (
            "\nplanning constraints:",
            "\n## modeling planning contract",
            "\nplannning constraints:",
        ):
            if stop in text:
                text = text.split(stop, 1)[0]
    return text


def regex_any(text: str, patterns: Tuple[str, ...]) -> bool:
    for pattern in patterns:
        try:
            if re.search(pattern, text):
                return True
        except re.error:
            tokens = []
            for token in re.findall(r"(?:\\u[0-9a-fA-F]{4})+", pattern):
                try:
                    tokens.append(token.encode("ascii").decode("unicode_escape"))
                except Exception:
                    continue
            if tokens:
                head, tail = tokens[0], tokens[1:]
                if tail:
                    head_index = text.find(head)
                    if head_index >= 0:
                        remainder = text[head_index + len(head) :]
                        if any(part in remainder for part in tail):
                            return True
                elif head in text:
                    return True
    return False


def analyze_stage_intent(text: str) -> StageIntent:
    """Infer stage scope from the user request without deleting ambiguity."""
    text = (text or "").lower()

    negated_geometry_only = regex_any(text, NEGATED_GEOMETRY_ONLY_PATTERNS)
    geometry_only = not negated_geometry_only and regex_any(text, GEOMETRY_ONLY_PATTERNS)

    no_uv = regex_any(text, NO_UV_PATTERNS)
    no_lighting = regex_any(text, NO_LIGHTING_PATTERNS)
    no_animation = regex_any(text, NO_ANIMATION_PATTERNS)
    no_render = regex_any(text, NO_RENDER_PATTERNS)

    uv_direct = regex_any(text, UV_DIRECT_PATTERNS)
    lighting_direct = regex_any(text, LIGHTING_DIRECT_PATTERNS)
    animation_direct = regex_any(text, ANIMATION_DIRECT_PATTERNS)
    render_direct = regex_any(text, RENDER_DIRECT_PATTERNS)
    camera_direct = regex_any(text, CAMERA_DIRECT_PATTERNS)
    material_deliverable = regex_any(text, MATERIAL_DELIVERABLE_PATTERNS)
    presentation_deliverable = regex_any(text, PRESENTATION_DELIVERABLE_PATTERNS)

    uv_requested = uv_direct and not no_uv
    lighting_requested = lighting_direct and not no_lighting
    animation_requested = animation_direct and not no_animation
    render_requested = render_direct and not no_render
    camera_requested = camera_direct and not no_render
    if geometry_only and no_render:
        render_requested = False
        camera_requested = False
        lighting_requested = lighting_requested and lighting_direct
    if material_deliverable and not (geometry_only or no_uv):
        uv_requested = True
    if presentation_deliverable and not geometry_only:
        if not no_uv:
            uv_requested = True
        if not no_lighting:
            lighting_requested = True
        if not no_render:
            render_requested = True

    requested_stages: List[str] = []
    if uv_requested:
        requested_stages.append("uv_texture_material")
    if lighting_requested:
        requested_stages.append("environment_lighting")
    if animation_requested:
        requested_stages.append("animation")
    if render_requested or camera_requested:
        if render_requested and not lighting_requested:
            requested_stages.append("environment_lighting")
        requested_stages.append("camera_render")

    stages = ["geometry_modeling"]
    for stage in requested_stages:
        if stage not in stages:
            stages.append(stage)

    contrast_scope = regex_any(text, CONTRAST_SCOPE_PATTERNS)
    has_conflict = geometry_only and bool(requested_stages) and contrast_scope
    if geometry_only and not requested_stages:
        return StageIntent(
            stages=["geometry_modeling"],
            primary_stage="geometry_modeling",
            confidence=0.96,
            explicit_scope="geometry_only",
            has_conflict=False,
        )

    if has_conflict:
        confidence = 0.68
        explicit_scope = "conflicting_explicit"
    elif geometry_only and requested_stages:
        confidence = 0.9
        explicit_scope = "explicit_limited"
    elif requested_stages:
        inferred_from_deliverable = (
            (material_deliverable and not uv_direct)
            or (presentation_deliverable and not (render_direct or camera_direct))
        )
        confidence = 0.72 if inferred_from_deliverable else 0.84
        explicit_scope = "explicit_multistage" if len(stages) > 2 else "explicit_stage"
    else:
        broad_request = regex_any(text, BROAD_REQUEST_PATTERNS)
        if broad_request:
            stages.extend(["uv_texture_material", "environment_lighting", "camera_render"])
            confidence = 0.52
            explicit_scope = "ambiguous_preserved"
        else:
            confidence = 0.64
            explicit_scope = "inferred_geometry"

    primary_stage = stages[-1]
    if "animation" in stages and primary_stage != "camera_render":
        primary_stage = "animation"
    if "uv_texture_material" in stages and len(stages) == 2:
        primary_stage = "uv_texture_material"
    return StageIntent(
        stages=stages,
        primary_stage=primary_stage,
        confidence=confidence,
        explicit_scope=explicit_scope,
        has_conflict=has_conflict,
    )


def valid_planning_stages() -> List[str]:
    return [
        "geometry_modeling",
        "uv_texture_material",
        "environment_lighting",
        "animation",
        "camera_render",
    ]


def build_requirement_assessment_prompt(
    prompt: str,
    fallback: Optional[StageIntent] = None,
) -> str:
    fallback_text = ""
    if fallback is not None:
        fallback_text = (
            "\nLocal heuristic fallback for reference only; override it when the user intent implies otherwise:\n"
            f"{json.dumps(fallback.__dict__, ensure_ascii=False)}\n"
        )
    return (
        "Assess the user's Blender task requirements before planning.\n"
        "Do not generate modeling steps. Return plain JSON only.\n\n"
        "Allowed stages, in order:\n"
        "- geometry_modeling: mesh/object construction, topology, transforms, booleans, bevels, hierarchy.\n"
        "- uv_texture_material: UV unwraps, seams, texture setup, simple color assignment, "
        "material assignment, PBR/material presets.\n"
        "- environment_lighting: lights, HDR/world/background, scene lighting setup.\n"
        "- animation: timeline, keyframes, motion, camera/object animation.\n"
        "- camera_render: render camera, render engine/settings, final still/video output.\n\n"
        "Decision policy:\n"
        "- If the user explicitly limits scope, keep only the requested stages.\n"
        "- If the user explicitly excludes a stage, include it in excluded_stages and do not request it.\n"
        "- If the wording is ambiguous, preserve more downstream stages rather than deleting possible intent.\n"
        "- Infer intent from deliverable goals, not only from exact keywords.\n\n"
        "Return exactly this JSON shape:\n"
        "{\n"
        '  "requested_stages": ["geometry_modeling"],\n'
        '  "excluded_stages": [],\n'
        '  "deliverable_level": "model_asset|textured_asset|lit_scene|animation|render_output|ambiguous",\n'
        '  "explicit_scope": true,\n'
        '  "confidence": 0.0,\n'
        '  "reason": "short explanation",\n'
        '  "risks": []\n'
        "}\n\n"
        f"{fallback_text}\n"
        "USER REQUEST:\n"
        f"{extract_stage_selection_text(prompt)}"
    )


def normalize_assessed_stage_intent(
    payload: Any,
    fallback: Optional[StageIntent],
    low_confidence_threshold: float = 0.7,
) -> StageIntent:
    if not isinstance(payload, dict):
        if fallback is not None:
            return fallback
        raise ValueError("requirement_assessment_invalid_payload: expected JSON object")

    allowed = valid_planning_stages()
    allowed_set = set(allowed)

    requested_raw = payload.get("requested_stages")
    excluded_raw = payload.get("excluded_stages")
    requested = [
        stage
        for stage in requested_raw
        if isinstance(stage, str) and stage in allowed_set
    ] if isinstance(requested_raw, list) else []
    excluded = {
        stage
        for stage in excluded_raw
        if isinstance(stage, str) and stage in allowed_set
    } if isinstance(excluded_raw, list) else set()

    if "geometry_modeling" not in requested:
        requested.insert(0, "geometry_modeling")

    ordered = [
        stage
        for stage in allowed
        if stage in requested and stage not in excluded
    ]
    if not ordered:
        ordered = ["geometry_modeling"]

    confidence_raw = payload.get("confidence", fallback.confidence if fallback is not None else 0.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence_raw)))
    except (TypeError, ValueError):
        confidence = fallback.confidence if fallback is not None else 0.0

    explicit_scope = bool(payload.get("explicit_scope", False))
    scope_label = "llm_explicit" if explicit_scope else "llm_inferred"
    if confidence < low_confidence_threshold and not explicit_scope:
        for stage in ("uv_texture_material", "environment_lighting", "camera_render"):
            if stage not in excluded and stage not in ordered:
                ordered.append(stage)
        scope_label = "llm_low_confidence_preserved"

    has_conflict = bool(set(requested) & excluded)
    primary_stage = ordered[-1]
    return StageIntent(
        stages=ordered,
        primary_stage=primary_stage,
        confidence=confidence,
        explicit_scope=scope_label,
        has_conflict=has_conflict,
    )


def select_adaptive_planning_stages(prompt: str) -> List[str]:
    text = extract_stage_selection_text(prompt)
    return analyze_stage_intent(text).stages


def infer_planning_stage(prompt: str) -> str:
    raw_text = (prompt or "").lower()
    if "current skill: render_image" in raw_text or "skill=render_image" in raw_text:
        return "camera_render"
    geometry_skill_markers = (
        "current skill: create_beveled_box",
        "skill=create_beveled_box",
        "current skill: create_primitive",
        "skill=create_primitive",
        "current skill: boolean_tool",
        "skill=boolean_tool",
        "current skill: add_modifier_boolean",
        "skill=add_modifier_boolean",
        "current skill: add_modifier_bevel",
        "skill=add_modifier_bevel",
        "current skill: set_parent",
        "skill=set_parent",
    )
    if any(marker in raw_text for marker in geometry_skill_markers):
        return "geometry_modeling"
    text = extract_stage_selection_text(prompt)
    intent = analyze_stage_intent(text)
    if "stage 2 / presentation" in text or "presentation only" in text:
        return "camera_render"
    if "adaptive stage / geometry modeling" in text:
        return "geometry_modeling"
    if "adaptive stage / uv texture material" in text:
        return "uv_texture_material"
    if "adaptive stage / environment lighting" in text:
        return "environment_lighting"
    if "adaptive stage / animation" in text:
        return "animation"
    if "adaptive stage / camera render" in text:
        return "camera_render"
    if "stage 1 / geometry" in text:
        return "geometry_modeling"
    return intent.primary_stage
