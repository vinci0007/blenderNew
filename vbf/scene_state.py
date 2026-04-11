"""Scene state capture for LLM feedback and replanning."""
import json
import time
from typing import Any, Dict, List, Optional, Set
from collections import OrderedDict


class SceneState:
    """Describes current Blender scene state for LLM consumption.

    Memory-optimized with incremental capture support.
    Uses OrderedDict for predictable object ordering and deduplication.
    """

    def __init__(self, previous_state: Optional["SceneState"] = None):
        # Use OrderedDict for O(1) lookup and predictable ordering
        self._objects: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.scene_name: Optional[str] = None
        self.frame_current: int = 1
        self.frame_start: int = 1
        self.frame_end: int = 250
        self._statistics: Dict[str, Any] = {}
        self._warnings: List[str] = []
        self._errors: List[str] = []
        self._captured_at: Optional[float] = None

        # Track which objects were modified since previous state
        self._modified_since: Optional[str] = None
        self._is_incremental: bool = False

        if previous_state:
            # Copy relevant state from previous capture
            self._modified_since = str(previous_state._captured_at)

    def add_object(self, name: str, obj_type: str, location: List[float],
                   size: Optional[List[float]] = None,
                   force_update: bool = False,
                   **kwargs) -> None:
        """Add or update an object in the scene state.

        Args:
            name: Object name (unique key)
            obj_type: Object type (MESH, CAMERA, LIGHT, etc.)
            location: [x, y, z] coordinates
            size: [width, height, depth] or None
            force_update: Force mark as modified even if unchanged
            **kwargs: Additional properties
        """
        obj = {"name": name, "type": obj_type, "location": location}
        if size:
            obj["size"] = size
        if kwargs:
            obj.update(kwargs)

        # Mark capture time for incremental tracking
        obj["_captured_at"] = time.time()

        # Check if actually modified from existing
        existing = self._objects.get(name)
        if existing is None or force_update or self._is_modified(existing, obj):
            obj["_modified"] = True

        self._objects[name] = obj

    def _is_modified(self, old: Dict, new: Dict) -> bool:
        """Check if object properties have changed (excluding internal fields)."""
        compare_keys = {"name", "type", "location", "size"}
        for key in compare_keys:
            if key in old or key in new:
                if old.get(key) != new.get(key):
                    return True
        return False

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self._warnings.append(warning)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self._errors.append(error)

    def set_statistics(self, **stats) -> None:
        """Set scene statistics."""
        self._statistics.update(stats)

    def finalize(self) -> None:
        """Finalize capture, record timestamp."""
        self._captured_at = time.time()

    def get_objects(self, only_modified: bool = False) -> List[Dict[str, Any]]:
        """Get objects list.

        Args:
            only_modified: If True, return only objects modified in this capture
        """
        if only_modified:
            return [obj for obj in self._objects.values() if obj.get("_modified")]
        return list(self._objects.values())

    @property
    def warnings(self) -> List[str]:
        """Public access to warnings."""
        return self._warnings

    @property
    def errors(self) -> List[str]:
        """Public access to errors."""
        return self._errors

    @property
    def statistics(self) -> Dict[str, Any]:
        """Public access to statistics."""
        return self._statistics

    def to_dict(self, incremental: bool = False,
                since_step_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert to dictionary.

        Args:
            incremental: If True, only include modified objects
            since_step_id: Step ID since last capture (for tracking)

        Returns:
            Scene state as dictionary
        """
        return {
            "scene_name": self.scene_name,
            "captured_at": self._captured_at,
            "incremental": incremental,
            "since_step_id": since_step_id,
            "frame": {
                "current": self.frame_current,
                "range": [self.frame_start, self.frame_end]
            },
            "objects": self.get_objects(only_modified=incremental),
            "statistics": self._statistics,
            "warnings": self._warnings,
            "errors": self._errors,
        }

    def to_prompt_text(self, incremental: bool = False,
                       since_step_id: Optional[str] = None) -> str:
        """Convert to text for LLM prompts.

        Args:
            incremental: If True, only show modified objects
            since_step_id: Reference step for incremental capture
        """
        lines = [
            f'Scene: {self.scene_name or "Unnamed"}',
            f'Frame: {self.frame_current}/{self.frame_end}',
        ]

        if incremental:
            lines.append(f"(Changes since step: {since_step_id or 'unknown'})")

        objects = self.get_objects(only_modified=incremental)
        lines.append(f'\nObjects ({len(objects)}):')

        for obj in objects:
            info = f"- {obj['name']} ({obj['type']}) loc={obj['location']!r}"
            if 'size' in obj:
                info += f" size={obj['size']!r}"
            if obj.get('_modified') and not incremental:
                info += " [modified]"
            lines.append(info)

        if self._statistics:
            lines.append(f"\nStatistics: {self._statistics}")

        if self._warnings:
            lines.append(f"\n⚠ Warnings: {self._warnings}")

        if self._errors:
            lines.append(f"\n✗ Errors: {self._errors}")

        return '\n'.join(lines)

    def diff(self, other: "SceneState") -> Dict[str, Any]:
        """Calculate diff between this state and another.

        Returns dict with added, removed, modified object lists.
        """
        self_names = set(self._objects.keys())
        other_names = set(other._objects.keys())

        added = list(other_names - self_names)
        removed = list(self_names - other_names)
        modified = []

        for name in self_names & other_names:
            if self._is_modified(self._objects[name], other._objects[name]):
                modified.append(name)

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
        }

    def clear(self) -> None:
        """Clear all state to free memory."""
        self._objects.clear()
        self._warnings.clear()
        self._errors.clear()
        self._statistics.clear()


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

    def to_plan_analysis_prompt(self, incremental: bool = True) -> str:
        """Generate analysis prompt with optional incremental scene capture."""
        lines = [
            f"## Step: {self.step_id}",
            f"Skill: {self.skill}",
            f"Args: {json.dumps(self.args, ensure_ascii=False)}",
            f"Result: {json.dumps(self.result, ensure_ascii=False, indent=2)}",
        ]

        if self.scene_after:
            lines.append(f"\nScene:\n{self.scene_after.to_prompt_text(incremental=incremental)}")

        if self.scene_before and self.scene_after:
            diff = self.scene_before.diff(self.scene_after)
            if any(diff.values()):
                lines.append(f"\nChanges: +{len(diff['added'])}, -{len(diff['removed'])}, ~{len(diff['modified'])}")

        lines.append("\nAnalyze: success? issues? adjustments needed?")
        return '\n'.join(lines)
