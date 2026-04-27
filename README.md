# Vibe-Blender-Flow (VBF)

Natural-language driven Blender modeling with staged planning, schema-aware skill execution, and feedback-guided recovery.

**[中文](README_CN.md)** | **English**

**[Changelog](CHANGELOG.md)** | **[更新日志](CHANGELOG_CN.md)** | **[Release Notes](RELEASE_NOTES.md)**

[![License](https://img.shields.io/badge/License-TBD-lightgray.svg)](LICENSE)
[![Blender](https://img.shields.io/badge/Blender-4.0%2B%20%7C%205.x-orange.svg)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-maintained-brightgreen.svg)]()
[![Stars](https://img.shields.io/github/stars/vinci-0007/vibe-blender-flow)](https://github.com/vinci-0007/vibe-blender-flow/stars)

## Example

![LLM creates a cellphone model](assets/llm_cellphone.gif)

## Overview

VBF turns a text prompt into executable Blender operations through three layers:

1. A Blender addon exposes hundreds of atomic modeling skills through a controlled API.
2. A Python client talks to Blender over WebSocket JSON-RPC and manages retries, recovery, state, and logging.
3. An OpenAI-compatible planning layer converts prompts into validated skill plans instead of free-form code.

This keeps the workflow inspectable, resumable, and much easier to debug than direct script generation.

## Recent Updates

- Added task-scoped logging with short task IDs such as `task_0426-151232_43b4d1a8`.
- Added per-task transcript logs that mirror all console stdout/stderr without truncating terminal output.
- Added a daily plain-text run event log plus a separate per-task result JSON snapshot.
- Added scene isolation controls so old objects do not leak into planning, feedback, and replan context by default.
- Changed requirement assessment to stay LLM-first in `auto` mode; local simple-model checks now act as advisory evidence instead of overriding explicit downstream requirements.
- Clarified that the `uv_texture_material` stage includes UVs, texture setup, simple color assignment, material assignment, and PBR/material presets.
- Added conservative analyzer JSON repair for near-valid LLM responses with missing closing brackets.
- Reduced feedback Analyzer calls by grouping sub-stage transitions into major/adaptive analysis stages.
- Added local autofix for `create_material_simple` plans missing `base_color`.
- Improved Blender diagnostics around modifier application order and `remove_doubles` vertex merge reporting.

## Current Architecture

The codebase is organized by domain instead of a flat root layout:

- `vbf/app/`: CLI entrypoint and main orchestration client
- `vbf/adapters/`: model adapters and provider-facing request shaping
- `vbf/llm/`: OpenAI-compatible config loading, rate limiting, caching, and planning helpers
- `vbf/feedback/`: capture, validation, stage analysis, and recovery control
- `vbf/core/`: task state, scene state, plan normalization, and protocol helpers
- `vbf/runtime/`: styles, logging, memory management, and progress helpers
- `vbf/transport/`: JSON-RPC WebSocket transport and connection pooling
- `blender_provider/vbf_addon/`: Blender addon and skill implementations

For a more detailed breakdown, see [vbf/MODULE_LAYOUT.md](vbf/MODULE_LAYOUT.md).

## Requirements

- Python `>= 3.13`
- Blender `4.0+` or `5.x`
- `uv` recommended for local development and test execution

## Quick Start

### 1. Install Python dependencies

```bash
uv sync
```

### 2. Configure the LLM

Create `vbf/config/config.toml` from the example:

```toml
[project.paths]
cache_dir = "vbf/cache"
logs_dir = "vbf/logs"
task_state_file = "vbf/cache/task_state.json"
last_gen_fail_file = "vbf/cache/last_gen_fail.txt"
last_plan_fail_file = "vbf/cache/last_plan_fail.txt"
last_plan_raw_file = "vbf/cache/last_plan_raw.txt"
llm_cache_dir = "vbf/cache/llm_cache"

[project.scene]
task_scene_policy = "isolate"
include_environment_objects = true

[llm]
use_llm = true
base_url = "https://api.openai.com/v1"
api_key = "YOUR_API_KEY"
model = "gpt-4o-mini"
temperature = 0.2
planning_mode = "adaptive_staged"

[llm.planning_context]
compression_mode = "capability_coverage"
target_prompt_budget_chars = 18000

[llm.requirement_assessment]
mode = "auto"
enable_local_fallback = false
prefer_geometry_for_simple_model_requests = true

[llm.planning_capability_probe]
enabled = true
timeout_seconds = 20
cache_ttl_seconds = 3600

[llm.llm_api_throttling]
max_concurrent_calls = 3
max_calls_per_minute = 20
call_timeout_seconds = 600
```

The full commented template lives at [vbf/config/config.toml.example](vbf/config/config.toml.example).

### 3. Install and start the Blender addon

1. Copy `blender_provider/vbf_addon/` into Blender's addon directory, or install it as a zip/package in Blender.
2. Enable `Vibe-Blender-Flow (VBF)` in Blender Preferences.
3. Start the VBF server from the addon panel.

By default, the local launcher prefers the repo-local addon copy. Set `VBF_PREFER_INSTALLED_ADDON=1` if you explicitly want the previously installed addon instead.
If you want VBF to auto-launch Blender headlessly, make sure Blender is on `PATH`, or pass `--blender-path`, or set `BLENDER_PATH` to the executable location.

### 4. Run a task

```bash
uv run python -m vbf --prompt "create a retro radio"
uv run python -m vbf --prompt-file assets/prompt_test.md
uv run python -m vbf --prompt "create a smartphone" --style hard_surface_realistic
```

### 5. Resume a saved task

```bash
uv run python -m vbf --prompt "continue" --resume vbf/cache/task_state.json
```

## Planning Pipeline

The current default planning flow is:

1. Assess the user's real deliverable scope, with LLM results preferred when the LLM is available.
2. Select stages such as geometry, UV/material, lighting, animation, or render.
3. Use local evidence as an advisory conflict check; severe requirement conflicts are resolved by a second LLM pass.
4. Compress the skill set per stage using required capabilities rather than a naive top-k list.
5. Ask the LLM for a structured plan.
6. Normalize and validate arguments against skill schemas.
7. Execute with feedback capture, local replan, resumable task state, and task-scoped logging.

This helps avoid common failure modes such as:

- asking for render skills during a geometry-only task
- dropping explicit material/color, lighting, animation, or render requirements from simple asset prompts
- dropping required modeling capabilities during context compression
- using unsupported tool/JSON modes on proxy gateways
- emitting malformed or underspecified skill arguments
- letting unrelated scene leftovers contaminate a new modeling request

## OpenAI-Compatible Provider Support

VBF uses a single OpenAI-compatible integration path for multiple providers and gateways. Typical examples include:

- OpenAI
- GLM / BigModel
- Moonshot / Kimi
- DashScope / Qwen
- MiniMax
- Ollama
- custom OpenAI-compatible gateways

Provider behavior can be tuned through `base_url`, `chat_completions_path`, proxy flags, extra request headers, and capability probes in `config.toml`.

## Runtime Files

Runtime-generated artifacts are kept out of source directories and are split by purpose:

- `vbf/cache/`: task state, plan snapshots, last raw failure payloads, and LLM disk cache
- `vbf/logs/run_events_YYYYMMDD.log`: daily plain-text event log for monitoring and tailing
- `vbf/logs/task_MMDD-HHMMSS_<id>.log`: per-task transcript log that mirrors all console output
- `vbf/logs/task_result_task_MMDD-HHMMSS_<id>.json`: final structured result snapshot for that task

Notes:

- A task ID is created once for the user's initial modeling request and is reused through feedback, replan, and recovery within that same task.
- Console output stays unchanged in the terminal and is also mirrored into the task transcript log.
- The daily event log is plain text by design for easier grep/tail/monitor workflows, while the final task result stays as JSON.

## Development

### Run the main test suite

```bash
uv run pytest tests/ -q
```

### Run targeted tests

```bash
uv run pytest tests/test_config_runtime.py tests/test_client_two_stage_planning.py -q
```

### Temporary test policy

- Keep stable regression tests in `tests/`.
- Put one-off diagnostics and temporary task-specific scripts under `tests/task_tmp/`.
- Default pytest discovery ignores `tests/task_tmp/`.
- Run a temporary test explicitly when needed, for example:

```bash
python -m pytest tests/task_tmp/test_example.py -q
```

## Release Notes And Version Source

- User-facing release highlights live in [RELEASE_NOTES.md](RELEASE_NOTES.md).
- `pyproject.toml` `[project].version` is the single version source and uses numeric `x.x.x` format.
- Each numeric segment may contain multiple digits, such as `2.13.105`.
- Automatic GitHub Releases are created only for major/minor release versions where the first or second segment increases and the third segment is `0`, such as `v1.0.0` or `v1.1.0`.
- Manual GitHub Release workflow runs may publish any numeric `x.x.x` project version, including patch versions such as `v1.1.1`.
- Patch versions where the third segment is greater than `0`, such as `v1.1.1`, are changelog-only unless released manually.
- When preparing a new `x.y.0` release, update `pyproject.toml` and the matching `RELEASE_NOTES.md` section together.

## Troubleshooting

| Issue | What to check |
|---|---|
| Blender connection fails | Confirm the addon is running and the WebSocket endpoint is available |
| Health check says running but tasks still hang | Restart the addon and verify the WebSocket + JSON-RPC probe succeeds |
| LLM config not loading | Use `vbf/config/config.toml`, not legacy JSON config files |
| A new task keeps mentioning old unrelated objects | Keep `[project.scene].task_scene_policy = "isolate"` so only task-relevant objects are sent into planning/feedback context |
| Simple prompts lose explicit colors/materials/render intent | Requirement assessment is LLM-first; keep `llm.requirement_assessment.prefer_geometry_for_simple_model_requests = true` as advisory evidence, not as a hard local override |
| Analyzer reports `LLM parse error` | Check `vbf/cache/last_gen_fail.txt`; recent versions repair simple missing JSON closers and recover partial quality fields before falling back to manual inspection |
| `plan_gate_missing_required ... create_material_simple missing arg=base_color` appears during replan | Recent versions auto-fill a neutral default `base_color`; upgrade if you still see hard failures |
| Blender prints "applied modifier is not first" warnings | VBF now moves the target modifier to the top before applying and logs the reorder for traceability |
| `remove_doubles` deletes an unexpectedly large number of vertices | Inspect the task log for before/after vertex counts and large-merge warnings before continuing |
| Need to resume a failed run | Use `--resume vbf/cache/task_state.json` |

## Additional References

- [CHANGELOG.md](CHANGELOG.md)
- [CHANGELOG_CN.md](CHANGELOG_CN.md)
- [vbf/MODULE_LAYOUT.md](vbf/MODULE_LAYOUT.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [blender_provider/vbf_addon/skills_docs/SKILL.md](blender_provider/vbf_addon/skills_docs/SKILL.md)

## License

TBD. See [LICENSE](LICENSE).
