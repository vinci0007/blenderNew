"""LLM-driven geometric quality analysis for stage boundary feedback.

This module provides GeometryFeedbackAnalyzer which uses the LLM to analyze
scene quality, detect issues, and suggest improvements at stage boundaries.

Usage:
    analyzer = GeometryFeedbackAnalyzer(client)
    analysis = await analyzer.analyze_geometry_quality(stage, scene, step_results)
    if analysis.quality == "bad":
        # Trigger checkpoint or replan
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json

from .scene_state import SceneState


@dataclass
class GeometryAnalysis:
    """Result of LLM geometry quality analysis.

    Attributes:
        quality: Overall quality assessment - "good" | "warning" | "bad"
        reason: Explanation of the quality assessment
        suggestions: List of specific improvements to make
        score: Numerical quality score 0.0-1.0
        critical_issues: List of blocking issues (if any)
        recommendations: Dict with per-area recommendations
    """
    quality: str  # "good" | "warning" | "bad"
    reason: str
    suggestions: List[str] = field(default_factory=list)
    score: float = 0.5
    critical_issues: List[str] = field(default_factory=list)
    recommendations: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dict."""
        return {
            "quality": self.quality,
            "reason": self.reason,
            "suggestions": self.suggestions,
            "score": self.score,
            "critical_issues": self.critical_issues,
            "recommendations": self.recommendations,
        }


class GeometryFeedbackAnalyzer:
    """
    Uses LLM to analyze geometric quality at stage boundaries.

    This analyzer is triggered at stage transitions to:
    1. Assess overall modeling quality for the completed stage
    2. Detect structural/geometric issues
    3. Suggest improvements for next stage
    4. Determine if checkpoint pause is needed

    Triggered at stage boundaries (user-requested frequency).
    """

    # Context-specific prompts for different analysis types
    CONTEXT_PROMPTS = {
        "silhouette": """
Focus on SILHOUETTE validation:
- Are the overall shapes and volumes correct?
- Does the silhouette match the described object?
- Are there any obvious shape errors or missing components?
- Check proportions between major forms.
""",
        "proportion": """
Focus on PROPORTION validation:
- Are the relative sizes of components correct?
- Do dimensions match realistic or intended proportions?
- Check scale relationships between parent/child objects.
- Flag any obviously disproportional elements.
""",
        "edge_flow": """
Focus on EDGE FLOW and TOPOLOGY:
- Is the edge flow logical and clean?
- Are there unnecessary ngons or triangles?
- Is the topology suitable for subdivision?
- Flag non-manifold geometry or bad edge loops.
""",
        "surface": """
Focus on SURFACE quality:
- Are surfaces smooth without artifacts?
- Is the normal orientation correct?
- Are bevels/chamfers applied consistently?
- Check for shading errors or topology issues.
""",
        "detail": """
Focus on DETAIL quality:
- Are fine details appropriate in scale?
- Do details align with the overall form?
- Check for detail consistency (uniform detail level).
- Flag details that break realistic appearance.
""",
        "general": """
Focus on GENERAL quality:
- Overall geometric integrity
- Structural soundness
- Progress toward the stated goal
- Readiness for next stage
""",
    }

    def __init__(self, client):
        """Initialize with VBFClient instance."""
        self.client = client

    async def analyze_geometry_quality(
        self,
        stage: str,
        scene: SceneState,
        step_results: Dict[str, Any],
        context: str = "general",
        task_prompt: Optional[str] = None,
    ) -> GeometryAnalysis:
        """
        Analyze scene quality at stage boundary.

        Args:
            stage: Current stage name (e.g., "blockout", "detail")
            scene: Current scene state
            step_results: Dict of all executed steps and results
            context: Analysis focus type (silhouette, proportion, etc.)
            task_prompt: Original user modeling goal for semantic alignment checks

        Returns:
            GeometryAnalysis with quality assessment and recommendations
        """
        adapter = await self.client._ensure_adapter()

        # Build context-specific prompt
        context_prompt = self.CONTEXT_PROMPTS.get(context, self.CONTEXT_PROMPTS["general"])

        # Get recent step history (last 10 for context)
        recent_steps = self._format_step_history(step_results, limit=10)

        # Scene summary
        scene_text = scene.to_prompt_text()
        goal_text = task_prompt or "No explicit goal provided."

        prompt = f"""Analyze the current 3D modeling quality for completed stage: {stage.upper()}

{context_prompt}

USER GOAL:
{goal_text}

CURRENT SCENE STATE:
{scene_text}

RECENT EXECUTION STEPS (last {len(recent_steps)} steps):
{recent_steps}

Please analyze the modeling progress and return a JSON assessment:

{{
    "quality": "good|warning|bad",
    "reason": "Brief explanation of assessment",
    "suggestions": ["suggestion 1", "suggestion 2", ...],
    "score": 0.0-1.0,
    "critical_issues": ["issue 1", ...],
    "recommendations": {{
        "immediate": ["do this now"],
        "next_stage": ["for the next stage"],
        "overall": ["improvement suggestions"]
    }}
}}

Quality guidelines:
- "good" (0.7-1.0): Progress is on track, no blocking issues
- "warning" (0.4-0.7): Minor issues, should be addressed but not blocking
- "bad" (0.0-0.4): Significant problems requiring attention, consider checkpoint

Score calculation (0.0-1.0):
Consider: geometric accuracy, structural integrity, proportion correctness,
topology quality, and progress toward the stated goal.

Critical requirement:
- Check semantic goal alignment. If goal is "smartphone", output should not degrade into
  unrelated primitives (e.g., a single cube) or disconnected parts with no coherent structure."""

        messages = [
            {"role": "system", "content": """You are an expert 3D modeling quality analyzer.
Your job is to assess the current state of a Blender modeling task and provide actionable feedback.
Be honest but constructive. Identify actual issues, not hypothetical ones.
Always return valid JSON matching the requested format exactly."""},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.client._adapter_call(messages)
            return self._parse_analysis_response(response)
        except Exception as e:
            print(f"[Analyzer] LLM analysis failed: {e}")
            # Return a neutral fallback
            return GeometryAnalysis(
                quality="good",
                reason=f"Analysis failed, assuming acceptable quality",
                suggestions=["Consider manual inspection"],
                score=0.5,
                critical_issues=[str(e)],
            )

    def _format_step_history(
        self,
        step_results: Dict[str, Any],
        limit: int = 10,
    ) -> str:
        """Format recent step results for LLM prompt."""
        items = list(step_results.items())[-limit:]

        lines = []
        for step_id, result in items:
            skill = result.get("data", {}).get("_skill", "unknown")
            status = "OK" if result.get("ok") else "FAIL"
            lines.append(f"  - {step_id}: {skill} [{status}]")

        return "\n".join(lines) if lines else "  (no recent steps)"

    def _parse_analysis_response(self, response: Dict) -> GeometryAnalysis:
        """Parse LLM response into GeometryAnalysis."""
        if not isinstance(response, dict):
            response = {}

        quality = response.get("quality", "good").lower()
        if quality not in ("good", "warning", "bad"):
            quality = "good"

        score = float(response.get("score", 0.5))
        score = max(0.0, min(1.0, score))

        return GeometryAnalysis(
            quality=quality,
            reason=response.get("reason", "No reason provided"),
            suggestions=self._ensure_list(response.get("suggestions", [])),
            score=score,
            critical_issues=self._ensure_list(response.get("critical_issues", [])),
            recommendations=response.get("recommendations", {}),
        )

    def _ensure_list(self, value) -> List[str]:
        """Ensure value is a list of strings."""
        if isinstance(value, list):
            return [str(item) for item in value]
        if value:
            return [str(value)]
        return []

    async def analyze_repair_strategy(
        self,
        failed_step: str,
        error: str,
        scene: SceneState,
        allowed_skills: List[str],
    ) -> Dict[str, Any]:
        """
        Ask LLM for a repair strategy after validation failure.

        This generates a focused repair plan when a step fails validation.
        """
        adapter = await self.client._ensure_adapter()

        prompt = f"""Generate a repair strategy for a failed modeling step.

Failed step: {failed_step}
Validation error: {error}

Current scene:
{scene.to_prompt_text()}

Available skills: {', '.join(allowed_skills[:20])}...

Provide a concise repair strategy in JSON:
{{
    "strategy": "one of: retry|modify|rollback|skip",
    "reason": "why this strategy",
    " suggested_fix": "specific action to take",
    "required_skills": ["skill1", "skill2"],
    "undo_steps": 0
}}"""

        messages = [
            {"role": "system", "content": "You are a 3D modeling recovery expert."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.client._adapter_call(messages)
            return response if isinstance(response, dict) else {}
        except Exception:
            return {
                "strategy": "retry",
                "reason": "Analysis failed, defaulting to retry",
            }


# Convenience exports
__all__ = [
    "GeometryAnalysis",
    "GeometryFeedbackAnalyzer",
]
