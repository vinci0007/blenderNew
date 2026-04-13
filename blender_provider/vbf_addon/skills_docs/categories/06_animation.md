# Category: Animation (11 skills)

## For Developers & LLM Agents

**Category**: Animation
**Description**: Animation and keyframe skills
**Total Skills**: 11

### When to Use This Category
For object animation, driven by keyframes or drivers

### Prerequisites
Animation timeline must be set

### Common Workflow Sequence
```
[set_frame_range] → [insert_keyframe] → [set_keyframe_interpolation]
```

---

## Skills
## add_driver

**Description**: Add a driver to an object property.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |
| target_property | str | Yes | - |
| index | int | No | -1 |
| expression | str | No | '' |

---

## delete_keyframe

**Description**: Delete a keyframe from an object's property.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| frame | float | Yes | - |
| data_path | str | No | 'location' |
| index | int | No | -1 |

---

## driver_add_shape_key

**Description**: Add a driver to a shape key value.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| shape_key_name | str | Yes | - |
| expression | str | Yes | - |

---

## driver_add_variable

**Description**: Add a variable to a driver.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |
| target_property | str | Yes | - |
| var_name | str | Yes | - |
| var_type | str | No | 'SINGLE_PROP' |
| source_object | Optional[str] | No | None |
| source_property | Optional[str] | No | None |
| index | int | No | -1 |

---

## driver_copy

**Description**: Copy a driver from one object/property to another.

| Parameter | Type | Required | Default |
|---|---|---|---|
| source_object | str | Yes | - |
| target_object | str | Yes | - |
| source_property | str | Yes | - |
| target_property | str | Yes | - |

---

## driver_list

**Description**: List all drivers on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |

---

## driver_remove

**Description**: Remove a driver from an object property.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |
| target_property | str | Yes | - |
| index | int | No | -1 |

---

## driver_set_expression

**Description**: Set the expression for a driver.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |
| target_property | str | Yes | - |
| expression | str | Yes | - |
| index | int | No | -1 |

---

## insert_keyframe

**Description**: Insert a keyframe for an object's property.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| frame | float | Yes | - |
| data_path | str | No | 'location' |
| index | int | No | -1 |

---

## shape_key_from_mix

**Description**: Create a new shape key from the current mix of shape keys.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| new_key_name | str | Yes | - |

---
