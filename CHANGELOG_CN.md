# 更新日志

本项目采用 Keep a Changelog 风格维护版本记录。

这里优先记录对用户、架构和工作流有实际影响的变更，而不是逐条列出所有提交。

**中文** | **[English](CHANGELOG.md)**

## [2.3.2] - 2026-04-28

### 变更

- 调整默认 Prompt 风格行为，CLI/运行时默认不再自动追加 style 模板，只有用户显式传入 `--style` 时才应用风格。
- 调整 `auto` 模式下的需求评估，保持 LLM 判断优先；本地简单模型规则只作为辅助证据，不再直接覆盖 LLM 阶段结果。
- 明确 `uv_texture_material` 阶段契约，包含 UV、贴图、简单颜色分配、材质分配和 PBR/material preset。
- 调整反馈 Analyzer 触发频率，从每个计划小阶段切换改为按主要/adaptive 分析阶段触发。

### 修复

- 修复带有明确颜色/材质要求的简单资产请求被本地 simple-model guard 压成纯几何阶段的问题。
- 修复 Analyzer 遇到近似合法 JSON 时频繁进入解析兜底的问题，现在会先保守修复简单缺失闭合符，再回退到失败内容恢复。

### 文档

- 更新 README 和 README_CN，说明 LLM 优先需求评估、本地辅助证据、Analyzer 降频，以及扩展后的 `uv_texture_material` 阶段含义。
- 新增 Release Notes 和 GitHub Release 自动化，发布版本统一读取 `pyproject.toml`；版本号使用数字三段式 `x.x.x` 并支持每段多位数字，自动触发的 GitHub Release 仅限大版本/阶段版本 `x.y.0`，手动触发可发布任意项目 `x.x.x` 版本。

## [2.3.1] - 2026-04-27

### 新增

- 新增任务级短 ID，例如 `task_0426-151232_43b4d1a8`，用于标识一次新的建模请求。
- 新增每任务 transcript 日志，所有控制台 stdout/stderr 会同步写入 `vbf/logs/<task_id>.log`。
- 新增按天滚动的纯文本运行事件日志 `vbf/logs/run_events_YYYYMMDD.log`。
- 新增按任务保存的结构化结果快照 `vbf/logs/task_result_<task_id>.json`。
- 新增 `[project.scene]` 场景隔离配置，默认避免旧场景对象污染新任务。

### 变更

- 调整日志格式，监控日志以简短文本行为主，最终完整任务结果继续单独保存为 JSON。
- 调整任务日志策略，终端显示内容不删减，同时原样镜像到任务 transcript 日志。
- 调整规划、反馈和重规划使用的场景上下文，默认只使用当前任务相关对象，并可选保留相机和灯光。
- 调整简单资产请求的阶段判断，例如“制作一个沙发 3D 模型”默认优先停留在几何建模阶段，除非用户明确要求后续阶段。

### 修复

- 修复 Analyzer 严格 JSON 解析失败后的行为，尽量从失败内容中恢复 `quality`、`reason`、`score` 和 `suggestions`。
- 修复 Analyzer 解析失败时误判为 `"good"` 的问题，改为更保守的回退策略。
- 修复重规划中 `create_material_simple` 缺少 `base_color` 时直接失败的问题，现会自动补一个中性色默认值。
- 修复 modifier 应用顺序不稳定的问题，应用前会先把目标 modifier 移到顶部并写入日志。
- 修复 `remove_doubles` 可观测性不足的问题，现会记录前后顶点数、删除数量和大规模合并警告。
- 修复在当前 capture level 未包含顶点统计时，对 `create_beveled_box` 产生误报的几何告警。

### 文档

- 更新 README 和 README_CN，补充任务日志模型、场景隔离配置、Analyzer 兜底行为和 Blender 诊断日志说明。

## [2.3.0] - 2026-04-26

### 新增

- 新增基于 TOML 的运行时配置文件 `vbf/config/config.toml`
- 新增带注释的模板文件 `vbf/config/config.toml.example`
- 新增正式规划前的用户需求阶段评估
- 新增 `adaptive_staged` 作为主规划路径
- 新增面向阶段规划的能力覆盖式技能压缩
- 新增针对 OpenAI 兼容网关的规划能力探测
- 新增需求评估的本地兜底开关与相关控制项
- 新增配置/运行时测试用的工作区本地临时目录辅助逻辑，降低对系统临时目录的依赖
- 新增 `tests/task_tmp/conftest.py`，使显式执行的临时测试可以稳定导入仓库代码

### 变更

- 默认运行时配置文件由旧 JSON 切换为 TOML
- README 与 README_CN 已按当前架构、运行布局和规划流程重写
- 运行时产物统一整理到 `vbf/cache/` 与 `vbf/logs/`
- 规划阶段选择从单纯关键词判断，升级为结合需求评估来判断真实交付阶段
- 规划上下文压缩改为先保留必要能力，再按预算裁剪
- 本地 Blender 启动器默认优先使用仓库内插件副本
- 插件自检由仅检查 TCP 改为真实的 WebSocket + JSON-RPC 探测
- `tests/test_config_runtime.py` 改为使用工作区本地临时目录，不再依赖 pytest `tmp_path`
- 临时测试约定更新为：一次性测试放在 `tests/task_tmp/`，并显式运行

### 修复

- 修复 Blender 5.1 渲染调用兼容问题，对不支持的参数自动回退
- 修复纯几何任务会被风格文本、质量约束文本、泛化词汇误判阶段的问题
- 修复初始规划路径与压缩规划路径之间阶段推断不一致的问题
- 修复反馈捕获在对象尚未真正创建前就尝试读取该对象的问题
- 修复 `create_beveled_box` 的参数归一化，支持 `dimensions`、`width/height/depth`、`position` 等别名
- 修复原始体类型归一化，兼容 `UV-Sphere`、`uv_sphere`、`box` 等写法
- 修复 OpenAI 兼容配置加载对旧 JSON 配置文件名的显式拒绝逻辑
- 修复测试中 TOML 字符串生成与合法 TOML 约束不一致的问题
- 修复 `tests/task_tmp` 显式 pytest 收集时会被历史临时目录阻塞的问题

### 文档

- 重写英文 README，使其与当前架构和工作流一致
- 重写中文 README，移除陈旧内容并与当前项目状态对齐
- README 中所有配置说明从 JSON 更新为 TOML
- 更新 handoff / session 说明，使其反映 TOML 迁移和当前测试状态

### 测试

- 新增或更新以下回归覆盖：
  - 需求评估与阶段选择行为
  - stage intent 的置信度与保守策略
  - TOML 配置加载与旧文件拒绝逻辑
  - OpenAI 兼容网关请求头解析
  - 嵌套 TOML 限流配置加载
  - Blender 5.1 API 兼容性检查
