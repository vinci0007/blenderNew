# Vibe-Blender-Flow (VBF)

**自然语言驱动的 Blender 原子化建模系统**

**[中文版](README_CN.md)** | **[English](README.md)**

[![许可证](https://img.shields.io/badge/许可证-TBD-lightgray.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![测试](https://img.shields.io/badge/测试-162%20通过-brightgreen.svg)]()
[![Stars](https://img.shields.io/github/stars/vinci-0007/vibe-blender-flow)](https://github.com/vinci-0007/vibe-blender-flow/stars)

## 示例：制作手机

![LLM 创建手机模型](assets/llm_cellphone.gif)

---

## 概述

VBF 通过三个核心原则实现自然语言驱动的 Blender 建模：

1. **高级技能封装**：Blender 插件提供 362 个原子技能（禁止直接操作 bmesh）
2. **JSON-RPC 协议**：Python 客户端通过 WebSocket 调用技能，自动错误恢复
3. **LLM 集成**：Schema 感知的计划生成 + 渐进式技能披露，防止参数幻觉

## 最新更新

**v2.2.0 - 当前版本 (2026-04-13):**
- **统一适配器架构**：单一 `OpenAICompatAdapter` 通过配置处理所有 OpenAI 兼容 API
- **10 个支持模型**：OpenAI、GLM-4、Kimi、Qwen、MiniMax、Ollama 等
- **SkillRegistry 单例**：全局技能缓存，多适配器实例共享
- **362 个技能** 覆盖 48 个模块、17 个分类
- **162 个测试** 全部通过

**v2.1.0 (2026-04-12):**
- **18 阶段专业建模流程**：参考 → 粗模 → 结构 → 细节 → 打磨 → 完成
- **用户反馈循环**：4 个关键检查点（继续/调整/重做/暂停）
- **风格模板系统**：内置 4 种预设（写实硬表面、低多边形、有机角色、工业道具）
- **性能模块**：内存管理器、LLM 限流器、响应缓存、WebSocket 连接池
- **进度可视化**：Console/Rich/JSON/Quiet 模式，实时进度条

**v2.0 (2026-04-11):**
- **四层控制系统**：断点续传、增强错误恢复、主动重规划、实时反馈
- **RadioTask 完全移除**：纯 LLM 驱动，无硬编码演示任务
- **场景状态捕获**：将当前场景上下文反馈给 LLM，实现智能重规划

---

## 仓库结构

```
/vbf                      Python 主包
├─ adapters/              统一 LLM 适配器系统
│   ├─ __init__.py        工厂函数：get_adapter()，支持 10 个模型
│   ├─ base_adapter.py    VBFModelAdapter 基类
│   ├─ openai_compat_adapter.py  统一 OpenAI 兼容适配器
│   └─ skill_registry.py  SkillRegistry 单例（全局缓存）
├─ client.py              VBFClient（四层控制系统）
├─ config/llm_config.json LLM 配置
├─ llm_rate_limiter.py    速率限制（429 指数退避重试）
└─ ...

/blender_provider/vbf_addon/   Blender 插件
├─ server.py              WebSocket JSON-RPC 服务器（端口 8006）
├─ skills_impl/           362 个技能实现
│   ├─ registry.py        SKILL_REGISTRY 字典
│   └─ [48 个领域模块...]
└─ skills_docs/           完整技能文档

/tests/                   测试套件（162 个测试）
```

---

## 系统要求

- **客户端**：Python >= 3.10，`uv sync` 或 `pip install openai websockets`
- **Blender**：4.0+ / 5.x

---

## 快速开始

### Blender 插件
1. 将 `blender_provider/vbf_addon/` 复制到 Blender 插件目录
2. 在 编辑 → 偏好设置 → 插件 中启用 "Vibe-Blender-Flow (VBF)"
3. 启动服务器：N 面板 → VBF 标签 → Start

### 客户端
```bash
# 运行任务
uv run python -m vbf --prompt "create a retro radio"

# 使用风格预设
uv run python -m vbf --prompt "create a smartphone" --style hard_surface_realistic

# 从断点恢复
uv run python -m vbf --prompt "continue" --resume vbf/config/task_state.json
```

### Python API
```python
import asyncio
from vbf import VBFClient

async def main():
    client = VBFClient()
    await client.ensure_connected()

    # 运行任务（自动错误恢复）
    result = await client.run_task("create a detailed spaceship")

    # 从断点恢复
    result = await client.run_task(
        "create a detailed spaceship",
        resume_state_path="vbf/config/task_state.json"
    )

asyncio.run(main())
```

---

## 10 个支持的 LLM 模型

| 模型 | 供应商 | 配置示例 |
|------|--------|----------|
| GLM-4 | 智谱 BigModel | `https://open.bigmodel.cn/api/paas/v4` |
| Kimi | Moonshot | `https://api.moonshot.cn/v1` |
| Qwen | 阿里 DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| MiniMax | MiniMax | `https://api.minimax.chat/v1` |
| GPT-4 / GPT-4o | OpenAI | `https://api.openai.com/v1` |
| Ollama | 本地部署 | `http://localhost:11434/v1` |

---

## LLM 配置

创建 `vbf/config/llm_config.json`:

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

## 362 个技能（17 个分类）

| 分类 | 示例 |
|------|------|
| **网关** | py_get, py_set, py_call, ops_invoke |
| **几何体** | create_primitive, create_beveled_box |
| **几何操作** | extrude_faces, inset_faces, subdivide_mesh |
| **边控制** | mark_edge_crease, set_edge_bevel_weight |
| **UV** | unwrap_mesh, pack_uv_islands |
| **修改器** | add_modifier_array, add_modifier_solidify |
| **材质** | create_material_simple, create_shader_node_tree |
| **动画** | insert_keyframe, set_frame_range, bake_animation |
| **几何节点** | create_geometry_node_tree |
| **骨骼** | create_armature, add_bone, skin_to_armature |
| **灯光/物理** | light_add, rigidbody_add |

完整文档：[SKILL.md](blender_provider/vbf_addon/skills_docs/SKILL.md)

---

## 开发

```bash
# 运行测试（必须指定 tests/ 目录）
uv run pytest tests/

# 详细模式
uv run pytest tests/ -v
```

---

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| WS 连接失败 | 验证 Blender 插件运行中（N 面板 → VBF → 状态 "Running"） |
| LLM 未配置 | 编辑 `vbf/config/llm_config.json` 填入 API 凭证 |
| 429 速率限制 | 自动指数退避重试 |
| 从断点恢复 | `vbf --prompt "..." --resume vbf/config/task_state.json` |

---

## 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

---

## 贡献者

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 许可证

TBD - 详见 [LICENSE](LICENSE) 文件。

---

## 代码频率

[![提交活动](https://github-readme-activity-graph.vercel.app/graph?username=vinci0007&repo=vibe-blender-flow&theme=github-dark&bg_color=1a1b26&color=7aa2f7&line=7aa2f7&point=7aa2f7&area=true&hide_border=false)](https://github.com/vinci0007/vibe-blender-flow/graphs/code-frequency)

*提交活动和代码变更：[查看完整图表](https://github.com/vinci0007/vibe-blender-flow/graphs/code-frequency)*

---

**为 Blender 社区制造 ❤️**