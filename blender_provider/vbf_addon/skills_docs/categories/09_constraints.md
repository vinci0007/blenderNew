# Category: Constraints (5 skills)

## For Developers & LLM Agents

**Category**: Constraints
**Description**: Object and bone constraints
**Total Skills**: 5

### When to Use This Category
For procedural animation or object relationships

### Prerequisites
Target and constraint source objects must exist

### Common Workflow Sequence
```
[add_constraint_copy_location] → [add_constraint_limit_location]
```

---

## Skills
## add_constraint_copy_location

**Description**: Add a Copy Location constraint to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| target_name | str | Yes | - |
| influence | float | No | 1.0 |
| use_x | bool | No | True |
| use_y | bool | No | True |
| use_z | bool | No | True |
| invert_x | bool | No | False |
| invert_y | bool | No | False |
| invert_z | bool | No | False |

---

## add_constraint_copy_rotation

**Description**: Add a Copy Rotation constraint to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| target_name | str | Yes | - |
| influence | float | No | 1.0 |
| use_x | bool | No | True |
| use_y | bool | No | True |
| use_z | bool | No | True |
| invert_x | bool | No | False |
| invert_y | bool | No | False |
| invert_z | bool | No | False |

---

## add_constraint_copy_scale

**Description**: Add a Copy Scale constraint to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| target_name | str | Yes | - |
| influence | float | No | 1.0 |
| use_x | bool | No | True |
| use_y | bool | No | True |
| use_z | bool | No | True |
| power | float | No | 1.0 |
| additive | bool | No | False |

---

## add_constraint_limit_location

**Description**: Add a Limit Location constraint.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| use_min_x | bool | No | False |
| min_x | float | No | 0.0 |
| use_max_x | bool | No | False |
| max_x | float | No | 0.0 |
| use_min_y | bool | No | False |
| min_y | float | No | 0.0 |
| use_max_y | bool | No | False |
| max_y | float | No | 0.0 |
| use_min_z | bool | No | False |
| min_z | float | No | 0.0 |
| use_max_z | bool | No | False |
| max_z | float | No | 0.0 |

---
