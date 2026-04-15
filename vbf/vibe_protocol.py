import copy
from typing import Any, Dict

def resolve_refs_in_value(value: Any, step_results: Dict[str, Dict[str, Any]]) -> Any:
    """
    Resolve {"$ref": "step_id.data.key"} into actual values from step_results.

    Supported roots: "data" (canonical) and "result" (alias for data).
    """
    if isinstance(value, dict) and set(value.keys()) == {"$ref"}:
        ref = value["$ref"]
    elif isinstance(value, str) and value.startswith("$ref:"):
        ref = value[len("$ref:") :].strip()
    else:
        return value

    if not isinstance(ref, str) or not ref:
        raise ValueError("Invalid $ref")

    parts = [p for p in ref.split(".") if p]
    if len(parts) < 3:
        raise ValueError(f"Ref path too short: {ref}")

    step_id = parts[0]
    # Normalize: LLM may use "step_001" format while step_results uses "001"
    if step_id.startswith("step_"):
        step_id = step_id[len("step_") :]
    root = parts[1]
    key_path = parts[2:]

    if step_id not in step_results:
        raise KeyError(f"Unknown step_id in ref: {step_id}")

    node: Any = step_results[step_id]
    if root in ("data", "result"):
        node = node.get("data", {}) if root == "data" else node.get("data", {})
    else:
        node = node.get(root)

    for k in key_path:
        if not isinstance(node, dict):
            raise KeyError(f"Ref path invalid at {k} for ref={ref}")
        if k not in node:
            raise KeyError(f"Ref key missing: {k} for ref={ref}")
        node = node[k]

    return node

def resolve_refs(args: Any, step_results: Dict[str, Dict[str, Any]]) -> Any:
    """Recursively resolve $ref tokens in nested dict/list structures."""
    args_copy = copy.deepcopy(args)

    def rec(x: Any) -> Any:
        if isinstance(x, dict):
            if set(x.keys()) == {"$ref"} or (len(x) == 1 and "$ref" in x):
                return resolve_refs_in_value(x, step_results)
            out: Dict[str, Any] = {}
            for k, v in x.items():
                out[k] = rec(v)
            return out
        if isinstance(x, list):
            return [rec(i) for i in x]
        return resolve_refs_in_value(x, step_results)

    return rec(args_copy)

def merge_step_results_for_prompt(step_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Compact step results for inclusion in LLM repair prompts."""
    compact: Dict[str, Any] = {}
    for step_id, payload in step_results.items():
        if payload.get("ok") is True:
            compact[step_id] = {"ok": True, "data": payload.get("data")}
        else:
            compact[step_id] = {"ok": False, "error": payload.get("error", payload)}
    return compact