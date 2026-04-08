from typing import Callable, Dict

# Domain imports
from .anchors import move_object_anchor_to_point
from .animation import (
    clear_animation,
    delete_keyframe,
    evaluate_fcurve,
    get_current_frame,
    insert_keyframe,
    list_fcurves,
    set_animation_fps,
    set_current_frame,
    set_frame_range,
    set_keyframe_interpolation,
)
from .antenna import create_nested_cones
from .api import api_validator
from .booleans import boolean_tool, join_objects
from .camera import (
    camera_look_at,
    create_camera,
    get_camera_info,
    set_camera_active,
    set_camera_properties,
)
from .collections import (
    create_collection,
    isolate_in_collection,
    link_to_collection,
    list_collections,
    move_to_layer,
    remove_collection,
    unlink_from_collection,
)
from .constraints import (
    add_constraint_copy_location,
    add_constraint_copy_rotation,
    add_constraint_copy_scale,
    add_constraint_limit_location,
    clear_parent,
    list_constraints,
    remove_constraint,
    set_parent,
)
from .geometry import create_beveled_box
from .lighting import (
    create_light,
    set_light_properties,
    set_render_engine,
    set_render_resolution,
)
from .materials import assign_material, create_material_simple
from .modifiers import add_modifier_bevel, add_modifier_subdivision, apply_modifier
from .primitives import create_primitive
from .scene import delete_object, rename_object, scene_clear
from .spatial import spatial_query
from .transforms import apply_transform
from .runtime_gateway import (
    data_collections_list,
    ops_introspect,
    ops_invoke,
    ops_list,
    ops_search,
    py_call,
    py_get,
    py_set,
    types_list,
)

SKILL_REGISTRY: Dict[str, Callable] = {
    # Scene / objects
    "scene_clear": scene_clear,
    "delete_object": delete_object,
    "rename_object": rename_object,

    # Geometry
    "create_primitive": create_primitive,
    "create_beveled_box": create_beveled_box,
    "create_nested_cones": create_nested_cones,

    # Transforms & spatial awareness
    "apply_transform": apply_transform,
    "spatial_query": spatial_query,
    "move_object_anchor_to_point": move_object_anchor_to_point,

    # Booleans / composition
    "boolean_tool": boolean_tool,
    "join_objects": join_objects,

    # Materials
    "create_material_simple": create_material_simple,
    "assign_material": assign_material,

    # Modifiers
    "add_modifier_bevel": add_modifier_bevel,
    "add_modifier_subdivision": add_modifier_subdivision,
    "apply_modifier": apply_modifier,

    # Lighting
    "create_light": create_light,
    "set_light_properties": set_light_properties,
    "set_render_engine": set_render_engine,
    "set_render_resolution": set_render_resolution,

    # Camera
    "create_camera": create_camera,
    "set_camera_active": set_camera_active,
    "set_camera_properties": set_camera_properties,
    "camera_look_at": camera_look_at,
    "get_camera_info": get_camera_info,

    # Collections
    "create_collection": create_collection,
    "link_to_collection": link_to_collection,
    "unlink_from_collection": unlink_from_collection,
    "remove_collection": remove_collection,
    "list_collections": list_collections,
    "isolate_in_collection": isolate_in_collection,
    "move_to_layer": move_to_layer,

    # Constraints & Parenting
    "set_parent": set_parent,
    "clear_parent": clear_parent,
    "add_constraint_copy_location": add_constraint_copy_location,
    "add_constraint_copy_rotation": add_constraint_copy_rotation,
    "add_constraint_copy_scale": add_constraint_copy_scale,
    "add_constraint_limit_location": add_constraint_limit_location,
    "remove_constraint": remove_constraint,
    "list_constraints": list_constraints,

    # Animation
    "insert_keyframe": insert_keyframe,
    "delete_keyframe": delete_keyframe,
    "set_current_frame": set_current_frame,
    "get_current_frame": get_current_frame,
    "set_frame_range": set_frame_range,
    "set_animation_fps": set_animation_fps,
    "clear_animation": clear_animation,
    "list_fcurves": list_fcurves,
    "set_keyframe_interpolation": set_keyframe_interpolation,
    "evaluate_fcurve": evaluate_fcurve,

    # API validation
    "api_validator": api_validator,

    # Full Blender API coverage gateway
    "py_get": py_get,
    "py_set": py_set,
    "py_call": py_call,
    "ops_list": ops_list,
    "ops_search": ops_search,
    "ops_invoke": ops_invoke,
    "ops_introspect": ops_introspect,
    "types_list": types_list,
    "data_collections_list": data_collections_list,
}

# Metadata for documentation
SKILL_CATEGORIES = {
    "Scene": ["scene_clear", "delete_object", "rename_object"],
    "Geometry": ["create_primitive", "create_beveled_box", "create_nested_cones"],
    "Transforms": ["apply_transform", "spatial_query", "move_object_anchor_to_point"],
    "Booleans": ["boolean_tool", "join_objects"],
    "Materials": ["create_material_simple", "assign_material"],
    "Modifiers": ["add_modifier_bevel", "add_modifier_subdivision", "apply_modifier"],
    "Lighting": ["create_light", "set_light_properties", "set_render_engine", "set_render_resolution"],
    "Camera": ["create_camera", "set_camera_active", "set_camera_properties", "camera_look_at", "get_camera_info"],
    "Collections": ["create_collection", "link_to_collection", "unlink_from_collection", "remove_collection", "list_collections", "isolate_in_collection", "move_to_layer"],
    "Constraints": ["set_parent", "clear_parent", "add_constraint_copy_location", "add_constraint_copy_rotation", "add_constraint_copy_scale", "add_constraint_limit_location", "remove_constraint", "list_constraints"],
    "Animation": ["insert_keyframe", "delete_keyframe", "set_current_frame", "get_current_frame", "set_frame_range", "set_animation_fps", "clear_animation", "list_fcurves", "set_keyframe_interpolation", "evaluate_fcurve"],
    "Gateway": ["py_get", "py_set", "py_call", "ops_list", "ops_search", "ops_invoke", "ops_introspect", "types_list", "data_collections_list", "api_validator"],
}

SKILL_COUNT = len(SKILL_REGISTRY)
CATEGORY_COUNT = len(SKILL_CATEGORIES)
