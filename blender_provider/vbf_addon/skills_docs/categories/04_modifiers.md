# Category: Modifiers (4 skills)

## For Developers & LLM Agents

**Category**: Modifiers
**Description**: Standard modifier operations
**Total Skills**: 4

### When to Use This Category
After basic geometry creation for non-destructive editing

### Prerequisites
Target object must exist

### Common Workflow Sequence
```
[create_primitive] → [add_modifier_bevel] → [add_modifier_subdivision]
```

---

## Skills
## add_modifier_bevel

**Description**: Add a Bevel modifier to an object for rounded edges.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| width | float | No | 0.03 |
| segments | int | No | 3 |

---

## add_modifier_subdivision

**Description**: Add a Subdivision Surface modifier to an object for smooth geometry.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| levels | int | No | 2 |
| render_levels | int | No | 3 |

---

## apply_modifier

**Description**: Apply (bake) a modifier on an object, making its effect permanent.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| modifier_name | str | Yes | - |

---
