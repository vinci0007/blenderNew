# Changelog

This project follows a Keep a Changelog style structure.

The entries below focus on meaningful user-facing, architecture, and workflow changes rather than listing every commit.

## [2.3.1] - 2026-04-27

### Added

- Added short task-scoped IDs such as `task_0426-151232_43b4d1a8` for new modeling requests.
- Added per-task transcript logs that mirror all console stdout/stderr to `vbf/logs/<task_id>.log`.
- Added daily plain-text run event logs at `vbf/logs/run_events_YYYYMMDD.log`.
- Added per-task structured result snapshots at `vbf/logs/task_result_<task_id>.json`.
- Added scene isolation controls through `[project.scene]` so old scene objects do not pollute new tasks by default.

### Changed

- Changed log formatting to favor short task-prefixed text lines for monitoring while keeping the final full task result in JSON.
- Changed task logging so the terminal output is not reduced or truncated and is mirrored as-is into the task transcript log.
- Changed planning, feedback, and replan scene context to use task-relevant objects by default while optionally preserving cameras/lights.
- Changed simple asset prompts such as "make a sofa 3D model" to stay in geometry-oriented planning unless downstream stages are explicitly requested.

### Fixed

- Fixed analyzer strict JSON failures so partial `quality`, `reason`, `score`, and `suggestions` can be recovered from failure payloads when possible.
- Fixed analyzer fallback behavior so parse failures no longer default to a misleading `"good"` assessment.
- Fixed replan schema failures for `create_material_simple` by auto-filling a neutral default `base_color`.
- Fixed modifier-application instability by moving the target modifier to the top before applying it and logging the reorder.
- Fixed poor `remove_doubles` observability by logging before/after vertex counts, removed counts, and large-merge warnings.
- Fixed false geometry warnings for `create_beveled_box` when the current capture level did not include vertex counts.

### Docs

- Updated README and README_CN with the new task logging model, scene isolation config, analyzer fallback behavior, and Blender diagnostics notes.

## [2.3.0] - 2026-04-26

### Added

- Added TOML-based runtime configuration via `vbf/config/config.toml`.
- Added a commented template at `vbf/config/config.toml.example`.
- Added requirement assessment before formal staged planning.
- Added adaptive staged planning as the primary planning path.
- Added capability-coverage based skill compression for stage-specific planning.
- Added planning capability probes for OpenAI-compatible gateways.
- Added local opt-in fallback controls for requirement assessment.
- Added workspace-local temporary config helpers in config/runtime tests to avoid fragile environment temp usage.
- Added `tests/task_tmp/conftest.py` so explicitly-invoked temporary tests can import the repo package cleanly.

### Changed

- Changed the default runtime config filename from legacy JSON to TOML.
- Changed README and README_CN to reflect the current architecture, runtime layout, and planning flow.
- Changed runtime artifact locations to consistently use `vbf/cache/` and `vbf/logs/`.
- Changed planning scope selection so deliverable stage selection is determined through requirement assessment rather than narrow stage keyword shortcuts alone.
- Changed planning context compression to preserve required capabilities before applying prompt budget trimming.
- Changed the local Blender launcher to prefer the repo-local addon by default.
- Changed addon self-check behavior from a TCP-only check to a WebSocket + JSON-RPC probe.
- Changed `tests/test_config_runtime.py` to use workspace-local temp directories instead of pytest `tmp_path`.
- Changed temporary test guidance so one-off tests stay in `tests/task_tmp/` and are run explicitly.

### Fixed

- Fixed Blender 5.1 render compatibility by falling back from unsupported render operator arguments to supported calls.
- Fixed geometry-only planning misclassification caused by style text, quality-contract text, and generic wording collisions.
- Fixed stage inference inconsistencies between initial planning and compressed planning paths.
- Fixed feedback capture attempting to read newly-created objects before they existed in the scene.
- Fixed plan normalization for `create_beveled_box` aliases such as `dimensions`, `width/height/depth`, and `position`.
- Fixed primitive normalization for enum variants such as `UV-Sphere`, `uv_sphere`, and `box`.
- Fixed OpenAI-compatible config loading to reject legacy JSON config filenames explicitly.
- Fixed TOML parsing issues in tests by aligning generated test data with valid TOML string constraints.
- Fixed `tests/task_tmp` explicit pytest runs so leftover runtime directories no longer break collection.

### Docs

- Rewrote the English README to match the current architecture and workflow.
- Rewrote the Chinese README to remove stale content and align with the current project state.
- Updated README references from JSON config files to TOML config files.
- Updated handoff/session notes to reflect the TOML migration and current testing status.

### Tests

- Added and updated regression coverage for:
  - staged requirement assessment behavior
  - stage-intent confidence and preservation behavior
  - TOML config loading and legacy-file rejection
  - request header parsing for OpenAI-compatible gateways
  - rate limiter config loading from nested TOML sections
  - Blender 5.1 API compatibility checks

## [2.2.0] - 2026-04-13

### Added

- Introduced the unified OpenAI-compatible adapter architecture.
- Expanded support for multiple OpenAI-compatible providers and gateways.
- Added shared skill caching through a registry-style adapter path.
- Synced a broader skill surface into the adapter-driven planning workflow.

### Changed

- Continued the migration away from a flatter adapter layout into a more reusable provider abstraction.
- Improved response parsing and model-specific response path handling.

### Fixed

- Fixed multiple documentation and skill-sync mismatches across generated skill references.

## [2.1.0] - 2026-04-12

### Added

- Added the 18-phase professional modeling workflow baseline.
- Added the user feedback loop system and checkpoint interactions.
- Added style templates and style selection through CLI options.
- Added memory management, LLM rate limiting, LLM cache, and WebSocket connection pooling.
- Added progress visualization modes for long-running workflows.

### Changed

- Refactored large parts of orchestration code into more focused supporting modules.

## [2.0.0] - 2026-04-11

### Added

- Added the four-layer closed-loop modeling control system.
- Added the foundations for LLM throttling, caching, and pooled transport.

### Removed

- Removed the old RadioTask-style hardcoded demo flow in favor of LLM-driven planning.

### Changed

- Shifted the project toward scene-aware replanning and more modular planning/runtime components.

## [1.5.0] - 2026-04-08

### Added

- Added rollback, resume, and repair-plan support for interrupted tasks.
- Expanded Blender 4.x / 5.x coverage and broadened skill coverage across more domains.

## [1.0.0] - 2026-04-01

### Added

- Initial release of Vibe-Blender-Flow.
- Established the Blender addon + Python client + LLM planning architecture.
