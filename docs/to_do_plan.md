# VBF 建模流程改进计划

**创建时间**: 2026-04-12
**分析来源**: 基于 Blender 专业建模流程知识
**状态**: 待实施

---

## 问题总结

当前 VBF 9 阶段建模流程存在的三大核心问题：

1. **阶段定义与专业流程不符** - 术语非标准，顺序可优化
2. **缺少用户反馈循环** - 当前为"一次性"生成模式
3. **缺少图像输入支持** - 无法分析用户提供的参考图

---

## 实施计划

### 实施 A: 重构 Stage 流程 (P0 - 高优先级)

**目标**: 将 9 阶段扩展为标准专业建模流程

**预计工期**: 2-4 小时

**文件修改**:
- `vbf/client.py` - 修改 `stage_order` 定义
- `vbf/llm_integration.py` - 更新 LLM Prompt schema
- `blender_provider/SKILL.md` - 更新文档

**具体改动**:

```python
# 当前 (vbf/client.py:126-134)
stage_order = {
    "discover": 0,
    "blockout": 1,
    "boolean": 2,
    "detail": 3,
    "bevel": 4,
    "normal_fix": 5,
    "accessories": 6,
    "material": 7,
    "finalize": 8,
}

# 重构为专业流程
PROFESSIONAL_STAGE_ORDER = {
    # Phase 1: Concept
    "reference_analysis": 0,    # 分析用户输入（原 discover）
    "mood_board": 1,            # NEW: 情绪板创建
    "style_definition": 2,      # NEW: 风格确立
    
    # Phase 2: Blocking
    "primitive_blocking": 3,    # 粗块创建（原 blockout）
    "silhouette_validation": 4, # NEW: 轮廓验证
    "proportion_check": 5,      # NEW: 比例确认
    
    # Phase 3: Structure
    "topology_prep": 6,         # NEW: 拓扑准备
    "edge_flow": 7,             # NEW: 边流控制
    "boolean_operations": 8,    # Boolean切割（保留）
    
    # Phase 4: Detail
    "bevel_chamfer": 9,         # 倒角（先于细节）
    "micro_detailing": 10,      # 微观细节（原 detail）
    "high_poly_finalize": 11,   # NEW: 高模最终化
    
    # Phase 5: Polish
    "normal_baking": 12,        # 标准术语（原 normal_fix）
    "uv_prep": 13,              # NEW: UV准备
    "material_prep": 14,        # 材质准备（原 accessories 重命名）
    
    # Phase 6: Finish
    "material_assignment": 15,  # 材质分配（原 material）
    "lighting_check": 16,       # NEW: 灯光预览
    "finalize": 17              # 最终导出（保留）
}
```

**验收标准**:
- [ ] stage_order 更新为专业术语
- [ ] 所有测试通过 (tests/test_stage_system.py)
- [ ] LLM Prompt schema 更新（9阶段 → 18阶段）
- [ ] 文档 README.md 更新

---

### 实施 B: 增加用户反馈循环 (P0 - 高优先级)

**目标**: 在关键节点提供中途预览和用户确认

**预计工期**: 4-6 小时

**新增模块**:
- `vbf/feedback_loop.py` - 反馈循环控制器
- `vbf/feedback_ui.py` - 预览和交互界面

**关键节点**:
```python
FEEDBACK_CHECKPOINTS = [
    ("after_silhouette", 20),      # 轮廓确认
    ("after_blocking", 35),        # 比例确认
    ("after_bevel", 60),             # 细节程度确认
    ("before_material", 85),        # 最终高模确认
]
```

**接口设计**:
```python
class UIModelingFeedback:
    async def checkpoint(
        self,
        stage: str,
        current_progress: float,
        preview_path: str
    ) -> UserFeedback:
        """在特定 stage 暂停，等待用户确认"""
        pass
```

**验收标准**:
- [ ] 4个关键反馈节点实现
- [ ] 预览截图自动生成
- [ ] 用户可选项：[继续, 调整, 重做, 停止]
- [ ] 中断后可恢复机制

---

### 实施 C: 集成图像分析能力 (P1 - 中优先级)

**目标**: 支持用户上传参考图，LLM 分析后生成建模计划

**预计工期**: 3-5 小时

**新增模块**:
- `vbf/image_analyzer.py` - 图像分析器
- `vbf/vlm_adapter.py` - VLM 接入层

**VLM 选型** (可选):
- GPT-4V (OpenAI)
- Claude 3 Vision (Anthropic)
- Gemini Pro Vision (Google)
- 本地模型 (LLaVA 等，需 GPU)

**功能实现**:
```python
class ReferenceImageAnalyzer:
    async def analyze(self, image_path: str) -> ImageAnalysisResult:
        """分析参考图，返回建模指导"""
        return {
            "object_type": "硬表面/角色/有机",
            "dominant_shapes": ["立方体", "圆柱", "圆环"],
            "estimated_dimensions": {"height": 2.0, "width": 1.5, "depth": 1.0},
            "key_features": ["尖锐边缘", "圆角过渡", "表面按钮"],
            "style_hints": "写实/风格化/低多边形",
            "complexity_level": "简单/中等/复杂"
        }
```

**CLI 更新**:
```bash
# 新选项
vbf --prompt "create a retro radio" --reference-image "./radio_sketch.jpg"
```

**验收标准**:
- [ ] 支持常见图片格式 (PNG/JPG/WebP)
- [ ] 图像分析结果用于生成第一阶段 plan
- [ ] CLI 支持 --reference-image 参数
- [ ] 文档更新

---

### 实施 D: 风格模板系统 (P2 - 低优先级)

**目标**: 预置风格模板，快速切换建模风格

**预计工期**: 3-4 小时

**预置模板**:
```python
STYLE_TEMPLATES = {
    "hard_surface_realistic": {
        "bevel_amount": 0.02,
        "topology": "quad_only",
        "subdivision": "catmull_clark",
        "material_workflow": "pbr_metallic_roughness"
    },
    "stylized_low_poly": {
        "bevel_amount": 0,
        "topology": "triangle_friendly",
        "subdivision": "none",
        "material_workflow": "vertex_color"
    },
    "organic_character": {
        "bevel_amount": 0.1,
        "topology": "animation_ready",
        "subdivision": "catmull_clark_high",
        "material_workflow": "pbr_subsurface"
    }
}
```

**验收标准**:
- [ ] 3种以上风格模板
- [ ] CLI 支持 --style 参数
- [ ] 模板可扩展

---

## 实施优先级

```
Phase 1 (必须): [实施 A] + [实施 B]
  ├── 重构 stage 流程 (2-4h)
  └── 增加反馈循环 (4-6h)
  总工期: 6-10 小时

Phase 2 (推荐): [实施 C]
  └── 图像分析能力 (3-5h)
  
Phase 3 (可选): [实施 D]
  └── 风格模板系统 (3-4h)

总工期: 12-19 小时
```

---

## 风险与依赖

| 风险 | 影响 | 缓解方案 |
|------|------|---------|
| VLM API 成本 | 实施 C | 提供本地模型选项，或使用 cost‑effective 的 VLM |
| 用户反馈中断恢复 | 实施 B | 强化 TaskState 机制 |
| 阶段增多导致 LLM 计划过长 | 实施 A | 优化 Prompt，或使用温和的提示 |

---

## 相关文件

- `vbf/client.py` - run_task() 核心流程
- `vbf/llm_integration.py` - LLM Prompt 构建
- `vbf/task_state.py` - 状态保存/恢复
- `vbf/progress.py` - 进度显示
- `vbf/scene_state.py` - 场景捕获

---

**最后更新**: 2026-04-12
**状态**: 待用户确认后开始实施
