from __future__ import annotations

import bpy  # type: ignore


def _addon_id() -> str:
    # e.g. "vbf_addon"
    return __package__ or "vbf_addon"


class VBFAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = _addon_id()

    host: bpy.props.StringProperty(  # type: ignore
        name="Host",
        default="127.0.0.1",
        description="WebSocket server bind host",
    )

    port: bpy.props.IntProperty(  # type: ignore
        name="Port",
        default=8006,
        min=1,
        max=65535,
        description="WebSocket server listen port",
    )

    autostart: bpy.props.BoolProperty(  # type: ignore
        name="Autostart Server",
        default=False,
        description="Start VBF server automatically when the add-on is enabled",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "host")
        layout.prop(self, "port")
        layout.prop(self, "autostart")


__all__ = ["VBFAddonPreferences"]

