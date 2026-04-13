# Category: Scene (18 skills)

## For Developers & LLM Agents

**Category**: Scene
**Description**: Scene and object management skills
**Total Skills**: 18

### When to Use This Category
At the beginning of any workflow to set up scene structure, or when organizing objects

### Prerequisites
None

### Common Workflow Sequence
```
[scene_clear] → [create_collection] → [create_primitive]
```

---

## Skills
## clear_animation

**Description**: Clear all or specific animation data from an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| data_path | str | None | No |

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

## make_paths_absolute

**Description**: Convert all paths to absolute paths.

| Parameter | Type | Required | Default |
|---|---|---|---|
| target_directory | str | No | - |

---

## make_paths_relative

**Description**: Convert all paths to relative paths.

| Parameter | Type | Required | Default |
|---|---|---|---|
| start_directory | str | No | - |

---

## move_object_anchor_to_point

**Description**: Move an object so that a specific anchor point aligns with a target world position.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| anchor_type | str | Yes | - |
| target_point | List[float] | Yes | - |

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

## scene_clear

**Description**: Delete all objects in the current scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| confirm | bool | No | false |

---

## unlink_from_collection

**Description**: Unlink an object from a collection.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| collection_name | str | Yes | - |

---
