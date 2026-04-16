# Vibe-Blender-Flow (VBF)

**Natural-Language Driven Atomic Modeling System for Blender**

**[中文版](README_CN.md)** | **English**

[![License](https://img.shields.io/badge/License-TBD-lightgray.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-162%20passed-brightgreen.svg)]()
[![Stars](https://img.shields.io/github/stars/vinci-0007/vibe-blender-flow)](https://github.com/vinci-0007/vibe-blender-flow/stars)

## Example: Make a Cellphone

![LLM creates a cellphone model](assets/llm_cellphone.gif)

---

## Overview

VBF enables natural-language driven 3D modeling in Blender through three core principles:

1. **High-Level Skills**: Blender addon provides 362 atomic skills (no direct bmesh manipulation)
2. **JSON-RPC Protocol**: Python client calls skills via WebSocket with automatic error recovery
3. **LLM Integration**: Schema-aware planning with progressive disclosure prevents parameter hallucination

## What's New

**v2.2.0 - Current (2026-04-13):**
- **Unified Adapter Architecture**: Single `OpenAICompatAdapter` handles all OpenAI-compatible APIs via config
- **10 Supported Models**: OpenAI, GLM-4, Kimi, Qwen, MiniMax, Ollama, and more
- **SkillRegistry Singleton**: Global skill caching, shared across all adapter instances
- **362 Skills** across 48 modules, 17 categories
- **162 Tests** all passing

**v2.1.0 (2026-04-12):**
- **18-Phase Professional Modeling Workflow**: Reference → Blockout → Structure → Detail → Polish → Finalize
- **User Feedback Loop**: 4 key checkpoints for human confirmation (continue/adjust/redo/pause)
- **Style Templates**: Built-in presets (Realistic Hard-Surface, Low-Poly, Organic Character, Industrial Prop)
- **Performance Modules**: Memory manager, LLM rate limiter, response cache, WebSocket connection pool
- **Progress Visualization**: Console/Rich/JSON/Quiet modes with real-time progress bars

**v2.0 (2026-04-11):**
- **Four-Layer Control System**: Checkpoint/Resume, Enhanced Recovery, Active Replanning, Real-time Feedback
- **Complete RadioTask Removal**: Pure LLM-driven workflow, no hardcoded demo tasks
- **Scene State Capture**: Current scene context fed back to LLM for smart replanning

---

## Repository Structure

```
/vbf                      Main Python package
├─ adapters/              Unified LLM adapter system
│   ├─ __init__.py        Factory: get_adapter(), 10 supported models
│   ├─ base_adapter.py    VBFModelAdapter base class
│   ├─ openai_compat_adapter.py  Unified OpenAI-compatible adapter
│   └─ skill_registry.py  SkillRegistry singleton (global cache)
├─ client.py              VBFClient (4-layer control system)
├─ config/llm_config.json LLM configuration
├─ llm_rate_limiter.py    Rate limiting with 429 exponential backoff
└─ ...

/blender_provider/vbf_addon/   Blender addon
├─ server.py              WebSocket JSON-RPC server (port 8006)
├─ skills_impl/           362 skill implementations
│   ├─ registry.py        SKILL_REGISTRY dict
│   └─ [48 domain modules...]
└─ skills_docs/           Full skill documentation

/tests/                   Test suite (162 tests)
```

---

## Requirements

- **Client**: Python >= 3.10, `uv sync` or `pip install openai websockets`
- **Blender**: 4.0+ / 5.x

---

## Quick Start

### Blender Addon
1. Copy `blender_provider/vbf_addon/` to Blender addons directory
2. Enable "Vibe-Blender-Flow (VBF)" in Edit → Preferences → Add-ons
3. Start server: N-panel → VBF tab → Start

### Client
```bash
# Run task
uv run python -m vbf --prompt "create a retro radio"

# With style
uv run python -m vbf --prompt "create a smartphone" --style hard_surface_realistic

# Resume
uv run python -m vbf --prompt "continue" --resume vbf/config/task_state.json
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

    # Resume from checkpoint
    result = await client.run_task(
        "create a detailed spaceship",
        resume_state_path="vbf/config/task_state.json"
    )

asyncio.run(main())
```

---

## 10 Supported LLM Models

| Model | Provider | Config Example |
|-------|----------|----------------|
| GLM-4 | 智谱 BigModel | `https://open.bigmodel.cn/api/paas/v4` |
| Kimi | Moonshot | `https://api.moonshot.cn/v1` |
| Qwen | 阿里 DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| MiniMax | MiniMax | `https://api.minimax.chat/v1` |
| GPT-4 / GPT-4o | OpenAI | `https://api.openai.com/v1` |
| Ollama | Local | `http://localhost:11434/v1` |

---

## LLM Configuration

Create `vbf/config/llm_config.json`:

```json
{
  "use_llm": true,
  "base_url": "https://open.bigmodel.cn/api/paas/v4",
  "api_key": "YOUR_KEY",
  "model": "glm-4.7-flash",
  "temperature": 0.2,
  "llm_api_throttling": {
    "max_concurrent_calls": 1,
    "max_calls_per_minute": 20,
    "call_timeout_seconds": 120,
    "retry_on_failure": { "max_attempts": 3 }
  }
}
```

---

## 362 Skills (17 Categories)

| Category | Examples |
|----------|----------|
| **Gateway** | py_get, py_set, py_call, ops_invoke |
| **Primitives** | create_primitive, create_beveled_box |
| **Geometry** | extrude_faces, inset_faces, subdivide_mesh |
| **Edge Control** | mark_edge_crease, set_edge_bevel_weight |
| **UV** | unwrap_mesh, pack_uv_islands |
| **Modifiers** | add_modifier_array, add_modifier_solidify |
| **Materials** | create_material_simple, create_shader_node_tree |
| **Animation** | insert_keyframe, set_frame_range, bake_animation |
| **Geometry Nodes** | create_geometry_node_tree |
| **Armature** | create_armature, add_bone, skin_to_armature |
| **Lighting/Physics** | light_add, rigidbody_add |

Full docs: [SKILL.md](blender_provider/vbf_addon/skills_docs/SKILL.md)

---

## Development

```bash
# Run tests (MUST specify tests/ directory)
uv run pytest tests/

# Verbose mode
uv run pytest tests/ -v
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| WS connection failed | Verify Blender addon running (N-panel → VBF → Status "Running") |
| LLM not configured | Edit `vbf/config/llm_config.json` with API credentials |
| 429 Rate limit | Auto-retries with exponential backoff |
| Resume task | `vbf --prompt "..." --resume vbf/config/task_state.json` |

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## Contributors

See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## License

TBD - See [LICENSE](LICENSE) file.

---

## Code Frequency

[![Contribution Activity](https://github-readme-activity-graph.vercel.app/graph?username=vinci0007&repo=vibe-blender-flow&theme=github-dark&bg_color=1a1b26&color=7aa2f7&line=7aa2f7&point=7aa2f7&area=true&hide_border=false)](https://github.com/vinci0007/vibe-blender-flow/graphs/code-frequency)

*Commit activity and code changes: [View full graphs](https://github.com/vinci0007/vibe-blender-flow/graphs/code-frequency)*

---

**Made with ❤️ for the Blender community**