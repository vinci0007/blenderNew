# Category: Geometry (33 skills)

## For Developers & LLM Agents

**Category**: Geometry
**Description**: Mesh geometry processing and editing skills
**Total Skills**: 33

### When to Use This Category
During Phase 3 (Structure) and Phase 4 (Detailing) of 3D workflow

### Prerequisites
Must be in Edit Mode or target mesh object must be active

### Common Workflow Sequence
```
[subdivide_mesh] → [loop_cut] → [extrude_faces] → [recalculate_normals]
```

---

## Skills
## bridge_edge_loops

**Description**: Bridge selected edge loops in a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## create_attribute

**Description**: Create a new attribute on mesh geometry.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| attribute_name | str | Yes | - |
| domain | str | No | 'POINT' |
| data_type | str | No | 'FLOAT' |

---

## create_beveled_box

**Description**: Create a cube with a bevel modifier applied for rounded edges.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| size | List[float] | Yes | - |
| location | List[float] | Yes | - |
| bevel_width | float | No | 0.03 |
| bevel_segments | int | No | 3 |

---

## create_camera

**Description**: Create a camera in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| location | List[float] | Yes | - |
| rotation_euler | List[float] | None | No |
| focal_length | float | No | 50.0 |
| sensor_width | float | No | 36.0 |

---

## create_collection

**Description**: Create a new collection in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| parent_name | str | None | No |

---

## create_compositor_tree

**Description**: Enable and set up compositing node tree for a scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| scene_name | Optional[str] | No | None |

---

## create_curve_bezier

**Description**: Create a Bezier curve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| location | List[float] | Yes | - |
| points | List[List[float]] | Yes | - |
| is_cyclic | bool | No | False |

---

## create_curve_circle

**Description**: Create a circular curve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| location | List[float] | Yes | - |
| radius | float | No | 1.0 |
| is_nurbs | bool | No | False |

---

## create_geometry_nodes_tree

**Description**: Create a new Geometry Nodes modifier and node tree for an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| tree_name | str | None | No |

---

## create_image_texture

**Description**: Create a new blank image texture.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| width | int | No | 1024 |
| height | int | No | 1024 |
| color | List[float] | None | No |

---

## create_light

**Description**: Create a light source in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| light_type | str | Yes | - |
| name | str | Yes | - |
| location | List[float] | Yes | - |
| energy | float | No | 10.0 |
| color | List[float] | None | No |
| rotation_euler | List[float] | None | No |

---

## create_nested_cones

**Description**: Create a set of nested, progressively smaller cones joined into one object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name_prefix | str | Yes | - |
| base_location | List[float] | Yes | - |
| layers | int | No | 4 |
| base_radius | float | No | 0.06 |
| top_radius | float | No | 0.006 |
| height | float | No | 0.24 |
| z_jitter | float | No | 0.0 |

---

## create_node_group

**Description**: Create a reusable node group.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |

---

## create_particle_system

**Description**: Add a particle system to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| system_name | str | Yes | - |
| type | str | No | 'EMITTER' |

---

## create_primitive

**Description**: Create a mesh primitive object in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| primitive_type | str | Yes | - |
| name | str | Yes | - |
| location | List[float] | Yes | - |
| rotation_euler | List[float] | None | No |
| scale | List[float] | None | No |
| size | List[float] | None | No |
| radius | float | None | No |
| height | float | None | No |

---

## create_shader_node_tree

**Description**: Create a new shader node tree for an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| tree_name | str | No | 'ShaderNodeTree' |

---

## create_text

**Description**: Create a text object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| text | str | Yes | - |
| location | List[float] | Yes | - |
| size | float | No | 1.0 |
| extrude | float | No | 0.0 |

---

## create_vertex_group

**Description**: Create a new vertex group on a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| group_name | str | Yes | - |

---

## extrude_faces

**Description**: Extrude faces of a mesh object along normals.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| amount | float | No | 1.0 |
| normal | List[float] | None | No |

---

## inset_faces

**Description**: Inset faces of a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| thickness | float | No | 0.1 |
| depth | float | No | 0.0 |

---

## join_objects

**Description**: Merge multiple mesh objects into a single object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | Yes | - |
| new_name | str | None | No |

---

## recalculate_normals

**Description**: Recalculate mesh vertex normals.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| inside | bool | No | False |

---

## remove_attribute

**Description**: Remove a geometry attribute.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| attribute_name | str | Yes | - |

---

## remove_collection

**Description**: Remove a collection from the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| delete_objects | bool | No | False |

---

## remove_constraint

**Description**: Remove a constraint from an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| constraint_name | str | Yes | - |

---

## remove_doubles

**Description**: Merge duplicate vertices by distance.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| distance | float | No | 0.0001 |

---

## remove_particle_system

**Description**: Remove a particle system from an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| system_name | str | Yes | - |

---

## set_sharp_edges

**Description**: Mark edges as sharp based on angle.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| angle | float | No | 60.0 |

---

## shade_flat

**Description**: Set flat shading on a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## shade_smooth

**Description**: Set smooth shading on a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| auto_smooth | bool | No | True |

---

## subdivide_mesh

**Description**: Subdivide mesh faces.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| cuts | int | No | 1 |
| smoothness | float | No | 0.0 |

---

## triangulate_faces

**Description**: Convert mesh polygons to triangles.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---
