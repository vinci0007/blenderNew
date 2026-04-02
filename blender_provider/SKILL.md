---
name: Vibe-Blender-Flow Skills (VBF)
description: Execute Blender modeling actions via pre-registered High-Level Skills over JSON-RPC.
metadata:
  {
    "openai_compat_planner": {
      "requires": { "bins": ["websockets"] },
      "notes": "Planner runs in client; this doc constrains the model to output skills_plan JSON only."
    }
  }
---

# Vibe-Blender-Flow Skills

你必须只输出 `skills_plan` / `repair_plan` 的 JSON（Controller 负责执行 Blender bpy 操作）。

## Claude Skill Mode Guardrails
- 绝不输出任何 `bpy`/`bmesh` 代码、也不输出 Blender 插件脚本代码片段。
- 只能在 plan 中选择允许的 `skill` 名称；禁止编造未知 skill。
- 所有步骤参数必须是 JSON 可序列化类型（number/string/boolean/null/array/object）。
- 如果需要从先前步骤获取对象名或坐标，请使用 `$ref`：
  - 规范用法：`{"$ref":"<step_id>.data.<key>"}`
  - 若使用 `on_success.store_as` 存储别名，后续可用：`{"$ref":"<alias_name>.data.<key>"}`
  - 若存储的是非对象/非 dict 值，请引用：`{"$ref":"<alias_name>.data.value"}`
- 坐标/对齐优先使用 anchor 技能（例如 `move_object_anchor_to_point`），避免在 `$ref` 中做算术。

## skills_plan JSON Schema（必须严格匹配）
每次请求只返回一个 JSON 对象：

```json
{
  "vbf_version": "1.0",
  "plan_id": "string",
  "execution": { "max_retries_per_step": 2 },
  "steps": [
    {
      "step_id": "string",
      "stage": "discover|blockout|boolean|detail|bevel|normal_fix|accessories|material|finalize",
      "skill": "string",
      "args": { "any": "json-serializable" },
      "on_success": {
        "store_as": {
          "alias_name": "string",
          "step_return_json_path": "data.<key>"
        }
      }
    }
  ]
}
```

repair_plan 用于某一步失败后自动修复（Controller 会从失败步开始替换执行）：

```json
{
  "vbf_version": "1.0",
  "plan_id": "string",
  "repair": { "replace_from_step_id": "failed_step_id" },
  "execution": { "max_retries_per_step": 2 },
  "steps": [
    { "step_id": "string", "skill": "string", "args": { "any": "json-serializable" } }
  ]
}
```

## Allowed Skills（当前注册表）
下面是本项目当前允许的 skills（Controller 侧会校验）：

- `scene_clear`
  - args: `{}`
- `create_primitive`
  - args: `{ "primitive_type": "cube|cylinder|cone|sphere", "name": "string", "location": [x,y,z], "rotation_euler": [rx,ry,rz]?, "scale": [sx,sy,sz]?, "size": [..]?, "radius": number?, "height": number? }`
- `apply_transform`
  - args: `{ "object_name": "string", "location": [x,y,z]?, "rotation_euler": [rx,ry,rz]?, "scale": [sx,sy,sz]? }`
- `spatial_query`
  - args: `{ "object_name": "string", "query_type": "top_center|bottom_center|side_center|center" }`
  - returns: `{ "location": [x,y,z] }`
- `create_beveled_box`
  - args: `{ "name": "string", "size": [x,y,z], "location": [x,y,z], "bevel_width": number?, "bevel_segments": int? }`
- `create_nested_cones`
  - args: `{ "name_prefix": "string", "base_location": [x,y,z], "layers": int?, "base_radius": number?, "top_radius": number?, "height": number?, "z_jitter": number? }`
- `boolean_tool`
  - args: `{ "target_name": "string", "tool_name": "string", "operation": "difference|union|intersect", "apply": true|false?, "delete_tool": true|false? }`
- `delete_object`
  - args: `{ "object_name": "string" }`
- `rename_object`
  - args: `{ "object_name": "string", "new_name": "string" }`
- `join_objects`
  - args: `{ "object_names": ["string", ...], "new_name": "string"? }`
- `move_object_anchor_to_point`
  - args: `{ "object_name": "string", "anchor_type": "top_center|bottom_center|side_center|center", "target_point": [x,y,z] }`
- `create_material_simple`
  - args: `{ "name": "string", "base_color": [r,g,b], "roughness": number?, "metallic": number? }`
- `assign_material`
  - args: `{ "object_name": "string", "material_name": "string", "slot_index": int? }`
- `add_modifier_bevel`
  - args: `{ "object_name": "string", "width": number?, "segments": int? }`
- `add_modifier_subdivision`
  - args: `{ "object_name": "string", "levels": int?, "render_levels": int? }`
- `apply_modifier`
  - args: `{ "object_name": "string", "modifier_name": "string" }`
- `api_validator`
  - args: `{ "api_path": "string" }`

## 全量 Blender API 覆盖（通用网关 skills）
为了实现“覆盖全部 Blender API”，本项目提供 3 个通用反射型 skills。它们仍然满足 Claude skill 模式：模型只输出 JSON，真正调用由 Controller -> Blender 插件完成。

### `py_get`（读取任意 bpy 路径）
- args：`{ "path_steps": [ ... ] }`
- `path_steps` 是一组 token，不允许写 `bpy.xxx` 字符串、也不使用 eval：
  - `{"attr":"data"}` 表示 `.data`
  - `{"attr":"objects"}` 表示 `.objects`
  - `{"key":"Cube"}` 表示 `["Cube"]`
  - `{"index":0}` 表示 `[0]`

示例：读取 `bpy.data.objects["Cube"].location`：

```json
{
  "skill": "py_get",
  "args": {
    "path_steps": [
      {"attr":"data"},
      {"attr":"objects"},
      {"key":"Cube"},
      {"attr":"location"}
    ]
  }
}
```

### `py_set`（写入任意 bpy 路径）
- args：`{ "path_steps": [ ... ], "value": <json> }`
- 最后一个 token 必须是 `attr/key/index` 之一，表示要写入的目标位点。

### `py_call`（调用任意 bpy 可调用对象：全 API 覆盖入口）
- args：
  - `callable_path_steps`: `[ ... ]`（同 token 规则）
  - `args`: `[...]`（可选）
  - `kwargs`: `{...}`（可选）

示例：调用 `bpy.ops.mesh.primitive_cube_add(size=1.0)`：

```json
{
  "skill": "py_call",
  "args": {
    "callable_path_steps": [
      {"attr":"ops"},
      {"attr":"mesh"},
      {"attr":"primitive_cube_add"}
    ],
    "kwargs": {"size": 1.0}
  }
}
```

### 安全约束
- 禁止访问 dunder（`__xxx__`）属性；`path_steps` 中的 `attr` 会做拦截。
- 建议优先使用高层建模 skills（如 `create_primitive`/`boolean_tool`/`spatial_query`），只有当高层 skill 不覆盖时才用通用网关。

## bpy.ops 专用全量覆盖（推荐优先于 py_call）
为避免模型自行拼 `path_steps`，可以优先使用下面两个 skills：

### `ops_list`
- args: `{ "prefix": "mesh."?, "head_limit": 200? }`
- returns:
  - `operators`: `["mesh.primitive_cube_add", ...]`
  - `count`: `int`

### `ops_search`
- args:
  - `query`: `"cube add"` / `"mesh.primitive_cube_add"` 等关键词
  - `head_limit`: `20?`
- returns:
  - `results`: `[{ "operator_id": "...", "score": 900 }, ...]`
  - `count`: `int`

### `ops_invoke`
- args:
  - `operator_id`: `"mesh.primitive_cube_add"`（`<module>.<operator>`）
  - `kwargs`: `{...}`（可选）
  - `execution_context`: `"EXEC_DEFAULT"`（可选）

示例：

```json
{
  "skill": "ops_invoke",
  "args": {
    "operator_id": "mesh.primitive_cube_add",
    "kwargs": {"size": 1.0, "location": [0, 0, 0]}
  }
}
```

### `ops_introspect`
- args:
  - `operator_id`: `"mesh.primitive_cube_add"`
- returns:
  - `name` / `description`
  - `properties`: 参数元信息数组（identifier/type/default/is_required/is_readonly 等）

推荐顺序：`ops_search -> ops_introspect -> ops_invoke`（必要时用 `ops_list` 做全量浏览）

### `types_list`
- args: `{ "prefix": "Mesh"?, "head_limit": 200? }`
- returns:
  - `types`: `["Mesh", "Object", ...]`
  - `count`: `int`

### `data_collections_list`
- args: `{ "prefix": "mat"?, "head_limit": 200? }`
- returns:
  - `collections`: `["materials", "meshes", "objects", ...]`
  - `count`: `int`

## Example：从主体顶部生成并修剪天线（RadioTask 的抽象）
模型只输出 steps；Controller 自动执行并在失败时自动 repair。

（示例不包含任何 bpy 代码）

