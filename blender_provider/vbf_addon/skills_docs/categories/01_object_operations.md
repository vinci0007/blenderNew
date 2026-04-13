# Category: Object Operations (11 skills)

## For Developers & LLM Agents

**Category**: Object Operations
**Description**: Object-level operations and transformations
**Total Skills**: 11

### When to Use This Category
After creating objects, to manipulate, select, or transform them

### Prerequisites
Objects must exist in scene

### Common Workflow Sequence
```
[object_select_all] → [object_duplicate] → [object_origin_set]
```

---

## Skills
---

## object_convert

**Description**: Convert object to different type (mesh/curve/etc).

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| target_type | str | Yes | MESH |

---

## object_duplicate

**Description**: Duplicate selected objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | No | [] |
| linked | bool | No | False |

---

## object_hide_set

**Description**: Hide or show objects in viewport.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | No | [] |
| hide | bool | No | True |

---

## object_make_local

**Description**: Make linked objects local.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## object_move_to_collection

**Description**: Move objects to a different collection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | Yes | - |
| collection_name | str | Yes | - |

---

## object_origin_set

**Description**: Set object origin to geometry center, 3D cursor, etc.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| origin_type | str | No | GEOMETRY_ORIGIN |
| center | str | No | BOUNDS |

---

## object_select_all

**Description**: Select or deselect all objects in scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| action | str | No | SELECT |

---

## object_select_by_type

**Description**: Select objects by their type.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_type | str | Yes | - |
| extend | bool | No | False |

---

## object_shade_flat

**Description**: Set flat shading on objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | No | [] |

---

## object_shade_smooth

**Description**: Set smooth shading on objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | No | [] |

---
