# 更新日志 (Changelog)

本文件记录 Vibe-Blender-Flow 的各个版本更新内容。

遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范。

---

## [2.2.0] - 2026-04-13

### 新增 (Added)

#### 统一适配器架构 (v2)
- **统一 OpenAI 兼容适配器** (vbf/adapters/)
- base_adapter.py - 通用适配器基类，RPC技能加载
- openai_compat_adapter.py - 统一适配所有OpenAI兼容API
- 配置驱动，无硬编码模型分支
- 支持流式响应（可选）
- 工厂函数 get_adapter() 自动选择适配器

#### 支持的模型
- OpenAI: gpt-4, gpt-4o, gpt-3.5
- 中国模型: GLM-4, Kimi, Qwen, MiniMax
- 本地模型: Ollama（few-shot示例）
- 自定义端点（通过 vbf/config/llm_config.json 配置）

#### RPC技能同步
- 初始化时通过WebSocket RPC从Blender实时获取技能
- 批量获取技能定义（每批50个）
- 支持分离部署（客户端无需访问插件目录）

#### YouTube 技能扩展
- 分析 57 个 YouTube 教程视频
- 新增 69 个关键技能 (edge_crease, bevel_weight, uv_project_from_view 等)
- 补充 views3d 操作技能 (view3d_view_all, view3d_snap_cursor_to_center 等)
- 扩展修改器技能阵列 (add_modifier_array, add_modifier_solidify 等)
- 增强动画技能 (insert_keyframe_bone, bake_animation, NLA 等)
- 硬表面专用技能 (mark_edge_crease, set_edge_bevel_weight)

### 修复 (Fixed)

#### 技能文档同步
- **362 个技能** 完整同步 SKILL.md ↔ categories/*.md
- 修复 76 个丢失技能 (存在于 categories 但不在主文档)
- 修复 13 个技能的无参数表问题 (asset_list, compositor_list_nodes 等)

#### 架构 (Architecture)

#### 适配器架构 v2 改进
- **SkillRegistry 单例** (`skill_registry.py`) - 全局技能缓存
  - 技能加载后全局共享，多适配器实例复用
  - 线程安全的异步锁保护
  - 支持 force_refresh 强制刷新

- **响应格式配置化** - 响应路径从硬编码改为配置驱动
  - `response_content_path` 支持点号路径: `choices[0].message.content`
  - 每个模型可配置独立响应路径
  - 默认模型使用 `llm_config.json` 配置
  - **api_key 优先从配置读取** - 支持 `llm_config.json` 直接存储的 API Key
  - `response_format` 配置化支持 json_object

- **Streaming 支持完善** - `format_messages(stream=True)` 参数
  - 传递 stream 参数影响请求格式
  - 添加流式响应系统提示

#### 项目结构调整（Breaking）
- `vbf/adapters/` 从 `blender_provider` 移至项目根目录
- 适配器库独立于 Blender 插件，支持任意 Python 环境
- 新增 `_prompts/universal_system_prompt.md` 多模型系统提示词
- SKILL.md 从 299 行导航指南扩展为 362 技能完整定义文档

### 架构 (Architecture)

#### 适配器架构 v2 改进
- **SkillRegistry 单例** (`skill_registry.py`) - 全局技能缓存
- 技能加载后全局共享，多适配器实例复用
- 线程安全的异步锁保护，支持 force_refresh 强制刷新

- **响应格式配置化** - 响应路径从硬编码改为配置驱动
- `response_content_path` 支持点号路径: `choices[0].message.content`
- 每个模型可配置独立响应路径，默认模型使用 `llm_config.json`

- **OpenAICompatAdapter.call_llm()** - 统一 LLM 调用方法
- 整合 `build_api_request` + HTTP 调用 + `parse_response`
- 支持 TimeoutError / ConnectionError 区分（用于重试逻辑）

#### 适配器完全集成 (Migration)
- **client.py 完全迁移到 vbf/adapters/**
- `run_task()` → `_ensure_adapter()` + `_adapter_call()`
- `generate_skill_plan()` → `adapter.format_messages()` + `_adapter_call()`
- 移除 `build_skill_plan_messages()` / `build_skill_repair_messages()`
- 保留 `llm_rate_limiter`（速率限制）和 `llm_cache`（响应缓存）
- 移除 `llm_integration.py` 中的 plan 生成函数（由适配器接管）

### 文档 (Documentation)

- 新架构说明文档
- 29 个分类技能文档 (00_gateway～17_asset)
- INDEX.md 工作流索引

---

## [2.1.0] - 2026-04-12

### 新增 (Added)

#### 核心功能
- **18 阶段专业建模流程** - 重构 9 阶段为行业标准 18 阶段
  - Phase 1 (概念): reference_analysis → mood_board → style_definition
  - Phase 2 (粗模): primitive_blocking → silhouette_validation → proportion_check
  - Phase 3 (结构): topology_prep → edge_flow → boolean_operations
  - Phase 4 (细节): bevel_chamfer → micro_detailing → high_poly_finalize
  - Phase 5 (打磨): normal_baking → uv_prep → material_prep
  - Phase 6 (完成): material_assignment → lighting_check → finalize

- **用户反馈循环系统** (`feedback_loop.py`、`feedback_ui.py`)
  - 4 个关键检查点用户确认机制
  - 支持决策：继续/调整/重做/暂停任务
  - 可保存状态并恢复执行
  - 21 个专用测试覆盖

- **风格模板系统** (`style_templates.py`)
  - 预置 4 种建模风格：写实硬表面、低多边形、有机角色、工业道具
  - CLI 支持 `--style` 参数快速切换
  - 支持 `--list-styles` 查看可用风格
  - 用户可通过 JSON 配置自定义风格
  - 26 个专用测试覆盖

- **进度可视化系统** - 新增实时建模进度显示
  - 支持四种显示模式：console、rich、json、quiet
  - 实时进度条、阶段显示、时间估算
  - LLM 调用次数和内存使用监控
  
#### Phase 2 性能优化模块
- **内存管理器** (`memory_manager.py`)
  - 自动垃圾回收触发，防止 OOM
  - Step 结果历史大小限制（默认 100 条）
  - 内存阈值警告（默认 512MB）
  - 每 10 步自动 GC
  
- **LLM API 限流器** (`llm_rate_limiter.py`)
  - 并发调用数限制（默认 3）
  - 每分钟调用数限制（默认 20）
  - 指数退避重试机制（最多 3 次）
  - 配置项：`vbf/config/llm.json` → `llm_api_throttling`
  
- **LLM 响应缓存** (`llm_cache.py`)
  - 两级缓存：内存 LRU + 磁盘 JSON
  - SHA256 键值哈希，O(1) 查找
  - 模糊匹配相似提示（>0.9 相似度）
  - 默认 TTL 2 小时，最大 128 条内存缓存
  - 预期减少 50-80% 重复 API 调用
  
- **WebSocket 连接池** (`connection_pool.py`)
  - 2-8 个动态连接管理
  - 自动健康检查和重连（30 秒周期）
  - 最少负载优先调度
  - 批量调用 API `call_batch()`
  - 预期延迟降低 40%，吞吐量提升 3-5 倍

#### 四层闭环建模控制系统
- **第一层：断点续传**
  - 配置检查失败自动保存状态
  - `TaskInterruptedError` 支持恢复
  - `_create_interrupt()` 统一中断处理
  
- **第二层：增强错误恢复**
  - 物理回滚 `rollback_to_step()`
  - LLM 自动生成修复计划
  - 状态保留与重试机制
  
- **第三层：主动重规划**
  - `request_replan()` 支持从任意步骤重新开始
  - 场景状态反馈 LLM
  - 动态调整未执行计划
  
- **第四层：实时反馈**
  - `analyze_step_result()` 每步可选 LLM 分析
  - 场景状态增量捕获

### 优化 (Changed)

- **代码重构** - `client.py` 从 963 行优化至 445 行（-54%）
  - 移除 RadioTask 全部硬编码代码
  - 功能模块化至独立文件
  
- **内存优化** - `TaskState` 添加 `__slots__`
  - 减少实例内存开销 30%
  - `SceneState` 支持增量捕获和差异计算
  
- **WebSocket 连接** - 弃用 `asyncio.get_event_loop()`
  - 使用 `asyncio.get_running_loop()`（Python 3.10+ 兼容）
  
- **路径构造** - `llm_cache.py` 改进健壮性
  - 添加 `__file__` 不可用的回退机制
  
- **单例并发** - `llm_rate_limiter.py` 双检锁保护
  - 线程安全初始化，避免双重实例化

### 安全修复 (Security)

| 问题 | 严重性 | 文件 | 修复 |
|------|--------|------|------|
| asyncio 弃用 API | 低 | `connection_pool.py` | `get_event_loop()` → `get_running_loop()` |
| 路径构造健壮性 | 低 | `llm_cache.py` | 添加 `__file__` 回退到 `Path.cwd()` |
| 单例并发安全 | 低 | `llm_rate_limiter.py` | 添加 `threading.Lock` 双检锁 |

### 文档 (Documentation)

- 更新中英文 README
  - 添加代码演进历史（行数统计、技能增长）
  - 四层控制系统详细文档
  - 性能收益量化说明
  - 进度可视化使用指南

### 测试 (Tests)

- 新增测试文件
  - `tests/test_llm_cache.py` - 15 个缓存测试
  - `tests/test_llm_rate_limiter.py` - 速率限制测试
  - `tests/test_system.py` - 22 个系统集成测试
  
- 测试覆盖率：74 个测试，95.5% 通过率

---

## [2.0.0] - 2026-04-11

### 新增 (Added)

- **四层闭环建模控制系统** 完整实现
- **LLM 限流与缓存** 基础架构
- **WebSocket 连接池** 并发支持
- **进度可视化** 基础框架

### 移除 (Removed)

- **RadioTask 完全移除**
  - 删除 `_deterministic_radio_steps()`
  - 删除 `run_radio_task()`
  - 删除所有 "复古收音机" 相关代码
  - 纯 LLM 驱动建模工作流

### 变更 (Changed)

- 架构升级：四层控制系统（断点续传、错误恢复、主动重规划、实时反馈）
- 模块解耦：`llm_integration.py`、`plan_normalization.py`、`scene_state.py`

---

## [1.5.0] - 2026-04-08

### 新增 (Added)

- **物理回滚** `rollback_to_step()` - 支持撤销到指定步骤
- **LLM 修复计划** - 失败时自动生成修复步骤
- **任务续传** `--resume` 标志支持中断后恢复
- **290+ 技能** 覆盖 38 个领域模块

### 扩展 (Expanded)

- Blender 4.0/5.x 完整兼容
- EEVEE_NEXT 渲染引擎支持
- 新增模块：骨骼、资产、合成器、驱动器、几何节点、蜡笔、粒子、物理、雕刻、序列器、追踪

---

## [1.0.0] - 2026-04-01

### 初始发布 (Initial Release)

- **核心理念**：自然语言驱动 Blender 原子化建模
- **三大组件**：
  - Blender 插件端（290+ 技能）
  - Python 客户端（WebSocket JSON-RPC）
  - LLM 集成（Schema 感知计划生成）
- **18 阶段专业建模流程** (v2.0)
  - Phase 1 (概念): reference_analysis → mood_board → style_definition
  - Phase 2 (粗模): primitive_blocking → silhouette_validation → proportion_check
  - Phase 3 (结构): topology_prep → edge_flow → boolean_operations
  - Phase 4 (细节): bevel_chamfer → micro_detailing → high_poly_finalize
  - Phase 5 (打磨): normal_baking → uv_prep → material_prep
  - Phase 6 (完成): material_assignment → lighting_check → finalize
- **$ref 机制**：步骤间结果引用和传递
- **网关技能**：`py_get/py_set/py_call`、`ops_invoke/ops_introspect`

---

## 贡献指南

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

## 许可证

[MIT License](LICENSE)

Copyright (c) 2026 VBF Development Team
