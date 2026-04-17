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

try:
    from .prefs import VBFAddonPreferences
    from .server import VBF_OT_serve, VBF_OT_stop, start_vbf_ws_server  # type: ignore
    from .ui import VBF_PT_main
except Exception:
    # Fallback for script-style loading without package context.
    from prefs import VBFAddonPreferences  # type: ignore
    from server import VBF_OT_serve, VBF_OT_stop, start_vbf_ws_server  # type: ignore
    from ui import VBF_PT_main  # type: ignore


classes = [VBFAddonPreferences, VBF_OT_serve, VBF_OT_stop, VBF_PT_main]


def _addon_key() -> str:
    if __package__:
        return __package__
    base = (__name__ or "").split(".", 1)[0]
    if base and base not in {"__main__", "__init__"}:
        return base
    return "vbf_addon"


def register():
    for c in classes:
        bpy.utils.register_class(c)
    # Optional: autostart server when enabling addon.
    try:
        prefs = bpy.context.preferences.addons[_addon_key()].preferences
        if getattr(prefs, "autostart", False):
            bpy.ops.vbf.serve()
    except Exception:
        pass


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


__all__ = ["register", "unregister", "start_vbf_ws_server"]
