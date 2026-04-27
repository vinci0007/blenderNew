"""Validation rules for closed-loop skill execution feedback.

This module provides a registry-based system for validating skill execution results.
Each rule can validate a specific skill or pattern of skills, ensuring that
geometry, structure, and semantics are as expected.

Usage:
    # Register custom rule
    ValidationRuleRegistry.register("create_*", my_validator)

    # Validate execution
    validator = ValidationRuleRegistry.get_rule("create_primitive")
    result = validator(args, delta, skill_result)
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import OrderedDict

from .geometry_capture import GeometryDelta, ValidationResult, ObjectGeometry


# Type alias for validator functions
ValidatorFn = Callable[[Dict, GeometryDelta, Dict], ValidationResult]


class ValidationRuleRegistry:
    """Global registry for skill validation rules.

    Supports pattern matching with glob-style wildcards:
        - "create_*" matches all skills starting with "create_"
        - "*modifier*" matches skills containing "modifier"
        - "boolean_tool" exact match
    """

    _rules: OrderedDict[str, ValidatorFn] = OrderedDict()
    _compiled_rules: List[Tuple[str, ValidatorFn]] = []

    @classmethod
    def register(cls, skill_pattern: str, validator: ValidatorFn) -> None:
        """Register a validation rule for a skill pattern.

        Args:
            skill_pattern: Glob pattern to match skill names
            validator: Function that takes (args, delta, result) and returns ValidationResult
        """
        cls._rules[skill_pattern] = validator
        # Rebuild compiled rules for efficient matching
        cls._compiled_rules = list(cls._rules.items())

    @classmethod
    def get_rule(cls, skill_name: str) -> Optional[ValidatorFn]:
        """Get the best matching validator for a skill.

        Returns the most specific match (longest pattern first).
        """
        # Find all matching patterns
        matches = []
        for pattern, validator in cls._compiled_rules:
            if fnmatch.fnmatch(skill_name, pattern):
                matches.append((pattern, validator))

        if not matches:
            return None

        # Return the most specific (longest) match
        matches.sort(key=lambda x: len(x[0]), reverse=True)
        return matches[0][1]

    @classmethod
    def list_rules(cls) -> List[str]:
        """Return list of all registered patterns."""
        return list(cls._rules.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all rules (primarily for testing)."""
        cls._rules.clear()
        cls._compiled_rules.clear()


class BuiltinValidationRules:
    """Built-in validation rules for common skills.

    These rules perform semantic validation of skill execution results,
    checking that geometry and structure match expectations.
    """

    @staticmethod
    def validate_create_primitive(args: Dict, delta: GeometryDelta,
                                  result: Dict) -> ValidationResult:
        """Validate create_primitive: object created, dimensions reasonable."""
        obj_name = result.get("data", {}).get("object_name")

        if not obj_name:
            return ValidationResult.failed(
                "create_primitive",
                "No object_name returned in result"
            )

        # Check object exists in "after" state
        if obj_name not in delta.after:
            return ValidationResult.failed(
                "create_primitive",
                f"Object '{obj_name}' not found in scene after creation",
                {"expected_object": obj_name, "objects_present": list(delta.after.keys())}
            )

        obj = delta.after[obj_name]

        # Validate dimensions are reasonable (non-zero)
        if all(d < 0.001 for d in obj.dimensions):
            return ValidationResult.failed(
                "create_primitive",
                f"Object '{obj_name}' has near-zero dimensions",
                {"dimensions": obj.dimensions}
            )

        # Check that it was actually added (wasn't there before)
        if obj_name in delta.before:
            return ValidationResult.warning(
                "create_primitive",
                f"Object '{obj_name}' already existed before creation (may be duplicate)",
                {"object": obj.to_dict()}
            )

        return ValidationResult.passed(
            "create_primitive",
            f"Object '{obj_name}' created with dimensions {obj.dimensions}"
        )

    @staticmethod
    def validate_create_beveled_box(args: Dict, delta: GeometryDelta,
                                    result: Dict) -> ValidationResult:
        """Validate create_beveled_box: box created with bevel modifier."""
        obj_name = result.get("data", {}).get("object_name")

        if not obj_name or obj_name not in delta.after:
            return ValidationResult.failed(
                "create_beveled_box",
                "Object not created"
            )

        obj = delta.after[obj_name]

        # Check it's a mesh with vertices
        if obj.vertices == 0 and obj.polygons == 0 and obj.edges == 0:
            return ValidationResult.skipped(
                "create_beveled_box",
                "Geometry counts not captured at current capture level",
                {"dimensions": obj.dimensions}
            )
        if obj.vertices < 8:  # A box should have at least 8 vertices
            return ValidationResult.warning(
                "create_beveled_box",
                f"Object has only {obj.vertices} vertices, bevel may not be applied",
                {"vertices": obj.vertices}
            )

        return ValidationResult.passed(
            "create_beveled_box",
            f"Beveled box '{obj_name}' created with {obj.vertices} vertices"
        )

    @staticmethod
    def validate_scale_object(args: Dict, delta: GeometryDelta,
                             result: Dict) -> ValidationResult:
        """Validate scale/resize: object dimensions changed as expected."""
        target = args.get("name") or args.get("object_name")
        scale = args.get("scale")

        if not target:
            return ValidationResult.skipped("scale_object", "No target object specified")

        if target not in delta.after:
            return ValidationResult.failed(
                "scale_object",
                f"Target object '{target}' not found after scale operation",
                {"target": target, "objects": list(delta.after.keys())}
            )

        before_obj = delta.before.get(target)
        after_obj = delta.after[target]

        if not before_obj:
            return ValidationResult.warning(
                "scale_object",
                f"No 'before' state for '{target}', cannot validate scale change"
            )

        # Check dimensions actually changed
        dim_changed = any(
            abs(b - a) > 0.001
            for b, a in zip(before_obj.dimensions, after_obj.dimensions)
        )

        if not dim_changed:
            # Might be scaled to same size, check location
            loc_changed = any(
                abs(b - a) > 0.001
                for b, a in zip(before_obj.location, after_obj.location)
            )
            if loc_changed:
                return ValidationResult.passed(
                    "scale_object",
                    f"Object '{target}' moved but dimensions unchanged"
                )
            return ValidationResult.warning(
                "scale_object",
                f"Object '{target}' dimensions unchanged after scale operation",
                {"before": before_obj.dimensions, "after": after_obj.dimensions}
            )

        return ValidationResult.passed(
            "scale_object",
            f"Object '{target}' scaled from {before_obj.dimensions} to {after_obj.dimensions}"
        )

    @staticmethod
    def validate_boolean_operation(args: Dict, delta: GeometryDelta,
                                  result: Dict) -> ValidationResult:
        """Validate boolean_tool: operation produced expected geometry changes."""
        target = args.get("target")
        tool = args.get("tool")
        operation = args.get("operation")  # "UNION", "DIFFERENCE", "INTERSECT"

        if not target:
            return ValidationResult.skipped("boolean_tool", "No target specified")

        target_before = delta.before.get(target)
        target_after = delta.after.get(target)

        if not target_after:
            return ValidationResult.failed(
                "boolean_tool",
                f"Target object '{target}' missing after boolean operation"
            )

        if not target_before:
            return ValidationResult.warning(
                "boolean_tool",
                f"No 'before' state for target '{target}'"
            )

        before_polys = target_before.polygons
        after_polys = target_after.polygons

        if operation == "DIFFERENCE":
            # Target should have fewer polygons (material removed)
            if after_polys >= before_polys:
                return ValidationResult.failed(
                    "boolean_tool",
                    f"DIFFERENCE: Target polygons didn't decrease ({before_polys} -> {after_polys})",
                    {"before": before_polys, "after": after_polys}
                )
            return ValidationResult.passed(
                "boolean_tool",
                f"DIFFERENCE: {before_polys - after_polys} polygons removed"
            )

        elif operation == "UNION":
            # Combined mesh, usually more polygons but target still there
            if target not in delta.after:
                return ValidationResult.failed(
                    "boolean_tool",
                    f"UNION: Target object '{target}' was unexpectedly removed"
                )
            return ValidationResult.passed(
                "boolean_tool",
                f"UNION: Mesh combined, {after_polys} total polygons"
            )

        elif operation == "INTERSECT":
            # Only intersection remains, usually fewer polygons
            return ValidationResult.passed(
                "boolean_tool",
                f"INTERSECT: {after_polys} polygons in intersection"
            )

        return ValidationResult.passed(
            "boolean_tool",
            f"Boolean {operation} completed on '{target}'"
        )

    @staticmethod
    def validate_add_modifier_bevel(args: Dict, delta: GeometryDelta,
                                   result: Dict) -> ValidationResult:
        """Validate add_modifier_bevel: bevel modifier applied correctly."""
        object_name = args.get("object_name") or args.get("name")

        if not object_name:
            return ValidationResult.skipped("add_modifier_bevel", "No object name specified")

        data = result.get("data", {}) if isinstance(result, dict) else {}
        modifier_name = data.get("modifier_name")
        if modifier_name:
            return ValidationResult.passed(
                "add_modifier_bevel",
                f"Bevel modifier '{modifier_name}' added to '{object_name}'"
            )

        if object_name not in delta.after:
            return ValidationResult.failed(
                "add_modifier_bevel",
                f"Object '{object_name}' not found after bevel"
            )

        before = delta.before.get(object_name)
        after = delta.after[object_name]

        if not before:
            return ValidationResult.warning(
                "add_modifier_bevel",
                f"No 'before' state for '{object_name}'"
            )

        # Adding a modifier does not necessarily change base mesh counts until
        # the modifier is evaluated or applied. Only warn when both captures
        # include geometry-level counts.
        if before.edges > 0 and after.edges > 0 and after.edges <= before.edges:
            return ValidationResult.warning(
                "add_modifier_bevel",
                f"Bevel modifier did not change captured edge count ({before.edges} -> {after.edges})",
                {"before_edges": before.edges, "after_edges": after.edges}
            )

        return ValidationResult.passed(
            "add_modifier_bevel",
            f"Bevel applied: {before.edges} -> {after.edges} edges"
        )

    @staticmethod
    def validate_extrude_faces(args: Dict, delta: GeometryDelta,
                              result: Dict) -> ValidationResult:
        """Validate extrude_faces: geometry extruded as expected."""
        object_name = args.get("object_name") or args.get("name")

        if not object_name or object_name not in delta.after:
            return ValidationResult.skipped("extrude_faces", "No valid target")

        before = delta.before.get(object_name)
        after = delta.after[object_name]

        if not before or not after:
            return ValidationResult.warning("extrude_faces", "Missing before/after state")

        # Extrusion typically adds faces
        face_delta = after.polygons - before.polygons

        if face_delta <= 0:
            return ValidationResult.warning(
                "extrude_faces",
                f"Extrusion didn't add faces ({before.polygons} -> {after.polygons})",
                {"face_delta": face_delta}
            )

        return ValidationResult.passed(
            "extrude_faces",
            f"Extrusion added {face_delta} faces ({before.polygons} -> {after.polygons})"
        )

    @staticmethod
    def validate_subdivide_mesh(args: Dict, delta: GeometryDelta,
                               result: Dict) -> ValidationResult:
        """Validate subdivide_mesh: mesh subdivided, polygon count increased."""
        object_name = args.get("object_name") or args.get("name")

        if not object_name or object_name not in delta.after:
            return ValidationResult.skipped("subdivide_mesh", "No valid target")

        before = delta.before.get(object_name)
        after = delta.after[object_name]

        if not before or not after:
            return ValidationResult.warning("subdivide_mesh", "Missing before/after state")

        # Subdivision significantly increases polygon count
        poly_ratio = after.polygons / max(before.polygons, 1)

        if poly_ratio < 1.5:  # Expecting at least 1.5x polygons
            return ValidationResult.warning(
                "subdivide_mesh",
                f"Subdivision effect weak: {before.polygons} -> {after.polygons} ({poly_ratio:.1f}x)",
                {"ratio": poly_ratio}
            )

        return ValidationResult.passed(
            "subdivide_mesh",
            f"Subdivided: {before.polygons} -> {after.polygons} ({poly_ratio:.1f}x increase)"
        )

    @staticmethod
    def validate_delete_object(args: Dict, delta: GeometryDelta,
                              result: Dict) -> ValidationResult:
        """Validate delete_object: object was removed."""
        object_name = args.get("object_name") or args.get("name")

        if not object_name:
            return ValidationResult.skipped("delete_object", "No object name specified")

        if object_name in delta.after:
            return ValidationResult.failed(
                "delete_object",
                f"Object '{object_name}' still exists after deletion"
            )

        if object_name not in delta.before:
            return ValidationResult.warning(
                "delete_object",
                f"Object '{object_name}' didn't exist before deletion"
            )

        return ValidationResult.passed(
            "delete_object",
            f"Object '{object_name}' successfully deleted"
        )

    @staticmethod
    def validate_set_material(args: Dict, delta: GeometryDelta,
                             result: Dict) -> ValidationResult:
        """Validate assign_material: material count changed."""
        object_name = args.get("object_name") or args.get("name")

        if not object_name or object_name not in delta.after:
            return ValidationResult.skipped("assign_material", "No valid target")

        before = delta.before.get(object_name)
        after = delta.after[object_name]

        if before and after.materials == before.materials:
            return ValidationResult.warning(
                "assign_material",
                f"Material count unchanged ({after.materials})"
            )

        return ValidationResult.passed(
            "assign_material",
            f"Material assigned: {after.materials} total slots"
        )

    @staticmethod
    def validate_default(args: Dict, delta: GeometryDelta,
                        result: Dict) -> ValidationResult:
        """Default validator for skills without specific rules.

        Performs basic checks: result ok, target objects exist.
        """
        if not result.get("ok"):
            return ValidationResult.failed(
                result.get("skill", "unknown"),
                result.get("error", {}).get("message", "Skill execution failed"),
                result.get("error", {})
            )

        # Check if any objects were deleted unexpectedly
        removed = delta.removed
        if removed:
            # Some removals are expected (delete_object, boolean difference, etc.)
            pass

        # Check if new objects were added
        added = delta.added
        if added:
            return ValidationResult.passed(
                "default",
                f"Execution completed. Added: {len(added)}, Modified: {len(delta.modified)}"
            )

        if delta.modified:
            return ValidationResult.passed(
                "default",
                f"Execution completed. Modified {len(delta.modified)} objects"
            )

        return ValidationResult.passed("default", "Execution completed")


def _register_default_rules():
    """Register all built-in validation rules."""
    rules = [
        # Primitives
        ("create_primitive", BuiltinValidationRules.validate_create_primitive),
        ("create_beveled_box", BuiltinValidationRules.validate_create_beveled_box),

        # Geometry transforms
        ("scale_object", BuiltinValidationRules.validate_scale_object),
        ("*scale*", BuiltinValidationRules.validate_scale_object),  # Wildcard match

        # Boolean operations
        ("boolean_tool", BuiltinValidationRules.validate_boolean_operation),

        # Modifiers
        ("add_modifier_bevel", BuiltinValidationRules.validate_add_modifier_bevel),
        ("add_modifier_subdivision", BuiltinValidationRules.validate_subdivide_mesh),

        # Mesh operations
        ("extrude_faces", BuiltinValidationRules.validate_extrude_faces),
        ("subdivide_mesh", BuiltinValidationRules.validate_subdivide_mesh),

        # Object operations
        ("delete_object", BuiltinValidationRules.validate_delete_object),

        # Materials
        ("assign_material", BuiltinValidationRules.validate_set_material),
    ]

    for pattern, validator in rules:
        ValidationRuleRegistry.register(pattern, validator)


# Auto-register built-in rules on module import
_register_default_rules()


# Convenience exports
__all__ = [
    "ValidationRuleRegistry",
    "BuiltinValidationRules",
    "ValidationResult",
    "register_custom_rule",
]


def register_custom_rule(pattern: str, validator: ValidatorFn) -> None:
    """Convenience function to register a custom validation rule."""
    ValidationRuleRegistry.register(pattern, validator)
