# Category: Materials Enhanced (5 skills)

## For Developers & LLM Agents

**Category**: Materials Enhanced
**Description**: PBR materials and texture workflow
**Total Skills**: 5

### When to Use This Category
For realistic rendering requiring PBR workflow

### Prerequisites
UV maps must exist

### Common Workflow Sequence
```
[create_material_pbr] → [attach_texture_to_material] → [bake_texture]
```

---

## Skills
---

## attach_texture_to_material

**Description**: Attach an image texture to a material's base color.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| texture_path | str | Yes | - |
| node_name | str | No | Image Texture |

---

## create_material_pbr

**Description**: Create a PBR material with metallic/roughness workflow.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | No | PBR_Material |
| base_color | List[float] | No | [0.8, 0.8, 0.8, 1.0] |
| metallic | float | No | 0.0 |
| roughness | float | No | 0.5 |
| ior | float | No | 1.45 |

---

## create_material_preset

**Description**: Create material from preset (metal, plastic, glass, etc.).

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| preset_type | str | Yes | - |

---

## set_material_ior

**Description**: Set the Index of Refraction for a material.

| Parameter | Type | Required | Default |
|---|---|---|---|
| material_name | str | Yes | - |
| ior | float | Yes | 1.45 |

---
