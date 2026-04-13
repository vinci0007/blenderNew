# Category: Grease Pencil (18 skills)

## For Developers & LLM Agents

**Category**: Grease Pencil
**Description**: 2D animation and annotation tools
**Total Skills**: 18

### When to Use This Category
For 2D animation or 3D annotations

### Prerequisites
None

### Common Workflow Sequence
```
[gpencil_add_blank] → [gpencil_layer_create] → [gpencil_draw_stroke]
```

---

## Skills
## gpencil_add_blank

**Description**: Add a blank Grease Pencil object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | No | 'Grease Pencil' |
| location | List[float] | No | [0, 0, 0] |

---

## gpencil_convert_to_curve

**Description**: Convert Grease Pencil strokes to curve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| new_name | Optional[str] | No | None |

---

## gpencil_convert_to_mesh

**Description**: Convert Grease Pencil strokes to mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| new_name | Optional[str] | No | None |
| thickness | float | No | 0.01 |

---

## gpencil_delete_stroke

**Description**: Delete a stroke from Grease Pencil.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |
| stroke_index | int | No | -1 |

---

## gpencil_draw_line

**Description**: Draw a line stroke in Grease Pencil.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |
| start_point | List[float] | Yes | - |
| end_point | List[float] | Yes | - |
| pressure | float | No | 1.0 |
| strength | float | No | 1.0 |

---

## gpencil_draw_stroke

**Description**: Draw a multi-point stroke in Grease Pencil.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |
| points | List[List[float]] | Yes | - |
| pressure | float | No | 1.0 |
| strength | float | No | 1.0 |

---

## gpencil_duplicate_frame

**Description**: Duplicate a frame in Grease Pencil layer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |
| source_frame | int | Yes | - |
| target_frame | int | Yes | - |

---

## gpencil_export_svg

**Description**: Export Grease Pencil to SVG.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |

---

## gpencil_fill

**Description**: Draw a filled polygon stroke in Grease Pencil.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |
| points | List[List[float]] | Yes | - |
| pressure | float | No | 1.0 |

---

## gpencil_frame_add

**Description**: Add a frame to a Grease Pencil layer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |
| frame_number | Optional[int] | No | None |

---

## gpencil_import_svg

**Description**: Import SVG as Grease Pencil.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| scale | float | No | 1.0 |

---

## gpencil_layer_create

**Description**: Create a new Grease Pencil layer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |

---

## gpencil_layer_remove

**Description**: Remove a Grease Pencil layer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |

---

## gpencil_material_add

**Description**: Add a material to Grease Pencil.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| material_name | str | No | 'GP_Material' |
| stroke_color | List[float] | No | [0, 0, 0, 1] |
| fill_color | List[float] | No | [0.5, 0.5, 0.5, 1] |

---

## gpencil_set_line_attributes

**Description**: Set line attributes for Grease Pencil layer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |
| line_width | float | No | 3.0 |
| offset | float | No | 0.0 |

---

## gpencil_set_material

**Description**: Set active material for Grease Pencil.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| material_index | int | Yes | - |

---

## gpencil_set_view_layer

**Description**: Set view layer visibility and lock for Grease Pencil layer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| layer_name | str | Yes | - |
| show_in_view | bool | No | True |
| lock | bool | No | False |

---
