# Category: Gateway (11 skills)

## For Developers & LLM Agents

**Category**: Gateway
**Description**: Low-level runtime gateway skills for direct Blender API access
**Total Skills**: 11

### When to Use This Category
When high-level skills are insufficient. Use py_call/py_get/py_set for direct property access, or ops_invoke/ops_search for operator discovery

### Prerequisites
Understanding of Blender Python API (bpy)

### Common Workflow Sequence
```
[py_get/property check] → [py_set/set value] → [py_call/execute]
```

---

## Skills
---

## api_validator

**Description**: Check whether a bpy API path exists and is accessible.

| Parameter | Type | Required | Default |
|---|---|---|---|
| api_path | str | Yes | - |

---

## data_collections_list

**Description**: List all collections in the data.

| Parameter | Type | Required | Default |
|---|---|---|---|
| collection_type | str | No | - |

---

## ops_introspect

**Description**: Get parameters for a bpy operator.

| Parameter | Type | Required | Default |
|---|---|---|---|
| operator_id | str | Yes | - |

---

## ops_invoke

**Description**: Invoke a bpy operator directly.

| Parameter | Type | Required | Default |
|---|---|---|---|
| operator_id | str | Yes | - |
| kwargs | Dict | No | {} |

---

## ops_list

**Description**: List available bpy operators.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filter | str | No | None |

---

## ops_search

**Description**: Search for bpy operators by name.

| Parameter | Type | Required | Default |
|---|---|---|---|
| query | str | Yes | - |

---

## py_call

**Description**: Call Blender Python function.

| Parameter | Type | Required | Default |
|---|---|---|---|
| function_path | str | Yes | - |
| args | List | No | [] |
| kwargs | Dict | No | {} |

---

## py_get

**Description**: Get Blender property value via path.

| Parameter | Type | Required | Default |
|---|---|---|---|
| path_steps | List[Dict] | Yes | - |

---

## py_set

**Description**: Set Blender property value via path.

| Parameter | Type | Required | Default |
|---|---|---|---|
| path_steps | List[Dict] | Yes | - |
| value | Any | Yes | - |

---

## types_list

**Description**: List available bpy types.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filter_class | str | No | - |

---
