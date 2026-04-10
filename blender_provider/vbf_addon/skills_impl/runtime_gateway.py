# Enhanced Runtime Gateway with Schema Validation
from typing import Any, Dict, List, get_type_hints

import bpy

try:
    # Standard: installed as standalone addon folder (vbf_addon/skill_runtime)
    from ..skill_runtime import py_call, py_get, py_set
    from ..skills_impl import utils
except ImportError:
    # Fallback: Blender loads the folder as a plain script (no package context)
    from skill_runtime import py_call, py_get, py_set  # type: ignore
    from skills_impl import utils  # type: ignore


def _resolve_operator(operator_id: str):
    if not operator_id or "." not in operator_id:
        raise ValueError("operator_id must be like 'mesh.primitive_cube_add'")
    module_name, op_name = operator_id.split(".", 1)
    module = getattr(bpy.ops, module_name, None)
    if module is None:
        raise ValueError(f"bpy.ops module not found: {module_name}")
    op = getattr(module, op_name, None)
    if op is None:
        raise ValueError(f"bpy.ops operator not found: {operator_id}")
    return op


def _get_operator_schema(operator_id: str) -> Dict[str, Any]:
    """Get Blender RNA schema for operator parameters."""
    try:
        op = _resolve_operator(operator_id)
        rna = op.get_rna_type()
        props = []

        for p in rna.properties:
            if p.identifier in {"rna_type", "bl_idname", "bl_rna", "options"}:
                continue

            prop_info = {
                "identifier": p.identifier,
                "name": p.name,
                "description": p.description,
                "type": str(p.type),
                "is_required": bool(getattr(p, "is_required", False)),
                "is_readonly": bool(getattr(p, "is_readonly", False)),
            }

            # Add default value if available
            if hasattr(p, "default"):
                try:
                    default_val = p.default
                    if hasattr(default_val, '__len__') and not isinstance(default_val, str):
                        prop_info["default"] = list(default_val)
                    else:
                        prop_info["default"] = default_val
                except:
                    pass

            # Add enum items
            if hasattr(p, "enum_items"):
                try:
                    items = [item.identifier for item in p.enum_items]
                    prop_info["enum_items"] = items
                except:
                    pass

            # Add min/max bounds
            if hasattr(p, "soft_min"):
                prop_info["soft_min"] = p.soft_min
            if hasattr(p, "soft_max"):
                prop_info["soft_max"] = p.soft_max
            if hasattr(p, "min"):
                prop_info["hard_min"] = p.min
            if hasattr(p, "max"):
                prop_info["hard_max"] = p.max

            props.append(prop_info)

        return {
            "operator_id": operator_id,
            "name": rna.name,
            "description": rna.description,
            "properties": props,
        }
    except Exception as e:
        return {"operator_id": operator_id, "error": str(e), "properties": []}


def _validate_op_args(operator_id: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Validate operator arguments against Blender RNA schema.

    Returns:
        {"valid": bool, "errors": List[str], "warnings": List[str]}
    """
    errors = []
    warnings = []

    try:
        op = _resolve_operator(operator_id)
        rna = op.get_rna_type()

        # Get expected parameters
        expected_props = {}
        required_props = set()

        for p in rna.properties:
            if p.identifier in {"rna_type", "bl_idname", "bl_rna", "options"}:
                continue

            expected_props[p.identifier] = {
                "type": str(p.type),
                "is_required": getattr(p, "is_required", False),
                "readonly": getattr(p, "is_readonly", False),
            }

            if getattr(p, "is_required", False):
                required_props.add(p.identifier)

        # Check for unknown parameters
        for key in kwargs:
            if key not in expected_props:
                # Check if it's a typo (similar names)
                similar = [p for p in expected_props.keys() if p.upper() in key.upper() or key.upper() in p.upper()]
                if similar:
                    warnings.append(f"Unknown parameter '{key}'. Did you mean: {similar}?")
                else:
                    warnings.append(f"Unknown parameter '{key}'. Expected: {list(expected_props.keys())}")

        # Check required parameters
        for required in required_props:
            if required not in kwargs:
                errors.append(f"Missing required parameter: '{required}'")

        # Validate types
        type_mapping = {
            "BOOLEAN": (bool, int),
            "INT": (int,),
            "FLOAT": (int, float),
            "STRING": (str,),
            "ENUM": (str,),
            "POINTER": (str, object),
            "COLLECTION": (list, tuple, set),
        }

        for key, value in kwargs.items():
            if key not in expected_props:
                continue

            prop_type = expected_props[key]["type"]
            expected_types = type_mapping.get(prop_type, (object,))

            if prop_type == "FLOAT":
                if value is not None and not isinstance(value, (int, float)):
                    errors.append(f"'{key}' must be numeric (int or float), got {type(value).__name__}")
            elif prop_type == "INT":
                if value is not None and (isinstance(value, float) or not isinstance(value, int)):
                    try:
                        # Try to convert
                        int(value)
                    except (TypeError, ValueError):
                        errors.append(f"'{key}' must be int, got {type(value).__name__}")
            elif prop_type == "BOOLEAN":
                if value is not None and not isinstance(value, (bool, int)):
                    errors.append(f"'{key}' must be boolean, got {type(value).__name__}")
            elif prop_type == "STRING":
                if value is not None and not isinstance(value, str):
                    errors.append(f"'{key}' must be string, got {type(value).__name__}")
            elif prop_type == "ENUM":
                if value is not None and not isinstance(value, str):
                    errors.append(f"'{key}' (enum) must be string, got {type(value).__name__}")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

    except Exception as e:
        return {"valid": False, "errors": [f"Schema validation failed: {e}"], "warnings": warnings}


def ops_list(prefix: str | None = None, head_limit: int = 0) -> Dict[str, Any]:
    out: List[str] = []
    for module_name in dir(bpy.ops):
        if module_name.startswith("_"):
            continue
        module = getattr(bpy.ops, module_name, None)
        if module is None:
            continue
        for op_name in dir(module):
            if op_name.startswith("_"):
                continue
            op_id = f"{module_name}.{op_name}"
            if prefix and not op_id.startswith(prefix):
                continue
            out.append(op_id)
    out.sort()
    if head_limit and head_limit > 0:
        out = out[: int(head_limit)]
    return {"operators": out, "count": len(out)}


def ops_invoke(
    operator_id: str,
    kwargs: Dict[str, Any] | None = None,
    execution_context: str = "EXEC_DEFAULT",
    skip_validation: bool = False,
) -> Dict[str, Any]:
    """Invoke a Blender operator with optional parameter validation.

    Args:
        operator_id: Operator ID like 'mesh.primitive_cube_add'.
        kwargs: Operator parameters.
        execution_context: Execution context (EXEC_DEFAULT, INVOKE_DEFAULT, etc).
        skip_validation: If True, skip parameter validation (not recommended).

    Returns:
        Operator result with validation results if enabled.
    """
    params = kwargs or {}

    result: Dict[str, Any] = {
        "operator_id": operator_id,
        "validation": None,
        "schema": None,
        "result": None,
        "error": None,
    }

    # Pre-validation
    if not skip_validation:
        try:
            validation = _validate_op_args(operator_id, params)
            result["validation"] = validation

            if not validation["valid"]:
                error_msg = f"Parameter validation failed: {'; '.join(validation['errors'])}"
                result["error"] = {
                    "type": "ValidationError",
                    "message": error_msg,
                    "suggested_fix": f"Check parameter types and required fields",
                }
                return result

            # Get schema for documentation
            result["schema"] = _get_operator_schema(operator_id)

        except Exception as e:
            # Validation failed but we'll try execution anyway
            result["validation"] = {"valid": True, "errors": [f"Schema error: {e}"], "warnings": []}

    # Execute
    try:
        op = _resolve_operator(operator_id)

        # Convert numeric parameters to correct types
        if result["schema"]:
            for prop in result["schema"].get("properties", []):
                pid = prop["identifier"]
                if pid in params:
                    ptype = prop.get("type", "")
                    if ptype == "INT":
                        params[pid] = int(params[pid])
                    elif ptype == "FLOAT":
                        params[pid] = float(params[pid])

        exec_result = op(execution_context, **params)
        result["result"] = str(exec_result)

    except TypeError as e:
        # Parameter type mismatch
        result["error"] = {
            "type": "TypeError",
            "message": str(e),
            "suggested_fix": "Check parameter types in schema. Use ops_introspect() for details.",
            "suggested_call": _generate_sample_call(operator_id, result.get("schema", {}).get("properties", [])),
        }
    except RuntimeError as e:
        # Context error (wrong mode, etc.)
        result["error"] = {
            "type": "RuntimeError",
            "message": str(e),
            "suggested_fix": "Check object mode and selection context. Ensure mesh is in edit mode when required.",
        }
    except Exception as e:
        result["error"] = {
            "type": type(e).__name__,
            "message": str(e),
            "suggested_fix": "Check operator availability in current Blender version.",
        }

    return result


def _generate_sample_call(operator_id: str, properties: List[Dict[str, Any]]) -> str:
    """Generate a sample valid call based on schema."""
    if not properties:
        return f'ops_invoke("{operator_id}", {{}})'

    required = [p for p in properties if p.get("is_required")]
    optional = [p for p in properties if not p.get("is_required")][:2]  # Show max 2 optional

    def get_sample_value(prop: Dict[str, Any]) -> str:
        ptype = prop.get("type", "")
        enum = prop.get("enum_items")
        if enum:
            return f'"{enum[0]}"'
        if ptype == "BOOLEAN":
            return "True"
        if ptype == "INT":
            return "1"
        if ptype == "FLOAT":
            return "1.0"
        if ptype == "STRING":
            return f'"value"'
        return "None"

    args = ', '.join([f'"{p["identifier"]}": {get_sample_value(p)}' for p in required])
    if optional:
        args += ', ' + ', '.join([f'"{p["identifier"]}": {get_sample_value(p)}' for p in optional])

    return f'ops_invoke("{operator_id}", {{{args}}})'


def ops_introspect(operator_id: str) -> Dict[str, Any]:
    """Get detailed parameter schema for an operator.

    Args:
        operator_id: Operator ID like 'mesh.primitive_cube_add'.

    Returns:
        Full schema with parameter types, defaults, enums, and sample call.
    """
    schema = _get_operator_schema(operator_id)

    # Add sample call for better UX
    schema["example_call"] = _generate_sample_call(
        operator_id, schema.get("properties", [])
    )

    return schema


def ops_search(query: str, head_limit: int = 20) -> Dict[str, Any]:
    q = (query or "").strip().lower()
    if not q:
        return {"results": [], "count": 0}

    all_ops: List[str] = []
    for module_name in dir(bpy.ops):
        if module_name.startswith("_"):
            continue
        module = getattr(bpy.ops, module_name, None)
        if module is None:
            continue
        for op_name in dir(module):
            if op_name.startswith("_"):
                continue
            all_ops.append(f"{module_name}.{op_name}")

    def score(op_id: str) -> int:
        oid = op_id.lower()
        if oid == q:
            return 1000
        if oid.startswith(q):
            return 900
        if q in oid:
            return 600 - oid.index(q)
        qs = [t for t in q.replace(".", "_").split("_") if t]
        s = 0
        for t in qs:
            if t in oid:
                s += 50
        return s

    ranked = [(op_id, score(op_id)) for op_id in all_ops]
    ranked = [x for x in ranked if x[1] > 0]
    ranked.sort(key=lambda x: x[1], reverse=True)
    limit = max(1, int(head_limit)) if head_limit else 20
    top = ranked[:limit]

    return {
        "query": query,
        "count": len(top),
        "results": [{"operator_id": op_id, "score": sc} for op_id, sc in top],
    }


def types_list(prefix: str | None = None, head_limit: int = 0) -> Dict[str, Any]:
    out: List[str] = []
    for name in dir(bpy.types):
        if name.startswith("_"):
            continue
        if prefix and not name.startswith(prefix):
            continue
        out.append(name)
    out.sort()
    if head_limit and head_limit > 0:
        out = out[: int(head_limit)]
    return {"types": out, "count": len(out)}


def data_collections_list(prefix: str | None = None, head_limit: int = 0) -> Dict[str, Any]:
    out: List[str] = []
    for name in dir(bpy.data):
        if name.startswith("_"):
            continue
        if prefix and not name.startswith(prefix):
            continue
        out.append(name)
    out.sort()
    if head_limit and head_limit > 0:
        out = out[: int(head_limit)]
    return {"collections": out, "count": len(out)}


__all__ = [
    "py_get",
    "py_set",
    "py_call",
    "ops_list",
    "ops_search",
    "ops_invoke",
    "ops_introspect",
    "types_list",
    "data_collections_list",
]
