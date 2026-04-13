# Category: Motion Tracking (12 skills)

## For Developers & LLM Agents

**Category**: Motion Tracking
**Description**: Camera and object tracking tools
**Total Skills**: 12

### When to Use This Category
For VFX integration

### Prerequisites
Video footage required

### Common Workflow Sequence
```
[tracking_load_clip] → [tracking_create_track] → [tracking_solve_camera]
```

---

## Skills
## tracking_add_plane_track

**Description**: Create a plane track from markers.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| name | str | No | 'Plane' |
| corners | List[List[float]] | No | [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]] |


---

## tracking_create_object

**Description**: Create 3D object solved from tracking data.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| track_names | List[str] | Yes | - |
| object_type | str | No | 'CUBE' |


---

## tracking_create_scene_from_clip

**Description**: Create a new scene with tracking setup.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| name | str | No | 'Tracking' |


---

## tracking_create_track

**Description**: Create a tracking marker in a clip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| marker_name | Optional[str] | No | None |
| frame | int | No | 1 |
| location | List[float] | No | [0.5, 0.5] |


---

## tracking_delete_track

**Description**: Delete a tracking track.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| track_name | str | Yes | - |


---

## tracking_list_tracks

**Description**: List all tracking tracks in a clip.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |


---

## tracking_load_clip

**Description**: Load a movie clip for motion tracking.

| Parameter | Type | Required | Default |
|---|---|---|---|
| filepath | str | Yes | - |
| name | Optional[str] | No | None |


---

## tracking_set_camera

**Description**: Set up camera from solved tracking data.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |


---

## tracking_set_track_pattern_size

**Description**: Set the pattern size for a tracking marker.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| track_name | str | Yes | - |
| size | int | No | 11 |


---

## tracking_solve_camera

**Description**: Solve camera motion from tracks.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |


---

## tracking_track_frame

**Description**: Track a marker to a specific frame.

| Parameter | Type | Required | Default |
|---|---|---|---|
| clip_name | str | Yes | - |
| track_name | str | Yes | - |
| frame | int | Yes | - |


---
