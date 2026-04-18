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
import importlib
import os
import sys

def _load_symbols():
    """Load addon modules across package/script execution contexts."""
    errors = []

    # 1) Preferred: relative imports from current package.
    if __package__:
        try:
            prefs_mod = importlib.import_module(".prefs", package=__package__)
            server_mod = importlib.import_module(".server", package=__package__)
            ui_mod = importlib.import_module(".ui", package=__package__)
            return (
                prefs_mod.VBFAddonPreferences,
                server_mod.VBF_OT_serve,
                server_mod.VBF_OT_stop,
                server_mod.VBF_OT_self_check,
                server_mod.start_vbf_ws_server,
                ui_mod.VBF_PT_main,
            )
        except Exception as e:
            errors.append(f"relative import failed: {e}")

    # 2) Explicit package-name attempts.
    package_candidates = []
    base = (__name__ or "").split(".", 1)[0]
    if base and base not in {"__main__", "__init__"}:
        package_candidates.append(base)
    package_candidates.extend(["vbf_addon", "blender_provider.vbf_addon"])

    seen = set()
    for pkg in package_candidates:
        if pkg in seen:
            continue
        seen.add(pkg)
        try:
            prefs_mod = importlib.import_module(f"{pkg}.prefs")
            server_mod = importlib.import_module(f"{pkg}.server")
            ui_mod = importlib.import_module(f"{pkg}.ui")
            return (
                prefs_mod.VBFAddonPreferences,
                server_mod.VBF_OT_serve,
                server_mod.VBF_OT_stop,
                server_mod.VBF_OT_self_check,
                server_mod.start_vbf_ws_server,
                ui_mod.VBF_PT_main,
            )
        except Exception as e:
            errors.append(f"{pkg} import failed: {e}")

    # 3) Script-style fallback: ensure addon directory is importable.
    try:
        this_dir = os.path.dirname(__file__)
        if this_dir and this_dir not in sys.path:
            sys.path.insert(0, this_dir)
        prefs_mod = importlib.import_module("prefs")
        server_mod = importlib.import_module("server")
        ui_mod = importlib.import_module("ui")
        return (
            prefs_mod.VBFAddonPreferences,
            server_mod.VBF_OT_serve,
            server_mod.VBF_OT_stop,
            server_mod.VBF_OT_self_check,
            server_mod.start_vbf_ws_server,
            ui_mod.VBF_PT_main,
        )
    except Exception as e:
        errors.append(f"script import failed: {e}")

    raise ImportError("Failed to load VBF addon modules: " + " | ".join(errors))


(
    VBFAddonPreferences,
    VBF_OT_serve,
    VBF_OT_stop,
    VBF_OT_self_check,
    start_vbf_ws_server,
    VBF_PT_main,
) = _load_symbols()


classes = [VBFAddonPreferences, VBF_OT_serve, VBF_OT_stop, VBF_OT_self_check, VBF_PT_main]


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
