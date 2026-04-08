# Geometry Nodes Skills - Blender Geometry Nodes system
from typing import Any, Dict, List

import bpy

from .utils import ensure_object_mode, fmt_err, set_active_object


def create_geometry_nodes_tree(
    object_name: str,
    tree_name: str | None = None,
) -> Dict[str, Any]:
    """Create a new Geometry Nodes modifier and node tree for an object.

    Args:
        object_name: Name of the mesh object.
        tree_name: Optional name for the node tree. Defaults to {object_name}_GeometryNodes.

    Returns:
        {"object_name": str, "modifier_name": str, "tree_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Create node tree
        tree_name = tree_name or f"{obj.name}_GeometryNodes"
        node_tree = bpy.data.node_groups.new(name=tree_name, type="GeometryNodeTree")

        # Create modifier
        mod = obj.modifiers.new(name="GeometryNodes", type="NODES")
        mod.node_group = node_tree

        # Add input/output nodes
        input_node = node_tree.nodes.new("NodeGroupInput")
        input_node.location = (-400, 0)

        output_node = node_tree.nodes.new("NodeGroupOutput")
        output_node.location = (400, 0)

        # Add geometry socket
        if len(node_tree.outputs) == 0:
            node_tree.interface.new_socket(name="Geometry", socket_type="NodeSocketGeometry")

        return {
            "object_name": obj.name,
            "modifier_name": mod.name,
            "tree_name": node_tree.name,
        }
    except Exception as e:
        raise fmt_err("create_geometry_nodes_tree failed", e)


def add_geometry_node(
    tree_name: str,
    node_type: str,
    name: str | None = None,
    location: List[float] = [0, 0],
) -> Dict[str, Any]:
    """Add a node to a geometry nodes tree.

    Args:
        tree_name: Name of the geometry nodes tree.
        node_type: Node type (e.g., "GeometryNodeMeshCube", "GeometryNodeSetPosition").
        name: Optional custom node name.
        location: [x, y] position in node editor.

    Returns:
        {"tree_name": str, "node_name": str, "type": str}
    """
    try:
        node_tree = bpy.data.node_groups.get(tree_name)
        if not node_tree:
            raise ValueError(f"Node tree not found: {tree_name}")

        # Create node
        node = node_tree.nodes.new(type=node_type)

        if name:
            node.name = name

        node.location = (location[0], location[1])

        return {
            "tree_name": tree_name,
            "node_name": node.name,
            "type": node.bl_idname,
        }
    except Exception as e:
        raise fmt_err("add_geometry_node failed", e)


def link_geometry_nodes(
    tree_name: str,
    from_node: str,
    from_socket: str,
    to_node: str,
    to_socket: str,
) -> Dict[str, Any]:
    """Create a link between nodes in geometry nodes tree.

    Args:
        tree_name: Name of the node tree.
        from_node: Source node name.
        from_socket: Source socket identifier.
        to_node: Destination node name.
        to_socket: Destination socket identifier.

    Returns:
        {"tree_name": str, "link_created": bool}
    """
    try:
        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            raise ValueError(f"Node tree not found: {tree_name}")

        src = tree.nodes.get(from_node)
        dst = tree.nodes.get(to_node)

        if not src:
            raise ValueError(f"Source node not found: {from_node}")
        if not dst:
            raise ValueError(f"Destination node not found: {to_node}")

        # Find sockets by identifier
        out_socket = None
        for s in src.outputs:
            if s.identifier == from_socket or s.name == from_socket:
                out_socket = s
                break

        in_socket = None
        for s in dst.inputs:
            if s.identifier == to_socket or s.name == to_socket:
                in_socket = s
                break

        if not out_socket:
            available = [f"{s.identifier}/{s.name}" for s in src.outputs]
            raise ValueError(f"Output socket '{from_socket}' not found. Available: {available}")

        if not in_socket:
            available = [f"{s.identifier}/{s.name}" for s in dst.inputs]
            raise ValueError(f"Input socket '{to_socket}' not found. Available: {available}")

        tree.links.new(out_socket, in_socket)

        return {
            "tree_name": tree_name,
            "link_created": True,
            "from": f"{from_node}.{from_socket}",
            "to": f"{to_node}.{to_socket}",
        }
    except Exception as e:
        raise fmt_err("link_geometry_nodes failed", e)


def set_geometry_node_input(
    tree_name: str,
    node_name: str,
    input_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Set an input value on a geometry node.

    Args:
        tree_name: Name of the node tree.
        node_name: Name of the node.
        input_name: Input socket identifier or name.
        value: Value to set.

    Returns:
        {"tree_name": str, "node_name": str, "input": str}
    """
    try:
        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            raise ValueError(f"Node tree not found: {tree_name}")

        node = tree.nodes.get(node_name)
        if not node:
            raise ValueError(f"Node not found: {node_name}")

        # Find input
        for inp in node.inputs:
            if inp.identifier == input_name or inp.name == input_name:
                inp.default_value = value
                return {
                    "tree_name": tree_name,
                    "node_name": node_name,
                    "input": inp.identifier,
                }

        raise ValueError(f"Input not found: {input_name}")
    except Exception as e:
        raise fmt_err("set_geometry_node_input failed", e)


def set_node_tree_output(
    tree_name: str,
    node_name: str,
) -> Dict[str, Any]:
    """Connect a node to the output (or set as active output).

    Args:
        tree_name: Name of the node tree.
        node_name: Name of the node to connect.

    Returns:
        {"tree_name": str, "output_set": bool}
    """
    try:
        tree = bpy.data.node_groups.get(tree_name)
        if not tree:
            raise ValueError(f"Node tree not found: {tree_name}")

        src = tree.nodes.get(node_name)
        if not src:
            raise ValueError(f"Node not found: {node_name}")

        # Find output node
        output_node = None
        for node in tree.nodes:
            if node.type == "GROUP_OUTPUT" or node.bl_idname == "NodeGroupOutput":
                output_node = node
                break

        if not output_node:
            raise ValueError("No output node found in tree")

        # Connect geometry output to tree output
        if "Geometry" in [s.name for s in src.outputs]:
            geom_out = src.outputs["Geometry"]
            geom_in = output_node.inputs["Geometry"]
            tree.links.new(geom_out, geom_in)

        return {
            "tree_name": tree_name,
            "output_set": True,
        }
    except Exception as e:
        raise fmt_err("set_node_tree_output failed", e)


def bake_geometry_nodes(
    object_name: str,
    modifier_name: str = "GeometryNodes",
) -> Dict[str, Any]:
    """Bake geometry nodes to real mesh.

    Args:
        object_name: Name of object with geometry nodes modifier.
        modifier_name: Name of the modifier.

    Returns:
        {"object_name": str, "baked": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        mod = obj.modifiers.get(modifier_name)
        if not mod or mod.type != "NODES":
            raise ValueError(f"GeometryNodes modifier not found: {modifier_name}")

        # Bake to mesh
        bpy.ops.object.modifier_apply(modifier=mod.name)

        return {
            "object_name": obj.name,
            "baked": True,
        }
    except Exception as e:
        raise fmt_err("bake_geometry_nodes failed", e)


def geometry_nodes_to_mesh(
    object_name: str,
    new_name: str | None = None,
) -> Dict[str, Any]:
    """Convert geometry nodes result to a new mesh object.

    Args:
        object_name: Object with geometry nodes.
        new_name: Name for new object. Default: {object_name}_Baked.

    Returns:
        {"object_name": str, "new_object": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        # Duplicate and apply modifiers
        bpy.ops.object.duplicate()
        new_obj = bpy.context.active_object

        if new_name:
            new_obj.name = new_name
        else:
            new_obj.name = f"{obj.name}_Baked"

        # Apply all modifiers
        for mod in list(new_obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)

        return {
            "object_name": obj.name,
            "new_object": new_obj.name,
        }
    except Exception as e:
        raise fmt_err("geometry_nodes_to_mesh failed", e)


def create_attribute(
    object_name: str,
    attribute_name: str,
    domain: str = "POINT",
    data_type: str = "FLOAT",
) -> Dict[str, Any]:
    """Create a new attribute on mesh geometry.

    Args:
        object_name: Mesh object.
        attribute_name: Name for the attribute.
        domain: "POINT", "EDGE", "FACE", "CORNER", "CURVE", "INSTANCE".
        data_type: "FLOAT", "INT", "FLOAT_VECTOR", "FLOAT_COLOR", "BYTE_COLOR",
                   "STRING", "BOOLEAN", "FLOAT2".

    Returns:
        {"object_name": str, "attribute": str, "domain": str, "type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        mesh = obj.data

        # Create attribute
        attr = mesh.attributes.new(
            name=attribute_name,
            type=data_type,
            domain=domain,
        )

        return {
            "object_name": obj.name,
            "attribute": attr.name,
            "domain": attr.domain,
            "type": attr.data_type,
        }
    except Exception as e:
        raise fmt_err("create_attribute failed", e)


def set_attribute_values(
    object_name: str,
    attribute_name: str,
    values: List[Any],
) -> Dict[str, Any]:
    """Set values for an attribute.

    Args:
        object_name: Mesh object.
        attribute_name: Name of attribute to set.
        values: List of values (length must match element count).

    Returns:
        {"object_name": str, "attribute": str, "values_set": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        mesh = obj.data
        attr = mesh.attributes.get(attribute_name)
        if not attr:
            raise ValueError(f"Attribute not found: {attribute_name}")

        count = min(len(values), len(attr.data))
        for i in range(count):
            attr.data[i].value = values[i]

        return {
            "object_name": obj.name,
            "attribute": attr.name,
            "values_set": count,
        }
    except Exception as e:
        raise fmt_err("set_attribute_values failed", e)


def get_attribute_info(
    object_name: str,
    attribute_name: str,
) -> Dict[str, Any]:
    """Get information about a geometry attribute.

    Args:
        object_name: Mesh object.
        attribute_name: Attribute name.

    Returns:
        {"name": str, "domain": str, "type": str, "count": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        mesh = obj.data
        attr = mesh.attributes.get(attribute_name)
        if not attr:
            raise ValueError(f"Attribute not found: {attribute_name}")

        return {
            "name": attr.name,
            "domain": attr.domain,
            "type": attr.data_type,
            "count": len(attr.data),
        }
    except Exception as e:
        raise fmt_err("get_attribute_info failed", e)


def list_attributes(object_name: str) -> Dict[str, Any]:
    """List all geometry attributes on an object.

    Args:
        object_name: Mesh object.

    Returns:
        {"object_name": str, "attributes": List[Dict], "count": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        attrs = []
        for attr in obj.data.attributes:
            attrs.append({
                "name": attr.name,
                "domain": attr.domain,
                "type": attr.data_type,
            })

        return {
            "object_name": obj.name,
            "attributes": attrs,
            "count": len(attrs),
        }
    except Exception as e:
        raise fmt_err("list_attributes failed", e)


def remove_attribute(
    object_name: str,
    attribute_name: str,
) -> Dict[str, Any]:
    """Remove a geometry attribute.

    Args:
        object_name: Mesh object.
        attribute_name: Name of attribute to remove.

    Returns:
        {"removed": bool, "attribute": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        mesh = obj.data
        attr = mesh.attributes.get(attribute_name)
        if attr:
            mesh.attributes.remove(attr)
            return {"removed": True, "attribute": attribute_name}
        else:
            return {"removed": False, "reason": "Not found"}
    except Exception as e:
        raise fmt_err("remove_attribute failed", e)
