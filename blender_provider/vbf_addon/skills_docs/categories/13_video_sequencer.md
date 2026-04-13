# Category: Video Sequencer (13 skills)

## For Developers & LLM Agents

**Category**: Video Sequencer
**Description**: Video editing and compositing timeline
**Total Skills**: 13

### When to Use This Category
For video editing within Blender

### Prerequisites
Media files loaded

### Common Workflow Sequence
```
[sequencer_create_scene] → [sequencer_add_movie_strip]
```

---

## Skills
## sequencer_add_effect_strip

**Description**: Add an effect strip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| effect_type | str | Yes | - |
| channel | int | Yes | - |
| frame_start | int | Yes | - |
| frame_end | int | Yes | - |
| strip1 | str | Yes | - |
| strip2 | Optional[str] | No | None |
| name | Optional[str] | No | None |


---

## sequencer_add_image_strip

**Description**: Add an image strip to the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| channel | int | No | 1 |
| frame_start | int | No | 1 |
| frame_end | Optional[int] | No | None |
| name | Optional[str] | No | None |


---

## sequencer_add_movie_strip

**Description**: Add a movie strip to the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| channel | int | No | 1 |
| frame_start | int | No | 1 |
| name | Optional[str] | No | None |


---

## sequencer_add_sound_strip

**Description**: Add a sound strip to the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| channel | int | No | 2 |
| frame_start | int | No | 1 |
| name | Optional[str] | No | None |


---

## sequencer_add_text_strip

**Description**: Add a text strip to the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| text | str | Yes | - |
| channel | int | No | 3 |
| frame_start | int | No | 1 |
| frame_end | int | No | 25 |
| name | Optional[str] | No | None |


---

## sequencer_create_scene

**Description**: Create a new scene configured for video editing.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | No | 'Video Sequence Editor' |
| width | int | No | 1920 |
| height | int | No | 1080 |
| fps | int | No | 24 |


---

## sequencer_delete_strip

**Description**: Delete a strip from the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_name | str | Yes | - |


---

## sequencer_list_strips

**Description**: List all strips in the sequencer.

| Parameter | Type | Required | Default |
|---|---|---|---|
| channel | int | No | - |



---

## sequencer_meta_strip_create

**Description**: Create a meta strip from multiple strips.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_names | List[str] | Yes | - |
| name | str | No | 'Meta' |


---

## sequencer_set_strip_opacity

**Description**: Set opacity for a strip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_name | str | Yes | - |
| opacity | float | Yes | - |


---

## sequencer_set_strip_position

**Description**: Move a strip to new position.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_name | str | Yes | - |
| channel | int | Yes | - |
| frame_start | int | Yes | - |


---

## sequencer_set_strip_volume

**Description**: Set volume for a sound strip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| strip_name | str | Yes | - |
| volume | float | Yes | - |


---
