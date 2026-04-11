"""Scene state capture for LLM feedback and replanning."""
import json
from typing import Any, Dict, List, Optional


class SceneState:
    """Describes current Blender scene state for LLM consumption."""

    def __init__(self):
        self.objects: List[Dict[str, Any]] = []
        self.scene_name: Optional[str] = None
        self.frame_current: int = 1
        self.frame_start: int = 1
        self.frame_end: int = 250
        self.statistics: Dict[str, Any] = {}
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def add_object(self, name: str, obj_type: str, location: List[float],
                   size: Optional[List[float]] = None, **kwargs) -> None:
        obj = {"name": name, "type": obj_type, "location": location}
        if size:
            obj["size"] = size
        obj.update(kwargs)
        self.objects.append(obj)

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    def set_statistics(self, **stats) -> None:
        self.statistics.update(stats)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_name": self.scene_name,
            "frame": {"current": self.frame_current, "range": [self.frame_start, self.frame_end]},
            "objects": self.objects,
            "statistics": self.statistics,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def to_prompt_text(self) -> str:
        lines = [f'Scene: {self.scene_name or "Unnamed"}', f'Frame: {self.frame_current}/{self.frame_end}', '']
        lines.append(f'Objects ({len(self.objects)}):')
        for obj in self.objects:
            info = f"- {obj['name']} ({obj['type']}) loc={obj['location']!r}"
            if 'size' in obj:
                info += f" size={obj['size']!r}"
            if 'issues' in obj:
                info += f" ⚠ {obj['issues']}"
            lines.append(info)
        if self.warnings:
            lines.append(f"\n⚠ Warnings: {self.warnings}")
        if self.errors:
            lines.append(f"\n✗ Errors: {self.errors}")
        return '\n'.join(lines)


class FeedbackContext:
    """Context for skill execution feedback to LLM."""

    def __init__(self, step_id: str, skill: str, args: Dict, result: Dict,
                 scene_before: Optional[SceneState] = None,
                 scene_after: Optional[SceneState] = None):
        self.step_id = step_id
        self.skill = skill
        self.args = args
        self.result = result
        self.scene_before = scene_before
        self.scene_after = scene_after

    def to_plan_analysis_prompt(self) -> str:
        lines = [
            f"## Step: {self.step_id}",
            f"Skill: {self.skill}",
            f"Args: {json.dumps(self.args, ensure_ascii=False)}",
            f"Result: {json.dumps(self.result, ensure_ascii=False, indent=2)}",
        ]
        if self.scene_after:
            lines.append(f"\nScene after:\n{self.scene_after.to_prompt_text()}")
        lines.append("\nAnalyze: success? issues? adjustments needed?")
        return '\n'.join(lines)
