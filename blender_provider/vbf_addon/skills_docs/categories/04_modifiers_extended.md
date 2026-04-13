# Category: Modifiers Extended (11 skills)

## For Developers & LLM Agents

**Category**: Modifiers Extended
**Description**: Advanced modifier operations for professional workflows
**Total Skills**: 11

### When to Use This Category
During hard-surface modeling (solidify for panels) or procedural modeling (array, mirror)

### Prerequisites
Understanding of modifier stack order

### Common Workflow Sequence
```
[add_modifier_mirror] → [add_modifier_bevel] → [add_modifier_subdivision]
```

---

## Skills
---

## add_modifier_array

**Description**: Add an Array modifier to duplicate objects in a pattern.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| count | int | No | 2 |
| use_relative_offset | bool | No | True |
| relative_offset | List[float] | No | [1.0, 0.0, 0.0] |

---

## add_modifier_boolean

**Description**: Add a Boolean modifier for non-destructive mesh operations.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| operation | str | Yes | - |
| operand_object | str | Yes | - |

---

## add_modifier_curve

**Description**: Add a Curve modifier to deform mesh along a curve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| curve_object | str | Yes | - |
| deform_axis | str | No | X |

---

## add_modifier_displace

**Description**: Add a Displace modifier to displace mesh using a texture.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| texture_name | str | No | None |
| strength | float | No | 1.0 |

---

## add_modifier_mirror

**Description**: Add a Mirror modifier to create symmetrical copies.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| use_axis | List[bool] | No | [True, False, False] |
| use_bisect | bool | No | False |

---

## add_modifier_shrinkwrap

**Description**: Add a Shrinkwrap modifier to project mesh onto another surface.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| target | str | Yes | - |
| offset | float | No | 0.0 |

---

## add_modifier_solidify

**Description**: Add a Solidify modifier to thicken a mesh or create panel lines.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| thickness | float | No | 0.01 |
| offset | float | No | -1.0 |

---

## configure_modifier

**Description**: Configure properties of an existing modifier.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| modifier_name | str | Yes | - |
| properties | Dict | Yes | - |

---

## list_modifiers

**Description**: List all modifiers on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | No | None |

---

## move_modifier

**Description**: Change the order of modifiers in the stack.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| modifier_name | str | Yes | - |
| direction | str | Yes | UP |

---
