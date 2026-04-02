from typing import Callable, Dict

from .anchors import move_object_anchor_to_point
from .antenna import create_nested_cones
from .api import api_validator
from .booleans import boolean_tool, join_objects
from .geometry import create_beveled_box
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

