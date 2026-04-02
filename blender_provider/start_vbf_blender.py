"""
Entry point for Blender headless startup (-b -P start_vbf_blender.py).
It starts the VBF WebSocket server and polls the job queue.
"""

import os
import sys


def _ensure_module_path() -> None:
    # Make sure relative imports work when executed via Blender -P.
    this_dir = os.path.dirname(__file__)
    if this_dir not in sys.path:
        sys.path.insert(0, this_dir)
    repo_root = os.path.dirname(this_dir)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


_ensure_module_path()

from blender_provider import vbf_addon  # noqa: E402


vbf_addon.register()
vbf_addon.start_vbf_ws_server()

print("VBF WS server started.")

