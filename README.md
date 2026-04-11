# Vibe-Blender-Flow (VBF)

**Natural-Language Driven Atomic Modeling System for Blender**

**[中文版](README_CN.md)** | **English**

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Stars](https://img.shields.io/github/stars/vinci-0007/vibe-blender-flow)](https://github.com/vinci-0007/vibe-blender-flow/stars)

## Example: Make a Cellphone

![LLM creates a cellphone model](assets/llm_cellphone.gif)

---

## Overview

VBF enables natural-language driven 3D modeling in Blender through three core principles:

1. **High-Level Skills**: Blender addon provides 253 atomic skills (no direct bmesh manipulation)
2. **JSON-RPC Protocol**: Python client calls skills via WebSocket with automatic error recovery
3. **LLM Integration**: Schema-aware planning prevents parameter hallucination

## What's New

**v2.0 - Major Update (2026-04-11):**
- **Code Refactoring**: Client module reduced from 963 to 442 lines (-54%)
- **Four-Layer Control System**: Checkpoint/Resume, Enhanced Recovery, Active Replanning, Real-time Feedback
- **Complete RadioTask Removal**: No hardcoded demo tasks, pure LLM-driven workflow
- **Scene State Capture**: Current scene context fed back to LLM for smart replanning

**v1.5 - Smart Recovery (2026-04-08):**
- **290+ Skills Implemented** across 38 domain modules
- **Physical Rollback**: `vbf.rollback_to_step()` for undo to specific step
- **LLM Repair Planning**: Automatically regenerate repair plans on failure
- **Task Resumption**: `--resume` flag for interrupted tasks

See [API Coverage Analysis](docs/API_COVERAGE_ANALYSIS.md) for detailed coverage metrics.

---

## Project Statistics

```
Code Evolution:
Initial    v1.0    v2.0
│          │       │
▼          ▼       ▼
===========================================
client.py │  ████████████████████ (963 lines)
          │  ██████████████       (442 lines)  -54% ↓
          │
Skills    │  ████████████████████████ (100+)
          │  ████████████████████████████████████████ (253 skills)  +153% ↑
          │
Tests     │  ████ (8)
          │  ██████████████████████ (38+)  +375% ↑
```

**Current Stats:**
- **Client Lines**: 442 (clean, maintainable)
- **Skills**: 253 across 38 categories
- **Test Coverage**: 38+ tests
- **Modules**: 9 core Python modules

---

## Repository Structure

```
/vbf                          Main Python package (442 lines)
├─ cli.py                     CLI entry: `vbf --prompt "..."`
├─ client.py                  VBFClient class (4-layer system)
├─ jsonrpc_ws.py              WebSocket JSON-RPC client
├─ llm_integration.py         LLM integration (new module)
├─ plan_normalization.py      Plan normalization (new module)
├─ scene_state.py             Scene capture for feedback (new)
├─ task_state.py              Checkpoint/Resume state
├─ llm_openai_compat.py       OpenAI-compatible API support
└─ vibe_protocol.py           Plan resolver with $ref

/blender_provider             Blender addon source
└─ vbf_addon/                 Standard Blender addon
   ├─ server.py                WebSocket server
   └─ skills_impl/             253 skill implementations
      ├─ registry.py            SKILL_REGISTRY
      └─ [38 domain modules...]

/tests/                       Test suite
├─ test_plan_normalization.py Plan normalization tests
├─ test_llm_integration.py    LLM integration tests
└─ [other tests...]
```

---

## Requirements

### Client Side
- Python >= 3.10
- Dependencies: `openai>=2.30.0`, `websockets`

### Blender Side
- Blender 4.0+ or 5.x
- Python `websockets` package:

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
   - N-panel → VBF tab → Start button
   - Or: `bpy.ops.vbf.serve()`

### Client Installation

Using `uv` (recommended):
```bash
uv sync
```

Using pip:
```bash
pip install openai>=2.30.0 websockets
```

---

## LLM Configuration

**⚠️ Important:** VBF requires an LLM to function. Configure one of the following:

### Method A: Environment Variables (Recommended)

```bash
export VBF_LLM_BASE_URL="https://api.openai.com/v1"
export VBF_LLM_API_KEY="your-key"
export VBF_LLM_MODEL="gpt-4o-mini"
```

**Optional:**
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

**Note:** If LLM is not configured, VBF will save a checkpoint and request configuration:
```
[VBF] LLM not configured. State saved to: vbf/config/task_state.json
[VBF] Resume: vbf --prompt "..." --resume "vbf/config/task_state.json"
```

---

## Usage

### Quick Start

```bash
# Basic usage
python -m vbf --prompt "create a retro radio"

# With resume support
python -m vbf --prompt "create a retro radio" --resume vbf/config/task_state.json

# After uv installation
uv sync
vbf --prompt "create a detailed car model"
```

### CLI Options

```bash
vbf --prompt "your prompt" \
    --host 127.0.0.1 \
    --port 8006 \
    --blender-path "C:/Program Files/Blender/blender.exe" \
    --resume "path/to/task_state.json"
```

### Python API

```python
import asyncio
from vbf import VBFClient

async def main():
    client = VBFClient()
    await client.ensure_connected()
    
    # Run task with automatic error recovery
    result = await client.run_task("create a detailed spaceship")
    
    # Or resume from checkpoint
    result = await client.run_task(
        "create a detailed spaceship",
        resume_state_path="vbf/config/task_state.json"
    )

asyncio.run(main())
```

---

## Four-Layer Control System (New in v2.0)

### Layer 1: Checkpoint/Resume
**Problem:** Connection failures or LLM interruptions during long-running tasks.

**Solution:** Automatic state saving on any failure.

```python
# Task automatically saves progress on failure
try:
    await client.run_task("complex model")
except TaskInterruptedError as e:
    print(f"Interrupted: {e}")
    print(f"Resume: --resume '{e.state_path}'")
```

### Layer 2: Enhanced Error Recovery
**Problem:** Skill execution fails mid-plan.

**Solution:** Physical rollback + LLM-generated repair plan.

```python
# On step failure:
# 1. Roll back to pre-failure state
await client.rollback_to_step("failed_step_id")
# 2. Generate repair plan with current scene context
repair_plan = await client.request_repair(...)
```

### Layer 3: Active Replanning
**Problem:** Plan wasn't optimal from the start.

**Solution:** Request new plan from any step.

```python
# Replan from current position
new_plan, new_steps = await client.request_replan(
    prompt="make it more detailed",
    from_step_id="step_5",
    current_plan=plan,
    step_results=results
)
```

### Layer 4: Real-time Feedback (Optional)
**Problem:** LLM can't see actual scene state.

**Solution:** Feed scene state back after each step.

```python
result = await client.run_task(
    "create a car",
    enable_step_feedback=True  # Optional per-step LLM analysis
)
```

---

## Skill Categories (253 Skills)

| Category | Skills | Coverage |
|----------|--------|----------|
| **Primitives** | create_primitive, create_beveled_box, create_nested_cones | ✅ Complete |
| **Geometry** | extrude_faces, inset_faces, subdivide_mesh, triangulate | ✅ Complete |
| **UV** | unwrap_mesh, smart_project_uv, pack_uv_islands, mark_seam | ✅ Complete |
| **Materials** | create_material_simple, assign_material, create_shader_node_tree | ✅ Complete |
| **Animation** | insert_keyframe, set_frame_range, set_animation_fps | ✅ Complete |
| **Armature** | create_armature, add_bone, skin_to_armature, constraints | ✅ Complete |
| **Particles** | create_particle_system, set_particle_settings | ✅ Complete |
| **Physics** | rigidbody_add, cloth_add, fluid_domain_create | ✅ Complete |
| **Geometry Nodes** | create_geometry_node_tree, add_geometry_node, link_nodes | ✅ Complete |
| **Sculpting** | sculpt_draw, sculpt_smooth, dyntopo_enabled | ✅ Complete |
| **Compositor** | create_compositor_tree, add_compositor_node | ✅ Complete |
| **Runtime Gateway** | py_get, py_set, py_call, ops_invoke, ops_introspect | ✅ Complete |

---

## Development

### Running Tests

```bash
# Install dev dependencies
uv sync --group dev

# Run all tests
uv run pytest

# Run specific test with verbose
uv run pytest tests/test_plan_normalization.py -v
```

### Code Statistics

```bash
# Check lines of code
wc -l vbf/*.py

# Current (v2.0):
# vbf/client.py:          442 lines (was 963, -54%)
# vbf/llm_integration.py: 279 lines (new)
# vbf/plan_normalization.py: 126 lines (new)
# vbf/scene_state.py:     130 lines (new)
```

---

## Troubleshooting

### WebSocket Connection Failed
1. Verify Blender addon is running: N-panel → VBF → Status "Running"
2. Check `VBF_WS_HOST` and `VBF_WS_PORT` variables
3. Ensure port 8006 is not blocked

### LLM Not Configured
- **Error:** "LLM not configured. State saved to task_state.json"
- **Solution:** Set environment variables or create `vbf/config/llm.json`
- Then resume: `--resume vbf/config/task_state.json`

### Resume from Checkpoint
```bash
# After interruption
vbf --prompt "continue previous task" --resume vbf/config/task_state.json
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
- **Issues**: [GitHub Issues](https://github.com/vinci-0007/vibe-blender-flow/issues)
- **Chinese Version**: [中文文档](README_CN.md)

---

**Made with ❤️ for the Blender community**
