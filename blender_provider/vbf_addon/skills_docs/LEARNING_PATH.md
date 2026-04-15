# VBF 技能学习路径 - 从入门到精通

**VBF (Vibe-Blender-Flow)** 是一个基于 JSON-RPC 的 Blender 3D 建模技能系统，提供 363 个高级技能供 AI 调用。

---

## 学习路径概览

```
入门阶段 (Level 1-3) → 中级阶段 (Level 4-6) → 高级阶段 (Level 7-9) → 精通阶段 (Level 10+)
```

---

## 第一阶段：入门 (Level 1-3)

### Level 1: 基础场景操作
**目标**: 掌握 Blender 基本操作和场景管理

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 场景管理 | `scene_clear` | 清空场景 | [01_scene](../01_scene.md) |
| | `delete_object` | 删除对象 | [01_scene](../01_scene.md) |
| | `rename_object` | 重命名对象 | [01_scene](../01_scene.md) |
| | `duplicate_object` | 复制对象 | [01_scene](../01_scene.md) |
| 集合操作 | `create_collection` | 创建集合 | [01_collections](../01_collections.md) |
| | `link_to_collection` | 链接到集合 | [01_collections](../01_collections.md) |
| | `isolate_in_collection` | 隔离集合 | [01_collections](../01_collections.md) |

**实践项目**: 创建简单的场景组织结构（地板、相机、灯光）

---

### Level 2: 基础建模
**目标**: 掌握基本几何体创建和变换

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 创建基础体 | `create_primitive` | 创建基本体（立方体、球体等） | [02_primitives](../02_primitives.md) |
| | `create_beveled_box` | 创建倒角立方体 | [02_primitives](../02_primitives.md) |
| 变换操作 | `apply_transform` | 应用变换 | [05_transforms](../05_transforms.md) |
| | `move_object_anchor_to_point` | 锚点移动 | [05_transforms](../05_transforms.md) |
| 修改器入门 | `add_modifier_bevel` | 添加倒角修改器 | [04_modifiers](../04_modifiers.md) |
| | `add_modifier_subdivision` | 添加细分修改器 | [04_modifiers](../04_modifiers.md) |

**实践项目**: 创建一个带倒角的茶几（立方体+圆柱体+倒角修改器）

---

### Level 3: 基础编辑
**目标**: 掌握网格编辑和简单的布尔操作

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 几何处理 | `extrude_faces` | 挤出面 | [02_geometry](../02_geometry.md) |
| | `inset_faces` | 内插面 | [02_geometry](../02_geometry.md) |
| | `subdivide_mesh` | 细分网格 | [02_geometry](../02_geometry.md) |
| 布尔操作 | `boolean_tool` | 布尔工具 | [04_booleans](../04_booleans.md) |
| | `join_objects` | 合并对象 | [04_booleans](../04_booleans.md) |
| 平滑处理 | `shade_smooth` | 平滑着色 | [02_geometry](../02_geometry.md) |
| | `shade_flat` | 平直着色 | [02_geometry](../02_geometry.md) |

**实践项目**: 创建一个带螺丝孔的机械零件（立方体 + 挤出 + 布尔差）

---

## 第二阶段：中级 (Level 4-6)

### Level 4: UV 展开与基础材质
**目标**: 掌握 UV 映射和简单的 PBR 材质

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| UV 基础 | `mark_seam` | 标记缝合边 | [03_uv_mapping](../03_uv_mapping.md) |
| | `unwrap_mesh` | 展开 UV | [03_uv_mapping](../03_uv_mapping.md) |
| | `smart_project_uv` | 智能投影 UV | [03_uv_mapping](../03_uv_mapping.md) |
| UV 优化 | `pack_uv_islands` | 打包 UV 岛 | [03_uv_mapping](../03_uv_mapping.md) |
| | `arrange_uvs` | 整理 UV | [03_uv_mapping](../03_uv_mapping.md) |
| 材质基础 | `create_material_simple` | 创建简单材质 | [05_materials](../05_materials.md) |
| | `assign_material` | 分配材质 | [05_materials](../05_materials.md) |
| | `create_material_pbr` | 创建 PBR 材质 | [05_materials_enhanced](../05_materials_enhanced.md) |

**实践项目**: 为茶几创建木纹材质并正确展开 UV

---

### Level 5: 高级修改器
**目标**: 掌握完整的修改器工作流

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 阵列与镜像 | `add_modifier_array` | 阵列修改器 | [04_modifiers_extended](../04_modifiers_extended.md) |
| | `add_modifier_mirror` | 镜像修改器 | [04_modifiers_extended](../04_modifiers_extended.md) |
| 实体化与布尔 | `add_modifier_solidify` | 实体化修改器 | [04_modifiers_extended](../04_modifiers_extended.md) |
| | `add_modifier_boolean` | 布尔修改器 | [04_modifiers_extended](../04_modifiers_extended.md) |
| 曲线与适配 | `add_modifier_curve` | 曲线修改器 | [04_modifiers_extended](../04_modifiers_extended.md) |

**实践项目**: 创建复杂的栏杆（曲线 + 阵列 + 镜像修改器）

---

### Level 6: 高级几何编辑
**目标**: 掌握复杂的网格编辑技巧

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 边处理 | `mark_edge_crease` | 标记边折痕 | [03_edge_uv](../03_edge_uv.md) |
| | `set_edge_bevel_weight` | 设置边倒角权重 | [03_edge_uv](../03_edge_uv.md) |
| | `bridge_edge_loops` | 桥接边循环 | [02_geometry](../02_geometry.md) |
| 网格工具 | `loop_cut` | 循环切割 | [02_geometry](../02_geometry.md) |
| | `triangulate_faces` | 三角化面 | [02_geometry](../02_geometry.md) |
| | `remove_doubles` | 合并重复顶点 | [02_geometry](../02_geometry.md) |

**实践项目**: 创建硬表面机械部件（带折痕控制的细分表面）

---

## 第三阶段：高级 (Level 7-9)

### Level 7: 骨骼与动画
**目标**: 掌握骨骼绑定和基础动画

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 骨骼系统 | `create_armature` | 创建骨架 | [08_armature](../08_armature.md) |
| | `add_bone` | 添加骨骼 | [08_armature](../08_armature.md) |
| | `edit_bone` | 编辑骨骼 | [08_armature](../08_armature.md) |
| 权重绘制 | `create_vertex_group` | 创建顶点组 | [08_armature](../08_armature.md) |
| | `skin_to_armature` | 蒙皮到骨架 | [08_armature](../08_armature.md) |
| 动画基础 | `insert_keyframe` | 插入关键帧 | [06_animation](../06_animation.md) |
| | `insert_keyframe_bone` | 骨骼关键帧 | [06_animation](../06_animation.md) |
| | `set_action` | 设置动作 | [06_animation](../06_animation.md) |

**实践项目**: 创建一个可动的机械臂并制作简单动画

---

### Level 8: 物理与模拟
**目标**: 掌握刚体、布料和粒子系统

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 刚体物理 | `rigidbody_add` | 添加刚体 | [10_physics](../10_physics.md) |
| | `rigidbody_set_mass` | 设置质量 | [10_physics](../10_physics.md) |
| | `rigidbody_set_collision_shape` | 设置碰撞形状 | [10_physics](../10_physics.md) |
| 布料 | `cloth_add` | 添加布料 | [10_physics](../10_physics.md) |
| | `cloth_bake` | 烘焙布料 | [10_physics](../10_physics.md) |
| 粒子 | `create_particle_system` | 创建粒子系统 | [10_particles](../10_particles.md) |
| | `set_particle_emitter` | 设置粒子发射器 | [10_particles](../10_particles.md) |

**实践项目**: 物理模拟场景（刚体碰撞 + 布料旗帜 + 粒子烟雾）

---

### Level 9: 渲染与合成
**目标**: 掌握渲染设置和后期合成

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 相机动画 | `create_camera` | 创建相机 | [08_camera](../08_camera.md) |
| | `camera_look_at` | 相机看向目标 | [08_camera](../08_camera.md) |
| | `set_camera_properties` | 设置相机属性 | [08_camera](../08_camera.md) |
| 灯光设置 | `create_light` | 创建灯光 | [08_lighting](../08_lighting.md) |
| | `set_light_properties` | 设置灯光属性 | [08_lighting](../08_lighting.md) |
| 渲染 | `render_image` | 渲染图像 | [10_rendering_io](../10_rendering_io.md) |
| | `set_cycles_samples` | 设置 Cycles 采样 | [10_rendering_io](../10_rendering_io.md) |
| | `set_eevee_samples` | 设置 Eevee 采样 | [10_rendering_io](../10_rendering_io.md) |

**实践项目**: 创建专业的产品渲染布光场景并输出高质量图片

---

## 第四阶段：精通 (Level 10+)

### Level 10: 高级动画与驱动
**目标**: 掌握程序化动画和约束系统

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 约束 | `add_constraint_copy_location` | 复制位置约束 | [09_constraints](../09_constraints.md) |
| | `add_constraint_copy_rotation` | 复制旋转约束 | [09_constraints](../09_constraints.md) |
| | `add_constraint_limit_location` | 限制位置约束 | [09_constraints](../09_constraints.md) |
| 驱动器 | `add_driver` | 添加驱动器 | [06_drivers](../06_drivers.md) |
| | `driver_set_expression` | 设置驱动表达式 | [06_drivers](../06_drivers.md) |
| 骨骼高级 | `add_ik_constraint` | IK 约束 | [08_armature](../08_armature.md) |
| 运动层 | `nla_add_strip` | 添加 NLA 片段 | [06_animation](../06_animation.md) |

**实践项目**: 创建程序化的角色动画系统（IK 控制器 + 驱动器 + 混合动画）

---

### Level 11: 高级材质与几何节点
**目标**: 掌握程序化材质和几何节点

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 节点材质 | `create_shader_node_tree` | 创建着色器节点树 | [07_node_system](../07_node_system.md) |
| | `add_shader_node` | 添加着色器节点 | [07_node_system](../07_node_system.md) |
| | `link_nodes` | 链接节点 | [07_node_system](../07_node_system.md) |
| 几何节点 | `create_geometry_nodes_tree` | 创建几何节点树 | [07_geometry_nodes](../07_geometry_nodes.md) |
| | `add_geometry_node` | 添加几何节点 | [07_geometry_nodes](../07_geometry_nodes.md) |
| | `create_attribute` | 创建属性 | [07_geometry_nodes](../07_geometry_nodes.md) |

**实践项目**: 创建程序化生成的城市建筑（几何节点 + 材质实例）

---

### Level 12: 雕刻与特效
**目标**: 掌握数字雕刻和 grease pencil

| 模块 | 技能 | 说明 | 类别文件 |
|------|------|------|----------|
| 雕刻 | `set_sculpt_brush` | 设置雕刻笔刷 | [12_sculpting](../12_sculpting.md) |
| | `sculpt_draw` | 雕刻绘制 | [12_sculpting](../12_sculpting.md) |
| | `dyntopo_enabled` | 动态拓扑 | [12_sculpting](../12_sculpting.md) |
| Grease Pencil | `gpencil_add_blank` | 添加空白 GP | [15_grease_pencil](../15_grease_pencil.md) |
| | `gpencil_draw_stroke` | 绘制线条 | [15_grease_pencil](../15_grease_pencil.md) |

**实践项目**: 创建风格化角色（雕刻 + 手绘纹理 + grease pencil 轮廓）

---

## 进阶专题

### 专题 A: 硬表面建模工作流
1. **块面阶段**: `create_primitive` → `boolean_tool` → `bevel_mesh`
2. **细化阶段**: `mark_edge_crease` → `add_modifier_bevel` → `subdivide_mesh`
3. **完成阶段**: `apply_modifier` → `mark_seam` → `unwrap_mesh`

### 专题 B: 角色动画工作流
1. **绑定阶段**: `create_armature` → `add_bone` → `add_ik_constraint`
2. **蒙皮阶段**: `create_vertex_group` → `skin_to_armature` → `weight_paint_mode`
3. **动画阶段**: `create_action` → `insert_keyframe` → `bake_animation`

### 专题 C: 程序化生成工作流
1. **基础几何**: `create_primitive` → `subdivide_mesh` → `triangulate_faces`
2. **变形处理**: `add_modifier_displace` → `add_modifier_curve` → `bake_animation`
3. **实例分布**: `create_attribute` → `array_along_curve`

---

## 学习建议

### 每日练习
- **Level 1-3**: 每天练习 2-3 个新技能
- **Level 4-6**: 每周完成 1 个完整项目
- **Level 7-9**: 每月深入研究 1 个专题
- **Level 10+**: 持续探索和学习

### 资源参考
- **完整技能文档**: [SKILL.md](SKILL.md)
- **原完整参考**: [blender_provider/SKILL.md](../../../SKILL.md)
- **A-Z 索引**: [INDEX.md](../INDEX.md)
- **示例代码**: [工作流示例](SKILL.md#workflow-examples)

### 调试技巧
1. 使用 `api_validator` 验证 API 路径
2. 使用 `py_get` 检查对象属性
3. 使用 `ops_list` 查找可用操作
4. 查看 `categories/` 目录获取详细参数

---

**下一步**: 从 Level 1 开始，按顺序完成每个级别的学习，建议先完成入门阶段的三个级别再进入中级阶段。
