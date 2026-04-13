# Category: Asset (6 skills)

## For Developers & LLM Agents

**Category**: Asset
**Description**: Asset browser and management
**Total Skills**: 6

### When to Use This Category
For asset library management

### Prerequisites
Asset browser enabled

### Common Workflow Sequence
```
[asset_catalog_create] → [asset_mark] → [asset_set_metadata]
```

---

## Skills
## asset_catalog_create

**Description**: Create a new asset catalog.

| Parameter | Type | Required | Default |
|---|---|---|---|
| name | str | Yes | - |
| parent_path | str | No | '' |

---

## asset_clear

**Description**: Clear asset mark from an object.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |

---

## asset_list

**Description**: List all marked assets in the current file.

| Parameter | Type | Required | Default |
|---|---|---|---|
| - | - | - | - |

---

## asset_mark

**Description**: Mark an object as an asset.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| asset_type | str | No | 'OBJECT' |

---

## asset_set_metadata

**Description**: Set metadata for an asset.

| Parameter | Type | Required | Default |
|---|---|---|---|
| object_name | str | Yes | - |
| description | str | No | '' |
| author | str | No | '' |
| copyright | str | No | '' |
| license_type | str | No | '' |

---
