# Release Notes

This file summarizes user-facing release highlights. Detailed patch history remains in `CHANGELOG.md` and `CHANGELOG_CN.md`.

Release automation uses `pyproject.toml` `[project].version` as the single version source. Versions use numeric `x.x.x` format, and each segment may contain multiple digits, such as `2.13.105`. Automatic GitHub Releases are created only for major/minor release versions where the first or second segment increases and the third segment is `0`, such as `1.0.0` or `1.1.0`; manual workflow runs may publish any numeric `x.x.x` project version.

## 2.4.0

Focus: multimodal planning input, provider compatibility, safer Blender executor recovery, and release/license alignment.

Highlights:

- Added `--image` / `--image-file` so prompt text and one or more reference images can be sent together to vision-capable LLM providers.
- Added `auth_scheme = "auto" | "bearer" | "x-api-key"` so Anthropic Messages-compatible gateways such as LongCat can use Bearer authentication without changing the request-body protocol.
- Added executor health telemetry, `vbf.recover_executor`, client-side backpressure, and queued-job deadlines to recover stale Blender app-timer polling without interrupting an active skill.
- Made adaptive batch quality repair stage-aware, carrying future-stage gaps forward as pending work instead of repeatedly repairing the current geometry batch.
- Protected batch repair from deleting established parent/control objects that later repair steps still reference.
- Updated project package version, Blender addon version, planning protocol examples, tests, changelog, and release notes to `2.4.0`.
- Updated the license to a custom non-commercial license. Personal non-commercial use and personal secondary development are allowed, but personal derivative work must stay open source and retain original author, repository, and license attribution.
- Updated Blender 5.1 API docs compatibility checks so local extracted docs or `reference/blender_python_reference_5_1.zip` can be used, while missing reference docs skip cleanly in repositories that do not upload the docs bundle.

Validation:

- `uv run pytest tests/test_client_two_stage_planning.py tests/test_run_logging.py tests/test_openai_compat_adapter_response_format.py -q`
- `uv run pytest tests/test_cli_prompt_tokens.py tests/test_config_runtime.py tests/test_blender_51_api_docs_compat.py -q`

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
