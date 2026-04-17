import traceback
from typing import Any, Dict, List

import bpy  # type: ignore


class SkillRuntimeError(RuntimeError):
    pass


def _deny_unsafe_attr(name: str) -> None:
    if name.startswith("__") and name.endswith("__"):
        raise SkillRuntimeError(f"Unsafe attribute access blocked: {name}")
    if name in {"__class__", "__dict__", "__getattribute__", "__setattr__", "__delattr__"}:
        raise SkillRuntimeError(f"Unsafe attribute access blocked: {name}")


def _apply_steps(root: Any, steps: List[Dict[str, Any]]) -> Any:
    cur: Any = root
    for i, st in enumerate(steps):
        if not isinstance(st, dict) or len(st) != 1:
            raise SkillRuntimeError(f"Invalid path step at {i}: {st}")

        if "attr" in st:
            attr = st["attr"]
            if not isinstance(attr, str) or not attr:
                raise SkillRuntimeError(f"Invalid attr token at {i}: {st}")
            _deny_unsafe_attr(attr)
            if not hasattr(cur, attr):
                raise SkillRuntimeError(f"Attribute not found: {attr}")
            cur = getattr(cur, attr)
            continue

        if "key" in st:
            cur = cur[st["key"]]
            continue

        if "index" in st:
            idx = st["index"]
            if not isinstance(idx, int):
                raise SkillRuntimeError(f"Invalid index token at {i}: {st}")
            cur = cur[idx]
            continue

        if "len" in st:
            flag = st["len"]
            if flag is not True:
                raise SkillRuntimeError(f"Invalid len token at {i}: {st}")
            cur = len(cur)
            continue

        raise SkillRuntimeError(f"Unknown path token at {i}: {st}")

    return cur


def _serialize_best_effort(value: Any) -> Any:
    try:
        if hasattr(value, "to_tuple"):
            return list(value.to_tuple())
        if hasattr(value, "name"):
            return {"name": str(getattr(value, "name"))}
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [_serialize_best_effort(v) for v in value]
        if isinstance(value, dict):
            return {str(k): _serialize_best_effort(v) for k, v in value.items()}
    except Exception:
        pass
    return str(value)


def py_get(path_steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        if not isinstance(path_steps, list):
            raise SkillRuntimeError("path_steps must be a list")
        value = _apply_steps(bpy, path_steps)
        return {"value": _serialize_best_effort(value)}
    except Exception as e:
        raise RuntimeError(f"py_get failed: {e}\n{traceback.format_exc()}")


def py_set(path_steps: List[Dict[str, Any]], value: Any) -> Dict[str, Any]:
    try:
        if not isinstance(path_steps, list) or not path_steps:
            raise SkillRuntimeError("path_steps must be a non-empty list")

        parent_steps = path_steps[:-1]
        last = path_steps[-1]
        parent = _apply_steps(bpy, parent_steps) if parent_steps else bpy

        if not isinstance(last, dict) or len(last) != 1:
            raise SkillRuntimeError("Last path step must be a single token dict")

        if "attr" in last:
            attr = last["attr"]
            if not isinstance(attr, str) or not attr:
                raise SkillRuntimeError("Invalid attr token")
            _deny_unsafe_attr(attr)
            setattr(parent, attr, value)
            return {"ok": True}

        if "key" in last:
            parent[last["key"]] = value
            return {"ok": True}

        if "index" in last:
            idx = last["index"]
            if not isinstance(idx, int):
                raise SkillRuntimeError("Invalid index token")
            parent[idx] = value
            return {"ok": True}

        raise SkillRuntimeError("Unsupported last token")
    except Exception as e:
        raise RuntimeError(f"py_set failed: {e}\n{traceback.format_exc()}")


def py_call(
    callable_path_steps: List[Dict[str, Any]],
    args: List[Any] | None = None,
    kwargs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    try:
        if not isinstance(callable_path_steps, list) or not callable_path_steps:
            raise SkillRuntimeError("callable_path_steps must be a non-empty list")

        fn = _apply_steps(bpy, callable_path_steps)
        if not callable(fn):
            raise SkillRuntimeError("Resolved target is not callable")

        a = args or []
        k = kwargs or {}
        if not isinstance(a, list) or not isinstance(k, dict):
            raise SkillRuntimeError("args must be list and kwargs must be dict")

        result = fn(*a, **k)
        return {"result": _serialize_best_effort(result)}
    except Exception as e:
        raise RuntimeError(f"py_call failed: {e}\n{traceback.format_exc()}")
