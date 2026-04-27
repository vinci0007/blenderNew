# OpenAI Compatible Adapter
"""Universal adapter for all OpenAI-compatible APIs.

Implements progressive disclosure pattern (Anthropic/Claude Skill model):
- 启动时: Only skill metadata (name + description) in system prompt
- 触发时: LLM calls load_skill() tool to get full schema on demand
- 执行时: Uses loaded schema to generate correct plan JSON

Reference: CSDN "Skill原理及国内大模型实践" + Anthropic Agent Skills

Configuration-driven (no hardcoded model branches).
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
import json
import os
import re
import time

from .base_adapter import VBFModelAdapter
from .streaming_chat_completion_aggregator import (
    StreamingChatCompletionAggregator,
    iter_sse_json_chunks,
)
from ..llm.openai_compat import (
    _build_chat_completions_url,
    _parse_bool_field,
    _resolve_request_headers,
)

if TYPE_CHECKING:
    from ..app.client import VBFClient


class OpenAICompatAdapter(VBFModelAdapter):
    """Universal adapter for all OpenAI-compatible APIs.

    Uses configuration from SUPPORTED_MODELS for:
    - API endpoint (base_url)
    - Authentication (api_key_env)
    - Response format (response_content_path)
    - Streaming support

    Skills are loaded from Blender via SkillRegistry singleton.

    Progressive disclosure: Only metadata in prompt, full schema via
    load_skill() tool when LLM needs it.
    """
    _COMPAT_MODE_CACHE: Dict[str, Dict[str, Any]] = {}

    class _CompatHTTPError(RuntimeError):
        def __init__(self, status_code: int, message: str):
            super().__init__(message)
            self.status_code = status_code
            self.message = message

    def __init__(
        self,
        model_name: str,
        model_config: Dict[str, Any],
        client: Optional["VBFClient"] = None,
    ):
        super().__init__(client, model_config)
        self.model_name = model_name

        # Load configuration from model_config
        self.base_url = model_config.get("base_url", "")
        self.default_model = model_config.get("default_model", model_name)
        self.chat_completions_path = model_config.get(
            "chat_completions_path", "/chat/completions"
        )
        self.response_format = model_config.get("response_format", {})
        self.supports_streaming = model_config.get("supports_streaming", False)
        self.few_shot_required = model_config.get("few_shot_required", False)
        self.skills_subset_limit = model_config.get("skills_subset_limit", 0)
        self.temperature = model_config.get("temperature", 0.2)
        self.planning_context = (
            model_config.get("planning_context", {})
            if isinstance(model_config.get("planning_context"), dict)
            else {}
        )
        self.planning_capability_probe = (
            model_config.get("planning_capability_probe", {})
            if isinstance(model_config.get("planning_capability_probe"), dict)
            else {}
        )

        # Progressive disclosure: use function calling for on-demand skill loading
        use_function_calling = model_config.get("use_function_calling", True)
        if isinstance(use_function_calling, str):
            normalized_mode = use_function_calling.strip().lower()
            self.use_function_calling = normalized_mode in {"1", "true", "on", "auto"}
            self.function_calling_mode = normalized_mode
        else:
            self.use_function_calling = bool(use_function_calling)
            self.function_calling_mode = "true" if self.use_function_calling else "false"

        use_streaming = model_config.get("use_streaming", "auto")
        if isinstance(use_streaming, str):
            normalized_mode = use_streaming.strip().lower()
            self.use_streaming = normalized_mode in {"1", "true", "on", "auto"}
            self.streaming_mode = normalized_mode
        else:
            self.use_streaming = bool(use_streaming)
            self.streaming_mode = "true" if self.use_streaming else "false"

        # Configurable response content path (supports dot notation)
        self.response_content_path = model_config.get(
            "response_content_path", "choices[0].message.content"
        )

        # Resolve API key
        self.api_key = model_config.get("api_key")
        if not self.api_key:
            api_key_env = model_config.get("api_key_env", [])
            if isinstance(api_key_env, str):
                api_key_env = [api_key_env]
            self.api_key = self._resolve_api_key(api_key_env)
        self.is_proxy_api = _parse_bool_field(model_config, "is_proxy_api", False)
        self.enable_extra_request_headers = _parse_bool_field(
            model_config, "enable_extra_request_headers", False
        )
        self.use_curl_http_compat = _parse_bool_field(model_config, "use_curl_http_compat", False)
        self.http_timeout_seconds = float(model_config.get("http_timeout_seconds", 60.0))
        self.request_headers = _resolve_request_headers(
            model_config.get("request_headers"),
            is_proxy_api=self.is_proxy_api,
            enable_extra_request_headers=self.enable_extra_request_headers,
        )

        # Runtime compatibility mode (provider-specific, cached in-process).
        self._compat_mode_key = f"{self.base_url}|{self.default_model}"
        default_allow_json = self.response_format.get("type") == "json_object"
        default_allow_tools = bool(self.use_function_calling)
        default_allow_streaming = bool(self.use_streaming and self.supports_streaming)
        cached = self._COMPAT_MODE_CACHE.get(self._compat_mode_key, {})
        self._allow_json_object = bool(cached.get("allow_json_object", default_allow_json))
        self._allow_tools = bool(cached.get("allow_tools", default_allow_tools))
        self._allow_streaming = bool(cached.get("allow_streaming", default_allow_streaming))
        self._compat_mode_logged = False

    def _resolve_api_key(self, env_vars: List[str]) -> Optional[str]:
        """Get API key from environment variables."""
        for var in env_vars:
            key = os.getenv(var)
            if key:
                return key
        return None

    def _extract_by_path(self, data: Any, path: str) -> Optional[Any]:
        """Extract value from nested dict using dot notation path.

        Supports:
        - Literal key with brackets: {'choices[0].message.content': val}
        - Nested path: data.choices[0].message.content
        """
        if not isinstance(data, dict):
            return None

        # 1. Try literal key lookup first (handles keys like 'choices[0].message.content')
        if path in data:
            return data.get(path)

        # 2. Split path by dots, treating [N] as array index notation
        # e.g. "choices[0].message.content" -> ['choices', '[0]', 'message', 'content']
        # e.g. "data.choices[0].content" -> ['data', 'choices', '[0]', 'content']
        # Strategy: split on dots, BUT when we hit a [ collect up to the matching ]
        # as a single token.
        parts = []
        i = 0
        while i < len(path):
            if path[i] == '.':
                # End current segment
                parts.append('')
                i += 1
            elif path[i] == '[':
                # Collect the [N] token
                token = ''
                while i < len(path) and path[i] != '.':
                    token += path[i]
                    i += 1
                parts.append(token)
            else:
                # Regular chars - accumulate until dot or bracket
                token = ''
                while i < len(path) and path[i] not in '.[':
                    token += path[i]
                    i += 1
                parts.append(token)
        # Filter empty parts
        parts = [p for p in parts if p]

        # Navigate the path
        current = data
        for part in parts:
            if current is None:
                return None
            # Check if part is an array index: [N] where N is digits
            if re.match(r'^\[-?\d+\]$', part):
                idx = int(part[1:-1])
                current = current[idx] if isinstance(current, list) else None
            else:
                current = current.get(part) if isinstance(current, dict) else None

        return current


    # --- Progressive disclosure: skill metadata only ---

    def list_skill_summaries(self) -> Dict[str, str]:
        """Get skill name -> one-line description mapping.

        This is the "metadata" layer: minimal info for system prompt.
        LLM uses this to decide which skills to load in detail.
        """
        summaries = {}
        for skill_name in self.list_available_skills():
            skill = self.get_skill_full(skill_name)
            if skill:
                desc = skill.get("description", "").split("\n")[0].strip()
                summaries[skill_name] = desc[:80] if desc else "No description"
            else:
                summaries[skill_name] = "No description"
        return summaries

    def _get_skills_for_prompt(self) -> List[str]:
        """Get skills to include in system prompt.

        For small models (like Ollama), limit to subset to save tokens.
        """
        all_skills = self.list_available_skills()

        if self.skills_subset_limit > 0 and len(all_skills) > self.skills_subset_limit:
            return all_skills[: self.skills_subset_limit]

        return all_skills

    def _format_skill_metadata(self, skill_name: str, description: str) -> str:
        """Format a single skill metadata line (name + description only).

        This is the lightweight "启动时" layer - no params, just name+desc.
        """
        return f"- **{skill_name}**: {description}"

    @staticmethod
    def _normalize_type_hint(type_hint: Any) -> str:
        raw = str(type_hint or "any").lower()
        if "int" in raw:
            return "int"
        if "float" in raw or "double" in raw:
            return "float"
        if "bool" in raw:
            return "bool"
        if "dict" in raw or "mapping" in raw:
            return "dict"
        if "list" in raw or "tuple" in raw or "sequence" in raw:
            return "list"
        if "str" in raw or "string" in raw:
            return "str"
        return "any"

    def _build_schema_cards(self, skills_to_include: List[str], max_cards: int = 12) -> str:
        include_all = bool(
            self.planning_context.get("include_compact_schema_for_required", False)
            or self.planning_context.get("include_compact_schema_for_high_risk", False)
            or self.planning_context.get("include_compact_schema_for_all_retained_skills", False)
        )
        if include_all:
            max_cards = len(skills_to_include)

        cards: List[str] = []
        for skill_name in skills_to_include[:max_cards]:
            skill = self.get_skill_full(skill_name) or {}
            args = skill.get("args")
            if not isinstance(args, dict):
                continue

            required_fields: List[str] = []
            optional_fields: List[str] = []
            for param_name, param_info in args.items():
                if not isinstance(param_name, str):
                    continue
                info = param_info if isinstance(param_info, dict) else {}
                type_hint = self._normalize_type_hint(info.get("type"))
                field_repr = f"{param_name}:{type_hint}"
                if info.get("required") is True:
                    required_fields.append(field_repr)
                else:
                    optional_fields.append(field_repr)

            req_txt = ", ".join(required_fields[:8]) if required_fields else "none"
            opt_txt = ", ".join(optional_fields[:8]) if optional_fields else "none"
            cards.append(f"- {skill_name} | required: {req_txt} | optional: {opt_txt}")

        if not cards:
            return ""
        return (
            "## Compact Skill Signatures\n"
            "Use these function names and argument signatures exactly:\n"
            + "\n".join(cards)
        )

    def build_system_prompt(
        self, skills_subset: Optional[List[str]] = None
    ) -> str:
        """Build system prompt with progressive disclosure.

        Phase 1 (启动时): Only skill metadata (name + description).
        No detailed parameters - LLM decides which to load via load_skill().

        Args:
            skills_subset: Optional specific skills to include
        """
        if skills_subset:
            skills_to_include = skills_subset
        else:
            skills_to_include = self._get_skills_for_prompt()

        summaries = self.list_skill_summaries()

        # Format skill metadata list (lightweight)
        skills_text = "\n".join(
            self._format_skill_metadata(name, summaries.get(name, ""))
            for name in skills_to_include
            if name in summaries
        )

        # Progressive disclosure instruction
        tool_instruction = ""
        if self.use_function_calling:
            tool_instruction = """
## Progressive Disclosure (渐进式披露)

当需要某个技能的详细参数时，调用 **load_skill(skill_name)** 工具获取完整说明。
加载后，你可以看到该技能的参数类型、是否必填、默认值等信息。
不要猜测不熟悉的技能参数，先调用 load_skill 了解清楚再生成计划。
"""

        schema_cards = ""
        if not self.use_function_calling or not self._allow_tools:
            schema_cards = self._build_schema_cards(
                skills_to_include,
                max_cards=int(self._model_config.get("schema_cards_limit", 12)),
            )

        base_prompt = f"""You are VBF (Vibe-Blender-Flow), a professional Blender 3D modeling assistant.

## Core Rules
1. **Output JSON only** - Never output Python/bpy/bmesh code directly
2. **Use only available skills** - Validate skill names against the defined list
3. **Context references** - Use $ref to reference previous step results: {{"$ref": "step_001.data.object_name"}}
4. **Parameters** - Required params must be provided; optional params use defaults
5. **load_skill is NOT a Blender skill** - It is a documentation query tool only. Never use "load_skill" as the "skill" value in plan steps. Only use it via the function_calling tool to query skill documentation.
6. **Parent-Child Constraint** - When creating accessories (buttons, holes, ports, camera lenses, etc.), use **set_parent** to attach them to the main body. Format: {{"child_name": {{"$ref": "step_xxx.data.object_name"}}, "parent_name": {{"$ref": "step_001.data.object_name"}}}}
7. **No hardcoded object names in assembly** - For relationship skills like set_parent/constraints/material assignment, do not hardcode names like "CameraModule". Always reference names from prior step outputs via $ref.
8. **Creation before reference** - Every referenced object must be created in an earlier step. If a child/parent object is not explicitly created earlier, add creation steps first.
{tool_instruction}
{schema_cards}
## Available Skills ({len(skills_to_include)} total)
{skills_text}

## Output Format
```json
{{
  "vbf_version": "2.1",
  "plan_type": "skills_plan",
  "steps": [
    {{
      "step_id": "001",
      "stage": "primitive_blocking",
      "skill": "skill_name",
      "args": {{"param": "value"}},
      "$comment": "optional explanation"
    }}
  ]
}}
```

## Workflows
- Blocking: create_primitive -> object_select_all -> scale_object -> move_object
- Beveling: create_primitive -> add_modifier_bevel -> apply_modifier
- Assembly: create_body -> create_component -> set_parent (repeat for each component)
- UV Setup: select_edge_ring -> mark_seam -> unwrap_mesh -> pack_uv_islands"""

        # Add few-shot examples for small models
        if self.few_shot_required:
            base_prompt += """
## Examples

**User:** "Create a cube"
```json
{"vbf_version":"2.1","plan_type":"skills_plan","steps":[{"step_id":"001","skill":"create_primitive","args":{"primitive_type":"cube","name":"Cube","location":[0,0,0]}}]}
```

**User:** "Add bevel to MixingGlass"
```json
{"vbf_version":"2.1","plan_type":"skills_plan","steps":[{"step_id":"001","skill":"add_modifier_bevel","args":{"object_name":"MixingGlass","width":0.02,"segments":4}}]}

**User:** "Create a smooth sphere"
```json
{"vbf_version":"2.1","plan_type":"skills_plan","steps":[{"step_id":"001","skill":"create_primitive","args":{"primitive_type":"uv_sphere","name":"Sphere"}},{"step_id":"002","skill":"object_shade_smooth","args":{"object_name":"Sphere"}}]}

**User:** "Create a phone with power button"
```json
{"vbf_version":"2.1","plan_type":"skills_plan","steps":[{"step_id":"001","skill":"create_primitive","args":{"name":"phone","scale":[0.1,0.2,0.01]}},{"step_id":"002","skill":"create_primitive","args":{"name":"power_btn","location":[0.06,0,0]}},{"step_id":"003","skill":"set_parent","args":{"child_name":{"$ref":"002.data.object_name"},"parent_name":{"$ref":"001.data.object_name"}}}]}
```"""

        return base_prompt

    # --- Function calling: tools for LLM ---

    def load_skill(self, skill_name: str) -> Dict[str, Any]:
        """Load full skill schema (trigger-time loading).

        This is the "触发时" layer: returns complete skill documentation
        including parameters, types, defaults, and full docstring.

        Called by LLM via function_calling when it needs skill details.
        """
        skill = self.get_skill_full(skill_name)
        if not skill:
            return {
                "error": f"Skill '{skill_name}' not found",
                "available_skills": self.list_available_skills()[:10],
            }

        args = skill.get("args", {})
        params = {}
        required = []

        for param_name, param_info in args.items():
            if param_name == "self":
                continue
            is_required = param_info.get("required", False)
            param_type = param_info.get("type", "any")
            default = param_info.get("default")

            params[param_name] = {
                "type": param_type if param_type != "any" else "string",
                "description": f"{'[Required] ' if is_required else '[Optional] '}"
                f"default={default}" if default and not is_required else "",
            }
            if is_required:
                required.append(param_name)

        return {
            "skill_name": skill_name,
            "description": skill.get("description", ""),
            "doc": skill.get("doc", ""),
            "parameters": params,
            "required": required,
            "example": f"skill: {skill_name}, args: {{{', '.join(repr(r) for r in required)}}}",
        }

    def build_tools_for_llm(self) -> List[Dict[str, Any]]:
        """Build JSON Schema tool definitions for function calling.

        This is the "trigger layer" - LLM uses these tools to load
        skill details on demand (progressive disclosure).

        Returns:
            List of tool definitions matching OpenAI tool_calls format.
        """
        # load_skill tool: on-demand skill schema loading
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "load_skill",
                    "description": (
                        "加载指定技能的完整参数说明和文档。当你不确定某个技能的"
                        "参数类型、是否必填、或默认值时，先调用此工具获取详细信息。"
                        "返回技能名称、描述、所有参数（含类型/是否必填/默认值）和示例调用。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "description": (
                                    "技能名称，如 'create_primitive', 'add_modifier_bevel', "
                                    "'unwrap_mesh' 等。从 Available Skills 列表中选择。"
                                ),
                            }
                        },
                        "required": ["skill_name"],
                    },
                },
            }
        ]

        return tools

    def build_api_request(
        self, messages: List[Dict], stream: bool = False,
        tools: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Build API request body for OpenAI-compatible endpoint.

        Args:
            messages: Formatted messages
            stream: Whether to request streaming response
            tools: Optional list of tool definitions for function calling
        """
        request: Dict[str, Any] = {
            "model": self.default_model,
            "messages": messages,
            "temperature": self.temperature,
        }

        # Add tools for function calling (progressive disclosure)
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"

        # Add response_format when configured; streaming compatibility is probed separately.
        if self.response_format.get("type") == "json_object":
            request["response_format"] = {"type": "json_object"}

        # Add streaming flag if supported
        if stream and self.supports_streaming:
            request["stream"] = True

        return request

    def _persist_compat_mode(self) -> None:
        cached = dict(self._COMPAT_MODE_CACHE.get(self._compat_mode_key, {}))
        cached.update(
            {
                "allow_json_object": bool(self._allow_json_object),
                "allow_tools": bool(self._allow_tools),
                "allow_streaming": bool(self._allow_streaming),
            }
        )
        self._COMPAT_MODE_CACHE[self._compat_mode_key] = cached

    def _probe_enabled(self) -> bool:
        raw = self.planning_capability_probe.get("enabled", True)
        if isinstance(raw, str):
            return raw.strip().lower() not in {"0", "false", "no", "off"}
        return bool(raw)

    def _probe_timeout_seconds(self) -> float:
        try:
            return max(1.0, float(self.planning_capability_probe.get("timeout_seconds", 20)))
        except Exception:
            return 20.0

    def _probe_ttl_seconds(self) -> float:
        try:
            return max(0.0, float(self.planning_capability_probe.get("cache_ttl_seconds", 3600)))
        except Exception:
            return 3600.0

    def _compat_probe_cache_valid(self) -> bool:
        cached = self._COMPAT_MODE_CACHE.get(self._compat_mode_key, {})
        checked_at = cached.get("probe_checked_at")
        if not isinstance(checked_at, (int, float)):
            return False
        ttl = self._probe_ttl_seconds()
        return ttl > 0 and (time.time() - float(checked_at)) <= ttl

    def _mark_compat_probe_checked(self) -> None:
        cached = dict(self._COMPAT_MODE_CACHE.get(self._compat_mode_key, {}))
        cached.update(
            {
                "allow_json_object": bool(self._allow_json_object),
                "allow_tools": bool(self._allow_tools),
                "allow_streaming": bool(self._allow_streaming),
                "probe_checked_at": time.time(),
            }
        )
        self._COMPAT_MODE_CACHE[self._compat_mode_key] = cached

    def _maybe_probe_compatibility_sync(self, openai_cls: Any) -> None:
        """For auto mode, test tools/json support with a tiny request before planning."""
        if not self._probe_enabled():
            return
        should_probe_tools = self.function_calling_mode == "auto"
        should_probe_streaming = (
            self.streaming_mode == "auto"
            and self.use_streaming
            and self.supports_streaming
        )
        if not should_probe_tools and not should_probe_streaming:
            return
        if self._compat_probe_cache_valid():
            return

        probe_messages = [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": '{"ok": true}'},
        ]
        probe_tools = self.build_tools_for_llm() if self.use_function_calling else None
        allow_tools = bool(probe_tools) and bool(self._allow_tools)
        allow_json_object = bool(self._allow_json_object)
        client = None
        timeout_seconds = self._probe_timeout_seconds()
        if not self.use_curl_http_compat:
            client = openai_cls(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=self.request_headers or None,
                timeout=timeout_seconds,
            )

        try:
            if should_probe_tools:
                for _ in range(3):
                    request_body = self._build_api_request_with_mode(
                        probe_messages,
                        probe_tools,
                        allow_tools=allow_tools,
                        allow_json_object=allow_json_object,
                    )
                    try:
                        if self.use_curl_http_compat:
                            response = self._post_chat_completions_http(
                                request_body,
                                timeout_seconds=timeout_seconds,
                            )
                        else:
                            response = client.chat.completions.create(**request_body)
                    except Exception as e:
                        if self._should_retry_without_response_format(e, request_body) and allow_json_object:
                            allow_json_object = False
                            self._allow_json_object = False
                            self._persist_compat_mode()
                            continue
                        if self._should_retry_without_tools(e, request_body) and allow_tools:
                            allow_tools = False
                            self._allow_tools = False
                            self._persist_compat_mode()
                            continue
                        print(f"[VBF] planning_capability_probe skipped: {e}")
                        break

                    if self._is_empty_chunk_payload(response):
                        if allow_tools:
                            allow_tools = False
                            self._allow_tools = False
                            self._persist_compat_mode()
                            continue
                        if allow_json_object:
                            allow_json_object = False
                            self._allow_json_object = False
                            self._persist_compat_mode()
                            continue
                    break

            if should_probe_streaming:
                request_body = self._build_api_request_with_mode(
                    probe_messages,
                    probe_tools,
                    allow_tools=allow_tools,
                    allow_json_object=allow_json_object,
                    stream=True,
                )
                try:
                    if self.use_curl_http_compat:
                        response = self._post_chat_completions_http_stream(
                            request_body,
                            timeout_seconds=timeout_seconds,
                            log_progress=False,
                        )
                    else:
                        response = self._aggregate_streaming_response(
                            client.chat.completions.create(**request_body),
                            log_progress=False,
                        )
                except Exception as e:
                    self._allow_streaming = False
                    self._persist_compat_mode()
                    print(f"[VBF] streaming_probe result=fail reason={type(e).__name__}", flush=True)
                else:
                    if self._is_empty_chunk_payload(response):
                        self._allow_streaming = False
                        self._persist_compat_mode()
                        print("[VBF] streaming_probe result=fail reason=empty_chunk", flush=True)
                    else:
                        self._allow_streaming = True
                        self._persist_compat_mode()
                        print("[VBF] streaming_probe result=pass", flush=True)
        finally:
            self._mark_compat_probe_checked()

    def _build_api_request_with_mode(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]],
        allow_tools: bool,
        allow_json_object: bool,
        stream: bool = False,
    ) -> Dict[str, Any]:
        effective_tools = tools if allow_tools else None
        request = self.build_api_request(messages, stream=stream, tools=effective_tools)
        if not allow_json_object:
            request.pop("response_format", None)
        return request

    @staticmethod
    def _should_retry_without_response_format(
        error: Exception, request_body: Dict[str, Any]
    ) -> bool:
        """Detect providers that reject `response_format=json_object`."""
        if "response_format" not in request_body:
            return False
        msg = f"{getattr(error, 'message', '')} {error}".lower()
        return (
            "response_format" in msg
            and (
                "json_object" in msg
                or "json_schema" in msg
                or "must be" in msg
                or "invalid" in msg
            )
        )

    @staticmethod
    def _should_retry_without_tools(
        error: Exception, request_body: Dict[str, Any]
    ) -> bool:
        """Detect providers that reject tools/function-calling payloads."""
        if "tools" not in request_body and "tool_choice" not in request_body:
            return False
        msg = f"{getattr(error, 'message', '')} {error}".lower()
        return (
            "tool" in msg
            and (
                "unsupported" in msg
                or "not support" in msg
                or "invalid" in msg
                or "unknown" in msg
                or "must be" in msg
            )
        )

    def _log_compat_mode_once(self) -> None:
        if self._compat_mode_logged:
            return
        print(
            "[VBF] LLM request mode: "
            f"model={self.default_model}, "
            f"tools={'on' if self._allow_tools else 'off'}, "
            f"json_object={'on' if self._allow_json_object else 'off'}",
            f"stream={'on' if self._allow_streaming else 'off'}",
            flush=True,
        )
        self._compat_mode_logged = True

    def format_messages(
        self,
        user_input: str,
        context: Optional[Dict] = None,
        stream: bool = False,
        skills_subset: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Format messages for OpenAI-compatible API."""
        messages = [{"role": "system", "content": self.build_system_prompt(skills_subset=skills_subset)}]

        if context:
            context_str = json.dumps(context, indent=2, ensure_ascii=False)
            messages.append(
                {
                    "role": "system",
                    "content": f"Project Context:\n```json\n{context_str}\n```",
                }
            )

        if stream:
            messages.append(
                {
                    "role": "system",
                    "content": "IMPORTANT: Respond with streaming. "
                    "Use event: completion for incremental text output.",
                }
            )

        messages.append({"role": "user", "content": user_input})
        return messages

    def _compat_mode_snapshot(self) -> Dict[str, Any]:
        return {
            "allow_tools": bool(self._allow_tools),
            "allow_json_object": bool(self._allow_json_object),
            "allow_streaming": bool(self._allow_streaming),
            "model": self.default_model,
            "base_url": self.base_url,
        }

    @staticmethod
    def _is_empty_chunk_payload(payload: Any) -> bool:
        """Detect empty chunk-like provider payloads (no usable completion)."""
        obj = ""
        choices = None
        if isinstance(payload, dict):
            obj = str(payload.get("object", "") or "")
            choices = payload.get("choices")
        else:
            obj = str(getattr(payload, "object", "") or "")
            choices = getattr(payload, "choices", None)

        if not obj.startswith("chat.completion"):
            return False
        if not isinstance(choices, list):
            return False
        return len(choices) == 0

    @staticmethod
    def _extract_markdown_json_block(content: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return content.strip()

    @staticmethod
    def _extract_outermost_json_object(content: str) -> Optional[str]:
        start = content.find("{")
        if start < 0:
            return None

        in_string = False
        escaped = False
        depth = 0
        for idx in range(start, len(content)):
            ch = content[idx]
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    return content[start : idx + 1]
        return None

    @staticmethod
    def _repair_json_closers(content: str) -> Optional[str]:
        """Repair simple missing list/object closers in otherwise valid JSON text."""
        in_string = False
        escaped = False
        stack: List[str] = []
        repaired: List[str] = []

        for ch in content:
            if escaped:
                repaired.append(ch)
                escaped = False
                continue
            if ch == "\\":
                repaired.append(ch)
                escaped = True
                continue
            if ch == '"':
                repaired.append(ch)
                in_string = not in_string
                continue
            if in_string:
                repaired.append(ch)
                continue
            if ch in "{[":
                stack.append(ch)
                repaired.append(ch)
                continue
            if ch in "}]":
                opener = "{" if ch == "}" else "["
                closer_for_top = {"{": "}", "[": "]"}
                while stack and stack[-1] != opener:
                    previous = next((c for c in reversed(repaired) if not c.isspace()), "")
                    if stack[-1] == "[" and previous in {"[", ",", ":"}:
                        return None
                    repaired.append(closer_for_top[stack.pop()])
                if not stack:
                    return None
                stack.pop()
                repaired.append(ch)
                continue
            repaired.append(ch)

        closer_for_top = {"{": "}", "[": "]"}
        while stack:
            repaired.append(closer_for_top[stack.pop()])
        repaired_text = "".join(repaired)
        return repaired_text if repaired_text != content else None

    def parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse OpenAI-compatible API response to VBF plan.

        Handles both:
        1. Direct JSON content (text response from LLM)
        2. Tool calls (intermediate - returns list for caller to handle)
        """
        # If response is a list of tool results, return them for caller
        if isinstance(response, list):
            return {"tool_results": response}

        # Extract content using configured path
        content = self._extract_content(response)

        if not content:
            return {
                "error": "Empty response from API",
                "parse_stage": "extract_content",
                "raw_content": "",
                "fallback_mode": self._compat_mode_snapshot(),
            }

        raw_content = str(content)
        parse_stage = "strip_markdown"
        cleaned_content = self._extract_markdown_json_block(raw_content)

        parse_stage = "extract_outermost_json"
        json_text = self._extract_outermost_json_object(cleaned_content)
        if json_text is None:
            return {
                "error": "Failed to extract outermost JSON object from response",
                "parse_stage": parse_stage,
                "raw_content": raw_content[:12000],
                "fallback_mode": self._compat_mode_snapshot(),
            }

        parse_stage = "strict_json_loads"
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            repaired_json = self._repair_json_closers(json_text)
            if repaired_json is not None:
                try:
                    return json.loads(repaired_json)
                except json.JSONDecodeError:
                    pass
            return {
                "error": "Failed to parse JSON from response",
                "parse_stage": parse_stage,
                "parse_detail": str(e),
                "raw_content": raw_content[:12000],
                "extracted_json": json_text[:12000],
                "fallback_mode": self._compat_mode_snapshot(),
            }

    def _extract_content(self, response: Any) -> Optional[str]:
        """Extract message content from API response using configurable path."""
        if isinstance(response, str):
            return response

        if not isinstance(response, dict):
            return str(response) if response else None

        if self.response_content_path:
            content = self._extract_by_path(response, self.response_content_path)
            if content:
                return content

        # Fallback
        common_paths = [
            "choices[0].message.content",
            "data.choices[0].content",
            "result",
            "content",
        ]
        for path in common_paths:
            if path == self.response_content_path:
                continue
            content = self._extract_by_path(response, path)
            if content:
                return content

        return str(response)

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_standard_http_headers(self) -> Dict[str, str]:
        headers = self.get_auth_headers()
        headers["Accept"] = "application/json"
        if self.request_headers:
            headers.update(self.request_headers)
        return headers

    @staticmethod
    def _extract_error_message_from_http_response(response: Any) -> str:
        text = str(getattr(response, "text", "") or "").strip()
        if text:
            return text

        try:
            payload = response.json()
        except Exception:
            return ""

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if message:
                    return str(message)
            message = payload.get("message")
            if message:
                return str(message)
        return str(payload)

    @staticmethod
    def _get_choices(payload: Any) -> Any:
        if isinstance(payload, dict):
            return payload.get("choices")
        return getattr(payload, "choices", None)

    @staticmethod
    def _get_choice_message(choice: Any) -> Any:
        if isinstance(choice, dict):
            return choice.get("message")
        return getattr(choice, "message", None)

    @staticmethod
    def _get_choice_finish_reason(choice: Any) -> Any:
        if isinstance(choice, dict):
            return choice.get("finish_reason")
        return getattr(choice, "finish_reason", None)

    @staticmethod
    def _get_message_content(message: Any) -> Any:
        if isinstance(message, dict):
            return message.get("content")
        return getattr(message, "content", None)

    @staticmethod
    def _get_message_tool_calls(message: Any) -> Any:
        if isinstance(message, dict):
            return message.get("tool_calls")
        return getattr(message, "tool_calls", None)

    def _request_timeout_seconds(self) -> float:
        """Use a slightly shorter transport timeout than the outer throttle."""
        try:
            timeout = max(1.0, float(self.http_timeout_seconds))
        except Exception:
            return 60.0
        if timeout <= 30.0:
            return timeout
        return max(1.0, timeout - min(20.0, timeout * 0.10))

    @staticmethod
    def _message_content_char_count(messages: List[Dict]) -> int:
        total = 0
        for message in messages:
            if not isinstance(message, dict):
                total += len(str(message))
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                total += len(content)
            else:
                try:
                    total += len(json.dumps(content, ensure_ascii=False, default=str))
                except Exception:
                    total += len(str(content))
        return total

    def _log_llm_request_payload(
        self,
        request_body: Dict[str, Any],
        timeout_seconds: float,
        attempt: int,
    ) -> None:
        messages = request_body.get("messages", [])
        message_count = len(messages) if isinstance(messages, list) else 0
        char_count = (
            self._message_content_char_count(messages)
            if isinstance(messages, list)
            else len(str(messages))
        )
        print(
            "[VBF] llm_request "
            f"attempt={attempt} "
            f"messages={message_count} "
            f"message_chars={char_count} "
            f"tools={'on' if 'tools' in request_body else 'off'} "
            f"json_object={'on' if 'response_format' in request_body else 'off'} "
            f"stream={'on' if request_body.get('stream') else 'off'} "
            f"timeout={timeout_seconds:.1f}s",
            flush=True,
        )

    def _post_chat_completions_http(
        self,
        request_body: Dict[str, Any],
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        import httpx

        url = _build_chat_completions_url(self.base_url, self.chat_completions_path)
        try:
            with httpx.Client(timeout=timeout_seconds or self.http_timeout_seconds) as client:
                response = client.post(
                    url,
                    headers=self._build_standard_http_headers(),
                    json=request_body,
                )
                response.raise_for_status()
        except httpx.TimeoutException as e:
            raise TimeoutError("LLM call timed out") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            message = self._extract_error_message_from_http_response(e.response) or str(e)
            raise self._CompatHTTPError(e.response.status_code, message) from e

        try:
            return response.json()
        except Exception:
            return response.text

    def _aggregate_streaming_response(
        self,
        chunks: Any,
        log_progress: bool = True,
    ) -> Dict[str, Any]:
        aggregator = StreamingChatCompletionAggregator()
        start = time.time()
        first_chunk_logged = False
        last_progress = start

        for chunk in chunks:
            if not first_chunk_logged:
                first_chunk_logged = True
                if log_progress:
                    first_chunk_ms = int((time.time() - start) * 1000)
                    print(f"[VBF] stream_started first_chunk_ms={first_chunk_ms}", flush=True)

            aggregator.add_chunk(chunk)

            if log_progress:
                now = time.time()
                if now - last_progress >= 30.0:
                    stats = aggregator.stats()
                    print(
                        "[VBF] stream_progress "
                        f"chunks={stats['chunks']} "
                        f"content_chars={stats['content_chars']} "
                        f"tool_arg_chars={stats['tool_arg_chars']} "
                        f"elapsed={now - start:.1f}s",
                        flush=True,
                    )
                    last_progress = now

        if not first_chunk_logged:
            raise RuntimeError("stream returned no chunks")

        stats = aggregator.stats()
        if log_progress:
            print(
                "[VBF] stream_completed "
                f"chunks={stats['chunks']} "
                f"content_chars={stats['content_chars']} "
                f"tool_calls={stats['tool_calls']} "
                f"elapsed={time.time() - start:.1f}s",
                flush=True,
            )
        return aggregator.to_chat_completion()

    def _post_chat_completions_http_stream(
        self,
        request_body: Dict[str, Any],
        timeout_seconds: Optional[float] = None,
        log_progress: bool = True,
    ) -> Any:
        import httpx

        url = _build_chat_completions_url(self.base_url, self.chat_completions_path)
        try:
            with httpx.Client(timeout=timeout_seconds or self.http_timeout_seconds) as client:
                with client.stream(
                    "POST",
                    url,
                    headers=self._build_standard_http_headers(),
                    json=request_body,
                ) as response:
                    response.raise_for_status()
                    return self._aggregate_streaming_response(
                        iter_sse_json_chunks(response.iter_lines()),
                        log_progress=log_progress,
                    )
        except httpx.TimeoutException as e:
            raise TimeoutError("LLM stream timed out") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM stream connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            message = self._extract_error_message_from_http_response(e.response) or str(e)
            raise self._CompatHTTPError(e.response.status_code, message) from e

    async def call_llm(self, messages: List[Dict]) -> Dict[str, Any]:
        """Send messages to LLM with function-calling support.

        Progressive disclosure loop:
        1. Send messages + tools to LLM
        2. If LLM returns tool_calls -> execute, add results, loop
        3. If LLM returns content -> parse and return plan JSON

        Args:
            messages: Pre-formatted chat messages (from format_messages)

        Returns:
            Parsed plan dict with steps

        Raises:
            TimeoutError: On LLM request timeout
            ConnectionError: On network/connection errors
            RuntimeError: On API errors or max iterations
        """
        import asyncio
        from openai import OpenAI, APITimeoutError, APIConnectionError, APIError

        await asyncio.to_thread(self._maybe_probe_compatibility_sync, OpenAI)
        tools = self.build_tools_for_llm() if self.use_function_calling else None
        max_tool_calls = 10
        self._log_compat_mode_once()

        def _sync_http_call(req_messages: List[Dict], req_tools: Optional[List[Dict]]) -> Any:
            """Synchronous HTTP call (runs in thread pool)."""
            client = None
            request_timeout_seconds = self._request_timeout_seconds()
            if not self.use_curl_http_compat:
                client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    default_headers=self.request_headers or None,
                    timeout=request_timeout_seconds,
                )
            allow_tools = bool(req_tools) and bool(self._allow_tools)
            allow_json_object = bool(self._allow_json_object)
            allow_streaming = bool(
                self.use_streaming and self.supports_streaming and self._allow_streaming
            )
            max_attempts = 4
            tools_off_cards = ""
            has_tools_off_cards = any(
                isinstance(msg, dict)
                and msg.get("role") == "system"
                and (
                    "Schema Cards (Tools-Off Fallback)" in str(msg.get("content", ""))
                    or "Compact Skill Signatures" in str(msg.get("content", ""))
                )
                for msg in req_messages
            )

            for attempt in range(max_attempts):
                request_messages = req_messages
                if not allow_tools:
                    if not tools_off_cards and not has_tools_off_cards:
                        tools_off_cards = self._build_schema_cards(
                            self._get_skills_for_prompt(),
                            max_cards=int(self._model_config.get("schema_cards_limit", 12)),
                        )
                    if tools_off_cards:
                        request_messages = req_messages + [
                            {"role": "system", "content": tools_off_cards}
                        ]
                request_body = self._build_api_request_with_mode(
                    request_messages,
                    req_tools,
                    allow_tools=allow_tools,
                    allow_json_object=allow_json_object,
                    stream=allow_streaming,
                )
                self._log_llm_request_payload(
                    request_body,
                    timeout_seconds=request_timeout_seconds,
                    attempt=attempt + 1,
                )

                try:
                    if self.use_curl_http_compat:
                        if allow_streaming:
                            resp = self._post_chat_completions_http_stream(
                                request_body,
                                timeout_seconds=request_timeout_seconds,
                            )
                        else:
                            resp = self._post_chat_completions_http(
                                request_body,
                                timeout_seconds=request_timeout_seconds,
                            )
                    else:
                        if allow_streaming:
                            resp = self._aggregate_streaming_response(
                                client.chat.completions.create(**request_body)
                            )
                        else:
                            resp = client.chat.completions.create(**request_body)
                except Exception as e:
                    if allow_streaming:
                        allow_streaming = False
                        print(
                            "[VBF] fallback_mode=disable_streaming_retry_nonstream "
                            f"reason={type(e).__name__}",
                            flush=True,
                        )
                        continue
                    if isinstance(e, (APITimeoutError, TimeoutError)):
                        if allow_tools:
                            allow_tools = False
                            print("[VBF] fallback_mode=timeout_disable_tools_retry_once", flush=True)
                            continue
                        raise TimeoutError("LLM call timed out") from e
                    if isinstance(e, APIConnectionError):
                        raise ConnectionError(f"LLM connection failed: {e}") from e
                    if isinstance(e, APIError):
                        if self._should_retry_without_response_format(e, request_body) and allow_json_object:
                            allow_json_object = False
                            self._allow_json_object = False
                            self._persist_compat_mode()
                            print("[VBF] fallback_mode=disable_response_format_json_object")
                            continue
                        if self._should_retry_without_tools(e, request_body) and allow_tools:
                            allow_tools = False
                            self._allow_tools = False
                            self._persist_compat_mode()
                            print("[VBF] fallback_mode=disable_function_calling_tools")
                            continue
                        raise RuntimeError(f"LLM API error ({e.status_code}): {e.message}") from e
                    if isinstance(e, self._CompatHTTPError):
                        if self._should_retry_without_response_format(e, request_body) and allow_json_object:
                            allow_json_object = False
                            self._allow_json_object = False
                            self._persist_compat_mode()
                            print("[VBF] fallback_mode=disable_response_format_json_object")
                            continue
                        if self._should_retry_without_tools(e, request_body) and allow_tools:
                            allow_tools = False
                            self._allow_tools = False
                            self._persist_compat_mode()
                            print("[VBF] fallback_mode=disable_function_calling_tools")
                            continue
                        raise RuntimeError(f"LLM API error ({e.status_code}): {e.message}") from e
                    raise

                # Some gateways return empty chunk payloads with no choices/content.
                # Treat this as a compatibility issue and progressively downgrade.
                if self._is_empty_chunk_payload(resp):
                    if allow_tools:
                        allow_tools = False
                        self._allow_tools = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=empty_chunk_disable_tools_retry")
                        continue
                    if allow_json_object:
                        allow_json_object = False
                        self._allow_json_object = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=empty_chunk_disable_json_object_retry")
                        continue
                    raise RuntimeError("LLM returned empty chunk payload with no choices")

                # Some OpenAI-compatible gateways return plain text directly
                # instead of a ChatCompletion object.
                if isinstance(resp, str):
                    raw = resp.strip()
                    if raw.startswith("{") or raw.startswith("["):
                        try:
                            parsed = json.loads(raw)
                            if self._is_empty_chunk_payload(parsed):
                                if allow_tools:
                                    allow_tools = False
                                    self._allow_tools = False
                                    self._persist_compat_mode()
                                    print("[VBF] fallback_mode=empty_chunk_disable_tools_retry")
                                    continue
                                if allow_json_object:
                                    allow_json_object = False
                                    self._allow_json_object = False
                                    self._persist_compat_mode()
                                    print("[VBF] fallback_mode=empty_chunk_disable_json_object_retry")
                                    continue
                                raise RuntimeError("LLM returned empty chunk payload with no choices")
                            if isinstance(parsed, dict) and isinstance(parsed.get("steps"), list):
                                return parsed
                            if isinstance(parsed, list) and all(isinstance(x, dict) for x in parsed):
                                return {"steps": parsed}
                            return self.parse_response(parsed)
                        except json.JSONDecodeError:
                            pass
                    return self.parse_response(resp)

                # Some gateways return plain dict payloads instead of SDK
                # response models; parse through the configured content path.
                if isinstance(resp, dict) and isinstance(resp.get("steps"), list):
                    return resp

                choices = self._get_choices(resp)
                if isinstance(resp, dict) and not isinstance(choices, list):
                    return self.parse_response(resp)
                if not isinstance(choices, list) or not choices:
                    # Some providers return a ChatCompletion-like object but omit
                    # `choices` in edge cases. Treat as compatibility downgrade.
                    if allow_tools:
                        allow_tools = False
                        self._allow_tools = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=choice_missing_disable_tools_retry")
                        continue
                    if allow_json_object:
                        allow_json_object = False
                        self._allow_json_object = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=choice_missing_disable_json_object_retry")
                        continue
                    raise RuntimeError("LLM returned response without choices")

                choice = choices[0]
                if choice is None:
                    if allow_tools:
                        allow_tools = False
                        self._allow_tools = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=choice_missing_disable_tools_retry")
                        continue
                    if allow_json_object:
                        allow_json_object = False
                        self._allow_json_object = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=choice_missing_disable_json_object_retry")
                        continue
                    raise RuntimeError("LLM returned empty choice payload")

                finish_reason = self._get_choice_finish_reason(choice)
                message = self._get_choice_message(choice)
                if message is None:
                    if allow_tools:
                        allow_tools = False
                        self._allow_tools = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=message_missing_disable_tools_retry")
                        continue
                    if allow_json_object:
                        allow_json_object = False
                        self._allow_json_object = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=message_missing_disable_json_object_retry")
                        continue
                    raise RuntimeError(
                        f"LLM returned response with missing message (finish_reason={finish_reason})"
                    )

                # Handle function calling
                tool_calls = self._get_message_tool_calls(message)
                if tool_calls:
                    tool_results = []
                    for tc in tool_calls:
                        if isinstance(tc, dict):
                            function = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                            tool_name = str(function.get("name", ""))
                            arguments = function.get("arguments")
                            tool_call_id = str(tc.get("id", ""))
                        else:
                            function = getattr(tc, "function", None)
                            tool_name = getattr(function, "name", "")
                            arguments = getattr(function, "arguments", None)
                            tool_call_id = getattr(tc, "id", "")

                        try:
                            args = json.loads(arguments) if isinstance(arguments, str) else arguments
                        except json.JSONDecodeError:
                            args = {}

                        # Execute tool (sync call, no RPC needed for skill metadata)
                        if tool_name == "load_skill":
                            result = self.load_skill(args.get("skill_name", ""))
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}

                        tool_results.append({
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "args": args,
                            "result": result,
                        })

                    return {
                        "finish_reason": finish_reason,
                        "tool_results": tool_results,
                        "raw_message": message,
                    }

                # No tool calls - final response
                content = self._get_message_content(message)
                if content is None:
                    # Some providers stop with empty content for larger prompt+tool payloads.
                    if allow_tools:
                        allow_tools = False
                        self._allow_tools = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=empty_content_disable_tools_retry")
                        continue
                    if allow_json_object:
                        allow_json_object = False
                        self._allow_json_object = False
                        self._persist_compat_mode()
                        print("[VBF] fallback_mode=empty_content_disable_json_object_retry")
                        continue
                    raise RuntimeError(
                        f"LLM returned empty content (finish_reason={finish_reason})"
                    )

                # Successful plain content path.
                return self.parse_response({self.response_content_path: content})

            raise RuntimeError("LLM provider returned no usable content after compatibility fallbacks")

        # Tool call loop
        current_messages = list(messages)  # Copy to avoid mutating original
        current_tools = tools

        for iteration in range(max_tool_calls):
            response = await asyncio.to_thread(_sync_http_call, current_messages, current_tools)

            # Handle tool calls
            if "tool_results" in response:
                tool_results = response["tool_results"]
                raw_message = response["raw_message"]

                # Add assistant message with tool calls
                assistant_content = self._get_message_content(raw_message)
                if assistant_content is None:
                    assistant_content = ""
                current_messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": [
                        {
                            "id": tr["tool_call_id"],
                            "type": "function",
                            "function": {
                                "name": tr["tool_name"],
                                "arguments": (
                                    json.dumps(tr["args"], ensure_ascii=False)
                                    if not isinstance(tr["args"], str)
                                    else tr["args"]
                                ),
                            },
                        }
                        for tr in tool_results
                    ],
                })

                # Add tool result messages
                for tr in tool_results:
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "content": json.dumps(tr["result"], ensure_ascii=False, indent=2),
                    })

                # Continue loop
                continue

            # No tool calls - final response
            return response

        # Max iterations exceeded
        raise RuntimeError(
            f"Max tool call iterations ({max_tool_calls}) exceeded. "
            "LLM may be stuck in a tool-calling loop."
        )
