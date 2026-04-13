# Category: Geometry Nodes (13 skills)

## For Developers & LLM Agents

**Category**: Geometry Nodes
**Description**: Procedural geometry generation via node graphs
**Total Skills**: 13

### When to Use This Category
For procedural modeling, instancing, or parametric designs

### Prerequisites
Understanding of node-based workflows

### Common Workflow Sequence
```
[create_geometry_nodes_tree] → [add_geometry_node] → [bake_geometry_nodes]
```

---

## Skills
## add_geometry_node

**Description**: Add a node to a geometry nodes tree.

| Parameter | Type | Required | Default |
|---|---|---|---|
| tree_name | str | Yes | - |
| node_type | str | Yes | - |
| name | str | None | No |
| location | List[float] | No | [0, 0] |


---

## bake_geometry_nodes

**Description**: Bake geometry nodes to real mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| modifier_name | str | No | 'GeometryNodes' |


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

## create_geometry_nodes_tree

**Description**: Create a new Geometry Nodes modifier and node tree for an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| tree_name | str | None | No |


---

## geometry_nodes_to_mesh

**Description**: Convert geometry nodes result to a new mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| new_name | str | None | No |


---

## get_attribute_info

**Description**: Get information about a geometry attribute.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| attribute_name | str | Yes | - |


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

## list_attributes

**Description**: List all geometry attributes on an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |


---

## remove_attribute

**Description**: Remove a geometry attribute.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| attribute_name | str | Yes | - |


---

## set_attribute_values

**Description**: Set values for an attribute.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| attribute_name | str | Yes | - |
| values | List[Any] | Yes | - |


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

## set_node_tree_output

**Description**: Connect a node to the output (or set as active output).

| Parameter | Type | Required | Default |
|---|---|---|---|
| tree_name | str | Yes | - |
| node_name | str | Yes | - |


---
