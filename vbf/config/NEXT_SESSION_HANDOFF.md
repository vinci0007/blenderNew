# VBF Next Session Handoff

- Saved at: 2026-04-24 03:28:36 +08:00
- Branch: `main`
- HEAD: `df92cf0e00ea440980c9ee635ba0117bd34f28f4`

## Completed Work (Current Baseline)
- Configuration migration completed:
  - Runtime config file: `vbf/config/config.json` (local runtime)
  - Template config file: `vbf/config/config.json.example` (git tracked)
  - Runtime artifacts split to `vbf/cache` and `vbf/logs`
- Module layout refactor completed to domain packages:
  - `vbf/app`, `vbf/llm`, `vbf/feedback`, `vbf/core`, `vbf/runtime`, `vbf/transport`
  - Entrypoint switched to `vbf.app.cli:main`
- Root `vbf/` kept slim (`__init__.py`, `__main__.py`, `config_runtime.py` + subpackages)
- Last known full test status: `uv run pytest tests/ -q` => `270 passed`

## Current Runtime/Task Memory Files
- Task state: `vbf/cache/task_state.json`
- Last plan failure: `vbf/cache/last_plan_fail.txt`
- Last raw plan snapshot: `vbf/cache/last_plan_raw.txt`
- Last generation failure: `vbf/cache/last_gen_fail.txt`
- LLM cache dir: `vbf/cache/llm_cache`

## Current Task Snapshot
- Existing `task_state.json` currently has empty executable plan (`steps: []`)
- Last plan failure indicates non-executable steps after normalization
- Last raw plan snapshot exists and is available for next diagnosis

## Resume Instructions (Next Startup)
1. Confirm project interpreter:
   - `.venv\\Scripts\\python.exe -c "import openai; print('openai_ok')"`
2. If continuing prompt-based run, prefer file input (avoid multiline `--prompt` splitting in `Start-Process`):
   - `.venv\\Scripts\\python.exe -m vbf --port 28006 --prompt-file assets/prompt_test.md`
3. If plan still fails, collect and inspect:
   - `vbf/cache/last_plan_fail.txt`
   - `vbf/cache/last_plan_raw.txt`
   - `vbf/cache/task_state.json`
4. Regression check (fast):
   - `uv run pytest tests/test_config_runtime.py tests/test_client_plan_retry.py tests/test_client_plan_gate.py -q`

## Repo Working Tree Note
- Working tree is intentionally dirty with ongoing refactor-related edits/untracked files.
- Do not reset/clean blindly; continue from current state.

## Rule Reminder
- Temporary tests must be placed under: `tests/task_tmp/`
