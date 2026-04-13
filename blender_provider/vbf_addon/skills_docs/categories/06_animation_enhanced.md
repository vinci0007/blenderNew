# Category: Animation Enhanced (13 skills)

## For Developers & LLM Agents

**Category**: Animation Enhanced
**Description**: Advanced animation tools including NLA and shape keys
**Total Skills**: 13

### When to Use This Category
For bone animation, shape key animation, or layered animation

### Prerequisites
Armature or shape keys must exist

### Common Workflow Sequence
```
[create_action] → [insert_keyframe_bone] → [nla_add_strip]
```

---

## Skills
---

## bake_animation

**Description**: Bake animation to keyframes.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| frame_start | int | No | 1 |
| frame_end | int | No | 250 |
| only_selected | bool | No | True |

---

## copy_keyframes

**Description**: Copy keyframes to clipboard.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| data_path | str | No | None |
| frame_start | int | No | None |
| frame_end | int | No | None |

---

## create_action

**Description**: Create a new action for animation.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |

---

## delete_action

**Description**: Delete an action.

| Parameter | Type | Required | Default |
|---|---|---|---|
| action_name | str | Yes | - |

---

## insert_keyframe_bone

**Description**: Insert keyframe for a bone in pose mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |
| data_path | str | Yes | location |
| frame | int | No | None |

---

## insert_keyframe_shape_key

**Description**: Insert keyframe for a shape key value.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| shape_key_name | str | Yes | - |
| frame | int | No | None |
| value | float | No | 0.0 |

---

## list_actions

**Description**: List all available actions.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filter | str | No | - |

---

## nla_add_strip

**Description**: Add an animation strip to the NLA editor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| action_name | str | Yes | - |
| frame_start | int | No | 1 |

---

## paste_keyframes

**Description**: Paste keyframes from clipboard.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| data_path | str | No | None |
| frame_offset | int | No | 0 |

---

## set_action

**Description**: Set the active action for an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| action_name | str | Yes | - |

---

## set_keyframe_handle_type

**Description**: Set the interpolation handle type for keyframes.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| data_path | str | Yes | - |
| frame | int | Yes | - |
| handle_type | str | No | AUTO |

---

## set_nla_strip_properties

**Description**: Set properties of an NLA strip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strip_name | str | Yes | - |
| properties | Dict | Yes | - |

---
