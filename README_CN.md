# Vibe-Blender-Flow (VBF)

**自然语言驱动的 Blender 原子化建模系统**

[![许可证](https://img.shields.io/badge/许可证-MIT-blue.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

**中文版** | **[English](README.md)**

## 示例：制作手机

![LLM 创建手机模型](assets/llm_cellphone.gif)

---

## 概述

VBF 通过三个核心原则实现自然语言驱动的 Blender 建模：

1. **高级技能封装**：Blender 插件提供 290+ 原子技能（禁止直接操作 bmesh）
2. **JSON-RPC 协议**：Python 客户端通过 WebSocket 调用技能，自动错误恢复
3. **LLM 集成**：Schema 感知的规划避免参数幻觉

## 最新更新

**v2.0 - 重大更新 (2026-04-08):**
- **290+ 技能实现** 跨 38 个领域模块
- **完整 Blender 4.0/5.x 兼容**（EEVEE_NEXT 支持）
- **38 个新模块**：骨骼、资产、合成器、驱动器、几何节点、蜡笔、粒子、物理、雕刻、序列器、追踪等
- **生产就绪**：全面覆盖建模、UV、材质、动画、相机、灯光和约束

详见 [API 覆盖分析](docs/API_COVERAGE_ANALYSIS.md)。

---

## 仓库结构

```
/vbf                      主要 Python 包（VBFClient、CLI、LLM 集成）
  ├─ cli.py               CLI 入口：`vbf --prompt "..."`
  ├─ client.py            VBFClient 类
  ├─ jsonrpc_ws.py        WebSocket JSON-RPC 客户端
  ├─ llm_openai_compat.py LLM 集成（OpenAI 兼容 API）
  └─ vibe_protocol.py     带 $ref 支持的计划解析器

/blender_provider         Blender 插件源码
  └─ vbf_addon/           标准 Blender 插件（安装此目录）
      ├─ __init__.py      插件注册
      ├─ server.py        WebSocket 服务器（JSON-RPC 端点）
      └─ skills_impl/     290+ 技能实现
          ├─ registry.py  SKILL_REGISTRY 字典
          ├─ primitives.py, mesh_ops.py, uv_ops.py
          ├─ armature.py, particles.py, physics.py
          └─ [35 个模块...]

/client                   旧客户端（已弃用）
/reference                参考资料
```

---

## 系统要求

### 客户端
- Python >= 3.10
- 依赖：`websockets`

### Blender 端
- Blender 4.0+ 或 5.x
- Python `websockets` 包（安装在 Blender Python 中）：

```python
# 在 Blender Python 控制台：
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "websockets"])
```

---

## 安装

### Blender 插件安装

1. 将 `blender_provider/vbf_addon/` 复制到 Blender 插件目录：
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\4.x\scripts\addons\`
   - **Linux**: `~/.config/blender/4.x/scripts/addons/`
   - **macOS**: `~/Library/Application Support/Blender/4.x/scripts/addons/`

2. 启用插件：
   - 打开 Blender
   - 编辑 → 首选项 → 插件
   - 搜索 "Vibe-Blender-Flow (VBF)"
   - 启用插件

3. 启动服务器：
   - **方法 1**：N 面板 → VBF 标签 → Start 按钮
   - **方法 2**：Blender Python 控制台：`bpy.ops.vbf.serve()`

### 客户端安装

使用 `uv`（推荐）：
```bash
uv sync
```

使用 pip：
```bash
pip install websockets
```

---

## LLM 配置

VBF 支持 OpenAI 兼容 API。如未配置，自动退回到确定性 `RadioTask` 演示。

### 方法 A：环境变量（推荐）

```bash
export VBF_LLM_BASE_URL="https://api.openai.com/v1"
export VBF_LLM_API_KEY="your-key"
export VBF_LLM_MODEL="gpt-4o-mini"
```

可选：
- `VBF_LLM_TEMPERATURE`（默认：`0.2`）
- `VBF_LLM_CHAT_COMPLETIONS_PATH`（默认：`/v1/chat/completions`）

### 方法 B：JSON 配置文件

创建 `vbf/config/llm.json`：

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "YOUR_KEY",
  "model": "gpt-4o-mini",
  "temperature": 0.2
}
```

---

## 使用方法

### 快速开始

```bash
# 方法 1：模块调用（无需安装）
python -m vbf --prompt "制作一个复古收音机"

# 方法 2：安装后使用
uv sync
vbf --prompt "制作一个复古收音机"
```

### CLI 选项

```bash
vbf --prompt "你的提示词" \
    --host 127.0.0.1 \
    --port 8006 \
    --blender-path "C:/Program Files/Blender/blender.exe"
```

### 作为 Python 模块

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

## 技能分类（290+ 技能）

| 类别 | 技能 | 覆盖度 |
|------|------|--------|
| **场景管理** | scene_clear, delete_object, rename_object, duplicate_object | ✅ 完整 |
| **基础几何** | create_primitive (立方体/圆柱/圆锥/球体), create_beveled_box, create_nested_cones | ✅ 完整 |
| **几何操作** | extrude_faces, inset_faces, subdivide_mesh, triangulate, bridge_edge_loops | ✅ 完整 |
| **UV 操作** | unwrap_mesh, smart_project_uv, lightmap_pack, pack_uv_islands, mark_seam | ✅ 完整 |
| **材质** | create_material_simple, assign_material, create_shader_node_tree | ✅ 完整 |
| **纹理** | import_image_texture, add_texture_to_material, set_texture_mapping | ✅ 完整 |
| **灯光** | create_light (4 种类型), set_light_properties, set_render_engine | ✅ 完整 |
| **相机** | create_camera, set_camera_active, camera_look_at, get_camera_info | ✅ 完整 |
| **动画** | insert_keyframe, set_frame_range, set_animation_fps, evaluate_fcurve | ✅ 完整 |
| **集合** | create_collection, link_to_collection, isolate_in_collection | ✅ 完整 |
| **约束** | add_constraint_copy_location/rotation/scale, set_parent | ✅ 完整 |
| **曲线/文本** | create_curve_bezier, create_text, set_font, text_to_curve | ✅ 完整 |
| **骨骼** | create_armature, add_bone, skin_to_armature, add_bone_constraint | ✅ 完整（新增）|
| **粒子** | create_particle_system, set_particle_settings, hair_particles | ✅ 完整（新增）|
| **物理** | add_rigidbody, add_cloth, add_fluid, add_soft_body | ✅ 完整（新增）|
| **几何节点** | create_geometry_node_tree, add_geometry_node, link_geometry_nodes | ✅ 完整（新增）|
| **雕刻** | sculpt_mask, sculpt_draw, sculpt_smooth, dynamic_topology | ✅ 完整（新增）|
| **渲染** | set_render_engine, set_render_resolution, render_frame | ✅ 完整（新增）|
| **合成器** | create_compositor_node_tree, add_compositor_node, link_compositor_nodes | ✅ 完整（新增）|
| **运行时网关** | py_get, py_set, py_call, ops_invoke, ops_introspect | ✅ 完整 |

详见 [API 覆盖分析](docs/API_COVERAGE_ANALYSIS.md)。

---

## 建模工作流

VBF 强制执行 9 阶段建模流程：

```
探索 → 基础造型 → 布尔运算 → 细节建模 → 倒角 → 法线修复 → 配件 → 材质 → 收尾
```

### 阶段说明

| 阶段 | 描述 | 示例技能 |
|------|------|----------|
| `discover` | 探索 API、搜索操作符 | ops_search, ops_list |
| `blockout` | 基础造型确定 | create_primitive, apply_transform |
| `boolean` | 布尔运算 | boolean_tool, join_objects |
| `detail` | 添加细节（按钮、孔洞）| extrude_faces, inset_faces |
| `bevel` | 倒角处理 | add_modifier_bevel |
| `normal_fix` | 修复法线 | recalculate_normals, shade_smooth |
| `accessories` | 配件（线缆、螺丝）| create_curve_bezier |
| `material` | 应用材质 | create_material_simple, assign_material |
| `finalize` | 最终清理 | rename_object, create_collection |

---

## 计划 Schema

### 技能引用系统

技能可以使用 `$ref` 引用前序步骤的结果：

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

### 控制字段

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

## 架构

### 通信流程

```
VBFClient (Python)
    ↓ WebSocket (JSON-RPC 2.0)
VBF WebSocket 服务器 (Blender 插件)
    ↓
SKILL_REGISTRY
    ↓
bpy.ops / bpy.data (Blender API)
    ↓
返回 {ok: true, data: {...}}
```

### 设计原则

1. **禁止直接 bmesh**：技能封装 `bpy.ops`，不进行底层网格操作
2. **原子操作**：每个技能只做一件事
3. **自我验证**：技能验证参数并返回结构化错误
4. **阶段系统**：计划遵循 9 阶段工作流强制执行

---

## 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| `VBF_WS_HOST` | `127.0.0.1` | WebSocket 服务器主机 |
| `VBF_WS_PORT` | `8006` | WebSocket 服务器端口 |
| `BLENDER_PATH` | `blender` | Blender 可执行文件 |
| `VBF_LLM_BASE_URL` | - | LLM API 端点 |
| `VBF_LLM_API_KEY` | - | LLM API 密钥 |
| `VBF_LLM_MODEL` | `gpt-4o-mini` | LLM 模型名称 |

---

## 开发

### 运行测试

```bash
# 安装开发依赖
uv sync --group dev

# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_skill_schema_injection.py -v
```

### 添加新技能

1. 在 `blender_provider/vbf_addon/skills_impl/` 创建/编辑技能模块
2. 实现函数：`def skill_name(**kwargs) -> Dict[str, Any]`
3. 在 `registry.py` SKILL_REGISTRY 字典中注册
4. 返回 `{"ok": True, ...}` 或抛出 `fmt_err()`

示例：

```python
def create_cube(name: str, size: float = 1.0) -> Dict[str, Any]:
    try:
        bpy.ops.mesh.primitive_cube_add(size=size)
        obj = bpy.context.active_object
        obj.name = name
        return {"ok": True, "object_name": obj.name}
    except Exception as e:
        raise fmt_err("create_cube 失败", e)
```

---

## 故障排除

### WebSocket 连接失败

1. 验证 Blender 插件运行中：N 面板 → VBF → 状态应显示 "Running"
2. 检查主机/端口：`VBF_WS_HOST` 和 `VBF_WS_PORT` 环境变量
3. 确保防火墙未阻止端口 8006

### LLM 无响应

1. 检查 `VBF_LLM_API_KEY` 和 `VBF_LLM_BASE_URL` 已设置
2. 测试 API 连接：`curl $VBF_LLM_BASE_URL/models -H "Authorization: Bearer $VBF_LLM_API_KEY"`
3. 如未配置将退回到 RadioTask 演示

### Blender Python 依赖

如果 `websockets` 安装失败：
```python
# 在 Blender Python 控制台：
import sys
print(sys.executable)  # 记录此路径
# 使用此 Python 安装：/path/to/blender/python -m pip install websockets
```

---

## 贡献

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 链接

- **文档**：[API 覆盖分析](docs/API_COVERAGE_ANALYSIS.md)
- **问题**：[GitHub Issues](https://github.com/yourusername/vibe-blender-flow/issues)
- **English Version**: [English Documentation](README.md)