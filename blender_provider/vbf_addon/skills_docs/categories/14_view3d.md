# Category: View3D (8 skills)

## For Developers & LLM Agents

**Category**: View3D
**Description**: 3D viewport navigation and 3D cursor
**Total Skills**: 8

### When to Use This Category
For viewport control and snapping operations

### Prerequisites
None

### Common Workflow Sequence
```
[view3d_cursor_set] -> [view3d_snap_cursor_to_selected] -> [view3d_view_selected]
```

---

## Skills
---

## view3d_cursor_set

**Description**: Set the 3D cursor position.

| Parameter | Type | Required | Default |
|---|---|---|---|
| location | List[float] | Yes | - |

---

## view3d_localview

**Description**: Toggle local view (isolate selected).

| Parameter | Type | Required | Default |
|---|---|---|---|
| - | None | - | - |

---

## view3d_snap_cursor_to_center

**Description**: Snap 3D cursor to world origin.

| Parameter | Type | Required | Default |
|---|---|---|---|
| - | - | - | - |

---

## view3d_snap_cursor_to_selected

**Description**: Snap 3D cursor to selected elements.

| Parameter | Type | Required | Default |
|---|---|---|---|
| - | - | - | - |

---

## view3d_snap_selected_to_cursor

**Description**: Snap selected objects to 3D cursor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| use_offset | bool | No | True |
| use_rotation | bool | No | False |

---

## view3d_view_all

**Description**: Frame view on all objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| use_all_regions | bool | No | False |
| center | bool | No | False |

---

## view3d_view_selected

**Description**: Frame view on selected objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| use_all_regions | bool | No | False |

---
