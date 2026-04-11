# Vibe-Blender-Flow (VBF)【正在更新中……】

**自然语言驱动的 Blender 原子化建模系统**

**中文版** | **[English](README.md)**

[![许可证](https://img.shields.io/badge/许可证-MIT-blue.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Stars](https://img.shields.io/github/stars/vinci-0007/vibe-blender-flow)](https://github.com/vinci-0007/vibe-blender-flow/stars)

## 示例：制作手机

![LLM 创建手机模型](assets/llm_cellphone.gif)

---

## 概述

VBF 通过三个核心原则实现自然语言驱动的 Blender 建模：

1. **高级技能封装**：Blender 插件提供 253 个原子技能（禁止直接操作 bmesh）
2. **JSON-RPC 协议**：Python 客户端通过 WebSocket 调用技能，自动错误恢复
3. **LLM 集成**：Schema 感知的计划避免参数幻觉

## 最新更新

**v2.0 - 重大更新 (2026-04-11):**
- **代码重构**：客户端模块从 963 行减少至 442 行（-54%）
- **四层控制系统**：断点续传、增强错误恢复、主动重规划、实时反馈
- **完全移除 RadioTask**：无硬编码演示任务，纯 LLM 驱动工作流
- **场景状态捕获**：将当前场景上下文反馈给 LLM，实现智能重规划

**v1.5 - 智能恢复 (2026-04-08):**
- **290+ 技能实现**：涵盖 38 个领域模块
- **物理回滚**：`vbf.rollback_to_step()` 支持撤销到指定步骤
- **LLM 修复计划**：失败时自动生成修复计划
- **任务续传**：`--resume` 标志支持中断任务恢复

---

## 项目统计

```
代码演进:
初始版本   v1.0     v2.0
│         │        │
▼         ▼        ▼
===========================================
client.py │  ████████████████████ (963 行)
          │  ██████████████       (442 行)  -54% ↓
          │
技能      │  ████████████████████████ (100+)
          │  ████████████████████████████████████████ (253 项)  +153% ↑
          │
测试      │  ████ (8 个)
          │  ██████████████████████ (38+ 个)  +375% ↑
```

**当前统计：**
- **客户端代码**：442 行（简洁、可维护）
- **技能数量**：253 项，覆盖 38 个类别
- **测试覆盖**：38+ 个测试
- **核心模块**：9 个 Python 模块

---

## 仓库结构

```
/vbf                          主 Python 包（442 行）
├─ cli.py                     CLI 入口: `vbf --prompt "..."`
├─ client.py                  VBFClient 类（四层系统）
├─ jsonrpc_ws.py              WebSocket JSON-RPC 客户端
├─ llm_integration.py         LLM 集成（新模块）
├─ plan_normalization.py      计划归一化（新模块）
├─ scene_state.py             场景反馈捕获（新模块）
├─ task_state.py              断点续传状态
├─ llm_openai_compat.py       OpenAI 兼容 API 支持
└─ vibe_protocol.py           带 $ref 的计划解析器

/blender_provider             Blender 插件源码
└─ vbf_addon/                 标准 Blender 插件
   ├─ server.py               WebSocket 服务器
   └─ skills_impl/             253 个技能实现
      ├─ registry.py          SKILL_REGISTRY
      └─ [38 个领域模块...]

/tests/                       测试套件
├─ test_plan_normalization.py 计划归一化测试
├─ test_llm_integration.py    LLM 集成测试
└─ [其他测试...]
```

---

## 系统要求

### 客户端
- Python >= 3.10
- 依赖：`openai>=2.30.0`, `websockets`

### Blender 端
- Blender 4.0+ 或 5.x
- Python `websockets` 包：

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
   - N 面板 → VBF 标签 → Start 按钮
   - 或：`bpy.ops.vbf.serve()`

### 客户端安装

使用 `uv`（推荐）：
```bash
uv sync
```

使用 pip：
```bash
pip install openai>=2.30.0 websockets
```

---

## LLM 配置

**⚠️ 重要：** VBF 需要配置 LLM 才能运行。选择以下方式之一：

### 方式 A：环境变量（推荐）

```bash
export VBF_LLM_BASE_URL="https://api.openai.com/v1"
export VBF_LLM_API_KEY="your-key"
export VBF_LLM_MODEL="gpt-4o-mini"
```

**可选：**
- `VBF_LLM_TEMPERATURE`（默认：`0.2`）
- `VBF_LLM_CHAT_COMPLETIONS_PATH`（默认：`/v1/chat/completions`）

### 方式 B：JSON 配置文件

创建 `vbf/config/llm.json`：

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "YOUR_KEY",
  "model": "gpt-4o-mini",
  "temperature": 0.2
}
```

**注意：** 如果 LLM 未配置，VBF 会保存检查点并请求配置：
```
[VBF] LLM 未配置。状态已保存至：vbf/config/task_state.json
[VBF] 恢复：vbf --prompt "..." --resume "vbf/config/task_state.json"
```

---

## 使用方法

### 快速开始

```bash
# 基本用法
python -m vbf --prompt "制作一个复古收音机"

# 支持断点续传
python -m vbf --prompt "制作一个复古收音机" --resume vbf/config/task_state.json

# uv 安装后
uv sync
vbf --prompt "制作一个详细的汽车模型"
```

### CLI 选项

```bash
vbf --prompt "你的提示词" \
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
    
    # 运行任务（自动错误恢复）
    result = await client.run_task("制作一艘详细的空间站")
    
    # 或从检查点恢复
    result = await client.run_task(
        "制作一艘详细的空间站",
        resume_state_path="vbf/config/task_state.json"
    )

asyncio.run(main())
```

---

## 四层控制系统（v2.0 新增）

### 层1：断点续传
**问题：** 长时间运行任务期间连接失败或 LLM 中断。

**解决方案：** 任何失败自动保存状态。

```python
# 任务失败自动保存进度
try:
    await client.run_task("复杂模型")
except TaskInterruptedError as e:
    print(f"中断: {e}")
    print(f"恢复: --resume '{e.state_path}'")
```

### 层2：增强错误恢复
**问题：** 技能执行中途失败。

**解决方案：** 物理回滚 + LLM 生成修复计划。

```python
# 步骤失败时：
# 1. 回滚到失败前状态
await client.rollback_to_step("failed_step_id")
# 2. 基于当前场景生成修复计划
repair_plan = await client.request_repair(...)
```

### 层3：主动重规划
**问题：** 计划从开始就未达最佳。

**解决方案：** 从任何步骤请求新计划。

```python
# 从当前位置重新规划
new_plan, new_steps = await client.request_replan(
    prompt="让它更详细",
    from_step_id="step_5",
    current_plan=plan,
    step_results=results
)
```

### 层4：实时反馈（可选）
**问题：** LLM 无法看到实际场景状态。

**解决方案：** 每步后将场景状态反馈给LLM。

```python
result = await client.run_task(
    "制作一辆汽车",
    enable_step_feedback=True  # 可选的每步 LLM 分析
)
```

---

## 技能分类（253 项技能）

| 类别 | 技能 | 覆盖度 |
|------|------|--------|
| **基础几何** | create_primitive, create_beveled_box, create_nested_cones | ✅ 完整 |
| **几何操作** | extrude_faces, inset_faces, subdivide_mesh, triangulate | ✅ 完整 |
| **UV 操作** | unwrap_mesh, smart_project_uv, pack_uv_islands, mark_seam | ✅ 完整 |
| **材质** | create_material_simple, assign_material, create_shader_node_tree | ✅ 完整 |
| **动画** | insert_keyframe, set_frame_range, set_animation_fps | ✅ 完整 |
| **骨骼** | create_armature, add_bone, skin_to_armature, constraints | ✅ 完整 |
| **粒子** | create_particle_system, set_particle_settings | ✅ 完整 |
| **物理** | rigidbody_add, cloth_add, fluid_domain_create | ✅ 完整 |
| **几何节点** | create_geometry_node_tree, add_geometry_node, link_nodes | ✅ 完整 |
| **雕刻** | sculpt_draw, sculpt_smooth, dyntopo_enabled | ✅ 完整 |
| **合成器** | create_compositor_tree, add_compositor_node | ✅ 完整 |
| **运行时网关** | py_get, py_set, py_call, ops_invoke, ops_introspect | ✅ 完整 |

---

## 开发

### 运行测试

```bash
# 安装开发依赖
uv sync --group dev

# 运行所有测试
uv run pytest

# 运行特定测试（详细模式）
uv run pytest tests/test_plan_normalization.py -v
```

### 代码统计

```bash
# 查看代码行数
wc -l vbf/*.py

# 当前 (v2.0):
# vbf/client.py:          442 行 (原为 963, -54%)
# vbf/llm_integration.py: 279 行 (新)
# vbf/plan_normalization.py: 126 行 (新)
# vbf/scene_state.py:     130 行 (新)
```

---

## 故障排除

### WebSocket 连接失败
1. 验证 Blender 插件运行中：N 面板 → VBF → 状态 "Running"
2. 检查 `VBF_WS_HOST` 和 `VBF_WS_PORT` 变量
3. 确保端口 8006 未被阻塞

### LLM 未配置
- **错误：** "LLM 未配置。状态已保存到 task_state.json"
- **解决方案：** 设置环境变量或创建 `vbf/config/llm.json`
- 然后恢复：`--resume vbf/config/task_state.json`

### 从检查点恢复
```bash
# 中断后恢复
vbf --prompt "继续之前的任务" --resume vbf/config/task_state.json
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
- **议题**：[GitHub Issues](https://github.com/vinci-0007/vibe-blender-flow/issues)
- **英文版**：[English Documentation](README.md)

---

**为 Blender 社区制造 ❤️**
