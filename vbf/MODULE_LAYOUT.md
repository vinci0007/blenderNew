# VBF Module Layout

This package is being refactored from a flat root layout into feature subpackages.

## Current Structure

- `vbf/llm/`
  - `openai_compat.py`: OpenAI-compatible client config and JSON call wrapper
  - `rate_limiter.py`: LLM throttle and retry policy
  - `cache.py`: LLM response cache (memory + disk)
  - `integration.py`: planning/repair message builders and plan generation helpers
- `vbf/feedback/`
  - `control.py`: closed-loop feedback controller
  - `geometry_capture.py`: incremental scene capture and geometry delta
  - `rules.py`: validation rule registry and built-in rules
  - `llm.py`: stage-boundary quality analyzer
  - `loop.py`: user feedback loop primitives
  - `ui.py`: console/programmatic feedback UI adapter
- `vbf/core/`
  - `task_state.py`: task resume/interruption state
  - `scene_state.py`: scene snapshot representation for feedback/planning
  - `plan_normalization.py`: LLM plan schema normalization/validation
  - `vibe_protocol.py`: `$ref` resolution and step-result compaction helpers
- `vbf/transport/`
  - `jsonrpc_ws.py`: JSON-RPC over WebSocket client
  - `connection_pool.py`: pooled concurrent WebSocket transport
- `vbf/runtime/`
  - `style_templates.py`: modeling style template registry and helpers
  - `memory_manager.py`: memory monitoring/cleanup utilities
  - `progress.py`: task progress visualization utilities
- `vbf/app/`
  - `client.py`: main orchestration client
  - `cli.py`: command-line entrypoint

## Migration Rule

- New logic should be placed by domain (e.g. LLM code in `vbf/llm`, feedback code in `vbf/feedback`).
- Avoid adding new feature modules back to `vbf/` root unless they are package-level exports or shared config/runtime loaders.
- Keep cross-domain imports explicit (for example `from vbf.llm.rate_limiter import ...`).

## Next Suggested Steps

- Optionally add temporary compatibility shims (`vbf/client.py`, `vbf/cli.py`) if external callers still depend on old import paths.
- Group addon-facing helpers and developer utilities under dedicated subpackages when they become stable.
