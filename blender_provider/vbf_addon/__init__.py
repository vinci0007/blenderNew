bl_info = {
    "name": "Vibe-Blender-Flow (VBF)",
    "author": "VBF",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "Preferences > Add-ons",
    "description": "JSON-RPC over WebSocket bridge + skill registry for Blender automation",
    "category": "Object",
}

import bpy  # type: ignore

from .prefs import VBFAddonPreferences
from .server import VBF_OT_serve, VBF_OT_stop, start_vbf_ws_server  # type: ignore
from .ui import VBF_PT_main


classes = [VBFAddonPreferences, VBF_OT_serve, VBF_OT_stop, VBF_PT_main]


def register():
    for c in classes:
        bpy.utils.register_class(c)
    # Optional: autostart server when enabling addon.
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
        if getattr(prefs, "autostart", False):
            bpy.ops.vbf.serve()
    except Exception:
        pass


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


__all__ = ["register", "unregister", "start_vbf_ws_server"]

