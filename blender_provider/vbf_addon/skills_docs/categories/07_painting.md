# Category: Painting (18 skills)

## For Developers & LLM Agents

**Category**: Painting
**Description**: Texture, vertex, and weight painting tools
**Total Skills**: 18

### When to Use This Category
For hand-painted textures or vertex color workflows

### Prerequisites
UV unwrap or vertex paint mode

### Common Workflow Sequence
```
[uv_texture_paint_prep] → [texture_paint_mode] → [paint_image]
```

---

## Skills
## clone_from_image

**Description**: Set clone source image.

| Parameter | Type | Required | Default |
|---|---|---|---|
| image_name | str | Yes | - |


---

## image_paint_slot

**Description**: Set the active paint slot for texture painting.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| slot_index | int | Yes | - |


---

## paint_image

**Description**: Set the active paint image.

| Parameter | Type | Required | Default |
|---|---|---|---|
| image_name | str | Yes | - |


---

## paint_operator_enable

**Description**: Enable a paint operator (Clone, Smear, Soften, etc.).

| Parameter | Type | Required | Default |
|---|---|---|---|
| operator | str | Yes | - |


---

## project_paint

**Description**: Project paint using camera view.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| image_name | str | Yes | - |


---

## quick_paint

**Description**: Quick paint on a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| color | List[float] | Yes | - |
| size | int | No | 50 |


---

## set_paint_symmetry

**Description**: Set texture paint symmetry.

| Parameter | Type | Required | Default |
|---|---|---|---|
| x | bool | No | True |
| y | bool | No | False |
| z | bool | No | False |


---

## set_texture_paint_brush

**Description**: Configure the texture paint brush.

| Parameter | Type | Required | Default |
|---|---|---|---|
| brush_name | str | No | 'Brush' |
| size | int | No | 50 |
| strength | float | No | 1.0 |
| color | List[float] | No | [1.0, 1.0, 1.0, 1.0] |


---

## set_vertex_paint_brush

**Description**: Configure the vertex paint brush.

| Parameter | Type | Required | Default |
|---|---|---|---|
| brush_name | str | No | 'Draw' |
| size | int | No | 50 |
| strength | float | No | 1.0 |
| color | List[float] | No | [1.0, 1.0, 1.0, 1.0] |


---

## set_weight_paint_brush

**Description**: Configure the weight paint brush.

| Parameter | Type | Required | Default |
|---|---|---|---|
| brush_name | str | No | 'Draw' |
| size | int | No | 50 |
| strength | float | No | 1.0 |


---

## texture_paint_fill

**Description**: Fill the active image with a solid color.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| color | List[float] | Yes | - |


---

## texture_paint_mode

**Description**: Enter or exit texture paint mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| enable | bool | No | True |


---

## uv_texture_paint_prep

**Description**: Prepare object for UV texture painting.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| image_name | str | Yes | - |
| resolution | int | No | 1024 |


---

## vertex_paint_fill

**Description**: Fill vertex colors on a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| color | List[float] | Yes | - |


---

## vertex_paint_mode

**Description**: Enter or exit vertex paint mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| enable | bool | No | True |


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
