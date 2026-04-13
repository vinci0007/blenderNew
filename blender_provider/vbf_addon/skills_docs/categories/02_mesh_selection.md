# Category: Mesh Selection (8 skills)

## For Developers & LLM Agents

**Category**: Mesh Selection
**Description**: Mesh element selection tools
**Total Skills**: 8

### When to Use This Category
Before any geometry operation that requires specific faces/edges/vertices

### Prerequisites
Object must be in Edit Mode

### Common Workflow Sequence
```
[mesh_select_mode] → [mesh_select_similar] → [mesh_loop_select]
```

---

## Skills
---

## mesh_loop_select

**Description**: Select edge or face loops.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## mesh_select_all

**Description**: Select or deselect all mesh elements.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| action | str | No | SELECT |

---

## mesh_select_mirror

**Description**: Select mirrored elements.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| axis | str | No | X |

---

## mesh_select_mode

**Description**: Set the mesh selection mode (vertex/edge/face).

| Parameter | Type | Required | Default |
|---|---|---|---|
| mode | str | Yes | - |

---

## mesh_select_more_less

**Description**: Expand or contract selection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| mode | str | No | MORE |

---

## mesh_select_non_manifold

**Description**: Select non-manifold geometry.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## mesh_select_similar

**Description**: Select elements similar to current selection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| type | str | Yes | - |

---
