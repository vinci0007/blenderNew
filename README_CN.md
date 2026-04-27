# Vibe-Blender-Flow (VBF)

面向 Blender 的自然语言建模系统，强调分阶段规划、基于 Schema 的技能执行，以及带反馈闭环的恢复机制。

**中文** | **[English](README.md)**

**[更新日志](CHANGELOG_CN.md)** | **[Changelog](CHANGELOG.md)**

[![License](https://img.shields.io/badge/License-TBD-lightgray.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-maintained-brightgreen.svg)]()
[![Stars](https://img.shields.io/github/stars/vinci-0007/vibe-blender-flow)](https://github.com/vinci-0007/vibe-blender-flow/stars)

## 示例

![LLM 创建手机模型](assets/llm_cellphone.gif)

## 项目概览

VBF 会把自然语言需求转换成可执行的 Blender 操作，核心分为三层：

1. Blender 插件暴露大量原子级建模技能。
2. Python 客户端通过 WebSocket JSON-RPC 与 Blender 通信，并负责状态、恢复、重试和日志。
3. OpenAI 兼容规划层把 Prompt 转成结构化技能计划，而不是直接生成不可控脚本。

这样做的好处是：执行链路可检查、可恢复、可重规划，也更容易定位问题。

## 最近更新

- 新增任务级短 ID，例如 `task_0426-151232_43b4d1a8`。
- 新增每任务 transcript 日志，控制台 stdout/stderr 会完整镜像到任务日志中。
- 新增按天滚动的纯文本运行事件日志，以及单独保存的任务结果 JSON。
- 新增场景隔离配置，默认不会把旧任务对象带入新任务的规划、反馈和重规划上下文。
- 新增 Analyzer 解析兜底，LLM 非严格 JSON 输出不再轻易误判成 `"good"`。
- 新增简单建模请求的几何优先策略，例如“制作一个沙发 3D 模型”默认优先停留在 geometry 阶段。
- 新增 `create_material_simple` 缺少 `base_color` 时的本地自动补全。
- 强化 Blender 诊断日志，包括 modifier 应用顺序和 `remove_doubles` 顶点合并统计。

## 当前架构

当前代码按领域拆分，而不是堆在扁平目录中：

- `vbf/app/`: CLI 入口与主编排客户端
- `vbf/adapters/`: 模型适配器与请求侧能力处理
- `vbf/llm/`: OpenAI 兼容配置、限流、缓存、规划辅助
- `vbf/feedback/`: 反馈捕获、校验、阶段分析与恢复控制
- `vbf/core/`: 任务状态、场景状态、计划归一化与协议辅助
- `vbf/runtime/`: 风格、日志、内存管理与进度辅助
- `vbf/transport/`: JSON-RPC WebSocket 传输与连接池
- `blender_provider/vbf_addon/`: Blender 插件与技能实现

更详细的模块说明见 [vbf/MODULE_LAYOUT.md](vbf/MODULE_LAYOUT.md)。

## 环境要求

- Python `>= 3.13`
- Blender `4.0+` 或 `5.x`
- 推荐使用 `uv` 进行依赖安装与测试

## 快速开始

### 1. 安装 Python 依赖

```bash
uv sync
```

### 2. 配置 LLM

参考 `vbf/config/config.toml.example` 创建本地运行配置 `vbf/config/config.toml`：

```toml
[project.paths]
cache_dir = "vbf/cache"
logs_dir = "vbf/logs"
task_state_file = "vbf/cache/task_state.json"
last_gen_fail_file = "vbf/cache/last_gen_fail.txt"
last_plan_fail_file = "vbf/cache/last_plan_fail.txt"
last_plan_raw_file = "vbf/cache/last_plan_raw.txt"
llm_cache_dir = "vbf/cache/llm_cache"

[project.scene]
task_scene_policy = "isolate"
include_environment_objects = true

[llm]
use_llm = true
base_url = "https://api.openai.com/v1"
api_key = "YOUR_API_KEY"
model = "gpt-4o-mini"
temperature = 0.2
planning_mode = "adaptive_staged"

[llm.planning_context]
compression_mode = "capability_coverage"
target_prompt_budget_chars = 18000

[llm.requirement_assessment]
mode = "auto"
enable_local_fallback = false
prefer_geometry_for_simple_model_requests = true

[llm.planning_capability_probe]
enabled = true
timeout_seconds = 20
cache_ttl_seconds = 3600

[llm.llm_api_throttling]
max_concurrent_calls = 3
max_calls_per_minute = 20
call_timeout_seconds = 600
```

完整带注释模板见 [vbf/config/config.toml.example](vbf/config/config.toml.example)。

### 3. 安装并启动 Blender 插件

1. 将 `blender_provider/vbf_addon/` 安装到 Blender，或打包后通过 Blender 插件方式安装。
2. 在 Blender Preferences 中启用 `Vibe-Blender-Flow (VBF)`。
3. 在插件面板中启动 VBF 服务。

当前本地启动器默认优先使用仓库内插件副本。如果你明确希望使用 Blender 里已安装的旧副本，可设置 `VBF_PREFER_INSTALLED_ADDON=1`。
如果你希望 VBF 自动以无界面模式拉起 Blender，请确保 Blender 已加入 `PATH`，或通过 `--blender-path` / `BLENDER_PATH` 指定可执行文件路径。

### 4. 运行任务

```bash
uv run python -m vbf --prompt "create a retro radio"
uv run python -m vbf --prompt-file assets/prompt_test.md
uv run python -m vbf --prompt "create a smartphone" --style hard_surface_realistic
```

### 5. 恢复中断任务

```bash
uv run python -m vbf --prompt "continue" --resume vbf/cache/task_state.json
```

## 当前规划流程

默认规划链路大致如下：

1. 先评估用户真正想交付到哪个阶段。
2. 选择几何、UV/材质、灯光、动画、渲染等阶段。
3. 按阶段所需能力压缩技能集，而不是简单做 top-k 裁剪。
4. 请求 LLM 生成结构化计划。
5. 按技能 Schema 做归一化和参数校验。
6. 执行时结合反馈捕获、局部重规划、任务恢复和任务级日志继续推进。

这条链路主要用来避免几类常见问题：

- 纯几何任务被误判成材质或渲染任务
- 上下文压缩时把关键建模技能裁掉
- 代理网关不支持 tools 或 JSON object 时直接失败
- LLM 输出参数名错误或缺少必要参数
- 旧场景遗留对象污染新任务语义

## OpenAI 兼容接口支持

VBF 当前通过一条统一的 OpenAI 兼容链路适配不同服务，常见包括：

- OpenAI
- GLM / BigModel
- Moonshot / Kimi
- DashScope / Qwen
- MiniMax
- Ollama
- 其他 OpenAI 兼容网关

可以在 `config.toml` 中通过 `base_url`、`chat_completions_path`、代理相关开关、额外请求头和能力探测等配置做细化适配。

## 运行时文件

运行期产物按用途拆分保存：

- `vbf/cache/`: 任务状态、计划快照、最近失败原始内容、LLM 磁盘缓存
- `vbf/logs/run_events_YYYYMMDD.log`: 按天汇总的纯文本事件日志，适合 grep、tail 和监控
- `vbf/logs/task_MMDD-HHMMSS_<id>.log`: 单任务 transcript 日志，完整镜像控制台输出
- `vbf/logs/task_result_task_MMDD-HHMMSS_<id>.json`: 单任务最终结构化结果快照

说明：

- 一个任务 ID 只在用户最初发起建模请求时创建一次，之后同一任务内的反馈、重规划和恢复都沿用这个 ID。
- 终端中的打印内容不会删减，同时会原样写入任务日志。
- 事件日志使用纯文本格式，便于日常观察和监控；最终完整结果仍保留为 JSON。

## 开发与测试

### 运行主测试集

```bash
uv run pytest tests/ -q
```

### 运行指定测试

```bash
uv run pytest tests/test_config_runtime.py tests/test_client_two_stage_planning.py -q
```

### 临时测试约定

- 稳定回归测试放在 `tests/`
- 一次性的调试脚本和临时测试放在 `tests/task_tmp/`
- 默认 pytest discovery 会忽略 `tests/task_tmp/`
- 需要运行临时测试时请显式指定，例如：

```bash
python -m pytest tests/task_tmp/test_example.py -q
```

## 常见问题

| 问题 | 建议检查项 |
|---|---|
| Blender 连接失败 | 确认插件已启动，且 WebSocket 端点可访问 |
| 自检显示运行中但任务仍卡住 | 重启插件，并确认 WebSocket + JSON-RPC 探测通过 |
| LLM 配置未生效 | 使用 `vbf/config/config.toml`，不要再用旧 JSON 配置 |
| 新任务总提到旧任务对象 | 保持 `[project.scene].task_scene_policy = "isolate"`，默认只把当前任务相关对象送入规划/反馈上下文 |
| 简单请求过早进入材质或渲染阶段 | 保持 `llm.requirement_assessment.prefer_geometry_for_simple_model_requests = true` |
| Analyzer 出现 `LLM parse error` | 先看 `vbf/cache/last_gen_fail.txt`；新版本会尽量从失败内容中恢复 `quality/reason/score/suggestions` |
| 重规划时报 `create_material_simple missing arg=base_color` | 新版本会自动补一个中性默认色；如果仍然硬失败，先升级到最新代码 |
| Blender 提示“应用的修改器不是第一个” | VBF 现在会先把目标 modifier 移到顶部再应用，并把重排信息写入日志 |
| `remove_doubles` 删除顶点过多 | 检查任务日志中的前后顶点数、删除数量和 large-merge warning，再决定是否继续 |
| 需要恢复失败任务 | 使用 `--resume vbf/cache/task_state.json` |

## 参考文档

- [CHANGELOG_CN.md](CHANGELOG_CN.md)
- [CHANGELOG.md](CHANGELOG.md)
- [vbf/MODULE_LAYOUT.md](vbf/MODULE_LAYOUT.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [blender_provider/vbf_addon/skills_docs/SKILL.md](blender_provider/vbf_addon/skills_docs/SKILL.md)

## 许可证

TBD，详见 [LICENSE](LICENSE)。
