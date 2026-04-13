# Category: Rendering (12 skills)

## For Developers & LLM Agents

**Category**: Rendering
**Description**: Render and output settings
**Total Skills**: 12

### When to Use This Category
Final output stage

### Prerequisites
Cameras and lights set up

### Common Workflow Sequence
```
[set_cycles_samples] → [render_image] → [export_fbx]
```

---

## Skills
## camera_look_at

**Description**: Orient a camera to look at a specific point.

| Parameter | Type | Required | Default |
|---|---|---|---|
| camera_name | str | Yes | - |
| target_point | List[float] | Yes | - |
| up | str | No | 'z_up' |

---

## compositor_add_alpha_over

**Description**: Add an alpha over node to the compositor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | Optional[str] | No | None |

---

## compositor_add_blur

**Description**: Add a blur node to the compositor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| size_x | float | No | 10.0 |
| size_y | float | No | 10.0 |
| name | Optional[str] | No | None |

---

## compositor_add_bright_contrast

**Description**: Add brightness/contrast node to the compositor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| bright | float | No | 0.0 |
| contrast | float | No | 0.0 |
| name | Optional[str] | No | None |

---

## compositor_add_color_balance

**Description**: Add a color balance node to the compositor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| lift | List[float] | No | [1.0, 1.0, 1.0] |
| gamma | List[float] | No | [1.0, 1.0, 1.0] |
| gain | List[float] | No | [1.0, 1.0, 1.0] |
| name | Optional[str] | No | None |

---

## compositor_add_image

**Description**: Add an image input node to the compositor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| name | Optional[str] | No | None |

---

## compositor_add_mix

**Description**: Add a mix node to the compositor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| blend_type | str | No | 'MIX' |
| factor | float | No | 0.5 |
| name | Optional[str] | No | None |

---

## compositor_clear_tree

**Description**: Clear all nodes from the compositor tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| confirm | bool | No | false |

---

## compositor_delete_node

**Description**: Delete a compositor node.

| Parameter | Type | Required | Default |
|---|---|---|---|
| node_name | str | Yes | - |

---

## compositor_list_nodes

**Description**: List all nodes in the compositor tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filter_type | str | No | - |

---

## render_image

**Description**: Render a single image.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | Optional[str] | No | None |
| width | Optional[int] | No | None |
| height | Optional[int] | No | None |

---
