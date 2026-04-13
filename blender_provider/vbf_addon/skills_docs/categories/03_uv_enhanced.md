# Category: UV Enhanced (9 skills)

## For Developers & LLM Agents

**Category**: UV Enhanced
**Description**: Advanced UV projection and optimization
**Total Skills**: 9

### When to Use This Category
When unwrapping complex geometry or optimizing UV space

### Prerequisites
Mesh with UV seams marked

### Common Workflow Sequence
```
[uv_project_from_view] → [uv_minimize_stretch] → [uv_stitch]
```

---

## Skills
---

## uv_average_islands_scale

**Description**: Average scale of UV islands.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## uv_cube_project

**Description**: Cubic UV projection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## uv_cylinder_project

**Description**: Cylindrical UV projection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## uv_minimize_stretch

**Description**: Minimize UV stretch with least squares.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| iterations | int | No | 100 |

---

## uv_pin

**Description**: Pin UV vertices in place.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| pin | bool | No | True |

---

## uv_project_from_view

**Description**: Project UV from current camera/3D view.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## uv_sphere_project

**Description**: Spherical UV projection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## uv_stitch

**Description**: Stitch UVs of adjacent faces.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---
