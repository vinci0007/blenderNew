---
name: Vibe-Blender-Flow Skills (VBF)
description: Execute Blender modeling actions via 357 pre-registered High-Level Skills over JSON-RPC. Includes full coverage for modeling, UV, materials, animation, armature, particles, physics, geometry nodes, sculpting, rendering, and compositing.
metadata:
{
  "version": "2.2.0",
  "skills_count": 357,
  "modules_count": 32,
  "blender_version": "4.0+ / 5.x",
  "openai_compat_planner": {
    "requires": { "bins": ["websockets"] },
    "notes": "Planner runs in client; this doc constrains the model to output skills_plan JSON only."
  }
}
---

# Vibe-Blender-Flow Skills

你必须只输出 `skills_plan` / `repair_plan` 的 JSON（Controller 负责执行 Blender bpy 操作）。

## Claude Skill Mode Guardrails
- 绝不输出任何 `bpy`/`bmesh` 代码、也不输出 Blender 插件脚本代码片段。
- 只能在 plan 中选择允许的 `skill` 名称；禁止编造未知 skill。
- 所有步骤参数必须是 JSON 可序列化类型（number/string/boolean/null/array/object）。
- **上下文强制约束**：在调用任何修改对象、编辑几何体或设置属性的技能之前，必须确保目标对象是 `bpy.context.active_object`。如果 Plan 逻辑中存在对象切换，必须明确包含一个确保对象活跃的步骤，严禁在未确认活跃对象的情况下执行 `bpy.ops` 类操作。
- 如果需要从先前步骤获取对象名或坐标，请使用 `$ref`：
  - 规范用法：`{"$ref":"<step_id>.data.<key>"}`
  - 若使用 `on_success.store_as` 存储别名，后续可用：`{"$ref":"<alias_name>.data.<key>"}`
  - 若存储的是非对象/非 dict 值，请引用：`{"$ref":"<alias_name>.data.value"}`
- 坐标/对齐优先使用 anchor 技能（例如 `move_object_anchor_to_point`），避免在 `$ref` 中做算术。

## skills_plan JSON Schema
每次请求只返回一个 JSON 对象：

```json
{
  "vbf_version": "1.0",
  "plan_id": "string",
  "execution": { "max_retries_per_step": 2 },
  "steps": [
    {
      "step_id": "string",
      "stage": "discover|blockout|boolean|detail|bevel|normal_fix|accessories|material|finalize",
      "skill": "string",
      "args": { "any": "json-serializable" },
      "on_success": {
        "store_as": {
          "alias_name": "string",
          "step_return_json_path": "data.<key>"
        }
      }
    }
  ]
}
```

## repair_plan Schema

```json
{
  "vbf_version": "1.0",
  "plan_id": "string",
  "repair": { "replace_from_step_id": "failed_step_id" },
  "execution": { "max_retries_per_step": 2 },
  "steps": [
    {
      "step_id": "string",
      "skill": "string",
      "args": { "any": "json-serializable" }
    }
  ]
}
```


The following skills provide low-level access to Blender's full Python API. **Use only when high-level skills are insufficient.**

### py_get / py_set / py_call

Direct Python API access with path-based navigation:

```json
{
  "skill": "py_get",
  "args": {
    "path_steps": [
      {"attr": "data"},
      {"attr": "objects"},
      {"key": "Cube"},
      {"attr": "location"}
    ]
  }
}
```

**Safety**: Cannot access `__xxx__` dunder attributes.

### ops_invoke / ops_introspect / ops_search

Safe operator invocation with introspection:

```json
{
  "skill": "ops_invoke",
  "args": {
    "operator_id": "mesh.primitive_cube_add",
    "kwargs": {"size": 1.0}
  }
}
```

**Recommended flow**: `ops_search` → `ops_introspect` → `ops_invoke`

---

## Control Fields

```json
{
  "controls": {
    "max_steps": 80,
    "allow_low_level_gateway": false,
    "require_ops_introspect_before_invoke": true
  },
  "steps": [...]
}
```

---

## Notes

- All skills return `{"ok": true, "data": {...}}` or `{"ok": false, "error": "..."}`
- Use `$ref` to reference previous step outputs
- Follow 9-stage workflow: `discover → blockout → boolean → detail → bevel → normal_fix → accessories → material → finalize`
- For detailed parameter schemas, call `vbf.describe_skills` RPC method
## add_armature_constraint
**Description**: Add armature constraint to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| child_object | str | Yes | - |
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |
| constraint_type | str | No | 'CHILD_OF' |

---

## add_bone
**Description**: Add a bone to an armature in edit mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |
| head | List[float] | Yes | - |
| tail | List[float] | Yes | - |
| roll | float | No | 0.0 |
| parent_bone | str | None | No | None |
| connect | bool | No | False |

---

## add_compositor_node
**Description**: Add a node to the compositor node tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| node_type | str | Yes | - |
| name | Optional[str] | No | None |
| location | List[float] | No | [0, 0] |

---

## add_constraint_copy_location
**Description**: Add a Copy Location constraint to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| target_name | str | Yes | - |
| influence | float | No | 1.0 |
| use_x | bool | No | True |
| use_y | bool | No | True |
| use_z | bool | No | True |
| invert_x | bool | No | False |
| invert_y | bool | No | False |
| invert_z | bool | No | False |

---

## add_constraint_copy_rotation
**Description**: Add a Copy Rotation constraint to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| target_name | str | Yes | - |
| influence | float | No | 1.0 |
| use_x | bool | No | True |
| use_y | bool | No | True |
| use_z | bool | No | True |
| invert_x | bool | No | False |
| invert_y | bool | No | False |
| invert_z | bool | No | False |

---

## add_constraint_copy_scale
**Description**: Add a Copy Scale constraint to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| target_name | str | Yes | - |
| influence | float | No | 1.0 |
| use_x | bool | No | True |
| use_y | bool | No | True |
| use_z | bool | No | True |
| power | float | No | 1.0 |
| additive | bool | No | False |

---

## add_constraint_limit_location
**Description**: Add a Limit Location constraint.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| use_min_x | bool | No | False |
| min_x | float | No | 0.0 |
| use_max_x | bool | No | False |
| max_x | float | No | 0.0 |
| use_min_y | bool | No | False |
| min_y | float | No | 0.0 |
| use_max_y | bool | No | False |
| max_y | float | No | 0.0 |
| use_min_z | bool | No | False |
| min_z | float | No | 0.0 |
| use_max_z | bool | No | False |
| max_z | float | No | 0.0 |

---

## add_driver
**Description**: Add a driver to an object property.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |
| target_property | str | Yes | - |
| index | int | No | -1 |
| expression | str | No | '' |

---

## add_geometry_node
**Description**: Add a node to a geometry nodes tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| tree_name | str | Yes | - |
| node_type | str | Yes | - |
| name | str | None | No | None |
| location | List[float] | No | [0, 0] |

---

## add_ik_constraint
**Description**: Add Inverse Kinematics (IK) constraint to a pose bone.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| bone_name | str | Yes | - |
| chain_length | int | No | 2 |
| use_rotation | bool | No | False |

---

## add_modifier_bevel
**Description**: Add a Bevel modifier to an object for rounded edges.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| width | float | No | 0.03 |
| segments | int | No | 3 |

---

## add_modifier_subdivision
**Description**: Add a Subdivision Surface modifier to an object for smooth geometry.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| levels | int | No | 2 |
| render_levels | int | No | 3 |

---

## add_node_to_group
**Description**: Add a node to a node group.

| Parameter | Type | Required | Default |
|---|---|---|---|
| group_name | str | Yes | - |
| node_type | str | Yes | - |
| name | str | None | No | None |

---

## add_normal_map
**Description**: Add a normal map to a material.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| image_name | str | Yes | - |
| strength | float | No | 1.0 |

---

## add_shader_node
**Description**: Add a node to a material's node tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| node_type | str | Yes | - |
| name | str | None | No | None |
| location | List[float] | No | [0, 0] |

---

## add_shape_key
**Description**: Add a new shape key to a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| key_name | str | Yes | - |
| type | str | No | 'KEY' |

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

## add_uv_map
**Description**: Add a new UV map to a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| name | str | No | 'UVMap' |

---

## api_validator
**Description**: Check whether a bpy API path exists and is accessible.

| Parameter | Type | Required | Default |
|---|---|---|---|
| api_path | str | Yes | - |

---

## apply_modifier
**Description**: Apply (bake) a modifier on an object, making its effect permanent.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| modifier_name | str | Yes | - |

---

## apply_transform
**Description**: Set the location, rotation, and/or scale of an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| location | List[float] | None | No | None |
| rotation_euler | List[float] | None | No | None |
| scale | List[float] | None | No | None |

---

## arrange_nodes
**Description**: Auto-arrange nodes in a material for better layout.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |

---

## arrange_uvs
**Description**: Arrange UVs of multiple objects together.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | Yes | - |
| shape_method | str | No | 'AABB' |

---

## array_along_curve
**Description**: Add a modifier to array an object along a curve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| curve_name | str | Yes | - |
| count | int | No | 10 |

---

## asset_catalog_create
**Description**: Create a new asset catalog.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| parent_path | str | No | '' |

---

## asset_clear
**Description**: Clear asset mark from an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## asset_list
**Description**: List all marked assets in the current file.

*No parameters*

---

## asset_mark
**Description**: Mark an object as an asset.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| asset_type | str | No | 'OBJECT' |

---

## asset_set_metadata
**Description**: Set metadata for an asset.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| description | str | No | '' |
| author | str | No | '' |
| copyright | str | No | '' |
| license_type | str | No | '' |

---

## assign_material
**Description**: Assign an existing material to a material slot on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| material_name | str | Yes | - |
| slot_index | int | No | 0 |

---

## assign_vertex_weights
**Description**: Assign weights to vertices in a vertex group.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| group_name | str | Yes | - |
| vertex_indices | List[int] | Yes | - |
| weight | float | No | 1.0 |
| type | str | No | 'REPLACE' |

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
| pass_filter | List[str] | None | No | None |

---

## boolean_tool
**Description**: Apply a boolean modifier from one mesh object onto another.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_name | str | Yes | - |
| tool_name | str | Yes | - |
| operation | str | No | 'difference' |
| apply | bool | No | True |
| delete_tool | bool | No | True |

---

## bridge_edge_loops
**Description**: Bridge selected edge loops in a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## camera_look_at
**Description**: Orient a camera to look at a specific point.

| Parameter | Type | Required | Default |
|---|---|---|---|
| camera_name | str | Yes | - |
| target_point | List[float] | Yes | - |
| up | str | No | 'z_up' |

---

## clear_animation
**Description**: Clear all or specific animation data from an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| data_path | str | None | No | None |

---

## clear_node_tree
**Description**: Clear all nodes from a material's node tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |

---

## clear_parent
**Description**: Clear the parent relationship from an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| keep_transform | bool | No | True |
| clear_inverse | bool | No | True |

---

## clone_from_image
**Description**: Set clone source image.

| Parameter | Type | Required | Default |
|---|---|---|---|
| image_name | str | Yes | - |

---

## cloth_add
**Description**: Add cloth physics to a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| preset | str | No | 'COTTON' |

---

## cloth_bake
**Description**: Bake cloth simulation.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| start_frame | int | None | No | None |
| end_frame | int | None | No | None |

---

## cloth_pin_vertices
**Description**: Pin cloth vertices using vertex group.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| vertex_group | str | Yes | - |

---

## collision_add
**Description**: Add collision modifier to an object (for cloth, soft body, particles).

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| absorb | float | No | 0.0 |
| friction | float | No | 0.5 |

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

*No parameters*

---

## compositor_delete_node
**Description**: Delete a compositor node.

| Parameter | Type | Required | Default |
|---|---|---|---|
| node_name | str | Yes | - |

---

## compositor_list_nodes
**Description**: List all nodes in the compositor tree.

*No parameters*

---

## convert_particles_to_mesh
**Description**: Convert particle system to real mesh objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| system_name | str | Yes | - |
| new_name | str | None | No | None |

---

## create_armature
**Description**: Create a new armature object for character rigging.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| location | List[float] | No | [0.0, 0.0, 0.0] |

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
| rotation_euler | List[float] | None | No | None |
| focal_length | float | No | 50.0 |
| sensor_width | float | No | 36.0 |

---

## create_collection
**Description**: Create a new collection in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| parent_name | str | None | No | None |

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
| tree_name | str | None | No | None |

---

## create_image_texture
**Description**: Create a new blank image texture.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| width | int | No | 1024 |
| height | int | No | 1024 |
| color | List[float] | None | No | None |

---

## create_light
**Description**: Create a light source in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| light_type | str | Yes | - |
| name | str | Yes | - |
| location | List[float] | Yes | - |
| energy | float | No | 10.0 |
| color | List[float] | None | No | None |
| rotation_euler | List[float] | None | No | None |

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
| rotation_euler | List[float] | None | No | None |
| scale | List[float] | None | No | None |
| size | List[float] | None | No | None |
| radius | float | None | No | None |
| height | float | None | No | None |

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

## curve_to_mesh
**Description**: Convert a curve object to a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## delete_bone
**Description**: Delete a bone from an armature.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |

---

## delete_keyframe
**Description**: Delete a keyframe from an object's property.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| frame | float | Yes | - |
| data_path | str | No | 'location' |
| index | int | No | -1 |

---

## delete_node
**Description**: Delete a node from a material's node tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| node_name | str | Yes | - |

---

## delete_object
**Description**: Remove a single object from the scene by name.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## delete_shape_key
**Description**: Delete a shape key from an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| key_name | str | Yes | - |

---

## driver_add_shape_key
**Description**: Add a driver to a shape key value.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| shape_key_name | str | Yes | - |
| expression | str | Yes | - |

---

## driver_add_variable
**Description**: Add a variable to a driver.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |
| target_property | str | Yes | - |
| var_name | str | Yes | - |
| var_type | str | No | 'SINGLE_PROP' |
| source_object | Optional[str] | No | None |
| source_property | Optional[str] | No | None |
| index | int | No | -1 |

---

## driver_copy
**Description**: Copy a driver from one object/property to another.

| Parameter | Type | Required | Default |
|---|---|---|---|
| source_object | str | Yes | - |
| target_object | str | Yes | - |
| source_property | str | Yes | - |
| target_property | str | Yes | - |

---

## driver_list
**Description**: List all drivers on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |

---

## driver_remove
**Description**: Remove a driver from an object property.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |
| target_property | str | Yes | - |
| index | int | No | -1 |

---

## driver_set_expression
**Description**: Set the expression for a driver.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_object | str | Yes | - |
| target_property | str | Yes | - |
| expression | str | Yes | - |
| index | int | No | -1 |

---

## dyntopo_enabled
**Description**: Enable/disable dynamic topology sculpting.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| enable | bool | No | True |
| resolution | int | No | 100 |

---

## edit_bone
**Description**: Edit an existing bone's properties.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| bone_name | str | Yes | - |
| head | List[float] | None | No | None |
| tail | List[float] | None | No | None |
| roll | float | None | No | None |
| length | float | None | No | None |

---

## enable_pass
**Description**: Enable/disable a render pass.

| Parameter | Type | Required | Default |
|---|---|---|---|
| pass_type | str | Yes | - |
| enabled | bool | No | True |

---

## ensure_object_mode
**Description**: No description available.

*No parameters*

---

## evaluate_fcurve
**Description**: Evaluate an fcurve at a specific frame.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| data_path | str | Yes | - |
| array_index | int | Yes | - |
| frame | float | Yes | - |

---

## export_fbx
**Description**: Export scene or selection as FBX.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| selected_only | bool | No | True |

---

## export_gltf
**Description**: Export scene as glTF/glB.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| export_format | str | No | 'GLB' |

---

## export_obj
**Description**: Export scene or selection as OBJ.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| selected_only | bool | No | True |

---

## extrude_faces
**Description**: Extrude faces of a mesh object along normals.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| amount | float | No | 1.0 |
| normal | List[float] | None | No | None |

---

## face_center
**Description**: No description available.

| Parameter | Type | Required | Default |
|---|---|---|---|
| axis | str | Yes | - |
| extreme | str | Yes | - |

---

## find_missing_files
**Description**: Find missing files and search in directory.

| Parameter | Type | Required | Default |
|---|---|---|---|
| directory | str | Yes | - |

---

## fluid_bake
**Description**: Bake all fluid simulations in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| start_frame | int | None | No | None |
| end_frame | int | None | No | None |

---

## fluid_domain_create
**Description**: Create a fluid simulation domain.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| domain_type | str | No | 'FLUID' |
| resolution | int | No | 32 |

---

## fluid_effector_add
**Description**: Add a fluid effector (force field that affects fluid).

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| effector_type | str | No | 'GUIDE' |

---

## fluid_emitter_add
**Description**: Add a fluid emitter to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| fluid_type | str | No | 'LIQUID' |
| volume_initialization | str | No | 'VOLUME' |

---

## fmt_err
**Description**: No description available.

| Parameter | Type | Required | Default |
|---|---|---|---|
| prefix | str | Yes | - |
| e | Exception | Yes | - |

---

## force_field_add
**Description**: Add a force field to the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| field_type | str | Yes | - |
| name | str | Yes | - |
| location | List[float] | No | [0, 0, 0] |
| strength | float | No | 1.0 |

---

## geometry_nodes_to_mesh
**Description**: Convert geometry nodes result to a new mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| new_name | str | None | No | None |

---

## get_attribute_info
**Description**: Get information about a geometry attribute.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| attribute_name | str | Yes | - |

---

## get_camera_info
**Description**: Get detailed information about a camera.

| Parameter | Type | Required | Default |
|---|---|---|---|
| camera_name | str | Yes | - |

---

## get_current_frame
**Description**: Get the current frame.

*No parameters*

---

## get_node_info
**Description**: Get detailed info about a node including its sockets.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| node_name | str | Yes | - |

---

## get_sculpt_mask
**Description**: Get sculpt mask data from object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

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

## image_paint_slot
**Description**: Set the active paint slot for texture painting.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| slot_index | int | Yes | - |

---

## import_fbx
**Description**: Import FBX file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |

---

## import_gltf
**Description**: Import glTF/glB file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |

---

## import_image_texture
**Description**: Import an image file for use as a texture.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| name | str | None | No | None |

---

## import_obj
**Description**: Import OBJ file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |

---

## insert_keyframe
**Description**: Insert a keyframe for an object's property.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| frame | float | Yes | - |
| data_path | str | No | 'location' |
| index | int | No | -1 |

---

## inset_faces
**Description**: Inset faces of a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| thickness | float | No | 0.1 |
| depth | float | No | 0.0 |

---

## isolate_in_collection
**Description**: Move objects to a collection, optionally removing from other collections.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | Yes | - |
| collection_name | str | Yes | - |
| remove_from_others | bool | No | False |

---

## join_objects
**Description**: Merge multiple mesh objects into a single object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | Yes | - |
| new_name | str | None | No | None |

---

## library_append
**Description**: Append data from another .blend file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| directory | str | Yes | - |
| filename | str | Yes | - |

---

## library_link
**Description**: Link data from another .blend file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| directory | str | Yes | - |
| filename | str | Yes | - |

---

## library_list
**Description**: List all linked libraries.

*No parameters*

---

## library_reload
**Description**: Reload a linked library.

| Parameter | Type | Required | Default |
|---|---|---|---|
| library_name | str | Yes | - |

---

## lightmap_pack
**Description**: Pack UVs for lightmap baking.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| pack_quality | int | No | 12 |
| margin | float | No | 0.005 |

---

## link_compositor_nodes
**Description**: Create a link between compositor nodes.

| Parameter | Type | Required | Default |
|---|---|---|---|
| from_node | str | Yes | - |
| from_socket | str | Yes | - |
| to_node | str | Yes | - |
| to_socket | str | Yes | - |

---

## link_geometry_nodes
**Description**: Create a link between nodes in geometry nodes tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| tree_name | str | Yes | - |
| from_node | str | Yes | - |
| from_socket | str | Yes | - |
| to_node | str | Yes | - |
| to_socket | str | Yes | - |

---

## link_nodes
**Description**: Create a link between two nodes in a material.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| from_node | str | Yes | - |
| from_socket | str | Yes | - |
| to_node | str | Yes | - |
| to_socket | str | Yes | - |

---

## link_to_collection
**Description**: Link an object to a collection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| collection_name | str | Yes | - |

---

## list_attributes
**Description**: List all geometry attributes on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## list_bones
**Description**: List all bones in an armature.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |

---

## list_collections
**Description**: List all collections in the scene.

*No parameters*

---

## list_constraints
**Description**: List all constraints on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## list_fcurves
**Description**: List all fcurves (animation curves) on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## list_particle_systems
**Description**: List all particle systems on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## list_shape_keys
**Description**: List all shape keys of an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## make_paths_absolute
**Description**: Convert all paths to absolute paths.

*No parameters*

---

## make_paths_relative
**Description**: Convert all paths to relative paths.

*No parameters*

---

## mark_seam
**Description**: Mark selected edges as UV seams.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| clear | bool | No | False |

---

## move_object_anchor_to_point
**Description**: Move an object so that a specific anchor point aligns with a target world position.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| anchor_type | str | Yes | - |
| target_point | List[float] | Yes | - |

---

## move_to_layer
**Description**: Set the instance offset/origin for a collection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| collection_name | str | Yes | - |
| origin | List[float] | Yes | - |

---

## multires_add_level
**Description**: Add multiresolution subdivision levels.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| levels | int | No | 1 |

---

## multires_apply
**Description**: Apply multiresolution modifier at specific level.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| level | int | None | No | None |

---

## pack_blend
**Description**: Pack all external data into the .blend file.

*No parameters*

---

## pack_uv_islands
**Description**: Pack UV islands into UV space with minimal overlap.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| margin | float | No | 0.0 |
| rotate | bool | No | True |

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

## recalculate_normals
**Description**: Recalculate mesh vertex normals.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| inside | bool | No | False |

---

## remesh
**Description**: Remesh object using voxel remesher.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| voxel_size | float | No | 0.1 |
| adaptivity | float | No | 0.0 |

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

## rename_object
**Description**: Rename an existing object in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| new_name | str | Yes | - |

---

## rename_shape_key
**Description**: Rename a shape key.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| old_name | str | Yes | - |
| new_name | str | Yes | - |

---

## render_image
**Description**: Render a single image.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | Optional[str] | No | None |
| width | Optional[int] | No | None |
| height | Optional[int] | No | None |

---

## report_missing_files
**Description**: Report all missing files.

*No parameters*

---

## reset_shape_keys
**Description**: Reset all shape key values to 0.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## rigidbody_add
**Description**: Add rigid body physics to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| body_type | str | No | 'ACTIVE' |
| mass | float | No | 1.0 |
| collision_shape | str | No | 'MESH' |
| friction | float | No | 0.5 |
| bounce | float | No | 0.0 |

---

## rigidbody_bake
**Description**: Bake rigid body simulation to keyframes.

| Parameter | Type | Required | Default |
|---|---|---|---|
| start_frame | int | None | No | None |
| end_frame | int | None | No | None |

---

## rigidbody_connect
**Description**: Create a rigid body constraint between two objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object1 | str | Yes | - |
| object2 | str | Yes | - |
| constraint_type | str | No | 'FIXED' |
| name | str | None | No | None |

---

## rigidbody_set_collision_shape
**Description**: Set collision shape for rigid body.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| shape | str | Yes | - |
| margin | float | No | 0.04 |

---

## rigidbody_set_mass
**Description**: Set mass for a rigid body object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| mass | float | Yes | - |
| calculate_center | bool | No | True |

---

## save_image
**Description**: Save an image to file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| image_name | str | Yes | - |
| filepath | str | None | No | None |

---

## scale_normals
**Description**: Scale the normals of mesh faces (flat shading effect).

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| scale | float | No | 1.0 |

---

## scale_uv
**Description**: Scale UV coordinates.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| scale | List[float] | Yes | - |
| pivot | List[float] | None | No | None |

---

## scene_clear
**Description**: Delete all objects in the current scene.

*No parameters*

---

## sculpt_crease
**Description**: Create crease/sharp edge in sculpt mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strength | float | No | 0.5 |

---

## sculpt_draw
**Description**: Apply draw brush sculpt strokes to mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| locations | List[List[float]] | Yes | - |
| strength | float | No | 1.0 |

---

## sculpt_flatten
**Description**: Flatten mesh surface.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strength | float | No | 0.5 |

---

## sculpt_grab
**Description**: Grab/translate mesh surface in sculpt mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| grab_vector | List[float] | Yes | - |

---

## sculpt_inflate
**Description**: Inflate mesh surface outward.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strength | float | No | 0.5 |

---

## sculpt_layer
**Description**: Add/remove material layer in sculpt mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| height | float | No | 0.1 |

---

## sculpt_pinch
**Description**: Pinch mesh surface toward cursor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strength | float | No | 0.5 |

---

## sculpt_smooth
**Description**: Smooth mesh using sculpt smooth brush.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| iterations | int | No | 1 |

---

## sequencer_add_effect_strip
**Description**: Add an effect strip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| effect_type | str | Yes | - |
| channel | int | Yes | - |
| frame_start | int | Yes | - |
| frame_end | int | Yes | - |
| strip1 | str | Yes | - |
| strip2 | Optional[str] | No | None |
| name | Optional[str] | No | None |

---

## sequencer_add_image_strip
**Description**: Add an image strip to the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| channel | int | No | 1 |
| frame_start | int | No | 1 |
| frame_end | Optional[int] | No | None |
| name | Optional[str] | No | None |

---

## sequencer_add_movie_strip
**Description**: Add a movie strip to the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| channel | int | No | 1 |
| frame_start | int | No | 1 |
| name | Optional[str] | No | None |

---

## sequencer_add_sound_strip
**Description**: Add a sound strip to the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| channel | int | No | 2 |
| frame_start | int | No | 1 |
| name | Optional[str] | No | None |

---

## sequencer_add_text_strip
**Description**: Add a text strip to the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| text | str | Yes | - |
| channel | int | No | 3 |
| frame_start | int | No | 1 |
| frame_end | int | No | 25 |
| name | Optional[str] | No | None |

---

## sequencer_create_scene
**Description**: Create a new scene configured for video editing.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | No | 'Video Sequence Editor' |
| width | int | No | 1920 |
| height | int | No | 1080 |
| fps | int | No | 24 |

---

## sequencer_delete_strip
**Description**: Delete a strip from the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_name | str | Yes | - |

---

## sequencer_list_strips
**Description**: List all strips in the sequencer.

*No parameters*

---

## sequencer_meta_strip_create
**Description**: Create a meta strip from multiple strips.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_names | List[str] | Yes | - |
| name | str | No | 'Meta' |

---

## sequencer_set_strip_opacity
**Description**: Set opacity for a strip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_name | str | Yes | - |
| opacity | float | Yes | - |

---

## sequencer_set_strip_position
**Description**: Move a strip to new position.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_name | str | Yes | - |
| channel | int | Yes | - |
| frame_start | int | Yes | - |

---

## sequencer_set_strip_volume
**Description**: Set volume for a sound strip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_name | str | Yes | - |
| volume | float | Yes | - |

---

## set_active_object
**Description**: No description available.

| Parameter | Type | Required | Default |
|---|---|---|---|
| obj | bpy.types.Object | Yes | - |

---

## set_active_uv_map
**Description**: Set the active UV map for rendering/display.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| uv_map_name | str | Yes | - |

---

## set_animation_fps
**Description**: Set animation frame rate.

| Parameter | Type | Required | Default |
|---|---|---|---|
| fps | float | Yes | - |
| fps_base | float | No | 1.0 |

---

## set_armature_modifier
**Description**: Set or update armature modifier on a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| armature_name | str | Yes | - |
| modifier_name | str | No | 'Armature' |

---

## set_attribute_values
**Description**: Set values for an attribute.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| attribute_name | str | Yes | - |
| values | List[Any] | Yes | - |

---

## set_camera_active
**Description**: Set the active camera for the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| camera_name | str | Yes | - |

---

## set_camera_properties
**Description**: Configure camera properties.

| Parameter | Type | Required | Default |
|---|---|---|---|
| camera_name | str | Yes | - |
| focal_length | float | None | No | None |
| sensor_width | float | None | No | None |
| clip_start | float | None | No | None |
| clip_end | float | None | No | None |
| type | str | None | No | None |

---

## set_compositor_backdrop
**Description**: Enable/disable backdrop in the compositor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| enabled | bool | No | True |

---

## set_compositor_node_input
**Description**: Set an input value on a compositor node.

| Parameter | Type | Required | Default |
|---|---|---|---|
| node_name | str | Yes | - |
| input_name | str | Yes | - |
| value | Any | Yes | - |

---

## set_current_frame
**Description**: Set the current frame of the timeline.

| Parameter | Type | Required | Default |
|---|---|---|---|
| frame | float | Yes | - |

---

## set_curve_bevel
**Description**: Set bevel properties for a curve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| curve_name | str | Yes | - |
| bevel_depth | float | No | 0.0 |
| bevel_resolution | int | No | 2 |
| fill_mode | str | No | 'HALF' |

---

## set_curve_extrude
**Description**: Set extrusion amount for a curve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| curve_name | str | Yes | - |
| extrude | float | No | 0.0 |

---

## set_curve_taper
**Description**: Set taper object for a curve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| curve_name | str | Yes | - |
| taper_curve_name | str | None | No | None |

---

## set_cycles_denoise
**Description**: Enable/disable Cycles denoising.

| Parameter | Type | Required | Default |
|---|---|---|---|
| enable | bool | No | True |

---

## set_cycles_samples
**Description**: Set Cycles render samples.

| Parameter | Type | Required | Default |
|---|---|---|---|
| samples | int | No | 128 |
| preview_samples | int | No | 32 |

---

## set_eevee_samples
**Description**: Set Eevee render samples.

| Parameter | Type | Required | Default |
|---|---|---|---|
| samples | int | No | 16 |

---

## set_font
**Description**: Set the font for a text object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| font_name | str | None | No | None |

---

## set_frame_range
**Description**: Set animation frame range.

| Parameter | Type | Required | Default |
|---|---|---|---|
| start | int | No | 1 |
| end | int | No | 250 |

---

## set_geometry_node_input
**Description**: Set an input value on a geometry node.

| Parameter | Type | Required | Default |
|---|---|---|---|
| tree_name | str | Yes | - |
| node_name | str | Yes | - |
| input_name | str | Yes | - |
| value | Any | Yes | - |

---

## set_gpencil_brush
**Description**: Set the active Grease Pencil brush.

| Parameter | Type | Required | Default |
|---|---|---|---|
| brush_name | str | Yes | - |
| size | float | No | 30.0 |
| strength | float | No | 1.0 |

---

## set_keyframe_interpolation
**Description**: Set interpolation type for keyframes on an fcurve.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| data_path | str | Yes | - |
| array_index | int | Yes | - |
| interpolation | str | No | 'LINEAR' |

---

## set_light_properties
**Description**: Configure properties of an existing light.

| Parameter | Type | Required | Default |
|---|---|---|---|
| light_name | str | Yes | - |
| energy | float | None | No | None |
| color | List[float] | None | No | None |
| specular | float | None | No | None |
| shadow_soft_size | float | None | No | None |
| spot_size | float | None | No | None |
| spot_blend | float | None | No | None |
| angle | float | None | No | None |
| size | float | None | No | None |
| shape | str | None | No | None |

---

## set_node_group_input
**Description**: Set the value of a node group input.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| group_node_name | str | Yes | - |
| input_name | str | Yes | - |
| value | Any | Yes | - |

---

## set_node_property
**Description**: Set a property on a node.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| node_name | str | Yes | - |
| property_name | str | Yes | - |
| value | Any | Yes | - |

---

## set_node_tree_output
**Description**: Connect a node to the output (or set as active output).

| Parameter | Type | Required | Default |
|---|---|---|---|
| tree_name | str | Yes | - |
| node_name | str | Yes | - |

---

## set_paint_symmetry
**Description**: Set texture paint symmetry.

| Parameter | Type | Required | Default |
|---|---|---|---|
| x | bool | No | True |
| y | bool | No | False |
| z | bool | No | False |

---

## set_parent
**Description**: Set the parent object for another object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| child_name | str | Yes | - |
| parent_name | str | Yes | - |
| keep_transform | bool | No | True |
| inverse_parent | bool | No | True |

---

## set_particle_emitter
**Description**: Configure particle emission settings.

| Parameter | Type | Required | Default |
|---|---|---|---|
| system_name | str | Yes | - |
| count | int | No | 1000 |
| start_frame | int | No | 1 |
| end_frame | int | No | 250 |
| lifetime | int | No | 50 |

---

## set_particle_gravity
**Description**: Set particle gravity and physical properties.

| Parameter | Type | Required | Default |
|---|---|---|---|
| system_name | str | Yes | - |
| gravity | float | No | 1.0 |
| mass | float | No | 1.0 |
| size | float | No | 0.5 |

---

## set_particle_hair
**Description**: Configure hair particle settings.

| Parameter | Type | Required | Default |
|---|---|---|---|
| system_name | str | Yes | - |
| length | float | No | 1.0 |
| segments | int | No | 5 |

---

## set_particle_instance_object
**Description**: Set instance object for rendered particles.

| Parameter | Type | Required | Default |
|---|---|---|---|
| system_name | str | Yes | - |
| instance_object | str | Yes | - |

---

## set_particle_physics
**Description**: Set particle physics type.

| Parameter | Type | Required | Default |
|---|---|---|---|
| system_name | str | Yes | - |
| physics_type | str | No | 'NEWTON' |

---

## set_particle_render
**Description**: Set particle render settings.

| Parameter | Type | Required | Default |
|---|---|---|---|
| system_name | str | Yes | - |
| render_type | str | No | 'HALO' |
| material | int | No | 1 |

---

## set_particle_source
**Description**: Set particle emission source.

| Parameter | Type | Required | Default |
|---|---|---|---|
| system_name | str | Yes | - |
| source | str | No | 'VERT' |
| distribution | str | No | 'JIT' |

---

## set_particle_velocity
**Description**: Set initial particle velocity.

| Parameter | Type | Required | Default |
|---|---|---|---|
| system_name | str | Yes | - |
| normal | float | No | 1.0 |
| tangent | float | No | 0.0 |
| object_align | float | No | 0.0 |
| random | float | No | 0.0 |

---

## set_render_engine
**Description**: Set the active render engine.

| Parameter | Type | Required | Default |
|---|---|---|---|
| engine | str | No | 'BLENDER_EEVEE_NEXT' |

---

## set_render_output
**Description**: Set render output settings.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| file_format | str | No | 'PNG' |

---

## set_render_resolution
**Description**: Set render resolution.

| Parameter | Type | Required | Default |
|---|---|---|---|
| width | int | No | 1920 |
| height | int | No | 1080 |
| scale | int | No | 100 |

---

## set_sculpt_brush
**Description**: Configure the active sculpt brush settings.

| Parameter | Type | Required | Default |
|---|---|---|---|
| brush_name | str | Yes | - |
| radius | float | No | 50.0 |
| strength | float | No | 0.5 |
| smooth_strength | float | No | 0.5 |

---

## set_sculpt_symmetry
**Description**: Configure sculpt symmetry settings.

| Parameter | Type | Required | Default |
|---|---|---|---|
| x | bool | No | True |
| y | bool | No | False |
| z | bool | No | False |

---

## set_shape_key_range
**Description**: Set the value range of a shape key.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| key_name | str | Yes | - |
| min | float | No | 0.0 |
| max | float | No | 1.0 |

---

## set_shape_key_value
**Description**: Set the influence value of a shape key.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| key_name | str | Yes | - |
| value | float | No | 0.0 |

---

## set_shape_key_vertex_position
**Description**: Set the position of a vertex in a shape key.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| key_name | str | Yes | - |
| vertex_index | int | Yes | - |
| position | List[float] | Yes | - |

---

## set_sharp_edges
**Description**: Mark edges as sharp based on angle.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| angle | float | No | 60.0 |

---

## set_text_content
**Description**: Change text content of a text object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| text | str | Yes | - |

---

## set_text_properties
**Description**: Configure text object properties.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| size | float | None | No | None |
| extrude | float | None | No | None |
| bevel_depth | float | None | No | None |
| bevel_resolution | int | None | No | None |

---

## set_texture_mapping
**Description**: Set texture mapping for an image texture node.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| texture_node_name | str | Yes | - |
| mapping_type | str | No | 'UV' |
| projection | str | No | 'FLAT' |

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

## shape_key_from_mix
**Description**: Create a new shape key from the current mix of shape keys.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| new_key_name | str | Yes | - |

---

## skin_to_armature
**Description**: Skin/parent a mesh object to an armature with automatic weights.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| armature_name | str | Yes | - |
| create_modifiers | bool | No | True |

---

## smart_project_uv
**Description**: Smart UV project - automatic UV layout based on mesh geometry.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| angle_limit | float | No | 66.0 |
| island_margin | float | No | 0.02 |
| area_threshold | float | No | 0.0 |

---

## softbody_add
**Description**: Add soft body physics to a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| mass | float | No | 1.0 |
| stiffness | float | No | 10.0 |

---

## spatial_query
**Description**: Query a spatial point on an object's bounding box in world coordinates.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| query_type | str | Yes | - |

---

## subdivide_mesh
**Description**: Subdivide mesh faces.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| cuts | int | No | 1 |
| smoothness | float | No | 0.0 |

---

## symmetrize_bones
**Description**: Mirror bones across an axis.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| axis | str | No | 'X' |

---

## text_to_curve
**Description**: Convert a text object to a curve object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

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

## tracking_add_plane_track
**Description**: Create a plane track from markers.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| name | str | No | 'Plane' |
| corners | List[List[float]] | No | [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]] |

---

## tracking_create_object
**Description**: Create 3D object solved from tracking data.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| track_names | List[str] | Yes | - |
| object_type | str | No | 'CUBE' |

---

## tracking_create_scene_from_clip
**Description**: Create a new scene with tracking setup.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| name | str | No | 'Tracking' |

---

## tracking_create_track
**Description**: Create a tracking marker in a clip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| marker_name | Optional[str] | No | None |
| frame | int | No | 1 |
| location | List[float] | No | [0.5, 0.5] |

---

## tracking_delete_track
**Description**: Delete a tracking track.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| track_name | str | Yes | - |

---

## tracking_list_tracks
**Description**: List all tracking tracks in a clip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |

---

## tracking_load_clip
**Description**: Load a movie clip for motion tracking.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| name | Optional[str] | No | None |

---

## tracking_set_camera
**Description**: Set up camera from solved tracking data.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |

---

## tracking_set_track_pattern_size
**Description**: Set the pattern size for a tracking marker.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| track_name | str | Yes | - |
| size | int | No | 11 |

---

## tracking_solve_camera
**Description**: Solve camera motion from tracks.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |

---

## tracking_track_frame
**Description**: Track a marker to a specific frame.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| track_name | str | Yes | - |
| frame | int | Yes | - |

---

## triangulate_faces
**Description**: Convert mesh polygons to triangles.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## unlink_from_collection
**Description**: Unlink an object from a collection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| collection_name | str | Yes | - |

---

## unpack_blend
**Description**: Unpack data from the .blend file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| method | str | No | 'USE_ORIGINAL' |

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

## vec3
**Description**: No description available.

| Parameter | Type | Required | Default |
|---|---|---|---|
| v | List[float] | Yes | - |

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



## Runtime Gateway Skills
