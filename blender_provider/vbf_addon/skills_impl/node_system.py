# Node System Skills - Blender Shader/Geometry/Compositor Nodes
from typing import Any, Dict, List, Tuple

import bpy
from mathutils import Vector

from .utils import fmt_err, set_active_object


def create_shader_node_tree(
    object_name: str,
    tree_name: str = "ShaderNodeTree",
) -> Dict[str, Any]:
    """Create a new shader node tree for an object.

    Args:
        object_name: Name of the object (material will be created).
        tree_name: Name for the node tree.

    Returns:
        {"object_name": str, "material_name": str, "tree_name": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        # Create new material with node tree
        mat = bpy.data.materials.new(name=f"{object_name}_Material")
        mat.use_nodes = True

        # Clear default nodes
        nodes = mat.node_tree.nodes
        for node in nodes[:]:
            nodes.remove(node)

        # Add output node
        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (300, 0)

        # Assign material
        if obj.data and hasattr(obj.data, "materials"):
            if len(obj.data.materials) == 0:
                obj.data.materials.append(mat)
            else:
                obj.data.materials[0] = mat

        set_active_object(obj)

        return {
            "object_name": obj.name,
            "material_name": mat.name,
            "tree_name": mat.node_tree.name,
        }
    except Exception as e:
        raise fmt_err("create_shader_node_tree failed", e)


def add_shader_node(
    material_name: str,
    node_type: str,
    name: str | None = None,
    location: List[float] = [0, 0],
) -> Dict[str, Any]:
    """Add a node to a material's node tree.

    Args:
        material_name: Name of the material.
        node_type: Blender node type (e.g., "ShaderNodeBsdfPrincipled", "ShaderNodeTexImage").
        name: Optional custom name for the node.
        location: [x, y] position in node editor.

    Returns:
        {"material_name": str, "node_name": str, "type": str}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat:
            raise ValueError(f"Material not found: {material_name}")

        if not mat.use_nodes:
            raise ValueError(f"Material does not use nodes: {material_name}")

        # Create node
        node = mat.node_tree.nodes.new(type=node_type)

        if name:
            node.name = name

        node.location = (location[0], location[1])

        return {
            "material_name": mat.name,
            "node_name": node.name,
            "type": node.type,
            "bl_idname": node.bl_idname,
        }
    except Exception as e:
        raise fmt_err("add_shader_node failed", e)


def link_nodes(
    material_name: str,
    from_node: str,
    from_socket: str,
    to_node: str,
    to_socket: str,
) -> Dict[str, Any]:
    """Create a link between two nodes in a material.

    Args:
        material_name: Name of the material.
        from_node: Name of source node.
        from_socket: Name of output socket.
        to_node: Name of destination node.
        to_socket: Name of input socket.

    Returns:
        {"material_name": str, "link_created": bool}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat or not mat.use_nodes:
            raise ValueError(f"Material not found or no nodes: {material_name}")

        tree = mat.node_tree

        # Find nodes
        src = tree.nodes.get(from_node)
        dst = tree.nodes.get(to_node)

        if not src:
            raise ValueError(f"Source node not found: {from_node}")
        if not dst:
            raise ValueError(f"Destination node not found: {to_node}")

        # Find sockets
        output_socket = None
        for s in src.outputs:
            if s.name == from_socket or s.identifier == from_socket:
                output_socket = s
                break

        input_socket = None
        for s in dst.inputs:
            if s.name == to_socket or s.identifier == to_socket:
                input_socket = s
                break

        if not output_socket:
            available = [s.name for s in src.outputs]
            raise ValueError(f"Output socket '{from_socket}' not found. Available: {available}")

        if not input_socket:
            available = [s.name for s in dst.inputs]
            raise ValueError(f"Input socket '{to_socket}' not found. Available: {available}")

        # Create link
        tree.links.new(output_socket, input_socket)

        return {
            "material_name": mat.name,
            "link_created": True,
            "from": f"{from_node}.{from_socket}",
            "to": f"{to_node}.{to_socket}",
        }
    except Exception as e:
        raise fmt_err("link_nodes failed", e)


def set_node_property(
    material_name: str,
    node_name: str,
    property_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Set a property on a node.

    Args:
        material_name: Name of the material.
        node_name: Name of the node.
        property_name: Name of the property (e.g., "color", "roughness", "location").
        value: Value to set.

    Returns:
        {"material_name": str, "node_name": str, "property": str}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat or not mat.use_nodes:
            raise ValueError(f"Material not found or no nodes: {material_name}")

        node = mat.node_tree.nodes.get(node_name)
        if not node:
            raise ValueError(f"Node not found: {node_name}")

        # Handle special properties
        if property_name == "location":
            node.location = (value[0], value[1])
        elif property_name == "width":
            node.width = float(value)
        elif property_name == "hide":
            node.hide = bool(value)
        elif property_name == "mute":
            node.mute = bool(value)
        elif hasattr(node, property_name):
            setattr(node, property_name, value)
        elif property_name in node.inputs:
            # Set input default value
            socket = node.inputs[property_name]
            socket.default_value = value
        else:
            raise ValueError(f"Property not found: {property_name}")

        return {
            "material_name": mat.name,
            "node_name": node.name,
            "property": property_name,
        }
    except Exception as e:
        raise fmt_err("set_node_property failed", e)


def get_node_info(material_name: str, node_name: str) -> Dict[str, Any]:
    """Get detailed info about a node including its sockets.

    Args:
        material_name: Name of the material.
        node_name: Name of the node.

    Returns:
        {"material_name": str, "node": {...}}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat or not mat.use_nodes:
            raise ValueError(f"Material not found or no nodes: {material_name}")

        node = mat.node_tree.nodes.get(node_name)
        if not node:
            raise ValueError(f"Node not found: {node_name}")

        inputs_info = []
        for s in node.inputs:
            inputs_info.append({
                "name": s.name,
                "identifier": s.identifier,
                "type": s.type,
                "is_linked": s.is_linked,
                "value": str(s.default_value) if hasattr(s, "default_value") else None,
            })

        outputs_info = []
        for s in node.outputs:
            outputs_info.append({
                "name": s.name,
                "identifier": s.identifier,
                "type": s.type,
                "is_linked": s.is_linked,
            })

        return {
            "material_name": mat.name,
            "node": {
                "name": node.name,
                "type": node.type,
                "bl_idname": node.bl_idname,
                "location": list(node.location),
                "inputs": inputs_info,
                "outputs": outputs_info,
            },
        }
    except Exception as e:
        raise fmt_err("get_node_info failed", e)


def delete_node(material_name: str, node_name: str) -> Dict[str, Any]:
    """Delete a node from a material's node tree.

    Args:
        material_name: Name of the material.
        node_name: Name of the node to delete.

    Returns:
        {"deleted": bool, "node_name": str}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat or not mat.use_nodes:
            raise ValueError(f"Material not found or no nodes: {material_name}")

        node = mat.node_tree.nodes.get(node_name)
        if not node:
            return {"deleted": False, "reason": "Node not found"}

        mat.node_tree.nodes.remove(node)

        return {"deleted": True, "node_name": node_name}
    except Exception as e:
        raise fmt_err("delete_node failed", e)


def create_node_group(
    name: str,
) -> Dict[str, Any]:
    """Create a reusable node group.

    Args:
        name: Name for the node group.

    Returns:
        {"group_name": str, "type": str}
    """
    try:
        # Create new node group
        group = bpy.data.node_groups.new(name=name, type="ShaderNodeTree")

        # Add group input/output nodes
        input_node = group.nodes.new("NodeGroupInput")
        input_node.location = (-400, 0)

        output_node = group.nodes.new("NodeGroupOutput")
        output_node.location = (400, 0)

        return {
            "group_name": group.name,
            "type": group.type,
        }
    except Exception as e:
        raise fmt_err("create_node_group failed", e)


def add_node_to_group(
    group_name: str,
    node_type: str,
    name: str | None = None,
) -> Dict[str, Any]:
    """Add a node to a node group.

    Args:
        group_name: Name of the node group.
        node_type: Type of node to add.
        name: Optional name for the node.

    Returns:
        {"group_name": str, "node_name": str}
    """
    try:
        group = bpy.data.node_groups.get(group_name)
        if not group:
            raise ValueError(f"Node group not found: {group_name}")

        node = group.nodes.new(type=node_type)
        if name:
            node.name = name

        return {
            "group_name": group.name,
            "node_name": node.name,
        }
    except Exception as e:
        raise fmt_err("add_node_to_group failed", e)


def set_node_group_input(
    material_name: str,
    group_node_name: str,
    input_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Set the value of a node group input.

    Args:
        material_name: Name of the material.
        group_node_name: Name of the node group instance.
        input_name: Name of the group input socket.
        value: Value to set.

    Returns:
        {"material_name": str, "group": str, "input": str}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat or not mat.use_nodes:
            raise ValueError(f"Material not found: {material_name}")

        group_node = mat.node_tree.nodes.get(group_node_name)
        if not group_node or group_node.type != "GROUP":
            raise ValueError(f"Group node not found: {group_node_name}")

        if input_name in group_node.inputs:
            group_node.inputs[input_name].default_value = value

        return {
            "material_name": mat.name,
            "group": group_node.name,
            "input": input_name,
        }
    except Exception as e:
        raise fmt_err("set_node_group_input failed", e)


def clear_node_tree(material_name: str) -> Dict[str, Any]:
    """Clear all nodes from a material's node tree.

    Args:
        material_name: Name of the material.

    Returns:
        {"cleared": bool, "nodes_removed": int}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat or not mat.use_nodes:
            return {"cleared": False, "reason": "No nodes"}

        count = len(mat.node_tree.nodes)
        for node in list(mat.node_tree.nodes):
            mat.node_tree.nodes.remove(node)

        return {
            "cleared": True,
            "nodes_removed": count,
        }
    except Exception as e:
        raise fmt_err("clear_node_tree failed", e)


def arrange_nodes(material_name: str) -> Dict[str, Any]:
    """Auto-arrange nodes in a material for better layout.

    Args:
        material_name: Name of the material.

    Returns:
        {"material_name": str, "arranged": bool}
    """
    try:
        mat = bpy.data.materials.get(material_name)
        if not mat or not mat.use_nodes:
            return {"arranged": False, "reason": "No nodes"}

        # Use Blender's arrange operator
        # This requires UI context, so we do basic positioning instead
        nodes = mat.node_tree.nodes
        output_node = None
        for node in nodes:
            if node.type == "OUTPUT_MATERIAL":
                output_node = node
                break

        if output_node:
            output_node.location = (400, 0)

        return {
            "material_name": mat.name,
            "arranged": True,
        }
    except Exception as e:
        raise fmt_err("arrange_nodes failed", e)
