from typing import Any, Dict, List

import bpy  # type: ignore

try:
    # Standard: installed as standalone addon folder (vbf_addon/skill_runtime)
    from ..skill_runtime import py_call, py_get, py_set
except ImportError:
    # Fallback: Blender loads the folder as a plain script (no package context)
    from skill_runtime import py_call, py_get, py_set  # type: ignore


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
) -> Dict[str, Any]:
    op = _resolve_operator(operator_id)
    params = kwargs or {}
    if not isinstance(params, dict):
        raise ValueError("kwargs must be an object/dict")
    result = op(execution_context, **params)
    return {"operator_id": operator_id, "result": str(result)}


def ops_introspect(operator_id: str) -> Dict[str, Any]:
    op = _resolve_operator(operator_id)
    rna = op.get_rna_type()
    props = []
    for p in rna.properties:
        if p.identifier in {"rna_type"}:
            continue
        props.append(
            {
                "identifier": p.identifier,
                "name": p.name,
                "description": p.description,
                "type": str(p.type),
                "is_required": bool(getattr(p, "is_required", False)),
                "is_readonly": bool(getattr(p, "is_readonly", False)),
                "default": str(getattr(p, "default", None)),
            }
        )
    return {
        "operator_id": operator_id,
        "name": rna.name,
        "description": rna.description,
        "properties": props,
    }


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

