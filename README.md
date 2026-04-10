# Vibe-Blender-Flow (VBF)

**Natural-Language Driven Atomic Modeling System for Blender**

**[中文版](README_CN.md)** | **English**

[![License](TBD)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

## Example: Make a Cellphone

![LLM creates a cellphone model](assets/llm_cellphone.gif)

---

## Overview

VBF enables natural-language driven 3D modeling in Blender through three core principles:

1. **High-Level Skills**: Blender addon provides 290+ atomic skills (no direct bmesh manipulation)
2. **JSON-RPC Protocol**: Python client calls skills via WebSocket with automatic error recovery
3. **LLM Integration**: Schema-aware planning prevents parameter hallucination

## What's New

**v2.0 - Major Update (2026-04-08):**
- **290+ Skills Implemented** across 38 domain modules
- **Full Blender 4.0/5.x Compatibility** (EEVEE_NEXT support)
- **38 New Modules**: armature, asset, compositor, drivers, geometry_nodes, grease_pencil, particles, physics, sculpting, sequencer, tracking, and more
- **Production Ready**: Comprehensive coverage for modeling, UV, materials, animation, camera, lighting, and constraints

See [API Coverage Analysis](docs/API_COVERAGE_ANALYSIS.md) for detailed coverage metrics.

---

## Repository Structure

```
/vbf                      Main Python package (VBFClient, CLI, LLM integration)
  ├─ cli.py               CLI entry: `vbf --prompt "..."`
  ├─ client.py            VBFClient class
  ├─ jsonrpc_ws.py        WebSocket JSON-RPC client
  ├─ llm_openai_compat.py LLM integration (OpenAI-compatible APIs)
  └─ vibe_protocol.py     Plan resolver with $ref support

/blender_provider         Blender addon source
  └─ vbf_addon/           Standard Blender addon (install this)
      ├─ __init__.py      Addon registration
      ├─ server.py        WebSocket server (JSON-RPC endpoint)
      └─ skills_impl/     290+ skill implementations
          ├─ registry.py  SKILL_REGISTRY dict
          ├─ primitives.py, mesh_ops.py, uv_ops.py
          ├─ armature.py, particles.py, physics.py
          └─ [35 more modules...]

/client                   Legacy client (deprecated)
/reference                Reference materials
```

---

## Requirements

### Client Side
- Python >= 3.10
- Dependencies: `websockets`

### Blender Side
- Blender 4.0+ or 5.x
- Python `websockets` package (installed in Blender's Python):

```python
# In Blender Python Console:
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "websockets"])
```

---

## Installation

### Blender Addon Installation

1. Copy `blender_provider/vbf_addon/` to your Blender addons directory:
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\4.x\scripts\addons\`
   - **Linux**: `~/.config/blender/4.x/scripts/addons/`
   - **macOS**: `~/Library/Application Support/Blender/4.x/scripts/addons/`

2. Enable the addon:
   - Open Blender
   - Edit → Preferences → Add-ons
   - Search "Vibe-Blender-Flow (VBF)"
   - Enable the addon

3. Start the server:
   - **Method 1**: N-panel → VBF tab → Start button
   - **Method 2**: Blender Python Console: `bpy.ops.vbf.serve()`

### Client Installation

Using `uv` (recommended):
```bash
uv sync
```

Using pip:
```bash
pip install websockets
```

---

## LLM Configuration

VBF supports OpenAI-compatible APIs. If not configured, falls back to a deterministic `RadioTask` demo.

### Method A: Environment Variables (Recommended)

```bash
export VBF_LLM_BASE_URL="https://api.openai.com/v1"
export VBF_LLM_API_KEY="your-key"
export VBF_LLM_MODEL="gpt-4o-mini"
```

Optional:
- `VBF_LLM_TEMPERATURE` (default: `0.2`)
- `VBF_LLM_CHAT_COMPLETIONS_PATH` (default: `/v1/chat/completions`)

### Method B: JSON Config File

Create `vbf/config/llm.json`:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "YOUR_KEY",
  "model": "gpt-4o-mini",
  "temperature": 0.2
}
```

---

## Usage

### Quick Start

```bash
# Method 1: Module invocation (no install needed)
python -m vbf --prompt "create a retro radio"

# Method 2: After installation
uv sync
vbf --prompt "create a retro radio"
```

### CLI Options

```bash
vbf --prompt "your prompt" \
    --host 127.0.0.1 \
    --port 8006 \
    --blender-path "C:/Program Files/Blender/blender.exe"
```

### As Python Module

```python
import asyncio
from vbf import VBFClient

async def main():
    client = VBFClient()
    await client.ensure_connected()
    await client.run_radio_task(prompt="复古收音机")

asyncio.run(main())
```

---

## Skill Categories (290+ Skills)

| Category | Skills | Coverage |
|----------|--------|----------|
| **Scene Management** | scene_clear, delete_object, rename_object, duplicate_object | ✅ Complete |
| **Primitives** | create_primitive (cube/cylinder/cone/sphere), create_beveled_box, create_nested_cones | ✅ Complete |
| **Geometry** | extrude_faces, inset_faces, subdivide_mesh, triangulate, bridge_edge_loops | ✅ Complete |
| **UV Operations** | unwrap_mesh, smart_project_uv, lightmap_pack, pack_uv_islands, mark_seam | ✅ Complete |
| **Materials** | create_material_simple, assign_material, create_shader_node_tree | ✅ Complete |
| **Textures** | import_image_texture, add_texture_to_material, set_texture_mapping | ✅ Complete |
| **Lighting** | create_light (4 types), set_light_properties, set_render_engine | ✅ Complete |
| **Camera** | create_camera, set_camera_active, camera_look_at, get_camera_info | ✅ Complete |
| **Animation** | insert_keyframe, set_frame_range, set_animation_fps, evaluate_fcurve | ✅ Complete |
| **Collections** | create_collection, link_to_collection, isolate_in_collection | ✅ Complete |
| **Constraints** | add_constraint_copy_location/rotation/scale, set_parent | ✅ Complete |
| **Curves/Text** | create_curve_bezier, create_text, set_font, text_to_curve | ✅ Complete |
| **Armature** | create_armature, add_bone, skin_to_armature, add_bone_constraint | ✅ Complete (NEW) |
| **Particles** | create_particle_system, set_particle_settings, hair_particles | ✅ Complete (NEW) |
| **Physics** | add_rigidbody, add_cloth, add_fluid, add_soft_body | ✅ Complete (NEW) |
| **Geometry Nodes** | create_geometry_node_tree, add_geometry_node, link_geometry_nodes | ✅ Complete (NEW) |
| **Sculpting** | sculpt_mask, sculpt_draw, sculpt_smooth, dynamic_topology | ✅ Complete (NEW) |
| **Rendering** | set_render_engine, set_render_resolution, render_frame | ✅ Complete (NEW) |
| **Compositor** | create_compositor_node_tree, add_compositor_node, link_compositor_nodes | ✅ Complete (NEW) |
| **Runtime Gateway** | py_get, py_set, py_call, ops_invoke, ops_introspect | ✅ Complete |

See [API Coverage Analysis](docs/API_COVERAGE_ANALYSIS.md) for full details.

---

## Modeling Workflow

VBF enforces a 9-stage modeling process:

```
discover → blockout → boolean → detail → bevel → normal_fix → accessories → material → finalize
```

### Stage Descriptions

| Stage | Description | Example Skills |
|-------|-------------|----------------|
| `discover` | Explore API, search operators | ops_search, ops_list |
| `blockout` | Basic shape blocking | create_primitive, apply_transform |
| `boolean` | Boolean operations | boolean_tool, join_objects |
| `detail` | Add details (buttons, holes) | extrude_faces, inset_faces |
| `bevel` | Bevel edges | add_modifier_bevel |
| `normal_fix` | Fix normals | recalculate_normals, shade_smooth |
| `accessories` | Accessories (wires, screws) | create_curve_bezier |
| `material` | Apply materials | create_material_simple, assign_material |
| `finalize` | Final cleanup | rename_object, create_collection |

---

## Plan Schema

### Skill Reference System

Skills can reference results from previous steps using `$ref`:

```json
{
  "steps": [
    {
      "step_id": "s1",
      "skill": "create_primitive",
      "args": {"primitive_type": "cube", "name": "main"}
    },
    {
      "step_id": "s2",
      "skill": "spatial_query",
      "args": {
        "object_name": {"$ref": "s1.data.object_name"},
        "query_type": "top_center"
      }
    }
  ]
}
```

### Control Fields

```json
{
  "controls": {
    "max_steps": 80,
    "allow_low_level_gateway": false,
    "require_ops_introspect_before_invoke": true
  },
  "steps": [...]
}
```

---

## Architecture

### Communication Flow

```
VBFClient (Python)
    ↓ WebSocket (JSON-RPC 2.0)
VBF WebSocket Server (Blender Addon)
    ↓
SKILL_REGISTRY
    ↓
bpy.ops / bpy.data (Blender API)
    ↓
Return {ok: true, data: {...}}
```

### Design Principles

1. **No Direct bmesh**: Skills wrap `bpy.ops`, not low-level mesh manipulation
2. **Atomic Operations**: Each skill does one thing
3. **Self-Validating**: Skills validate parameters and return structured errors
4. **Stage System**: Plans follow 9-stage workflow enforcement

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VBF_WS_HOST` | `127.0.0.1` | WebSocket server host |
| `VBF_WS_PORT` | `8006` | WebSocket server port |
| `BLENDER_PATH` | `blender` | Blender executable |
| `VBF_LLM_BASE_URL` | - | LLM API endpoint |
| `VBF_LLM_API_KEY` | - | LLM API key |
| `VBF_LLM_MODEL` | `gpt-4o-mini` | LLM model name |

---

## Development

### Running Tests

```bash
# Install dev dependencies
uv sync --group dev

# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_skill_schema_injection.py -v
```

### Adding New Skills

1. Create/edit skill module in `blender_provider/vbf_addon/skills_impl/`
2. Implement function: `def skill_name(**kwargs) -> Dict[str, Any]`
3. Register in `registry.py` SKILL_REGISTRY dict
4. Return `{"ok": True, ...}` or raise `fmt_err()`

Example:

```python
def create_cube(name: str, size: float = 1.0) -> Dict[str, Any]:
    try:
        bpy.ops.mesh.primitive_cube_add(size=size)
        obj = bpy.context.active_object
        obj.name = name
        return {"ok": True, "object_name": obj.name}
    except Exception as e:
        raise fmt_err("create_cube failed", e)
```

---

## Troubleshooting

### WebSocket Connection Failed

1. Verify Blender addon is running: N-panel → VBF → Status should show "Running"
2. Check host/port: `VBF_WS_HOST` and `VBF_WS_PORT` environment variables
3. Ensure no firewall blocking port 8006

### LLM Not Responding

1. Check `VBF_LLM_API_KEY` and `VBF_LLM_BASE_URL` are set
2. Test API connection: `curl $VBF_LLM_BASE_URL/models -H "Authorization: Bearer $VBF_LLM_API_KEY"`
3. Falls back to RadioTask demo if not configured

### Blender Python Dependencies

If `websockets` install fails:
```python
# In Blender Python Console:
import sys
print(sys.executable)  # Note this path
# Use this Python to install: /path/to/blender/python -m pip install websockets
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License - see [LICENSE](LICENSE) file.

---

## Links

- **Documentation**: [API Coverage Analysis](docs/API_COVERAGE_ANALYSIS.md)
- **Issues**: [GitHub Issues](https://github.com/yourusername/vibe-blender-flow/issues)
- **Chinese Version**: [中文文档](README_CN.md)
