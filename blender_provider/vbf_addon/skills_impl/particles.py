# Particle System Skills - Blender Particle Systems
from typing import Any, Dict, List

import bpy

from .utils import ensure_object_mode, fmt_err, set_active_object, vec3


def create_particle_system(
    object_name: str,
    system_name: str,
    type: str = "EMITTER",
) -> Dict[str, Any]:
    """Add a particle system to an object.

    Args:
        object_name: Object to add particles to (must be a mesh).
        system_name: Name for the particle system.
        type: "EMITTER" or "HAIR".

    Returns:
        {"object_name": str, "system_name": str, "type": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "MESH":
            raise ValueError(f"Mesh object not found: {object_name}")

        set_active_object(obj)

        # Create particle system
        psys = obj.modifiers.new(name=system_name, type="PARTICLE_SYSTEM")
        psys.name = system_name
        settings = psys.particle_system.settings
        settings.type = type

        return {
            "object_name": obj.name,
            "system_name": system_name,
            "type": type,
        }
    except Exception as e:
        raise fmt_err("create_particle_system failed", e)


def set_particle_emitter(
    system_name: str,
    count: int = 1000,
    start_frame: int = 1,
    end_frame: int = 250,
    lifetime: int = 50,
) -> Dict[str, Any]:
    """Configure particle emission settings.

    Args:
        system_name: Name of the particle modifier.
        count: Total number of particles.
        start_frame: Emission start frame.
        end_frame: Emission end frame.
        lifetime: Particle lifetime in frames.

    Returns:
        {"system_name": str, "count": int}
    """
    try:
        settings = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.name == system_name:
                    settings = mod.particle_system.settings
                    break
            if settings:
                break

        if not settings:
            raise ValueError(f"Particle system not found: {system_name}")

        settings.count = count
        settings.frame_start = start_frame
        settings.frame_end = end_frame
        settings.lifetime = lifetime

        return {
            "system_name": system_name,
            "count": count,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "lifetime": lifetime,
        }
    except Exception as e:
        raise fmt_err("set_particle_emitter failed", e)


def set_particle_source(
    system_name: str,
    source: str = "VERT",
    distribution: str = "JIT",
) -> Dict[str, Any]:
    """Set particle emission source.

    Args:
        system_name: Name of particle modifier.
        source: "VERT" (vertices), "FACE" (faces), "VOLUME".
        distribution: "JIT" (jittered), "GRID", "RAND".

    Returns:
        {"system_name": str, "source": str}
    """
    try:
        settings = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.name == system_name:
                    settings = mod.particle_system.settings
                    break
            if settings:
                break

        if not settings:
            raise ValueError(f"Particle system not found: {system_name}")

        settings.emit_from = source
        if hasattr(settings, "distribution"):
            settings.distribution = distribution

        return {
            "system_name": system_name,
            "source": source,
        }
    except Exception as e:
        raise fmt_err("set_particle_source failed", e)


def set_particle_velocity(
    system_name: str,
    normal: float = 1.0,
    tangent: float = 0.0,
    object_align: float = 0.0,
    random: float = 0.0,
) -> Dict[str, Any]:
    """Set initial particle velocity.

    Args:
        system_name: Name of particle modifier.
        normal: Velocity along normal.
        tangent: Tangent velocity.
        object_align: Object-aligned velocity.
        random: Random velocity amount.

    Returns:
        {"system_name": str, "settings_applied": True}
    """
    try:
        settings = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.name == system_name:
                    settings = mod.particle_system.settings
                    break
            if settings:
                break

        if not settings:
            raise ValueError(f"Particle system not found: {system_name}")

        settings.normal_factor = normal
        settings.tangent_factor = tangent
        settings.object_align_factor = object_align
        settings.factor_random = random

        return {
            "system_name": system_name,
            "settings_applied": True,
        }
    except Exception as e:
        raise fmt_err("set_particle_velocity failed", e)


def set_particle_physics(
    system_name: str,
    physics_type: str = "NEWTON",
) -> Dict[str, Any]:
    """Set particle physics type.

    Args:
        system_name: Name of particle modifier.
        physics_type: "NO", "NEWTON", "KEYED", "BOIDS", "FLUID".

    Returns:
        {"system_name": str, "physics": str}
    """
    try:
        settings = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.name == system_name:
                    settings = mod.particle_system.settings
                    break
            if settings:
                break

        if not settings:
            raise ValueError(f"Particle system not found: {system_name}")

        settings.physics_type = physics_type

        return {
            "system_name": system_name,
            "physics": physics_type,
        }
    except Exception as e:
        raise fmt_err("set_particle_physics failed", e)


def set_particle_gravity(
    system_name: str,
    gravity: float = 1.0,
    mass: float = 1.0,
    size: float = 0.5,
) -> Dict[str, Any]:
    """Set particle gravity and physical properties.

    Args:
        system_name: Name of particle modifier.
        gravity: Gravity effect multiplier.
        mass: Particle mass.
        size: Particle size.

    Returns:
        {"system_name": str, "settings_applied": True}
    """
    try:
        settings = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.name == system_name:
                    settings = mod.particle_system.settings
                    break
            if settings:
                break

        if not settings:
            raise ValueError(f"Particle system not found: {system_name}")

        settings.effector_weights.gravity = gravity
        settings.mass = mass
        settings.particle_size = size

        return {
            "system_name": system_name,
            "gravity": gravity,
            "mass": mass,
            "size": size,
        }
    except Exception as e:
        raise fmt_err("set_particle_gravity failed", e)


def set_particle_render(
    system_name: str,
    render_type: str = "HALO",
    material: int = 1,
) -> Dict[str, Any]:
    """Set particle render settings.

    Args:
        system_name: Name of particle modifier.
        render_type: "NONE", "HALO", "LINE", "PATH", "OBJECT", "COLLECTION".
        material: Material slot index for particles.

    Returns:
        {"system_name": str, "render_type": str}
    """
    try:
        settings = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.name == system_name:
                    settings = mod.particle_system.settings
                    break
            if settings:
                break

        if not settings:
            raise ValueError(f"Particle system not found: {system_name}")

        settings.render_type = render_type
        settings.material = material

        return {
            "system_name": system_name,
            "render_type": render_type,
            "material_slot": material,
        }
    except Exception as e:
        raise fmt_err("set_particle_render failed", e)


def set_particle_hair(
    system_name: str,
    length: float = 1.0,
    segments: int = 5,
) -> Dict[str, Any]:
    """Configure hair particle settings.

    Args:
        system_name: Name of particle modifier.
        length: Hair length.
        segments: Hair segments/subdivisions.

    Returns:
        {"system_name": str, "length": float, "segments": int}
    """
    try:
        settings = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.name == system_name:
                    settings = mod.particle_system.settings
                    break
            if settings:
                break

        if not settings:
            raise ValueError(f"Particle system not found: {system_name}")

        if settings.type != "HAIR":
            raise ValueError("Particle system must be type HAIR")

        if hasattr(settings, "hair_length"):
            settings.hair_length = length
        settings.segments = segments

        return {
            "system_name": system_name,
            "length": length,
            "segments": segments,
        }
    except Exception as e:
        raise fmt_err("set_particle_hair failed", e)


def set_particle_instance_object(
    system_name: str,
    instance_object: str,
) -> Dict[str, Any]:
    """Set instance object for rendered particles.

    Args:
        system_name: Name of particle modifier.
        instance_object: Name of object to instance on particles.

    Returns:
        {"system_name": str, "instance_object": str}
    """
    try:
        settings = None
        for obj in bpy.data.objects:
            for mod in obj.modifiers:
                if mod.type == "PARTICLE_SYSTEM" and mod.name == system_name:
                    settings = mod.particle_system.settings
                    break
            if settings:
                break

        if not settings:
            raise ValueError(f"Particle system not found: {system_name}")

        if settings.render_type not in ["OBJECT", "COLLECTION"]:
            raise ValueError(f"Render type must be OBJECT or COLLECTION, got {settings.render_type}")

        inst_obj = bpy.data.objects.get(instance_object)
        if not inst_obj:
            raise ValueError(f"Instance object not found: {instance_object}")

        settings.instance_object = inst_obj

        return {
            "system_name": system_name,
            "instance_object": inst_obj.name,
        }
    except Exception as e:
        raise fmt_err("set_particle_instance_object failed", e)


def bake_particles(
    object_name: str,
    system_name: str,
) -> Dict[str, Any]:
    """Bake particle system to memory.

    Args:
        object_name: Object with particle system.
        system_name: Name of particle modifier.

    Returns:
        {"object_name": str, "system": str, "baked": bool}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        mod = obj.modifiers.get(system_name)
        if not mod or mod.type != "PARTICLE_SYSTEM":
            raise ValueError(f"Particle system not found: {system_name}")

        # Bake cache
        psys = mod.particle_system
        bpy.ops.ptcache.bake(
            {"point_cache": psys.point_cache},
            bake=True,
        )

        return {
            "object_name": obj.name,
            "system": system_name,
            "baked": True,
        }
    except Exception as e:
        raise fmt_err("bake_particles failed", e)


def convert_particles_to_mesh(
    object_name: str,
    system_name: str,
    new_name: str | None = None,
) -> Dict[str, Any]:
    """Convert particle system to real mesh objects.

    Args:
        object_name: Object with particle system.
        system_name: Name of particle modifier.
        new_name: Name for new object(s). Default uses particle names.

    Returns:
        {"object_name": str, "system": str, "converted": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        set_active_object(obj)

        mod = obj.modifiers.get(system_name)
        if not mod or mod.type != "PARTICLE_SYSTEM":
            raise ValueError(f"Particle system not found: {system_name}")

        # Make real
        bpy.ops.object.modifier_apply(modifier=mod.name)

        # Convert particles
        bpy.ops.object.particle_system_add()
        bpy.ops.object.particle_system_remove()

        # Get actual count from particles
        psys = mod.particle_system
        count = len([p for p in psys.particles])

        return {
            "object_name": obj.name,
            "system": system_name,
            "converted": count,
        }
    except Exception as e:
        raise fmt_err("convert_particles_to_mesh failed", e)


def remove_particle_system(
    object_name: str,
    system_name: str,
) -> Dict[str, Any]:
    """Remove a particle system from an object.

    Args:
        object_name: Object with particle system.
        system_name: Name of particle modifier.

    Returns:
        {"removed": bool, "system": str}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mod = obj.modifiers.get(system_name)
        if not mod or mod.type != "PARTICLE_SYSTEM":
            return {"removed": False, "reason": "Particle system not found"}

        obj.modifiers.remove(mod)

        return {"removed": True, "system": system_name}
    except Exception as e:
        raise fmt_err("remove_particle_system failed", e)


def list_particle_systems(object_name: str) -> Dict[str, Any]:
    """List all particle systems on an object.

    Args:
        object_name: Object to query.

    Returns:
        {"object_name": str, "systems": [{"name": str, "type": str, "count": int}], "count": int}
    """
    try:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        systems = []
        for mod in obj.modifiers:
            if mod.type == "PARTICLE_SYSTEM":
                settings = mod.particle_system.settings
                systems.append({
                    "name": mod.name,
                    "type": settings.type,
                    "count": settings.count,
                    "physics": settings.physics_type,
                    "render": settings.render_type,
                })

        return {
            "object_name": obj.name,
            "systems": systems,
            "count": len(systems),
        }
    except Exception as e:
        raise fmt_err("list_particle_systems failed", e)
