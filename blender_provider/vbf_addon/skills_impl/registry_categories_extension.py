# YouTube Tutorial Analysis Based Skill Categories Extension
# This file extends SKILL_CATEGORIES with new YouTube-based skills

# Import this after the main registry to extend categories
from .edge_control import (
    bisect_mesh,
    clear_edge_bevel_weight,
    clear_edge_crease,
    fill_holes,
    get_edge_data,
    mark_edge_crease,
    select_edge_rings,
    set_edge_bevel_weight,
    symmetrize_mesh,
)
from .materials_enhanced import (
    attach_texture_to_material,
    create_material_pbr,
    create_material_preset,
    set_material_ior,
)
from .modifiers_extended import (
    add_modifier_array,
    add_modifier_boolean,
    add_modifier_curve,
    add_modifier_displace,
    add_modifier_mirror,
    add_modifier_shrinkwrap,
    add_modifier_solidify,
    configure_modifier,
    list_modifiers,
    move_modifier,
)
from .animation_enhanced import (
    bake_animation,
    copy_keyframes,
    create_action,
    delete_action,
    insert_keyframe_bone,
    insert_keyframe_shape_key,
    list_actions,
    nla_add_strip,
    paste_keyframes,
    set_action,
    set_keyframe_handle_type,
    set_nla_strip_properties,
)

# Extended skill categories based on YouTube tutorial analysis
SKILL_CATEGORIES_YOUTUBE = {
    "Edge Control (YouTube)": [
        "mark_edge_crease",
        "clear_edge_crease",
        "set_edge_bevel_weight",
        "clear_edge_bevel_weight",
        "get_edge_data",
        "bisect_mesh",
        "fill_holes",
        "symmetrize_mesh",
        "select_edge_rings",
    ],
    "Extended Modifiers (YouTube)": [
        "add_modifier_solidify",
        "add_modifier_array",
        "add_modifier_mirror",
        "add_modifier_boolean",
        "add_modifier_shrinkwrap",
        "add_modifier_curve",
        "add_modifier_displace",
        "configure_modifier",
        "move_modifier",
        "list_modifiers",
    ],
    "Enhanced Materials (YouTube)": [
        "create_material_pbr",
        "attach_texture_to_material",
        "create_material_preset",
        "set_material_ior",
    ],
    "Animation Enhanced (YouTube)": [
        "insert_keyframe_bone",
        "insert_keyframe_shape_key",
        "set_keyframe_handle_type",
        "copy_keyframes",
        "paste_keyframes",
        "bake_animation",
        "create_action",
        "set_action",
        "list_actions",
        "delete_action",
        "nla_add_strip",
        "set_nla_strip_properties",
    ],
}
