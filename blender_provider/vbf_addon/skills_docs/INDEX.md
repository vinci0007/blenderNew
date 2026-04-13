# VBF Skills Index
## Version 2.1.0 - 363 Skills by Category

**导航**: [主文档 SKILL.md](SKILL.md) | [按字母索引](#a-z-index) | [分类文档](categories/)

---

## 按工作流分类的索引

比 A-Z 更适合大模型理解的分类方式

---

## 🔴 P0 优先级 (核心建模工作流)

### 场景与对象管理
**文件**: [01_scene.md](categories/01_scene.md) (23 技能)

| 技能 | 说明 | 参数 |
|------|------|------|
| **scene_clear** | 清空场景 | - |
| **delete_object** | 删除对象 | object_name |
| **rename_object** | 重命名 | object_name, new_name |
| ⭐NEW **object_origin_set** | 设置原点 [严重缺失] | origin_type, center |
| ⭐NEW **object_select_all** | 选择/取消全部 [缺失] | action |
| ⭐NEW **object_select_by_type** | 按类型选择 [缺失] | object_type, extend |
| ⭐NEW **object_duplicate** | 复制对象 | object_name, linked |
| ⭐NEW **object_shade_smooth** | 平滑着色 | object_names |
| ⭐NEW **object_shade_flat** | 平直着色 | object_names |

### 视图控制 (原本 0 技能!)
**文件**: [01_scene.md](categories/01_scene.md) View3D 部分

| 技能 | 说明 | 参数 |
|------|------|------|
| ⭐NEW **view3d_cursor_set** | 设置 3D 游标 | location  |
| ⭐NEW **view3d_snap_cursor_to_selected** | 吸附到选择 | - |
| ⭐NEW **view3d_snap_cursor_to_center** | 重置到中心 | - |
| ⭐NEW **view3d_snap_selected_to_cursor** | 物体→游标 | object_names |
| ⭐NEW **view3d_view_selected** | 查看选择项 | - |
| ⭐NEW **view3d_view_all** | 查看全部 | - |
| ⭐NEW **view3d_localview** | 孤立视图 | object_names |

### 几何处理
**文件**: [02_geometry.md](categories/02_geometry.md) (24 技能)

| 技能 | 说明 | 参数 |
|------|------|------|
| **create_primitive** | 创建基础体 | primitive_type, name, location |
| **create_beveled_box** | 带倒角盒子 | width, height, depth, bevel_width |
| **extrude_faces** | 挤出面 | object_name, face_indices, distance |
| **inset_faces** | 内插面 | object_name, face_indices, thickness |
| **subdivide_mesh** | 细分网格 | object_name, number_cuts |
| **bridge_edge_loops** | 桥接循环边 | object_name, edge_loops |
| **boolean_tool** | 布尔工具 | object_name, target_object, operation |
| ⭐NEW **mesh_select_all** | 全选网格元素 | object_name, action |
| ⭐NEW **mesh_select_mode** | 设置选择模式 | object_name, mode (VERT/EDGE/FACE) |
| ⭐NEW **mesh_loop_select** | 循环选择 | object_name, edge_index |
| ⭐NEW **mesh_select_non_manifold** | 选中非流形 | object_name |

---

## ⭐ YouTube 分析技能 (硬表面建模)

### 边缘控制与折痕
**文件**: [03_edge_uv.md](categories/03_edge_uv.md) - Edge 部分
**来源**: CG Boost, Francesco Milanese, PIXXO 3D (5+ 教程)

| 技能 | 说明 | 关键参数 |
|------|------|----------|
| ⭐NEW **mark_edge_crease** | 标记边缘折痕 [极关键] | edges, crease_value (0-1) |
| ⭐NEW **clear_edge_crease** | 清除折痕 | edges |
| ⭐NEW **set_edge_bevel_weight** | 倒角权重 [极关键] | edges, weight (0-1) |
| ⭐NEW **clear_edge_bevel_weight** | 清除权重 | edges |
| ⭐NEW **get_edge_data** | 获取边缘数据 | object_name |
| ⭐NEW **select_edge_rings** | 选择边环 | object_name, edge_index |

### UV 映射 (原本严重缺失)
**文件**: [03_edge_uv.md](categories/03_edge_uv.md) - UV 部分
**来源**: 覆盖率提升 P0

| 技能 | 说明 | 关键参数 |
|------|------|----------|
| ⭐NEW **uv_project_from_view** | 视图投影 UV [严重缺失] | camera_bounds |
| ⭐NEW **uv_cylinder_project** | 圆柱投影 | direction |
| ⭐NEW **uv_sphere_project** | 球面投影 | direction |
| ⭐NEW **uv_cube_project** | 立方体投影 | cube_size |
| ⭐NEW **uv_minimize_stretch** | 最小化拉伸 [严重缺失] | iterations |
| ⭐NEW **uv_stitch** | 缝合 UV | - |
| ⭐NEW **uv_average_islands_scale** | 平均缩放 | - |
| **unwrap_mesh** | 展开网格 | object_name, method |
| **smart_project_uv** | 智能投影 | object_name, angle_limit |
| **mark_seam** | 标记缝合边 | object_name, edge_indices |

### 修改器 (Extended)
**文件**: [04_modifiers.md](categories/04_modifiers.md)
**来源**: CG Boost 硬表面教程

| 技能 | 说明 | 关键参数 |
|------|------|----------|
| **add_modifier_bevel** | 倒角修改器 | width, segments |
| **add_modifier_subdivision** | 细分曲面修改器 | levels |
| ⭐NEW **add_modifier_solidify** | 实体化/面板线 [CG Boost] | thickness, offset |
| ⭐NEW **add_modifier_array** | 阵列 [机械建模] | count, relative_offset |
| ⭐NEW **add_modifier_mirror** | 镜像 [最常用] | use_x, use_clip |
| ⭐NEW **add_modifier_boolean** | 布尔 (非破坏式) | operation, operand_object |
| ⭐NEW **add_modifier_shrinkwrap** | 收缩包裹 [服装/装甲板] | target_object, wrap_method |
| ⭐NEW **add_modifier_curve** | 曲线变形 | curve_object, deform_axis |
| ⭐NEW **add_modifier_displace** | 置换 | strength, direction |
| ⭐NEW **configure_modifier** | 配置参数 | object_name, modifier_name, properties |
| ⭐NEW **move_modifier** | 调整顺序 | object_name, modifier_name, direction |
| ⭐NEW **list_modifiers** | 列出修改器 | object_name |
| **apply_modifier** | 应用修改器 | object_name, modifier_name |

---

## 🎨 材质与渲染 (PBR 工作流)

### PBR 材质 (YouTube 驱动)
**文件**: [05_materials.md](categories/05_materials.md)
**来源**: PBR 教程

| 技能 | 说明 | 关键参数 |
|------|------|----------|
| **create_material_simple** | 简单材质 | name, color |
| ⭐NEW **create_material_pbr** | 完整 PBR [CG Boost] | base_color, metallic, roughness, transmission, ior |
| ⭐NEW **create_material_preset** | 预设材质 | preset_name (GOLD/GLASS/SKIN/...) |
| ⭐NEW **attach_texture_to_material** | 纹理贴图 | material_name, texture_type, image_path |
| ⭐NEW **set_material_ior** | 折射率 | material_name, ior |
| **assign_material** | 分配材质 | object_name, material_name |
| **add_texture_to_material** | 添加纹理 | material_name, image_name |
| **add_normal_map** | 法线贴图 | material_name, image_name, strength |
| **create_image_texture** | 创建空白纹理 | name, width, height |
| **import_image_texture** | 导入图片 | filepath |
| **bake_texture** | 烘焙纹理 | object_name, image_name, bake_type |

### 材质预设
| 预设 | 适用场景 |
|------|---------|
| PLASTIC | 塑料 |
| METAL | 金属 |
| GOLD | 黄金 |
| GLASS | 玻璃 [ior=1.45, transmission=1] |
| SKIN | 皮肤 [subsurface=0.5] |
| CAR_PAINT | 车漆 [clearcoat=1] |
| EMISSIVE | 自发光 |

---

## 🎬 动画系统 (Extended)

### 骨骼动画 (YouTube 驱动)
**文件**: [06_animation.md](categories/06_animation.md)
**来源**: HulkFatZerg EP14

| 技能 | 说明 | 关键参数 |
|------|------|----------|
| **insert_keyframe** | 对象关键帧 | object_name, frame, data_path |
| ⭐NEW **insert_keyframe_bone** | 骨骼关键帧 [HulkFatZerg] | armature_name, bone_name, frame, data_path, value |
| **create_armature** | 创建骨骼 | name |
| **add_bone** | 添加骨骼 | armature_name, bone_name, head, tail |
| **skin_to_armature** | 绑定蒙皮 | object_name, armature_name |
| **create_shape_key** | 形状键 | object_name, name |
| ⭐NEW **insert_keyframe_shape_key** | 形状键关键帧 [3D Bibi] | shape_key_name, frame, value |

### 动画动作/NLA
**来源**: HulkFatZerg EP13 (物理动画烘焙)

| 技能 | 说明 | 关键参数 |
|------|------|----------|
| ⭐NEW **bake_animation** | 烘焙动画 [极关键] | object_name, frame_start, frame_end, bake_types |
| ⭐NEW **create_action** | 创建动作/片段 | action_name, object_name |
| ⭐NEW **set_action** | 设置动作 | object_name, action_name |
| ⭐NEW **list_actions** | 列出动作 | - |
| ⭐NEW **nla_add_strip** | NLA 添加片段 | object_name, action_name, start_frame |
| ⭐NEW **set_nla_strip_properties** | NLA 混合设置 | object_name, strip_name, blend_type, influence |

---

## 🔧 工具类

### Gateway (低级别访问)
**文件**: [00_gateway.md](categories/00_gateway.md)

| 技能 | 说明 | 用途 |
|------|------|------|
| **py_call** | 调用任意 bpy 函数 | 备用方案 |
| **py_get/py_set** | 读写属性 | 动态操作 |
| **ops_invoke** | 执行操作符 | 高级用法 |
| **ops_introspect** | 查看参数 | 探索 API |
| **ops_search** | 搜索操作符 | 发现功能 |

---

## 📊 完整分类统计

| 分类 | 技能数 | 新技能 | 来源 |
|------|--------|--------|------|
| Gateway | 10 | 0 | Core |
| Scene/Object (含 View3D) | 23 | 17 | P0 缺失 |
| Geometry | 24 | 7 | P0 |
| Edge Control | 9 | 9 | YouTube⭐ |
| UV Mapping | 17 | 8 | P0/YouTube⭐ |
| Modifiers | 15 | 10 | YouTube⭐ |
| Materials | 21 | 4 | YouTube⭐ |
| Textures | 8 | 0 | Core |
| Animation | 35 | 12 | YouTube⭐ |
| Armature | 15 | 0 | Core |
| Shape Keys | 10 | 0 | Core + New |
| Sculpting | 17 | 0 | Core |
| Physics | 17 | 0 | Core |
| Particles | 14 | 0 | Core |
| Grease Pencil | 18 | 0 | Core |
| Sequencer | 12 | 0 | Core |
| Tracking | 11 | 0 | Core |
| Compositor | 14 | 0 | Core |
| Drivers | 7 | 0 | Core |
| Assets | 13 | 0 | Core |
| Painting | 17 | 0 | Core |
| Rendering | 15 | 0 | Core |
| Gateway/Utils | 10 | 0 | Core |
| **其他...** | **40** | **0** | Core |
| **总计** | **363** | **69** | **-** |

---

## 🆕 新增技能来源汇总

| 来源 / Source | 技能数 | 重点技能 |
|--------------|--------|----------|
| **P0 严重缺失** | 27 | view3d_cursor_set, object_origin_set, mesh_select_mode, uv_project_from_view |
| **CG Boost** | 15 | mark_edge_crease, add_modifier_solidify, create_material_pbr, uv_minimize_stretch |
| **Francesco Milanese** | 5 | set_edge_bevel_weight, get_edge_data |
| **PIXXO 3D** | 3 | edge_crease variants |
| **HulkFatZerg EP14** | 8 | insert_keyframe_bone, bake_animation, insert_keyframe_shape_key |
| **HulkFatZerg EP13** | 4 | nla_add_strip, set_nla_strip_properties |
| **3D Bibi (日本)** | 3 | shape_key related |

**总计**: 69 新增技能

---

## A-Z Index

如需字母顺序查找，参见 [A-Z 完整列表](#az-full-list)

---

## 模型支持

所有 363 技能均支持:
- ✅ **Claude Code** - 原生读取
- ✅ **OpenAI GPT-4** - API 调用
- ✅ **GLM-4** - 智谱AI
- ✅ **Kimi** - Moonshot
- ✅ **Qwen** - 阿里云
- ✅ **MiniMax**
- ✅ **Ollama** - 本地部署

---

## 导航

**按类别**: [Gateway](categories/00_gateway.md) → [Scene](categories/01_scene.md) → [Geometry](categories/02_geometry.md) → [Edge/UV](categories/03_edge_uv.md) → [Modifiers](categories/04_modifiers.md) → [Materials](categories/05_materials.md) → [Animation](categories/06_animation.md) → Others

**主文档**: [SKILL.md](SKILL.md)
