# Category: Armature (12 skills)

## For Developers & LLM Agents

**Category**: Armature
**Description**: Rigging and armature/bone operations
**Total Skills**: 12

### When to Use This Category
For character rigging and skinning

### Prerequisites
Understanding of rigging fundamentals

### Common Workflow Sequence
```
[create_armature] → [add_bone] → [create_vertex_group] → [skin_to_armature]
```

---

## Skills
## add_armature_constraint

**Description**: Add armature constraint to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| child_object | str | Yes | - |
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |
| constraint_type | str | No | 'CHILD_OF' |

---

## add_bone

**Description**: Add a bone to an armature in edit mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |
| head | List[float] | Yes | - |
| tail | List[float] | Yes | - |
| roll | float | No | 0.0 |
| parent_bone | str | None | No |
| connect | bool | No | False |

---

## add_ik_constraint

**Description**: Add Inverse Kinematics (IK) constraint to a pose bone.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| bone_name | str | Yes | - |
| chain_length | int | No | 2 |
| use_rotation | bool | No | False |

---

## assign_vertex_weights

**Description**: Assign weights to vertices in a vertex group.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| group_name | str | Yes | - |
| vertex_indices | List[int] | Yes | - |
| weight | float | No | 1.0 |
| type | str | No | 'REPLACE' |

---

## create_armature

**Description**: Create a new armature object for character rigging.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| location | List[float] | No | [0.0, 0.0, 0.0] |

---

## delete_bone

**Description**: Delete a bone from an armature.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |

---

## edit_bone

**Description**: Edit an existing bone's properties.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |
| head | List[float] | None | No |
| tail | List[float] | None | No |
| roll | float | None | No |
| length | float | None | No |

---

## list_bones

**Description**: List all bones in an armature.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |

---

## skin_to_armature

**Description**: Skin/parent a mesh object to an armature with automatic weights.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| armature_name | str | Yes | - |
| create_modifiers | bool | No | True |

---

## weight_paint_mode

**Description**: Enter or exit weight paint mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| enable | bool | No | True |

---

## weight_paint_set

**Description**: Set weight for all vertices in a vertex group.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| vertex_group | str | Yes | - |
| weight | float | No | 1.0 |

---
