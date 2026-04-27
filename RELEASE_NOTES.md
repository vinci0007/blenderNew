# Release Notes

This file summarizes user-facing release highlights. Detailed patch history remains in `CHANGELOG.md` and `CHANGELOG_CN.md`.

Release automation uses `pyproject.toml` `[project].version` as the single version source. Versions use numeric `x.x.x` format, and each segment may contain multiple digits, such as `2.13.105`. Automatic GitHub Releases are created only for major/minor release versions where the first or second segment increases and the third segment is `0`, such as `1.0.0` or `1.1.0`; manual workflow runs may publish any numeric `x.x.x` project version.

## 2.3.2

Focus: staged planning reliability, task isolation, logs, and feedback stability.

Highlights:

- Added task-scoped logs and result snapshots under `vbf/logs/`.
- Added scene isolation so old task objects do not leak into new planning, feedback, or replan context by default.
- Made adaptive requirement assessment LLM-first in `auto` mode.
- Changed local simple-model checks into advisory evidence instead of a hard override.
- Clarified that `uv_texture_material` covers UVs, texture setup, simple color assignment, material assignment, and PBR/material presets.
- Reduced feedback Analyzer calls by grouping small plan-stage transitions into major/adaptive analysis stages.
- Added conservative repair for near-valid Analyzer JSON with missing closing brackets.
- Changed default prompt styling so no style template is prepended unless `--style` is passed explicitly.
- Added local autofix for `create_material_simple` plans missing `base_color`.
- Improved Blender diagnostics around modifier order and `remove_doubles` vertex merge reporting.

Validation:

- `uv run pytest tests/test_client_two_stage_planning.py -q`
- `uv run pytest tests/test_openai_compat_adapter_response_format.py tests/test_feedback_control_errors.py tests/test_feedback_system.py -q`

## 2.2

Focus: OpenAI-compatible adapter architecture and broader provider support.

Highlights:

- Introduced the unified OpenAI-compatible adapter path.
- Expanded support for multiple OpenAI-compatible providers and gateways.
- Added shared skill caching through a registry-style adapter flow.
- Improved response parsing and model-specific response path handling.
- Synced a broader skill surface into adapter-driven planning.

## 2.1

Focus: professional workflow foundations and feedback loops.

Highlights:

- Added the professional multi-stage modeling workflow baseline.
- Added the user feedback loop and checkpoint interactions.
- Added style templates and CLI style selection.
- Added memory management, LLM rate limiting, LLM cache, and WebSocket connection pooling.
