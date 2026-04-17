from __future__ import annotations

import bpy  # type: ignore

try:
    from .server import get_server
except Exception:
    # Fallback for script-style loading without package context.
    from server import get_server  # type: ignore


class VBF_PT_main(bpy.types.Panel):
    bl_idname = "VBF_PT_main"
    bl_label = "Vibe-Blender-Flow"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "VBF"

    def draw(self, context):
        layout = self.layout
        server = get_server()

        col = layout.column(align=True)
        col.label(text=f"Status: {'RUNNING' if server.running else 'STOPPED'}")
        col.label(text=f"Bind: {server.host}:{server.port}")

        row = layout.row(align=True)
        row.operator("vbf.serve", text="Start", icon="PLAY")
        row.operator("vbf.stop", text="Stop", icon="PAUSE")

        layout.separator()
        layout.label(text="Tips:")
        layout.label(text="Client connects to ws://host:port")


__all__ = ["VBF_PT_main"]
