# VBF Skills Documentation - Categories
## 分类技能文档导航

**总览**: 31 个分类文件，涵盖 357 个技能

---

## 📁 分类文档索引

| # | 分类 | 文件 | 技能数 | 描述 |
|---|------|------|--------|------|
| 00 | Gateway | [00_gateway.md](00_gateway.md) | 10 | py_call, ops_invoke 等低级API访问 |
| 01 | Scene | [01_scene.md](01_scene.md) | 23 | 场景、对象、视图控制 |
| 02 | Geometry | [02_geometry.md](02_geometry.md) | 24 | 几何处理、建模、选择 |
| 03 | Edge/UV | [03_edge_uv.md](03_edge_uv.md) | 26 | 边缘折痕、UV映射 (YouTube重点) |
| 04 | Modifiers | [04_modifiers.md](04_modifiers.md) | 15 | 修改器系统 (Extended) |
| 05 | Materials | [05_materials.md](05_materials.md) | 21 | 材质、PBR、纹理 |
| 06 | Animation | [06_animation.md](06_animation.md) | 35 | 动画、NLA、骨骼关键帧 (Extended) |

---

## 📊 YouTube 分析新增技能

### P0 优先级 (核心工作流)
| 分类 | 新增技能 | 来源 |
|------|---------|------|
| **Scene** | object_origin_set, object_select_all, view3d_cursor_set 等 10 个 | bpy.ops.object/ view3d 严重缺失 |
| **Edge/UV** | mark_edge_crease, uv_project_from_view 等 17 个 | CG Boost, PIXXO 3D |

### Extended (专业工作流)
| 分类 | 新增技能 | 来源 |
|------|---------|------|
| **Modifiers** | add_modifier_solidify, add_modifier_array 等 10 个 | CG Boost 硬表面教程 |
| **Materials** | create_material_pbr, create_material_preset 等 4 个 | PBR 工作流程 |
| **Animation** | insert_keyframe_bone, bake_animation, NLA 等 12 个 | HulkFatZerg EP13/14, 3D Bibi |

---

## 🚀 快速开始

### 新手建模
1. [01_scene.md](01_scene.md) - 创建对象
2. [02_geometry.md](02_geometry.md) - 编辑网格
3. [03_edge_uv.md](03_edge_uv.md) - UV展开

### 硬表面建模
1. [02_geometry.md](02_geometry.md) - 基础建模
2. [03_edge_uv.md](03_edge_uv.md) - mark_edge_crease, set_edge_bevel_weight
3. [04_modifiers.md](04_modifiers.md) - Solidify, Array, Boolean
4. [05_materials.md](05_materials.md) - PBR材质

### 角色动画
1. [01_scene.md](01_scene.md) - 资产管理
2. [06_animation.md](06_animation.md) - 骨骼动画、NLA

---

## 📝 文档结构

每个分类文档包含：
- **技能描述**: 功能说明
- **YouTube 来源**: 教程验证 (如适用)
- **参数表格**: 类型、必填、默认值
- **使用示例**: JSON 格式

---

## 🔗 主文档

- **[SKILL.md](../SKILL.md)** - 技能主文档
- **[INDEX.md](../INDEX.md)** - A-Z 技能索引
- **[_prompts/../universal_system_prompt.md](../_prompts/universal_system_prompt.md)** - 系统提示

---

## 📈 统计

```
Original Skills: 294
New YouTube Skills: 69
Total Skills: 363
New Categories: 7
Document Files: 7 + 1 (this)
```

---

**Back to**: [SKILL.md](../SKILL.md) | [INDEX.md](../INDEX.md)
