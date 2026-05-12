from __future__ import annotations

import bpy  # type: ignore

try:
    from .server import get_server, get_last_self_check
except Exception:
    # Fallback for script-style loading without package context.
    from server import get_server, get_last_self_check  # type: ignore


FOLDOUT_DEFAULTS = {
    "connection": True,
    "runtime": True,
    "executor_activity": True,
    "capabilities": False,
    "self_check": False,
    "tips": False,
}


def register_ui_properties() -> None:
    for key, default in FOLDOUT_DEFAULTS.items():
        prop_name = f"vbf_foldout_{key}"
        if hasattr(bpy.types.WindowManager, prop_name):
            continue
        setattr(
            bpy.types.WindowManager,
            prop_name,
            bpy.props.BoolProperty(default=bool(default)),
        )


def unregister_ui_properties() -> None:
    for key in FOLDOUT_DEFAULTS:
        prop_name = f"vbf_foldout_{key}"
        if hasattr(bpy.types.WindowManager, prop_name):
            try:
                delattr(bpy.types.WindowManager, prop_name)
            except Exception:
                pass


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

    @staticmethod
    def _foldout(layout, context, key: str, label: str, default: bool = True) -> bool:
        wm = context.window_manager
        prop_key = f"vbf_foldout_{key}"
        if not hasattr(wm, prop_key):
            try:
                setattr(wm, prop_key, bool(default))
            except Exception:
                pass
        is_open = bool(getattr(wm, prop_key, default))
        row = layout.row(align=True)
        row.prop(
            wm,
            prop_key,
            text=label,
            icon="TRIA_DOWN" if is_open else "TRIA_RIGHT",
            emboss=False,
        )
        return is_open

    @staticmethod
    def _format_seconds(value) -> str:
        if value is None:
            return "N/A"
        try:
            return f"{float(value):.1f}s"
        except Exception:
            return "N/A"

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
        try:
            executor = server.executor_status()
        except Exception:
            executor = {}

        if server.running:
            status_text = "RUNNING"
            status_icon = "PLAY"
        elif executor.get("thread_alive") or executor.get("server_bound"):
            status_text = "STOPPING / PORT MAY STILL BE BOUND"
            status_icon = "ERROR"
        else:
            status_text = "STOPPED"
            status_icon = "PAUSE"

        col.label(text=f"Status: {status_text}", icon=status_icon)
        col.label(text=f"Bind: {server.host}:{server.port}")

        if prefs is not None:
            layout.separator()
            if self._foldout(layout, context, "connection", "Connection", default=True):
                box = layout.box()
                conn_col = box.column(align=True)
                conn_col.prop(prefs, "host", text="Host")
                conn_col.prop(prefs, "port", text="Port")
                conn_col.label(text="Click Start to apply bind changes")

        row = layout.row(align=True)
        row.operator("vbf.serve", text="Start", icon="PLAY")
        row.operator("vbf.stop", text="Stop", icon="PAUSE")
        row.operator("vbf.self_check", text="Self Check", icon="CHECKMARK")

        layout.separator()

        if self._foldout(layout, context, "runtime", "Runtime", default=True):
            box = layout.box()
            runtime_col = box.column(align=True)
            runtime_col.label(
                text=(
                    "Thread/Loop/Socket: "
                    f"{'ON' if executor.get('thread_alive') else 'OFF'} / "
                    f"{'ON' if executor.get('loop_alive') else 'OFF'} / "
                    f"{'ON' if executor.get('server_bound') else 'OFF'}"
                )
            )
            runtime_col.label(
                text=(
                    "Timer/Queue/Poll: "
                    f"{'ON' if executor.get('timer_registered') else 'OFF'} / "
                    f"{executor.get('queue_size', 0)} / "
                    f"{self._format_seconds(executor.get('last_poll_age_s'))}"
                )
            )
            runtime_col.label(text=f"Executed jobs: {executor.get('executed_jobs', 0)}")

        layout.separator()
        if self._foldout(layout, context, "executor_activity", "Executor Activity", default=True):
            box = layout.box()
            activity_col = box.column(align=True)
            current = executor.get("current_job")
            if isinstance(current, dict):
                activity_col.label(
                    text=(
                        "Current: "
                        f"{current.get('skill') or current.get('method') or 'unknown'} "
                        f"step={current.get('step_id') or 'N/A'} "
                        f"running={self._format_seconds(current.get('running_s'))}"
                    ),
                    icon="TIME",
                )
            else:
                activity_col.label(text="Current: idle", icon="CHECKMARK")

            last = executor.get("last_job")
            if isinstance(last, dict):
                activity_col.label(
                    text=(
                        "Last: "
                        f"{last.get('skill') or last.get('method') or 'unknown'} "
                        f"step={last.get('step_id') or 'N/A'} "
                        f"{'OK' if last.get('ok') else 'FAIL'} "
                        f"{self._format_seconds(last.get('duration_s'))}"
                    ),
                    icon="CHECKMARK" if last.get("ok") else "ERROR",
                )
                if last.get("error"):
                    activity_col.label(text=f"Error: {str(last.get('error'))[:80]}", icon="ERROR")
            else:
                activity_col.label(text="Last: none")

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

        layout.separator()
        if self._foldout(layout, context, "capabilities", "Capabilities", default=False):
            box = layout.box()
            caps_col = box.column(align=True)
            self._draw_capability_row(caps_col, "Capability RPC", features.get("capabilities_rpc"))
            self._draw_capability_row(caps_col, "Scene Snapshot", features.get("scene_snapshot"))
            self._draw_capability_row(caps_col, "Scene Delta", features.get("scene_delta"))
            self._draw_capability_row(caps_col, "Rollback", features.get("rollback_to_step"))
            self._draw_capability_row(caps_col, "Executor Status", features.get("executor_status"))

        last_check = None
        try:
            last_check = get_last_self_check()
        except Exception:
            last_check = None

        if isinstance(last_check, dict):
            layout.separator()
            if self._foldout(layout, context, "self_check", "Self Check Result", default=False):
                box = layout.box()
                status_icon = "CHECKMARK" if last_check.get("ok") else "ERROR"
                box.label(text=f"Status: {'PASS' if last_check.get('ok') else 'FAIL'}", icon=status_icon)
                box.label(text=f"Checked: {last_check.get('checked_at', 'unknown')}")
                box.label(text=f"Summary: {last_check.get('summary', '')}")
                checks = last_check.get("checks", [])
                if isinstance(checks, list):
                    for item in checks:
                        if not isinstance(item, dict):
                            continue
                        ok = bool(item.get("ok"))
                        icon = "CHECKMARK" if ok else "ERROR"
                        name = str(item.get("name", "check"))
                        box.label(text=f"{name}: {'OK' if ok else 'FAIL'}", icon=icon)

        layout.separator()
        if self._foldout(layout, context, "tips", "Tips", default=False):
            box = layout.box()
            box.label(text="Client connects to ws://host:port")


__all__ = ["VBF_PT_main", "register_ui_properties", "unregister_ui_properties"]
