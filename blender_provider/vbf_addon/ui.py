from __future__ import annotations

import bpy  # type: ignore

try:
    from .server import get_server, get_last_self_check
except Exception:
    # Fallback for script-style loading without package context.
    from server import get_server, get_last_self_check  # type: ignore


class VBF_PT_main(bpy.types.Panel):
    bl_idname = "VBF_PT_main"
    bl_label = "Vibe-Blender-Flow"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "VBF"

    @staticmethod
    def _draw_capability_row(layout, label: str, enabled):
        if enabled is True:
            status = "ON"
            icon = "CHECKMARK"
        elif enabled is False:
            status = "OFF"
            icon = "X"
        else:
            status = "N/A"
            icon = "QUESTION"
        layout.label(text=f"{label}: {status}", icon=icon)

    def draw(self, context):
        layout = self.layout
        server = get_server()
        prefs = None
        try:
            addon_key = __package__ or "vbf_addon"
            addon_entry = context.preferences.addons.get(addon_key)
            if addon_entry and getattr(addon_entry, "preferences", None):
                prefs = addon_entry.preferences
        except Exception:
            prefs = None

        col = layout.column(align=True)
        col.label(text=f"Status: {'RUNNING' if server.running else 'STOPPED'}")
        col.label(text=f"Bind: {server.host}:{server.port}")

        if prefs is not None:
            layout.separator()
            layout.label(text="Connection:")
            conn_col = layout.column(align=True)
            conn_col.prop(prefs, "host", text="Host")
            conn_col.prop(prefs, "port", text="Port")
            layout.label(text="Click Start to apply bind changes")

        row = layout.row(align=True)
        row.operator("vbf.serve", text="Start", icon="PLAY")
        row.operator("vbf.stop", text="Stop", icon="PAUSE")
        row.operator("vbf.self_check", text="Self Check", icon="CHECKMARK")

        layout.separator()
        layout.label(text="Capabilities:")

        capabilities = None
        try:
            if hasattr(server, "_get_capabilities"):
                capabilities = server._get_capabilities()
        except Exception:
            capabilities = None

        features = {}
        if isinstance(capabilities, dict):
            maybe_features = capabilities.get("features")
            if isinstance(maybe_features, dict):
                features = maybe_features

        caps_col = layout.column(align=True)
        self._draw_capability_row(caps_col, "Capability RPC", features.get("capabilities_rpc"))
        self._draw_capability_row(caps_col, "Scene Snapshot", features.get("scene_snapshot"))
        self._draw_capability_row(caps_col, "Scene Delta", features.get("scene_delta"))
        self._draw_capability_row(caps_col, "Rollback", features.get("rollback_to_step"))

        last_check = None
        try:
            last_check = get_last_self_check()
        except Exception:
            last_check = None

        if isinstance(last_check, dict):
            layout.separator()
            layout.label(text="Self Check Result:")
            status_icon = "CHECKMARK" if last_check.get("ok") else "ERROR"
            layout.label(text=f"Status: {'PASS' if last_check.get('ok') else 'FAIL'}", icon=status_icon)
            layout.label(text=f"Checked: {last_check.get('checked_at', 'unknown')}")
            layout.label(text=f"Summary: {last_check.get('summary', '')}")
            checks = last_check.get("checks", [])
            if isinstance(checks, list):
                for item in checks[:4]:
                    if not isinstance(item, dict):
                        continue
                    ok = bool(item.get("ok"))
                    icon = "CHECKMARK" if ok else "ERROR"
                    name = str(item.get("name", "check"))
                    layout.label(text=f"{name}: {'OK' if ok else 'FAIL'}", icon=icon)

        layout.separator()
        layout.label(text="Tips:")
        layout.label(text="Client connects to ws://host:port")


__all__ = ["VBF_PT_main"]
