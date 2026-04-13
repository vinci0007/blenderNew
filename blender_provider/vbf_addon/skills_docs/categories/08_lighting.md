# Category: Lighting (3 skills)

## For Developers & LLM Agents

**Category**: Lighting
**Description**: Light creation and setup
**Total Skills**: 3

### When to Use This Category
For setup before rendering

### Prerequisites
None

### Common Workflow Sequence
```
[create_light] → [set_light_properties]
```

---

## Skills
## create_light

**Description**: Create a light source in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| light_type | str | Yes | - |
| name | str | Yes | - |
| location | List[float] | Yes | - |
| energy | float | No | 10.0 |
| color | List[float] | None | No |
| rotation_euler | List[float] | None | No |


---

## set_light_properties

**Description**: Configure properties of an existing light.

| Parameter | Type | Required | Default |
|---|---|---|---|
| light_name | str | Yes | - |
| energy | float | None | No |
| color | List[float] | None | No |
| specular | float | None | No |
| shadow_soft_size | float | None | No |
| spot_size | float | None | No |
| spot_blend | float | None | No |
| angle | float | None | No |
| size | float | None | No |
| shape | str | None | No |


---
