# Category: Others (98 skills)

## For Developers & LLM Agents

**Category**: Others
**Description**: Miscellaneous skills
**Total Skills**: 98

### When to Use This Category
When specific specialized features are needed

### Prerequisites
Varies by skill

### Common Workflow Sequence
```
See individual skill documentation
```

---

## Skills
## add_compositor_node

**Description**: Add a node to the compositor node tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| node_type | str | Yes | - |
| name | Optional[str] | No | None |
| location | List[float] | No | [0, 0] |

---

---

## add_node_to_group

**Description**: Add a node to a node group.

| Parameter | Type | Required | Default |
|---|---|---|---|
| group_name | str | Yes | - |
| node_type | str | Yes | - |
| name | str | None | No |

---

## add_normal_map

**Description**: Add a normal map to a material.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| image_name | str | Yes | - |
| strength | float | No | 1.0 |

---

## add_shape_key

**Description**: Add a new shape key to a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| key_name | str | Yes | - |
| type | str | No | 'KEY' |

---

## add_uv_map

**Description**: Add a new UV map to a mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| name | str | No | 'UVMap' |

---

## apply_transform

**Description**: Set the location, rotation, and/or scale of an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| location | List[float] | None | No |
| rotation_euler | List[float] | None | No |
| scale | List[float] | None | No |

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

## assign_material

**Description**: Assign an existing material to a material slot on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| material_name | str | Yes | - |
| slot_index | int | No | 0 |

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

---

## convert_particles_to_mesh

**Description**: Convert particle system to real mesh objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| system_name | str | Yes | - |
| new_name | str | None | No |

---

## enable_pass

**Description**: Enable/disable a render pass.

| Parameter | Type | Required | Default |
|---|---|---|---|
| pass_type | str | Yes | - |
| enabled | bool | No | True |

---

## ensure_object_mode

**Description**: Ensure object mode is active for editing.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | No | - |

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

---

---

## get_camera_info

**Description**: Get detailed information about a camera.

| Parameter | Type | Required | Default |
|---|---|---|---|
| camera_name | str | Yes | - |

---

## get_current_frame

**Description**: Get the current frame.

| Parameter | Type | Required | Default |
|---|---|---|---|
| scene_name | str | No | - |

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

---

## isolate_in_collection

**Description**: Move objects to a collection, optionally removing from other collections.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_names | List[str] | Yes | - |
| collection_name | str | Yes | - |
| remove_from_others | bool | No | False |

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

| Parameter | Type | Required | Default |
|---|---|---|---|
| filter | str | No | - |

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

---

## list_collections

**Description**: List all collections in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | No | - |

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
| level | int | None | No |

---

## pack_blend

**Description**: Pack all external data into the .blend file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| all_data | bool | No | true |

---

## pack_uv_islands

**Description**: Pack UV islands into UV space with minimal overlap.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| margin | float | No | 0.0 |
| rotate | bool | No | True |

---

---

---

---

## remesh

**Description**: Remesh object using voxel remesher.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| voxel_size | float | No | 0.1 |
| adaptivity | float | No | 0.0 |

---

## report_missing_files

**Description**: Report all missing files.

| Parameter | Type | Required | Default |
|---|---|---|---|
| verbose | bool | No | false |

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
| start_frame | int | None | No |
| end_frame | int | None | No |

---

## rigidbody_connect

**Description**: Create a rigid body constraint between two objects.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object1 | str | Yes | - |
| object2 | str | Yes | - |
| constraint_type | str | No | 'FIXED' |
| name | str | None | No |

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
| filepath | str | None | No |

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
| pivot | List[float] | None | No |

---

---

---

---

---

---

---

---

---

---

---

---

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
| focal_length | float | None | No |
| sensor_width | float | None | No |
| clip_start | float | None | No |
| clip_end | float | None | No |
| type | str | None | No |

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
| taper_curve_name | str | None | No |

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
| font_name | str | None | No |

---

## set_frame_range

**Description**: Set animation frame range.

| Parameter | Type | Required | Default |
|---|---|---|---|
| start | int | No | 1 |
| end | int | No | 250 |

---

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

---

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
| size | float | None | No |
| extrude | float | None | No |
| bevel_depth | float | None | No |
| bevel_resolution | int | None | No |

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

---

---

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

## symmetrize_bones

**Description**: Mirror bones across an axis.

| Parameter | Type | Required | Default |
|---|---|---|---|
| armature_name | str | Yes | - |
| axis | str | No | 'X' |

---

---

---

---

---

---

---

---

---

---

---

---

---

---

## unpack_blend

**Description**: Unpack data from the .blend file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| method | str | No | 'USE_ORIGINAL' |

---

## vec3

**Description**: No description available.

| Parameter | Type | Required | Default |
|---|---|---|---|
| v | List[float] | Yes | - |

---

---

---
