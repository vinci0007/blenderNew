# Compositor Nodes Skills - Blender Compositing
from typing import Any, Dict, List, Optional, Tuple, Union

import bpy

from .utils import fmt_err


def create_compositor_tree(
    scene_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Enable and set up compositing node tree for a scene.

    Args:
        scene_name: Scene name (default: current scene).

    Returns:
        {"scene_name": str, "enabled": bool}
    """
    try:
        scene = bpy.data.scenes.get(scene_name) if scene_name else bpy.context.scene
        if not scene:
            raise ValueError(f"Scene not found: {scene_name}")

        # Enable compositing
        scene.use_nodes = True
        tree = scene.node_tree

        # Clear default nodes
        tree.nodes.clear()

        # Add render layers node
        render_layers = tree.nodes.new(type="CompositorNodeRLayers")
        render_layers.location = (0, 0)

        # Add composite output
        composite = tree.nodes.new(type="CompositorNodeComposite")
        composite.location = (300, 0)

        # Link them
        tree.links.new(render_layers.outputs["Image"], composite.inputs["Image"])

        return {
            "scene_name": scene.name,
            "enabled": True,
            "nodes": len(tree.nodes),
        }
    except Exception as e:
        raise fmt_err("create_compositor_tree failed", e)


def add_compositor_node(
    node_type: str,
    name: Optional[str] = None,
    location: List[float] = [0, 0],
) -> Dict[str, Any]:
    """Add a node to the compositor node tree.

    Args:
        node_type: Node type (e.g., "CompositorNodeBlur", "CompositorNodeColorBalance").
        name: Optional custom name.
        location: [x, y] position.

    Returns:
        {"node_name": str, "type": str}
    """
    try:
        scene = bpy.context.scene
        if not scene.use_nodes:
            scene.use_nodes = True

        tree = scene.node_tree
        node = tree.nodes.new(type=node_type)

        if name:
            node.name = name

        node.location = (location[0], location[1])

        return {
            "node_name": node.name,
            "type": node.bl_idname,
        }
    except Exception as e:
        raise fmt_err("add_compositor_node failed", e)


def link_compositor_nodes(
    from_node: str,
    from_socket: str,
    to_node: str,
    to_socket: str,
) -> Dict[str, Any]:
    """Create a link between compositor nodes.

    Args:
        from_node: Source node name.
        from_socket: Source socket name.
        to_node: Destination node name.
        to_socket: Destination socket name.

    Returns:
        {"link_created": bool, "from": str, "to": str}
    """
    try:
        scene = bpy.context.scene
        if not scene.use_nodes:
            raise ValueError("Compositor not enabled")

        tree = scene.node_tree

        src = tree.nodes.get(from_node)
        dst = tree.nodes.get(to_node)

        if not src:
            raise ValueError(f"Source node not found: {from_node}")
        if not dst:
            raise ValueError(f"Destination node not found: {to_node}")

        # Find sockets
        out_socket = None
        for s in src.outputs:
            if s.name == from_socket or s.identifier == from_socket:
                out_socket = s
                break

        in_socket = None
        for s in dst.inputs:
            if s.name == to_socket or s.identifier == to_socket:
                in_socket = s
                break

        if not out_socket:
            available = [s.name for s in src.outputs]
            raise ValueError(f"Output socket '{from_socket}' not found. Available: {available}")
        if not in_socket:
            available = [s.name for s in dst.inputs]
            raise ValueError(f"Input socket '{to_socket}' not found. Available: {available}")

        tree.links.new(out_socket, in_socket)

        return {
            "link_created": True,
            "from": f"{from_node}.{from_socket}",
            "to": f"{to_node}.{to_socket}",
        }
    except Exception as e:
        raise fmt_err("link_compositor_nodes failed", e)


def set_compositor_node_input(
    node_name: str,
    input_name: str,
    value: Any,
) -> Dict[str, Any]:
    """Set an input value on a compositor node.

    Args:
        node_name: Node name.
        input_name: Input socket or property name.
        value: Value to set.

    Returns:
        {"node_name": str, "input": str}
    """
    try:
        scene = bpy.context.scene
        if not scene.use_nodes:
            raise ValueError("Compositor not enabled")

        tree = scene.node_tree
        node = tree.nodes.get(node_name)
        if not node:
            raise ValueError(f"Node not found: {node_name}")

        # Find input socket
        found = False
        for inp in node.inputs:
            if inp.name == input_name or inp.identifier == input_name:
                inp.default_value = value
                found = True
                break

        if not found:
            # Try setting as property
            if hasattr(node, input_name):
                setattr(node, input_name, value)
                found = True

        if not found:
            raise ValueError(f"Input or property not found: {input_name}")

        return {
            "node_name": node.name,
            "input": input_name,
        }
    except Exception as e:
        raise fmt_err("set_compositor_node_input failed", e)


def compositor_add_blur(
    size_x: float = 10.0,
    size_y: float = 10.0,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a blur node to the compositor.

    Args:
        size_x: Blur size in X.
        size_y: Blur size in Y.
        name: Optional node name.

    Returns:
        {"node_name": str, "type": str}
    """
    try:
        result = add_compositor_node("CompositorNodeBlur", name)
        node_name = result["node_name"]

        set_compositor_node_input(node_name, "Size", [size_x, size_y])

        return result
    except Exception as e:
        raise fmt_err("compositor_add_blur failed", e)


def compositor_add_color_balance(
    lift: List[float] = [1.0, 1.0, 1.0],
    gamma: List[float] = [1.0, 1.0, 1.0],
    gain: List[float] = [1.0, 1.0, 1.0],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a color balance node to the compositor.

    Args:
        lift: Lift values [r, g, b].
        gamma: Gamma values [r, g, b].
        gain: Gain values [r, g, b].
        name: Optional node name.

    Returns:
        {"node_name": str, "type": str}
    """
    try:
        result = add_compositor_node("CompositorNodeColorBalance", name)
        node_name = result["node_name"]

        node = bpy.context.scene.node_tree.nodes.get(node_name)
        node.lift = lift
        node.gamma = gamma
        node.gain = gain

        return result
    except Exception as e:
        raise fmt_err("compositor_add_color_balance failed", e)


def compositor_add_mix(
    blend_type: str = "MIX",
    factor: float = 0.5,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a mix node to the compositor.

    Args:
        blend_type: Type of blend (MIX, ADD, MULTIPLY, SCREEN, OVERLAY, etc.).
        factor: Mix factor.
        name: Optional node name.

    Returns:
        {"node_name": str, "type": str}
    """
    try:
        result = add_compositor_node("CompositorNodeMixRGB", name)
        node_name = result["node_name"]

        node = bpy.context.scene.node_tree.nodes.get(node_name)
        node.blend_type = blend_type

        # Set factor
        if node.inputs.get("Fac"):
            node.inputs["Fac"].default_value = factor

        return result
    except Exception as e:
        raise fmt_err("compositor_add_mix failed", e)


def compositor_add_bright_contrast(
    bright: float = 0.0,
    contrast: float = 0.0,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add brightness/contrast node to the compositor.

    Args:
        bright: Brightness adjustment.
        contrast: Contrast adjustment.
        name: Optional node name.

    Returns:
        {"node_name": str, "type": str}
    """
    try:
        result = add_compositor_node("CompositorNodeBrightContrast", name)
        node_name = result["node_name"]

        node = bpy.context.scene.node_tree.nodes.get(node_name)
        node.inputs["Bright"].default_value = bright
        node.inputs["Contrast"].default_value = contrast

        return result
    except Exception as e:
        raise fmt_err("compositor_add_bright_contrast failed", e)


def compositor_add_alpha_over(
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an alpha over node to the compositor.

    Args:
        name: Optional node name.

    Returns:
        {"node_name": str, "type": str}
    """
    try:
        return add_compositor_node("CompositorNodeAlphaOver", name)
    except Exception as e:
        raise fmt_err("compositor_add_alpha_over failed", e)


def compositor_add_image(
    filepath: str,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Add an image input node to the compositor.

    Args:
        filepath: Path to image file.
        name: Optional node name.

    Returns:
        {"node_name": str, "image_name": str}
    """
    try:
        # Load or get image
        img = bpy.data.images.get(filepath)
        if not img:
            img = bpy.data.images.load(filepath, check_existing=True)

        result = add_compositor_node("CompositorNodeImage", name)
        node_name = result["node_name"]

        node = bpy.context.scene.node_tree.nodes.get(node_name)
        node.image = img

        return {
            "node_name": node_name,
            "image_name": img.name,
        }
    except Exception as e:
        raise fmt_err("compositor_add_image failed", e)


def compositor_delete_node(
    node_name: str,
) -> Dict[str, Any]:
    """Delete a compositor node.

    Args:
        node_name: Node to delete.

    Returns:
        {"deleted": bool, "name": str}
    """
    try:
        scene = bpy.context.scene
        if not scene.use_nodes:
            raise ValueError("Compositor not enabled")

        tree = scene.node_tree
        node = tree.nodes.get(node_name)
        if not node:
            return {"deleted": False, "reason": "Node not found"}

        tree.nodes.remove(node)
        return {"deleted": True, "name": node_name}
    except Exception as e:
        raise fmt_err("compositor_delete_node failed", e)


def compositor_clear_tree() -> Dict[str, Any]:
    """Clear all nodes from the compositor tree.

    Returns:
        {"cleared": bool, "count": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.use_nodes:
            return {"cleared": True, "count": 0}

        tree = scene.node_tree
        count = len(tree.nodes)
        tree.nodes.clear()

        return {"cleared": True, "count": count}
    except Exception as e:
        raise fmt_err("compositor_clear_tree failed", e)


def compositor_list_nodes() -> Dict[str, Any]:
    """List all nodes in the compositor tree.

    Returns:
        {"nodes": [{"name": str, "type": str, "location": [float, float]}], "count": int}
    """
    try:
        scene = bpy.context.scene
        if not scene.use_nodes:
            return {"nodes": [], "count": 0}

        tree = scene.node_tree
        nodes = []
        for node in tree.nodes:
            nodes.append({
                "name": node.name,
                "type": node.bl_idname,
                "location": [node.location[0], node.location[1]],
            })

        return {"nodes": nodes, "count": len(nodes)}
    except Exception as e:
        raise fmt_err("compositor_list_nodes failed", e)


def set_compositor_backdrop(
    enabled: bool = True,
) -> Dict[str, Any]:
    """Enable/disable backdrop in the compositor.

    Args:
        enabled: Whether to show backdrop.

    Returns:
        {"enabled": bool}
    """
    try:
        if bpy.context.space_data and bpy.context.space_data.type == "NODE_EDITOR":
            bpy.context.space_data.show_backdrop = enabled

        return {"enabled": enabled}
    except Exception as e:
        raise fmt_err("set_compositor_backdrop failed", e)
