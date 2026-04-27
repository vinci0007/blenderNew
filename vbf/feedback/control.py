"""Closed-loop control engine for VBF skill execution.

This module provides the ClosedLoopControl class that orchestrates
skill execution with validation, LLM feedback, and dynamic replanning.

Usage:
    loop = ClosedLoopControl(client, enable_auto_check=True, enable_llm_feedback=True)
    decision, post_state = await loop.execute_with_feedback(step, step_results, capture)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .geometry_capture import (
    CaptureLevel,
    GeometryDelta,
    IncrementalSceneCapture,
    ObjectGeometry,
    ValidationResult,
)
from .rules import ValidationRuleRegistry
from ..core.vibe_protocol import resolve_refs
from ..transport.jsonrpc_ws import JsonRpcError


@dataclass
class FeedbackDecision:
    """Result of feedback control decision for a step.

    Attributes:
        action: What to do next - "continue", "replan", "checkpoint", "rollback"
        detail: Additional context (validation result, analysis, etc.)
        validation: The validation result if applicable
    """
    action: str  # "continue" | "replan" | "checkpoint" | "rollback"
    detail: Dict[str, Any] = field(default_factory=dict)
    validation: Optional[ValidationResult] = None

    def __repr__(self) -> str:
        if self.validation:
            return f"FeedbackDecision({self.action}, {self.validation.status})"
        return f"FeedbackDecision({self.action})"


class ClosedLoopControl:
    """
    Closed-loop control engine for skill execution.

    Embeds into the run_task execution loop to:
    1. Capture scene state before/after each skill
    2. Validate execution results against expected geometry changes
    3. Trigger LLM analysis at stage boundaries
    4. Initiate replanning when validation fails
    """

    # Stage order for monotonicity tracking
    STAGE_ORDER = [
        "discover", "blockout", "boolean", "detail",
        "bevel", "normal_fix", "accessories", "material", "finalize"
    ]

    def __init__(
        self,
        client,
        enable_auto_check: bool = True,
        enable_llm_feedback: bool = True,
        capture_level: CaptureLevel = CaptureLevel.LIGHT,
        task_prompt: Optional[str] = None,
        stage_quality_threshold: float = 0.4,
    ):
        """
        Initialize closed-loop control.

        Args:
            client: VBFClient instance for RPC calls
            enable_auto_check: Run validation after each skill
            enable_llm_feedback: Run LLM analysis at stage boundaries
            capture_level: Detail level for scene capture
            task_prompt: Original user goal prompt, for semantic quality checks
            stage_quality_threshold: Replan threshold for stage quality score
        """
        self.client = client
        self.enable_auto_check = enable_auto_check
        self.enable_llm_feedback = enable_llm_feedback
        self.capture_level = capture_level
        self._task_prompt = task_prompt
        self._stage_quality_threshold = stage_quality_threshold

        self._validator = ValidationRuleRegistry()
        self._current_stage: Optional[str] = None
        self._stage_entry_index: int = 0
        self._step_index: int = 0
        self._stage_histories: Dict[str, List[str]] = {}  # stage -> [step_ids]

        # Track failed steps for analysis
        self._failed_steps: List[Tuple[str, ValidationResult]] = []

    @staticmethod
    def _is_object_creation_skill(skill: str) -> bool:
        return skill in {
            "create_primitive",
            "create_beveled_box",
            "create_curve_bezier",
            "create_curve_circle",
            "create_text",
            "clone_from_image",
        }

    @staticmethod
    def _extract_result_object_name(result: Dict[str, Any]) -> Optional[str]:
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict):
            return None
        for key in ("object_name", "name", "child"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
        nested = data.get("result")
        if isinstance(nested, dict):
            value = nested.get("object_name") or nested.get("name")
            if isinstance(value, str) and value:
                return value
        return None

    async def execute_with_feedback(
        self,
        step: Dict[str, Any],
        step_results: Dict[str, Any],
        scene_capture: IncrementalSceneCapture,
    ) -> Tuple[FeedbackDecision, Optional[Dict[str, ObjectGeometry]]]:
        """
        Execute a single step with feedback control.

        Args:
            step: Step definition (step_id, skill, args, stage, etc.)
            step_results: Dict of all previous step results
            scene_capture: IncrementalSceneCapture instance

        Returns:
            Tuple of (FeedbackDecision, scene_after or None)
        """
        step_id = step.get("step_id", f"s{self._step_index:03d}")
        skill = step.get("skill", "")
        args = step.get("args", {})
        try:
            resolved_args = resolve_refs(args, step_results)
        except Exception as e:
            validation = ValidationResult.failed(skill, f"Argument reference resolution failed: {e}")
            self._failed_steps.append((step_id, validation))
            return FeedbackDecision(
                action="replan",
                detail={
                    "step_id": step_id,
                    "skill": skill,
                    "error": str(e),
                    "reason": "resolve_refs_failed",
                },
                validation=validation,
            ), None
        stage = step.get("stage", "detail")
        self._step_index += 1

        # Stage boundary check (L3 - on stage exit)
        previous_stage = self._current_stage
        stage_changed = stage != previous_stage
        if stage_changed and previous_stage and self.enable_llm_feedback:
            analysis = await self._analyze_stage_boundary(previous_stage, step_results)
            if analysis and (
                analysis.quality == "bad"
                or float(getattr(analysis, "score", 1.0)) < self._stage_quality_threshold
            ):
                previous_stage_steps = self._stage_histories.get(previous_stage, [])
                rollback_step_id = previous_stage_steps[0] if previous_stage_steps else None
                return FeedbackDecision(
                    action="checkpoint",
                    detail={
                        "stage": previous_stage,
                        "analysis": analysis.to_dict() if hasattr(analysis, "to_dict") else analysis,
                        "reason": "quality_poor",
                        "step_id": step_id,
                        # Roll back to the beginning of the previous stage so poor-stage artifacts
                        # (e.g., draft cube blockout) can be cleaned before local replan.
                        "rollback_step_id": rollback_step_id,
                        "stage_step_ids": previous_stage_steps,
                    },
                    validation=None,
                ), None

        # Update stage tracking
        if stage_changed:
            self._current_stage = stage
            self._stage_entry_index = self._step_index - 1
            self._stage_histories[stage] = []
            print(f"[Feedback] Entering stage: {stage}")

        self._stage_histories.setdefault(stage, []).append(step_id)

        # Determine target objects for this step
        target_objects = self._extract_target_objects(skill, resolved_args, step_results)
        pre_capture_targets = [] if self._is_object_creation_skill(skill) else target_objects

        # Capture before state
        scene_before = await scene_capture.capture_objects(
            pre_capture_targets,
            level=self.capture_level,
            use_cache=True
        )

        # Execute skill
        try:
            result = await self.client.execute_skill(skill, resolved_args, step_id)
        except JsonRpcError as e:
            validation = ValidationResult.failed(skill, f"Execution failed: {e}")
            self._failed_steps.append((step_id, validation))
            step_results[step_id] = {"ok": False, "error": {"message": str(e)}}
            if self.enable_auto_check:
                return FeedbackDecision(
                    action="replan",
                    detail={
                        "step_id": step_id,
                        "skill": skill,
                        "error": str(e),
                        "reason": "execute_skill_failed",
                    },
                    validation=validation,
                ), None
            return FeedbackDecision(
                action="continue",
                detail={
                    "step_id": step_id,
                    "skill": skill,
                    "error": str(e),
                    "reason": "execute_skill_failed",
                },
                validation=validation,
            ), None

        step_results[step_id] = result

        # Check for execution error
        if not result.get("ok"):
            error_msg = result.get("error", {}).get("message", "Unknown error")
            validation = ValidationResult.failed(skill, f"Execution failed: {error_msg}")
            self._failed_steps.append((step_id, validation))

            # Check if we should replan or continue
            if self.enable_auto_check:
                return FeedbackDecision(
                    action="replan",
                    detail={
                        "step_id": step_id,
                        "skill": skill,
                        "error": error_msg,
                        "reason": "execute_result_failed",
                    },
                    validation=validation,
                ), None

            return FeedbackDecision(
                action="continue",
                detail={
                    "step_id": step_id,
                    "skill": skill,
                    "error": error_msg,
                    "reason": "execute_result_failed",
                },
                validation=validation,
            ), None

        # Extract post-state from result (if server provided it)
        post_state_dict = result.get("data", {}).get("_post_state", {})
        if post_state_dict:
            scene_capture.update_cache_from_result(post_state_dict)

        post_capture_targets = list(target_objects)
        created_name = self._extract_result_object_name(result)
        if created_name and created_name not in post_capture_targets:
            post_capture_targets.append(created_name)

        # Calculate delta from a fresh after-capture so new/modified objects do not
        # rely on stale cache entries.
        scene_after = await scene_capture.capture_objects(
            post_capture_targets,
            level=self.capture_level,
            use_cache=False,
        )

        delta = GeometryDelta.diff(scene_before, scene_after)

        # Auto-validation (L2)
        if self.enable_auto_check:
            validator_fn = self._validator.get_rule(skill)
            if validator_fn:
                validation = validator_fn(resolved_args, delta, result)

                if validation.status == "failed":
                    self._failed_steps.append((step_id, validation))
                    print(f"[Feedback] Validation failed for {step_id}: {validation.message}")

                    return FeedbackDecision(
                        action="replan",
                        detail={
                            "step_id": step_id,
                            "skill": skill,
                            "reason": "validation_failed",
                            "delta": delta.to_dict(),
                        },
                        validation=validation,
                    ), scene_after

                elif validation.status == "warning":
                    print(f"[Feedback] Validation warning for {step_id}: {validation.message}")

        return FeedbackDecision(
            action="continue",
            detail={"step_id": step_id, "delta": delta.to_dict()},
        ), scene_after

    def _extract_target_objects(
        self,
        skill: str,
        args: Dict,
        step_results: Dict,
    ) -> List[str]:
        """
        Extract target object names from skill arguments.

        Supports various naming conventions:
        - "name", "object_name", "target"
        - $ref resolution from previous steps
        """
        # Primary candidates
        candidates = [
            args.get("name"),
            args.get("object_name"),
            args.get("target"),
            args.get("object"),
        ]

        # Filter and resolve
        targets = []
        for candidate in candidates:
            if not candidate:
                continue

            if isinstance(candidate, str):
                # Handle $ref resolution
                if candidate.startswith("$ref:"):
                    ref_path = candidate[5:].strip()
                    ref_result = self._resolve_ref(ref_path, step_results)
                    if ref_result:
                        targets.append(ref_result)
                else:
                    targets.append(candidate)

        return list(dict.fromkeys(targets))  # Deduplicate while preserving order

    def _resolve_ref(self, ref: str, step_results: Dict) -> Optional[str]:
        """Resolve a $ref to get object name from previous step result."""
        parts = ref.split(".")
        if len(parts) < 2:
            return None

        step_id = parts[0]
        if step_id.startswith("step_"):
            step_id = step_id[5:]  # Normalize

        step_result = step_results.get(step_id)
        if not step_result:
            step_result = step_results.get(f"step_{step_id}")

        if not step_result:
            return None

        # Navigate the path
        data = step_result.get("data", {})
        for key in parts[1:]:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None

        return str(data) if data else None

    async def _analyze_stage_boundary(
        self,
        stage: str,
        step_results: Dict,
    ) -> Optional[Any]:
        """Trigger LLM analysis at stage boundary."""
        try:
            from .llm import GeometryFeedbackAnalyzer

            analyzer = GeometryFeedbackAnalyzer(self.client)
            scene_state = await self.client.capture_scene_state()
            if hasattr(self.client, "_filter_scene_for_task_context"):
                scene_state = self.client._filter_scene_for_task_context(scene_state)

            analysis = await analyzer.analyze_geometry_quality(
                stage=stage,
                scene=scene_state,
                step_results=step_results,
                context=self._get_stage_context(stage),
                task_prompt=self._task_prompt,
            )

            return analysis
        except ImportError:
            print("[Feedback] LLM analyzer not available, skipping stage analysis")
            return None
        except Exception as e:
            print(f"[Feedback] Stage analysis failed: {e}")
            return None

    def _get_stage_context(self, stage: str) -> str:
        """Get the analysis context type for a stage."""
        context_map = {
            "discover": "silhouette",
            "blockout": "proportion",
            "boolean": "silhouette",
            "detail": "edge_flow",
            "bevel": "surface",
            "normal_fix": "surface",
            "accessories": "detail",
            "material": "surface",
            "finalize": "general",
        }
        return context_map.get(stage, "general")

    def get_failed_steps(self) -> List[Tuple[str, ValidationResult]]:
        """Return list of failed steps for analysis."""
        return self._failed_steps.copy()

    def get_stage_history(self, stage: str) -> List[str]:
        """Return step IDs executed in a given stage."""
        return self._stage_histories.get(stage, []).copy()

    def get_stats(self) -> Dict[str, Any]:
        """Return control statistics."""
        return {
            "total_steps": self._step_index,
            "current_stage": self._current_stage,
            "failed_count": len(self._failed_steps),
            "stages_executed": list(self._stage_histories.keys()),
        }
