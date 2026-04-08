# Physics Skills - Blender Physics Simulations (Rigid Body, Cloth, Fluid, Soft Body)
from typing import Any, Dict, List

import bpy

from .utils import ensure_object_mode, fmt_err, set_active_object, vec3


def rigidbody_add(
    object_name: str,
    body_type: str = "ACTIVE",
    mass: float = 1.0,
    collision_shape: str = "MESH",
    friction: float = 0.5,
    bounce: float = 0.0,
) -> Dict[str, Any]:
    """Add rigid body physics to an object.

    Args:
        object_name: Name of object to add physics to.
        body_type: "ACTIVE" or "PASSIVE".
        mass: Mass in kg (for active bodies).
        collision_shape: "BOX", "SPHERE", "CAPSULE", "CYLINDER", "CONE", "MESH", "CONVEX_HULL".
        friction: Surface friction (0.0 - 1.0).
        bounce: Bounciness (0.0 - 1.0).

    Returns:
        {"object_name": str, "body_type": str, "mass": float}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        # Ensure scene has rigid body world
        if not bpy.context.scene.rigidbody_world:
            bpy.ops.rigidbody.world_add()

        # Add rigid body
        bpy.ops.rigidbody.object_add(type=body_type)

        # Configure properties
        rb = obj.rigid_body
        if rb:
            rb.mass = mass
            rb.collision_shape = collision_shape
            rb.friction = friction
            rb.restitution = bounce

        return {
            "object_name": obj.name,
            "body_type": body_type,
            "mass": mass,
            "collision_shape": collision_shape,
        }
    except Exception as e:
        raise fmt_err("rigidbody_add failed", e)


def rigidbody_set_mass(
    object_name: str,
    mass: float,
    calculate_center: bool = True,
) -> Dict[str, Any]:
    """Set mass for a rigid body object.

    Args:
        object_name: Name of rigid body object.
        mass: Mass in kg.
        calculate_center: Auto-calculate center of mass.

    Returns:
        {"object_name": str, "mass": float}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        rb = obj.rigid_body
        if not rb:
            raise ValueError(f"Object is not a rigid body: {object_name}")

        rb.mass = mass

        if calculate_center:
            bpy.ops.rigidbody.mass_calculate(mesh_compartment_multiplier=1.0)

        return {"object_name": obj.name, "mass": rb.mass}
    except Exception as e:
        raise fmt_err("rigidbody_set_mass failed", e)


def rigidbody_set_collision_shape(
    object_name: str,
    shape: str,
    margin: float = 0.04,
) -> Dict[str, Any]:
    """Set collision shape for rigid body.

    Args:
        object_name: Name of rigid body object.
        shape: "BOX", "SPHERE", "CAPSULE", "CYLINDER", "CONE", "MESH",
               "CONVEX_HULL", "COMPOUND".
        margin: Collision margin.

    Returns:
        {"object_name": str, "shape": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        rb = obj.rigid_body
        if not rb:
            raise ValueError(f"Object is not a rigid body: {object_name}")

        rb.collision_shape = shape
        rb.collision_margin = margin

        return {"object_name": obj.name, "shape": shape}
    except Exception as e:
        raise fmt_err("rigidbody_set_collision_shape failed", e)


def rigidbody_connect(
    object1: str,
    object2: str,
    constraint_type: str = "FIXED",
    name: str | None = None,
) -> Dict[str, Any]:
    """Create a rigid body constraint between two objects.

    Args:
        object1: First rigid body object.
        object2: Second rigid body object.
        constraint_type: "FIXED", "POINT", "HINGE", "SLIDER", "PISTON",
                         "GENERIC", "GENERIC_SPRING", "MOTOR".
        name: Optional name for constraint.

    Returns:
        {"constraint_name": str, "type": str, "objects": List[str]}
    """
    try:
        obj1 = bpy.data.objects.get(object1)
        obj2 = bpy.data.objects.get(object2)
        if not obj1 or not obj2:
            raise ValueError("One or both objects not found")

        # Set active to obj1
        set_active_object(obj1)

        # Create constraint
        bpy.ops.rigidbody.constraint_add(type=constraint_type)
        con_obj = bpy.context.object

        if name:
            con_obj.name = name

        # Set constraint objects
        rbc = con_obj.rigid_body_constraint
        if rbc:
            rbc.object1 = obj1
            rbc.object2 = obj2

        return {
            "constraint_name": con_obj.name,
            "type": constraint_type,
            "objects": [obj1.name, obj2.name],
        }
    except Exception as e:
        raise fmt_err("rigidbody_connect failed", e)


def rigidbody_bake(
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> Dict[str, Any]:
    """Bake rigid body simulation to keyframes.

    Args:
        start_frame: Start frame (default: scene start).
        end_frame: End frame (default: scene end).

    Returns:
        {"baked": bool, "start": int, "end": int}
    """
    try:
        scene = bpy.context.scene
        start = start_frame or scene.frame_start
        end = end_frame or scene.frame_end

        # Cache and bake
        if scene.rigidbody_world:
            scene.rigidbody_world.point_cache.frame_start = int(start)
            scene.rigidbody_world.point_cache.frame_end = int(end)

            # Bake to action
            bpy.ops.ptcache.bake(
                {"point_cache": scene.rigidbody_world.point_cache},
                frame_start=int(start),
                frame_end=int(end),
            )

        return {"baked": True, "start": int(start), "end": int(end)}
    except Exception as e:
        raise fmt_err("rigidbody_bake failed", e)


def cloth_add(
    object_name: str,
    preset: str = "COTTON",
) -> Dict[str, Any]:
    """Add cloth physics to a mesh object.

    Args:
        object_name: Name of mesh object.
        preset: Material preset. "COTTON", "DENIM", "LEATHER",
                "SILK", "RUBBER", "WOOL".

    Returns:
        {"object_name": str, "preset": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Add cloth modifier
        mod = obj.modifiers.new(name="Cloth", type="CLOTH")

        # Apply preset settings
        cloth = mod.settings
        presets = {
            "COTTON": {"mass": 0.15, "structural": 5.0, "bending": 0.5},
            "DENIM": {"mass": 0.3, "structural": 15.0, "bending": 2.0},
            "LEATHER": {"mass": 0.4, "structural": 20.0, "bending": 5.0},
            "SILK": {"mass": 0.07, "structural": 2.5, "bending": 0.3},
            "RUBBER": {"mass": 0.25, "structural": 30.0, "bending": 10.0},
            "WOOL": {"mass": 0.2, "structural": 8.0, "bending": 1.0},
        }

        if preset in presets:
            p = presets[preset]
            cloth.mass = p["mass"]
            cloth.tension_stiffness = p["structural"]
            cloth.bending_stiffness = p["bending"]

        return {
            "object_name": obj.name,
            "preset": preset,
            "modifier": mod.name,
        }
    except Exception as e:
        raise fmt_err("cloth_add failed", e)


def cloth_pin_vertices(
    object_name: str,
    vertex_group: str,
) -> Dict[str, Any]:
    """Pin cloth vertices using vertex group.

    Args:
        object_name: Cloth object name.
        vertex_group: Name of vertex group to pin.

    Returns:
        {"object_name": str, "pinned_group": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        if vertex_group not in obj.vertex_groups:
            raise ValueError(f"Vertex group not found: {vertex_group}")

        # Find cloth modifier
        cloth_mod = None
        for mod in obj.modifiers:
            if mod.type == "CLOTH":
                cloth_mod = mod
                break

        if not cloth_mod:
            raise ValueError(f"No cloth modifier on object: {object_name}")

        # Set pin group
        cloth_mod.settings.vertex_group_mass = vertex_group

        return {
            "object_name": obj.name,
            "pinned_group": vertex_group,
        }
    except Exception as e:
        raise fmt_err("cloth_pin_vertices failed", e)


def cloth_bake(
    object_name: str,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> Dict[str, Any]:
    """Bake cloth simulation.

    Args:
        object_name: Cloth object name.
        start_frame: Start frame.
        end_frame: End frame.

    Returns:
        {"object_name": str, "baked": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        scene = bpy.context.scene
        start = start_frame or scene.frame_start
        end = end_frame or scene.frame_end

        # Find cloth modifier
        cloth_mod = None
        for mod in obj.modifiers:
            if mod.type == "CLOTH":
                cloth_mod = mod
                break

        if not cloth_mod:
            raise ValueError(f"No cloth modifier on object: {object_name}")

        # Set bake range and bake
        cloth_mod.point_cache.frame_start = int(start)
        cloth_mod.point_cache.frame_end = int(end)

        bpy.ops.ptcache.bake(
            {"point_cache": cloth_mod.point_cache},
            frame_start=int(start),
            frame_end=int(end),
        )

        return {
            "object_name": obj.name,
            "baked": True,
            "start": int(start),
            "end": int(end),
        }
    except Exception as e:
        raise fmt_err("cloth_bake failed", e)


def fluid_domain_create(
    object_name: str,
    domain_type: str = "FLUID",
    resolution: int = 32,
) -> Dict[str, Any]:
    """Create a fluid simulation domain.

    Args:
        object_name: Object to convert to fluid domain (typically a cube).
        domain_type: "FLUID", "GAS", "LIQUID".
        resolution: Grid resolution (higher = more detail, slower).

    Returns:
        {"object_name": str, "domain_type": str, "resolution": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        # Add fluid modifier as domain
        mod = obj.modifiers.new(name="Fluid", type="FLUID")
        mod.fluid_type = "DOMAIN"
        mod.domain_settings.domain_type = domain_type
        mod.domain_settings.resolution_max = resolution

        return {
            "object_name": obj.name,
            "domain_type": domain_type,
            "resolution": resolution,
        }
    except Exception as e:
        raise fmt_err("fluid_domain_create failed", e)


def fluid_emitter_add(
    object_name: str,
    fluid_type: str = "LIQUID",
    volume_initialization: str = "VOLUME",
) -> Dict[str, Any]:
    """Add a fluid emitter to an object.

    Args:
        object_name: Object to convert to fluid emitter.
        fluid_type: "LIQUID" or "GAS".
        volume_initialization: "VOLUME" or "EMITTER".

    Returns:
        {"object_name": str, "fluid_type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        # Add fluid modifier as effector/emitter
        mod = obj.modifiers.new(name="Fluid", type="FLUID")
        mod.fluid_type = "EFFECTOR"
        mod.effector_settings.effector_type = "LIQUID" if fluid_type == "LIQUID" else "OUTFLOW"

        return {
            "object_name": obj.name,
            "fluid_type": fluid_type,
        }
    except Exception as e:
        raise fmt_err("fluid_emitter_add failed", e)


def fluid_effector_add(
    object_name: str,
    effector_type: str = "GUIDE",
) -> Dict[str, Any]:
    """Add a fluid effector (force field that affects fluid).

    Args:
        object_name: Object to create effector from.
        effector_type: "GUIDE", "PLANE", "LOCAL", "DRAG", etc.

    Returns:
        {"object_name": str, "effector_type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        # Add as effector
        mod = obj.modifiers.new(name="Fluid", type="FLUID")
        mod.fluid_type = "EFFECTOR"
        mod.effector_settings.effector_type = effector_type

        return {
            "object_name": obj.name,
            "effector_type": effector_type,
        }
    except Exception as e:
        raise fmt_err("fluid_effector_add failed", e)


def fluid_bake(
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> Dict[str, Any]:
    """Bake all fluid simulations in the scene.

    Args:
        start_frame: Start frame.
        end_frame: End frame.

    Returns:
        {"baked": bool, "start": int, "end": int}
    """
    try:
        scene = bpy.context.scene
        start = start_frame or scene.frame_start
        end = end_frame or scene.frame_end

        # Bake fluid for all domains
        for obj in scene.objects:
            for mod in obj.modifiers:
                if mod.type == "FLUID" and mod.fluid_type == "DOMAIN":
                    mod.domain_settings.cache_frame_start = int(start)
                    mod.domain_settings.cache_frame_end = int(end)

        # Trigger bake (this is simulation-specific)
        bpy.ops.fluid.bake_all()

        return {"baked": True, "start": int(start), "end": int(end)}
    except Exception as e:
        raise fmt_err("fluid_bake failed", e)


def softbody_add(
    object_name: str,
    mass: float = 1.0,
    stiffness: float = 10.0,
) -> Dict[str, Any]:
    """Add soft body physics to a mesh.

    Args:
        object_name: Mesh object name.
        mass: Mass of soft body vertices.
        stiffness: Spring stiffness.

    Returns:
        {"object_name": str, "mass": float, "stiffness": float}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Add soft body modifier
        mod = obj.modifiers.new(name="Softbody", type="SOFT_BODY")

        # Configure
        sb = mod.settings
        sb.mass = mass
        sb.inner_material = stiffness

        return {
            "object_name": obj.name,
            "mass": mass,
            "stiffness": stiffness,
        }
    except Exception as e:
        raise fmt_err("softbody_add failed", e)


def force_field_add(
    field_type: str,
    name: str,
    location: List[float] = [0, 0, 0],
    strength: float = 1.0,
) -> Dict[str, Any]:
    """Add a force field to the scene.

    Args:
        field_type: "WIND", "FORCE", "VORTEX", "MAGNET", "HARMONIC",
                    "CHARGE", "LENNARDJONES", "CURVE", "BOID", "TURBULENCE",
                    "DRAG", "FLUID", "SMOKE".
        name: Name for the force field object.
        location: [x, y, z] position.
        strength: Field strength.

    Returns:
        {"object_name": str, "field_type": str, "strength": float}
    """
    try:
        loc = vec3(location)

        # Add empty with force field
        bpy.ops.object.effector_add(
            type=field_type,
            location=loc,
        )
        obj = bpy.context.active_object
        obj.name = name

        # Set strength
        if obj.field:
            obj.field.strength = strength

        return {
            "object_name": obj.name,
            "field_type": field_type,
            "strength": strength,
        }
    except Exception as e:
        raise fmt_err("force_field_add failed", e)


def collision_add(
    object_name: str,
    absorb: float = 0.0,
    friction: float = 0.5,
) -> Dict[str, Any]:
    """Add collision modifier to an object (for cloth, soft body, particles).

    Args:
        object_name: Object to add collision to.
        absorb: Cloth damping absorb.
        friction: Surface friction.

    Returns:
        {"object_name": str, "modifier": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        mod = obj.modifiers.new(name="Collision", type="COLLISION")

        # Configure
        coll = mod.settings
        coll.absorb = absorb
        coll.friction = friction

        return {
            "object_name": obj.name,
            "modifier": mod.name,
        }
    except Exception as e:
        raise fmt_err("collision_add failed", e)
