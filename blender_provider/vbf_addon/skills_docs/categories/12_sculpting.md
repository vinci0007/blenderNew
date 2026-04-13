# Category: Sculpting (10 skills)

## For Developers & LLM Agents

**Category**: Sculpting
**Description**: Digital sculpting tools
**Total Skills**: 10

### When to Use This Category
For organic modeling or high-poly detailing

### Prerequisites
Multiresolution or dynamic topology recommended

### Common Workflow Sequence
```
[dyntopo_enabled] → [set_sculpt_brush] → [sculpt_draw]
```

---

## Skills
## dyntopo_enabled

**Description**: Enable/disable dynamic topology sculpting.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| enable | bool | No | True |
| resolution | int | No | 100 |

---

## sculpt_crease

**Description**: Create crease/sharp edge in sculpt mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strength | float | No | 0.5 |

---

## sculpt_draw

**Description**: Apply draw brush sculpt strokes to mesh.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| locations | List[List[float]] | Yes | - |
| strength | float | No | 1.0 |

---

## sculpt_flatten

**Description**: Flatten mesh surface.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strength | float | No | 0.5 |

---

## sculpt_grab

**Description**: Grab/translate mesh surface in sculpt mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| grab_vector | List[float] | Yes | - |

---

## sculpt_inflate

**Description**: Inflate mesh surface outward.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strength | float | No | 0.5 |

---

## sculpt_layer

**Description**: Add/remove material layer in sculpt mode.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| height | float | No | 0.1 |

---

## sculpt_pinch

**Description**: Pinch mesh surface toward cursor.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| strength | float | No | 0.5 |

---

## sculpt_smooth

**Description**: Smooth mesh using sculpt smooth brush.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| iterations | int | No | 1 |

---
