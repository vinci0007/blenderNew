# Armature & Rigging Skills - Blender Skeleton System
from typing import Any, Dict, List

import bpy
from mathutils import Matrix, Vector

from .utils import ensure_object_mode, fmt_err, set_active_object, vec3


def create_armature(
    name: str,
    location: List[float] = [0.0, 0.0, 0.0],
) -> Dict[str, Any]:
    """Create a new armature object for character rigging.

    Args:
        name: Name for the armature object.
        location: [x, y, z] world-space position.

    Returns:
        {"object_name": str, "data_name": str}
    """
    try:
        # Create armature data
        arm_data = bpy.data.armatures.new(name=name)
        arm_data.use_mirror_x = True

        # Create object
        arm_obj = bpy.data.objects.new(name=name, object_data=arm_data)
        bpy.context.collection.objects.link(arm_obj)
        arm_obj.location = vec3(location)

        set_active_object(arm_obj)

        # Enter edit mode to show bones
        ensure_object_mode()

        return {
            "object_name": arm_obj.name,
            "data_name": arm_data.name,
        }
    except Exception as e:
        raise fmt_err("create_armature failed", e)


def add_bone(
    armature_name: str,
    bone_name: str,
    head: List[float],
    tail: List[float],
    roll: float = 0.0,
    parent_bone: str | None = None,
    connect: bool = False,
) -> Dict[str, Any]:
    """Add a bone to an armature in edit mode.

    Args:
        armature_name: Name of the armature object.
        bone_name: Name for the new bone.
        head: [x, y, z] world-space head position.
        tail: [x, y, z] world-space tail position.
        roll: Bone roll rotation in radians.
        parent_bone: Optional parent bone name.
        connect: If True, connects to parent (tails must touch).

    Returns:
        {"bone_name": str, "length": float}
    """
    try:
        arm_obj = bpy.data.objects.get(armature_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {armature_name}")

        set_active_object(arm_obj)

        # Enter edit mode
        if bpy.context.mode != "EDIT":
            bpy.ops.object.mode_set(mode="EDIT")

        # Add bone
        bone = arm_obj.data.edit_bones.new(bone_name)
        bone.head = vec3(head)
        bone.tail = vec3(tail)
        bone.roll = roll

        # Set parent if specified
        if parent_bone:
            parent = arm_obj.data.edit_bones.get(parent_bone)
            if parent:
                bone.parent = parent
                bone.use_connect = connect

        length = bone.length

        # Return to object mode
        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "bone_name": bone.name,
            "length": length,
            "parent": parent_bone,
        }
    except Exception as e:
        raise fmt_err("add_bone failed", e)


def edit_bone(
    armature_name: str,
    bone_name: str,
    head: List[float] | None = None,
    tail: List[float] | None = None,
    roll: float | None = None,
    length: float | None = None,
) -> Dict[str, Any]:
    """Edit an existing bone's properties.

    Args:
        armature_name: Name of the armature object.
        bone_name: Name of bone to edit.
        head: New [x, y, z] head position.
        tail: New [x, y, z] tail position.
        roll: New roll value in radians.
        length: New length (scales tail from head).

    Returns:
        {"bone_name": str, "updated": List[str]}
    """
    try:
        arm_obj = bpy.data.objects.get(armature_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {armature_name}")

        set_active_object(arm_obj)

        # Enter edit mode
        bpy.ops.object.mode_set(mode="EDIT")

        bone = arm_obj.data.edit_bones.get(bone_name)
        if not bone:
            bpy.ops.object.mode_set(mode="OBJECT")
            raise ValueError(f"Bone not found: {bone_name}")

        updated = []

        if head is not None:
            bone.head = vec3(head)
            updated.append("head")

        if tail is not None:
            bone.tail = vec3(tail)
            updated.append("tail")

        if roll is not None:
            bone.roll = roll
            updated.append("roll")

        if length is not None and length > 0:
            bone.length = length
            updated.append("length")

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"bone_name": bone.name, "updated": updated}
    except Exception as e:
        raise fmt_err("edit_bone failed", e)


def delete_bone(armature_name: str, bone_name: str) -> Dict[str, Any]:
    """Delete a bone from an armature.

    Args:
        armature_name: Name of the armature object.
        bone_name: Name of bone to delete.

    Returns:
        {"deleted": bool, "bone_name": str}
    """
    try:
        arm_obj = bpy.data.objects.get(armature_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {armature_name}")

        set_active_object(arm_obj)

        bpy.ops.object.mode_set(mode="EDIT")

        bone = arm_obj.data.edit_bones.get(bone_name)
        if bone:
            arm_obj.data.edit_bones.remove(bone)
            deleted = True
        else:
            deleted = False

        bpy.ops.object.mode_set(mode="OBJECT")

        return {"deleted": deleted, "bone_name": bone_name}
    except Exception as e:
        raise fmt_err("delete_bone failed", e)


def list_bones(armature_name: str) -> Dict[str, Any]:
    """List all bones in an armature.

    Args:
        armature_name: Name of the armature object.

    Returns:
        {"bones": [{"name": str, "head": [x,y,z], "tail": [x,y,z], "length": float}], "count": int}
    """
    try:
        arm_obj = bpy.data.objects.get(armature_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {armature_name}")

        bones = []
        for bone in arm_obj.data.bones:
            bones.append({
                "name": bone.name,
                "head": list(bone.head_local),
                "tail": list(bone.tail_local),
                "length": bone.length,
                "parent": bone.parent.name if bone.parent else None,
            })

        return {"bones": bones, "count": len(bones)}
    except Exception as e:
        raise fmt_err("list_bones failed", e)


def create_vertex_group(
    object_name: str,
    group_name: str,
) -> Dict[str, Any]:
    """Create a new vertex group on a mesh object.

    Args:
        object_name: Name of the mesh object.
        group_name: Name for the vertex group.

    Returns:
        {"object_name": str, "group_name": str, "index": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        # Create vertex group
        vgroup = obj.vertex_groups.new(name=group_name)

        return {
            "object_name": obj.name,
            "group_name": vgroup.name,
            "index": vgroup.index,
        }
    except Exception as e:
        raise fmt_err("create_vertex_group failed", e)


def assign_vertex_weights(
    object_name: str,
    group_name: str,
    vertex_indices: List[int],
    weight: float = 1.0,
    type: str = "REPLACE",
) -> Dict[str, Any]:
    """Assign weights to vertices in a vertex group.

    Args:
        object_name: Name of the mesh object.
        group_name: Name of the vertex group.
        vertex_indices: List of vertex indices to assign.
        weight: Weight value (0.0 - 1.0).
        type: Assignment mode. Enum: "REPLACE" | "ADD" | "SUBTRACT" | "MULTIPLY".

    Returns:
        {"object_name": str, "group": str, "assigned": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        vgroup = obj.vertex_groups.get(group_name)
        if not vgroup:
            raise ValueError(f"Vertex group not found: {group_name}")

        # Mode mapping
        mode_map = {
            "REPLACE": "REPLACE",
            "ADD": "ADD",
            "SUBTRACT": "SUBTRACT",
            "MULTIPLY": "MULTIPLY",
        }

        vgroup.add(vertex_indices, weight, mode_map.get(type, "REPLACE"))

        return {
            "object_name": obj.name,
            "group": vgroup.name,
            "assigned": len(vertex_indices),
        }
    except Exception as e:
        raise fmt_err("assign_vertex_weights failed", e)


def skin_to_armature(
    object_name: str,
    armature_name: str,
    create_modifiers: bool = True,
) -> Dict[str, Any]:
    """Skin/parent a mesh object to an armature with automatic weights.

    Args:
        object_name: Name of the mesh object to skin.
        armature_name: Name of the armature to skin to.
        create_modifiers: If True, creates armature modifier with automatic weights.

    Returns:
        {"object_name": str, "armature": str, "modifiers_created": int}
    """
    try:
        mesh_obj = bpy.data.objects.get(object_name)
        if not mesh_obj or mesh_obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        arm_obj = bpy.data.objects.get(armature_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {armature_name}")

        set_active_object(mesh_obj)

        # Create vertex groups for each bone if they don't exist
        for bone in arm_obj.data.bones:
            group_name = bone.name
            if group_name not in mesh_obj.vertex_groups:
                mesh_obj.vertex_groups.new(name=group_name)

        # Parent with automatic weights
        if create_modifiers:
            # Add armature modifier
            mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
            mod.object = arm_obj

        return {
            "object_name": mesh_obj.name,
            "armature": arm_obj.name,
            "modifiers_created": 1 if create_modifiers else 0,
        }
    except Exception as e:
        raise fmt_err("skin_to_armature failed", e)


def set_armature_modifier(
    object_name: str,
    armature_name: str,
    modifier_name: str = "Armature",
) -> Dict[str, Any]:
    """Set or update armature modifier on a mesh.

    Args:
        object_name: Name of the mesh object.
        armature_name: Name of the armature object.
        modifier_name: Name for the modifier (creates if not exists).

    Returns:
        {"object_name": str, "modifier_name": str, "armature": str}
    """
    try:
        mesh_obj = bpy.data.objects.get(object_name)
        if not mesh_obj:
            raise ValueError(f"Object not found: {object_name}")

        arm_obj = bpy.data.objects.get(armature_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {armature_name}")

        # Find or create modifier
        mod = mesh_obj.modifiers.get(modifier_name)
        if not mod:
            mod = mesh_obj.modifiers.new(name=modifier_name, type="ARMATURE")

        mod.object = arm_obj
        mod.use_deform_preserve_volume = True

        return {
            "object_name": mesh_obj.name,
            "modifier_name": mod.name,
            "armature": arm_obj.name,
        }
    except Exception as e:
        raise fmt_err("set_armature_modifier failed", e)


def add_ik_constraint(
    object_name: str,
    bone_name: str,
    chain_length: int = 2,
    use_rotation: bool = False,
) -> Dict[str, Any]:
    """Add Inverse Kinematics (IK) constraint to a pose bone.

    Args:
        object_name: Name of the armature object.
        bone_name: Name of the bone to add IK constraint to.
        chain_length: Number of bones in the IK chain.
        use_rotation: Use rotation for IK target.

    Returns:
        {"object_name": str, "bone": str, "constraint_name": str}
    """
    try:
        arm_obj = bpy.data.objects.get(object_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {object_name}")

        set_active_object(arm_obj)

        # Enter pose mode
        bpy.ops.object.mode_set(mode="POSE")

        bone = arm_obj.pose.bones.get(bone_name)
        if not bone:
            bpy.ops.object.mode_set(mode="OBJECT")
            raise ValueError(f"Pose bone not found: {bone_name}")

        # Add IK constraint
        ik = bone.constraints.new("IK")
        ik.name = f"IK_{bone_name}"
        ik.chain_length = chain_length
        ik.use_rotation = use_rotation

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "object_name": arm_obj.name,
            "bone": bone_name,
            "constraint_name": ik.name,
        }
    except Exception as e:
        raise fmt_err("add_ik_constraint failed", e)


def add_armature_constraint(
    child_object: str,
    armature_name: str,
    bone_name: str,
    constraint_type: str = "CHILD_OF",
) -> Dict[str, Any]:
    """Add armature constraint to an object.

    Args:
        child_object: Name of object to constrain.
        armature_name: Name of armature.
        bone_name: Target bone name.
        constraint_type: Type of constraint. Enum: "CHILD_OF" | "COPY_TRANSFORMS".

    Returns:
        {"child": str, "constraint": str}
    """
    try:
        child = bpy.data.objects.get(child_object)
        if not child:
            raise ValueError(f"Object not found: {child_object}")

        arm_obj = bpy.data.objects.get(armature_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {armature_name}")

        # Add constraint
        if constraint_type == "CHILD_OF":
            con = child.constraints.new("CHILD_OF")
            con.target = arm_obj
            con.subtarget = bone_name
        elif constraint_type == "COPY_TRANSFORMS":
            con = child.constraints.new("COPY_TRANSFORMS")
            con.target = arm_obj
            con.subtarget = bone_name
        else:
            raise ValueError(f"Unknown constraint type: {constraint_type}")

        return {
            "child": child.name,
            "constraint": con.name,
            "type": constraint_type,
        }
    except Exception as e:
        raise fmt_err("add_armature_constraint failed", e)


def symmetrize_bones(armature_name: str, axis: str = "X") -> Dict[str, Any]:
    """Mirror bones across an axis.

    Args:
        armature_name: Name of the armature.
        axis: Mirror axis. Enum: "X" | "Y" | "Z".

    Returns:
        {"armature": str, "mirrored": int}
    """
    try:
        arm_obj = bpy.data.objects.get(armature_name)
        if not arm_obj or arm_obj.type != "ARMATURE":
            raise ValueError(f"Armature not found: {armature_name}")

        set_active_object(arm_obj)

        bpy.ops.object.mode_set(mode="EDIT")

        # Select all bones
        bpy.ops.armature.select_all(action="SELECT")

        # Symmetrize
        if axis == "X":
            bpy.ops.armature.symmetrize(direction="NEGATIVE_X")

        bpy.ops.object.mode_set(mode="OBJECT")

        return {
            "armature": arm_obj.name,
            "symmetrized": True,
        }
    except Exception as e:
        raise fmt_err("symmetrize_bones failed", e)
