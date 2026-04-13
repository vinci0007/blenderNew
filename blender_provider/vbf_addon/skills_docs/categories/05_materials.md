# Category: Materials (7 skills)

## For Developers & LLM Agents

**Category**: Materials
**Description**: Material creation and assignment
**Total Skills**: 7

### When to Use This Category
After geometry is finalized, before rendering

### Prerequisites
UV unwrapped meshes preferred

### Common Workflow Sequence
```
[create_material_simple] → [add_shader_node] → [assign_material]
```

---

## Skills
## add_shader_node

**Description**: Add a node to a material's node tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| node_type | str | Yes | - |
| name | str | None | No |
| location | List[float] | No | [0, 0] |

---

## add_texture_to_material

**Description**: Add an image texture to a material.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| image_name | str | Yes | - |
| node_type | str | No | ' principled' |
| socket_name | str | No | 'Base Color' |

---

## bake_geometry_nodes

**Description**: Bake geometry nodes to real mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| modifier_name | str | No | 'GeometryNodes' |

---

## bake_particles

**Description**: Bake particle system to memory.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| system_name | str | Yes | - |

---

## bake_texture

**Description**: Bake texture from object(s) to an image.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| image_name | str | Yes | - |
| bake_type | str | No | 'DIFFUSE' |
| pass_filter | List[str] | None | No |

---

## create_material_simple

**Description**: Create or update a Principled BSDF material with basic PBR properties.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| base_color | List[float] | Yes | - |
| roughness | float | No | 0.4 |
| metallic | float | No | 0.0 |

---
