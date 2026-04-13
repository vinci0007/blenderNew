# Category: Edge Control (10 skills)

## For Developers & LLM Agents

**Category**: Edge Control
**Description**: Edge creasing and bevel weight control for subdivision surfaces
**Total Skills**: 10

### When to Use This Category
Before applying subdivision modifier to control hard/soft edges

### Prerequisites
Mesh with edges in Edit Mode

### Common Workflow Sequence
```
[mark_edge_crease] (1.0 for hard, 0.0 for soft) → [add_modifier_subdivision]
```

---

## Skills
---

## bisect_mesh

**Description**: Cut mesh with a plane (bisect operation).

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| plane_co | List[float] | No | [0, 0, 0] |
| plane_no | List[float] | No | [0, 0, 1] |
| clear_inner | bool | No | False |
| clear_outer | bool | No | False |

---

## clear_edge_bevel_weight

**Description**: Clear bevel weight from selected edges.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| edge_indices | List[int] | No | [] |

---

## clear_edge_crease

**Description**: Remove crease from selected edges.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| edge_indices | List[int] | No | [] |

---

## fill_holes

**Description**: Fill holes in mesh by creating faces.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| sides | int | No | 0 |

---

## get_edge_data

**Description**: Get data about edges in a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## mark_edge_crease

**Description**: Mark edges with crease value for subdivision surfaces.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| edge_indices | List[int] | No | [] |
| crease | float | No | 1.0 |

---

## select_edge_rings

**Description**: Select edge rings around a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| edge_index | int | No | 0 |

---

## set_edge_bevel_weight

**Description**: Set bevel weight for edges to control bevel modifier.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| edge_indices | List[int] | No | [] |
| weight | float | No | 1.0 |

---

## symmetrize_mesh

**Description**: Symmetrize mesh across an axis.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| direction | str | No | NEGATIVE_X |
| threshold | float | No | 0.0001 |

---
