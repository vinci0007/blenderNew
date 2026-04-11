# 更新日志 (Changelog)

本文件记录 Vibe-Blender-Flow 的各个版本更新内容。

遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 规范。

---

## [2.1.0] - 2026-04-12

### 新增 (Added)

#### 核心功能
- **进度可视化系统** - 新增实时建模进度显示
  - 支持四种显示模式：console、rich、json、quiet
  - 实时进度条、阶段显示、时间估算
  - LLM 调用次数和内存使用监控
  - 九个建模阶段（discover → finalize）可视化追踪
  
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
- **9 阶段建模流程**：discover → blockout → boolean → detail → bevel → normal_fix → accessories → material → finalize
- **$ref 机制**：步骤间结果引用和传递
- **网关技能**：`py_get/py_set/py_call`、`ops_invoke/ops_introspect`

---

## 贡献指南

详见 [CONTRIBUTING.md](CONTRIBUTING.md)

## 许可证

[MIT License](LICENSE)

Copyright (c) 2026 VBF Development Team
