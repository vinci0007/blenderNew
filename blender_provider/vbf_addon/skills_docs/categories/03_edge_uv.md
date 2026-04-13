# Category: Edge/UV (5 skills)

## For Developers & LLM Agents

**Category**: Edge/UV
**Description**: UV mapping and seam marking skills
**Total Skills**: 5

### When to Use This Category
After geometry is finalized, before texture painting or material export

### Prerequisites
Mesh must be unwrapped

### Common Workflow Sequence
```
[mark_seam] → [unwrap_mesh] → [pack_uv_islands]
```

---

## Skills
## mark_seam

**Description**: Mark selected edges as UV seams.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| clear | bool | No | False |

---

## project_paint

**Description**: Project paint using camera view.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| image_name | str | Yes | - |

---

## unwrap_mesh

**Description**: Unwrap mesh UVs using standard unwrap algorithm.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| method | str | No | 'ANGLE_BASED' |
| margin | float | No | 0.001 |

---

## uv_texture_paint_prep

**Description**: Prepare object for UV texture painting.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| image_name | str | Yes | - |
| resolution | int | No | 1024 |

---
