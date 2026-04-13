# Category: Physics (9 skills)

## For Developers & LLM Agents

**Category**: Physics
**Description**: Rigid body, cloth, fluid simulation
**Total Skills**: 9

### When to Use This Category
For realistic simulation in animations

### Prerequisites
Understanding of physics simulation

### Common Workflow Sequence
```
[rigidbody_add] → [cloth_add] → [fluid_domain_create] → [bake_animation]
```

---

## Skills
## cloth_add

**Description**: Add cloth physics to a mesh object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| preset | str | No | 'COTTON' |

---

## cloth_bake

**Description**: Bake cloth simulation.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| start_frame | int | None | No |
| end_frame | int | None | No |

---

## cloth_pin_vertices

**Description**: Pin cloth vertices using vertex group.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| vertex_group | str | Yes | - |

---

## collision_add

**Description**: Add collision modifier to an object (for cloth, soft body, particles).

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| absorb | float | No | 0.0 |
| friction | float | No | 0.5 |

---

## fluid_bake

**Description**: Bake all fluid simulations in the scene.

| Parameter | Type | Required | Default |
|---|---|---|---|
| start_frame | int | None | No |
| end_frame | int | None | No |

---

## fluid_domain_create

**Description**: Create a fluid simulation domain.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| domain_type | str | No | 'FLUID' |
| resolution | int | No | 32 |

---

## fluid_effector_add

**Description**: Add a fluid effector (force field that affects fluid).

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| effector_type | str | No | 'GUIDE' |

---

## fluid_emitter_add

**Description**: Add a fluid emitter to an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| fluid_type | str | No | 'LIQUID' |
| volume_initialization | str | No | 'VOLUME' |

---
