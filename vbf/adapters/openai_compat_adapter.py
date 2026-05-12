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
from .endpoint_protocol import (
    EndpointStreamingAggregator,
    build_protocol_request,
    iter_endpoint_sse_json_chunks,
    normalize_api_protocol,
)
from .internal_response import (
    VBFLLMResponse,
    chat_completion_to_internal,
    content_to_internal,
    endpoint_response_to_internal,
    internal_tool_call_to_chat,
)
from ..llm.openai_compat import (
    _build_chat_completions_url,
    _normalize_auth_scheme,
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
    _DEFAULT_SCHEMA_CARD_PRIORITY_SKILLS = (
        "create_primitive",
        "create_beveled_box",
        "apply_transform",
        "set_parent",
        "add_modifier_boolean",
        "boolean_tool",
        "add_modifier_bevel",
        "apply_modifier",
        "create_material_pbr",
        "assign_material",
        "create_light",
        "set_light_properties",
        "create_camera",
        "set_camera_active",
        "set_render_engine",
        "set_render_resolution",
        "set_cycles_samples",
    )

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
        self.api_protocol = normalize_api_protocol(model_config.get("api_protocol", "openai_responses"))
        self.auth_scheme = _normalize_auth_scheme(model_config.get("auth_scheme", "auto"))
        default_responses_path = "/messages" if self.api_protocol == "claude_responses" else "/responses"
        self.responses_path = model_config.get("responses_path", default_responses_path)
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
        raw_planning_tool_mode = (
            model_config.get("planning_tool_mode")
            or model_config.get("planning_tools_mode")
            or self.planning_context.get("planning_tool_mode")
            or "schema"
        )
        self.planning_tool_mode = str(raw_planning_tool_mode).strip().lower()
        try:
            self.planning_skill_tool_limit = max(
                0,
                int(
                    model_config.get(
                        "planning_skill_tool_limit",
                        self.planning_context.get("planning_skill_tool_limit", 32),
                    )
                ),
            )
        except Exception:
            self.planning_skill_tool_limit = 32
        self._active_skills_subset: Optional[List[str]] = None

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
        self.enable_proxy_compatibility_mode = _parse_bool_field(
            model_config, "enable_proxy_compatibility_mode", False
        )
        self.enable_extra_request_headers = _parse_bool_field(
            model_config, "enable_extra_request_headers", False
        )
        self.use_curl_http_compat = _parse_bool_field(model_config, "use_curl_http_compat", False)
        self.http_timeout_seconds = float(model_config.get("http_timeout_seconds", 60.0))
        self.request_headers = _resolve_request_headers(
            model_config.get("request_headers"),
            enable_proxy_compatibility_mode=self.enable_proxy_compatibility_mode,
            enable_extra_request_headers=self.enable_extra_request_headers,
        )

        # Runtime compatibility mode (provider/protocol/endpoint-specific,
        # cached in-process). Chat, Responses, and Messages-compatible
        # endpoints may reject different fields even for the same model.
        self._compat_mode_key = self._build_compat_mode_key()
        default_allow_json = self.response_format.get("type") == "json_object"
        default_allow_tools = bool(self.use_function_calling)
        default_allow_streaming = bool(self.use_streaming and self.supports_streaming)
        cached = self._COMPAT_MODE_CACHE.get(self._compat_mode_key, {})
        self._allow_json_object = bool(cached.get("allow_json_object", default_allow_json))
        self._allow_tools = bool(cached.get("allow_tools", default_allow_tools))
        self._allow_streaming = bool(cached.get("allow_streaming", default_allow_streaming))
        self._compat_mode_logged = False

    def _build_compat_mode_key(self) -> str:
        return "|".join(
            [
                str(self.base_url or ""),
                str(self.default_model or ""),
                self.api_protocol,
                self._endpoint_path(),
                f"proxy={int(self.enable_proxy_compatibility_mode)}",
            ]
        )

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

    @staticmethod
    def _json_schema_for_type_hint(type_hint: Any) -> Dict[str, Any]:
        normalized = OpenAICompatAdapter._normalize_type_hint(type_hint)
        if normalized == "int":
            return {"type": "integer"}
        if normalized == "float":
            return {"type": "number"}
        if normalized == "bool":
            return {"type": "boolean"}
        if normalized == "dict":
            return {"type": "object"}
        if normalized == "list":
            return {"type": "array"}
        if normalized == "str":
            return {"type": "string"}
        return {}

    def _planning_skill_tools_enabled(self) -> bool:
        return self.planning_tool_mode in {
            "schema",
            "schema_tools",
            "skill_schema",
            "skill_tools",
            "planning_schema",
            "planning_tools",
            "doc_and_schema",
            "doc_and_skill_tools",
        }

    def _planning_tool_skill_names_for_request(self) -> List[str]:
        if not self._planning_skill_tools_enabled() or self.planning_skill_tool_limit <= 0:
            return []
        if not self._active_skills_subset:
            return []

        names: List[str] = []
        seen = {"load_skill"}
        for name in self._active_skills_subset:
            if not isinstance(name, str) or name in seen:
                continue
            if not self.validate_skill(name):
                continue
            names.append(name)
            seen.add(name)
            if len(names) >= self.planning_skill_tool_limit:
                break
        return names

    def _build_planning_skill_tool(self, skill_name: str) -> Optional[Dict[str, Any]]:
        skill = self.get_skill_full(skill_name)
        if not isinstance(skill, dict):
            return None
        args = skill.get("args")
        if not isinstance(args, dict):
            args = {}

        properties: Dict[str, Any] = {}
        required: List[str] = []
        for param_name, param_info in args.items():
            if not isinstance(param_name, str) or param_name == "self":
                continue
            info = param_info if isinstance(param_info, dict) else {}
            schema = self._json_schema_for_type_hint(info.get("type"))
            description_parts: List[str] = []
            if info.get("description"):
                description_parts.append(str(info.get("description")))
            if info.get("default") not in (None, ""):
                description_parts.append(f"default={info.get('default')}")
            if description_parts:
                schema["description"] = "; ".join(description_parts)[:500]
            properties[param_name] = schema
            if info.get("required") is True:
                required.append(param_name)

        description = str(skill.get("description") or "").split("\n")[0].strip()
        if description:
            description = description[:500]
        else:
            description = f"Add a planning step using the registered Blender skill {skill_name}."

        return {
            "type": "function",
            "function": {
                "name": skill_name,
                "description": (
                    "Planning-only Blender skill step. Calling this tool records a "
                    f"plan step; it is not executed during LLM planning. {description}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def _schema_card_priority_order(
        self,
        skills_to_include: List[str],
        *,
        priority_only: bool,
    ) -> List[str]:
        if not priority_only:
            return list(skills_to_include)

        configured = self._model_config.get(
            "schema_card_priority_skills",
            self.planning_context.get("schema_card_priority_skills"),
        )
        if isinstance(configured, str):
            priority_skills = [item.strip() for item in configured.split(",") if item.strip()]
        elif isinstance(configured, list):
            priority_skills = [str(item) for item in configured if str(item).strip()]
        else:
            priority_skills = list(self._DEFAULT_SCHEMA_CARD_PRIORITY_SKILLS)

        retained = set(skills_to_include)
        ordered: List[str] = []
        for skill_name in priority_skills:
            if skill_name in retained and skill_name not in ordered:
                ordered.append(skill_name)
        for skill_name in skills_to_include:
            if skill_name not in ordered:
                ordered.append(skill_name)
        return ordered

    def _build_schema_cards(
        self,
        skills_to_include: List[str],
        max_cards: int = 12,
        *,
        priority_only: bool = False,
    ) -> str:
        include_all = bool(
            self.planning_context.get("include_compact_schema_for_all_retained_skills", False)
            or (
                not priority_only
                and (
                    self.planning_context.get("include_compact_schema_for_required", False)
                    or self.planning_context.get("include_compact_schema_for_high_risk", False)
                )
            )
        )
        if include_all:
            max_cards = len(skills_to_include)

        cards: List[str] = []
        ordered_skills = self._schema_card_priority_order(
            skills_to_include,
            priority_only=priority_only,
        )
        for skill_name in ordered_skills[:max_cards]:
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

        if self.use_function_calling and self._planning_skill_tools_enabled():
            tool_instruction += """

## Planning Skill Tools
Registered Blender skills may also be exposed as planning-only tools for this
request. Calling one of those skill tools does NOT execute Blender immediately;
VBF converts the tool call into a normal JSON plan step, then validates and
executes it through the feedback/rollback/resume pipeline. Use exact tool
signatures when they are available. `load_skill` remains documentation-only."""

        schema_cards = ""
        schema_cards_enabled = bool(
            self.planning_context.get("include_compact_schema_for_required", False)
            or self.planning_context.get("include_compact_schema_for_high_risk", False)
            or self.planning_context.get("include_compact_schema_for_all_retained_skills", False)
        )
        if schema_cards_enabled or not self.use_function_calling or not self._allow_tools:
            schema_cards = self._build_schema_cards(
                skills_to_include,
                max_cards=int(self._model_config.get("schema_cards_limit", 12)),
                priority_only=bool(self.use_function_calling and self._allow_tools),
            )

        base_prompt = f"""You are VBF (Vibe-Blender-Flow), a professional Blender 3D modeling assistant.

## Core Rules
1. **Output JSON only** - Never output Python/bpy/bmesh code directly
2. **Use only available skills** - Validate skill names against the defined list
3. **Context references** - Use $ref to reference previous step results: {{"$ref": "step_001.data.object_name"}}
4. **Parameters** - Required params must be provided; optional params use defaults
4a. **Primitive enum** - `create_primitive.primitive_type` supports only "cube", "cylinder", "cone", or "sphere". Do not use unsupported primitives such as "torus"; approximate wheel/tire/ring forms with cylinders plus bevel/detail steps.
5. **load_skill is NOT a Blender skill** - It is a documentation query tool only. Never use "load_skill" as the "skill" value in plan steps. Only use it via the function_calling tool to query skill documentation.
5a. **Planning tool calls are plan steps** - If registered Blender skill tools are available, calling them is an alternate way to output plan steps. They are not executed during planning.
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

        The default documentation tool is load_skill(). During planning calls,
        VBF may also expose selected registered Blender skill schemas as
        planning-only tools; those tool calls are converted into plan steps
        instead of being executed immediately.

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

        for skill_name in self._planning_tool_skill_names_for_request():
            tool = self._build_planning_skill_tool(skill_name)
            if tool:
                tools.append(tool)

        return tools

    def build_api_request(
        self, messages: List[Dict], stream: bool = False,
        tools: Optional[List[Dict]] = None,
        protocol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build API request body for OpenAI-compatible endpoint.

        Args:
            messages: Formatted messages
            stream: Whether to request streaming response
            tools: Optional list of tool definitions for function calling
        """
        effective_protocol = normalize_api_protocol(protocol or self.api_protocol)
        return build_protocol_request(
            protocol=effective_protocol,
            model=self.default_model,
            messages=messages,
            temperature=self.temperature,
            tools=tools,
            json_object=self.response_format.get("type") == "json_object",
            stream=bool(stream and self.supports_streaming),
            proxy_compatibility_mode=self.enable_proxy_compatibility_mode,
        )

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
        effective_protocol = self.api_protocol
        use_http_protocol = self.use_curl_http_compat or effective_protocol != "chat"
        if not use_http_protocol:
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
                        if use_http_protocol:
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

                    if self._is_empty_chunk_payload(response) or (
                        isinstance(response, VBFLLMResponse)
                        and self._is_empty_internal_response(response)
                    ):
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
                    if use_http_protocol:
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
                    if self._is_empty_chunk_payload(response) or (
                        isinstance(response, VBFLLMResponse)
                        and self._is_empty_internal_response(response)
                    ):
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
        protocol: Optional[str] = None,
    ) -> Dict[str, Any]:
        effective_tools = tools if allow_tools else None
        request = self.build_api_request(
            messages,
            stream=stream,
            tools=effective_tools,
            protocol=protocol,
        )
        if not allow_json_object:
            request.pop("response_format", None)
            request.pop("text", None)
        return request

    @staticmethod
    def _should_retry_without_response_format(
        error: Exception, request_body: Dict[str, Any]
    ) -> bool:
        """Detect providers that reject `response_format=json_object`."""
        if "response_format" not in request_body and "text" not in request_body:
            return False
        msg = f"{getattr(error, 'message', '')} {error}".lower()
        return (
            ("response_format" in msg or "json_object" in msg or "json_schema" in msg or "text.format" in msg)
            and (
                "json_object" in msg
                or "json_schema" in msg
                or "text.format" in msg
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
            f"protocol={self.api_protocol}, "
            f"model={self.default_model}, "
            f"doc_tools={'on' if self._allow_tools else 'off'}, "
            f"planning_tools={len(self._planning_tool_skill_names_for_request()) if self._allow_tools else 0}, "
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
        self._active_skills_subset = list(skills_subset) if skills_subset else None
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

        Handles direct JSON content from the normalized VBF LLM response.
        """
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
        if isinstance(response, VBFLLMResponse):
            return response.content

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
            "output_text",
            "output[0].content[0].text",
            "content[0].text",
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
            auth_scheme = self.auth_scheme
            if auth_scheme == "auto":
                auth_scheme = "x-api-key" if self.api_protocol == "claude_responses" else "bearer"
            if auth_scheme == "x-api-key":
                headers["x-api-key"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_standard_http_headers(self) -> Dict[str, str]:
        headers = self.get_auth_headers()
        headers["Accept"] = "application/json"
        if self.api_protocol == "claude_responses":
            headers.setdefault("anthropic-version", "2023-06-01")
        if self.request_headers:
            headers.update(self.request_headers)
        return headers

    def _endpoint_path(self) -> str:
        return self._endpoint_path_for_protocol(self.api_protocol)

    def _endpoint_path_for_protocol(self, protocol: Optional[str] = None) -> str:
        protocol = normalize_api_protocol(protocol or self.api_protocol)
        if protocol in {"openai_responses", "claude_responses"}:
            return str(self.responses_path or "/responses")
        return str(self.chat_completions_path or "/chat/completions")

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
        messages = request_body.get("messages", request_body.get("input", []))
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
            f"doc_tools={'on' if 'tools' in request_body else 'off'} "
            f"json_object={'on' if 'response_format' in request_body or 'text' in request_body else 'off'} "
            f"stream={'on' if request_body.get('stream') else 'off'} "
            f"timeout={timeout_seconds:.1f}s",
            flush=True,
        )

    def _post_chat_completions_http(
        self,
        request_body: Dict[str, Any],
        timeout_seconds: Optional[float] = None,
        protocol: Optional[str] = None,
    ) -> Any:
        import httpx

        url = _build_chat_completions_url(
            self.base_url,
            self._endpoint_path_for_protocol(protocol),
        )
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
        return chat_completion_to_internal("chat", aggregator.to_chat_completion())

    def _aggregate_endpoint_streaming_response(
        self,
        chunks: Any,
        log_progress: bool = True,
        protocol: Optional[str] = None,
    ) -> Dict[str, Any]:
        aggregator = EndpointStreamingAggregator(
            normalize_api_protocol(protocol or self.api_protocol)
        )
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
        return aggregator.to_internal_response()

    def _post_chat_completions_http_stream(
        self,
        request_body: Dict[str, Any],
        timeout_seconds: Optional[float] = None,
        log_progress: bool = True,
        protocol: Optional[str] = None,
    ) -> Any:
        import httpx

        effective_protocol = normalize_api_protocol(protocol or self.api_protocol)
        url = _build_chat_completions_url(
            self.base_url,
            self._endpoint_path_for_protocol(effective_protocol),
        )
        try:
            with httpx.Client(timeout=timeout_seconds or self.http_timeout_seconds) as client:
                with client.stream(
                    "POST",
                    url,
                    headers=self._build_standard_http_headers(),
                    json=request_body,
                ) as response:
                    response.raise_for_status()
                    if effective_protocol == "chat":
                        return self._aggregate_streaming_response(
                            iter_sse_json_chunks(response.iter_lines()),
                            log_progress=log_progress,
                        )
                    return self._aggregate_endpoint_streaming_response(
                        iter_endpoint_sse_json_chunks(response.iter_lines()),
                        log_progress=log_progress,
                        protocol=effective_protocol,
                    )
        except httpx.TimeoutException as e:
            raise TimeoutError("LLM stream timed out") from e
        except httpx.RequestError as e:
            raise ConnectionError(f"LLM stream connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            message = self._extract_error_message_from_http_response(e.response) or str(e)
            raise self._CompatHTTPError(e.response.status_code, message) from e

    def _normalize_provider_response(
        self,
        protocol: str,
        response: Any,
    ) -> VBFLLMResponse:
        if isinstance(response, VBFLLMResponse):
            return response

        if isinstance(response, str):
            raw = response.strip()
            if raw.startswith("{") or raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    return content_to_internal(response, protocol=protocol, raw=response)
                if isinstance(parsed, dict) and "choices" in parsed:
                    return chat_completion_to_internal(protocol, parsed)
                if isinstance(parsed, dict) and isinstance(parsed.get("steps"), list):
                    return content_to_internal(
                        json.dumps(parsed, ensure_ascii=False),
                        protocol=protocol,
                        raw=response,
                    )
                if isinstance(parsed, list) and all(isinstance(x, dict) for x in parsed):
                    return content_to_internal(
                        json.dumps({"steps": parsed}, ensure_ascii=False),
                        protocol=protocol,
                        raw=response,
                    )
            return content_to_internal(response, protocol=protocol, raw=response)

        if isinstance(response, dict) and isinstance(response.get("steps"), list):
            return content_to_internal(
                json.dumps(response, ensure_ascii=False),
                protocol=protocol,
                raw=response,
            )

        if protocol != "chat":
            return endpoint_response_to_internal(protocol, response)

        normalized = chat_completion_to_internal(protocol, response)
        if not normalized.content and not normalized.tool_calls and isinstance(response, dict):
            extracted = self._extract_content(response)
            if extracted:
                return content_to_internal(
                    extracted,
                    protocol=protocol,
                    raw=response,
                    finish_reason=normalized.finish_reason,
                    response_id=normalized.response_id,
                )
        return normalized

    @staticmethod
    def _is_empty_internal_response(response: VBFLLMResponse) -> bool:
        return not response.content and not response.tool_calls

    @staticmethod
    def _is_empty_responses_output(response: VBFLLMResponse) -> bool:
        """Detect Responses API completions that spent tokens but returned output=[]."""
        if response.protocol != "openai_responses" or not isinstance(response.raw, dict):
            return False
        raw = response.raw
        if raw.get("output") != []:
            return False
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        output_tokens = usage.get("output_tokens")
        details = (
            usage.get("output_tokens_details")
            if isinstance(usage.get("output_tokens_details"), dict)
            else {}
        )
        reasoning_tokens = details.get("reasoning_tokens")
        try:
            return int(output_tokens or 0) > 0 or int(reasoning_tokens or 0) > 0
        except Exception:
            return bool(output_tokens or reasoning_tokens)

    @staticmethod
    def _build_tool_budget_exhaustion_messages(
        current_messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build a compact tools-off retry prompt from accumulated tool history."""
        source_messages = [msg for msg in current_messages if isinstance(msg, dict)]
        user_messages = [
            str(msg.get("content", ""))
            for msg in source_messages
            if msg.get("role") == "user" and str(msg.get("content", "")).strip()
        ]
        system_messages = [
            str(msg.get("content", ""))
            for msg in source_messages
            if msg.get("role") == "system" and str(msg.get("content", "")).strip()
        ]
        tool_summaries: List[Dict[str, Any]] = []
        for msg in source_messages:
            if msg.get("role") != "tool":
                continue
            try:
                payload = json.loads(str(msg.get("content") or "{}"))
            except Exception:
                payload = {"raw": str(msg.get("content", ""))[:500]}
            tool_summaries.append(
                {
                    "tool_call_id": msg.get("tool_call_id"),
                    "skill_name": payload.get("skill_name"),
                    "required": payload.get("required"),
                    "parameters": list((payload.get("parameters") or {}).keys())[:20]
                    if isinstance(payload.get("parameters"), dict)
                    else [],
                }
            )

        retry_messages: List[Dict[str, Any]] = []
        if system_messages:
            retry_messages.append({"role": "system", "content": system_messages[0][:4000]})
        retry_messages.append(
            {
                "role": "user",
                "content": (
                    (user_messages[-1] if user_messages else "")[:16000]
                    + "\n\nCOMPACT LOADED SKILL SUMMARY:\n"
                    + json.dumps(tool_summaries[-24:], ensure_ascii=False)
                ),
            }
        )
        retry_messages.append(
            {
                "role": "system",
                "content": (
                    "The local load_skill tool budget for this planning call is exhausted. "
                    "Tools are now disabled. Return one final executable VBF plan JSON "
                    "with a non-empty `steps` array. Use only registered skill names and "
                    "exact registered argument names from the compact loaded skill summary. "
                    "Keep the plan concise and do not include explanations."
                ),
            }
        )
        return retry_messages

    @staticmethod
    def _messages_contain_tool_history(messages: List[Dict[str, Any]]) -> bool:
        for message in messages:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "tool":
                return True
            tool_calls = message.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                return True
        return False

    @staticmethod
    def _messages_contain_compact_tool_retry(messages: List[Dict[str, Any]]) -> bool:
        return any(
            isinstance(message, dict)
            and "COMPACT LOADED SKILL SUMMARY" in str(message.get("content", ""))
            for message in messages
        )

    def _record_empty_provider_response(
        self,
        *,
        reason: str,
        protocol: str,
        request_body: Dict[str, Any],
        response: Any,
    ) -> None:
        """Persist raw empty-provider responses for postmortem diagnostics."""
        recorder = getattr(self.client, "_record_plan_shape_failure", None)
        if not callable(recorder):
            return
        raw_response = response.raw if isinstance(response, VBFLLMResponse) else response
        payload = {
            "reason": reason,
            "protocol": protocol,
            "request": {
                "messages": len(request_body.get("messages", request_body.get("input", [])))
                if isinstance(request_body.get("messages", request_body.get("input", [])), list)
                else 0,
                "tools": "tools" in request_body,
                "json_object": "response_format" in request_body or "text" in request_body,
                "stream": bool(request_body.get("stream")),
            },
            "response_type": type(raw_response).__name__,
            "response": raw_response,
        }
        if isinstance(response, VBFLLMResponse):
            payload["internal_response"] = {
                "content_chars": len(response.content or ""),
                "tool_calls": len(response.tool_calls),
                "finish_reason": response.finish_reason,
                "response_id": response.response_id,
                "protocol": response.protocol,
            }
        try:
            recorder(
                f"LLM returned empty response ({reason})",
                payload,
                stage="llm_empty_response",
            )
        except Exception:
            pass

    def _is_planning_skill_tool_call(self, tool_name: str) -> bool:
        return (
            isinstance(tool_name, str)
            and tool_name != "load_skill"
            and self._planning_skill_tools_enabled()
            and self.validate_skill(tool_name)
        )

    def _planning_tool_calls_to_plan(self, tool_calls: List[Any]) -> Dict[str, Any]:
        steps: List[Dict[str, Any]] = []
        for index, tool_call in enumerate(tool_calls, start=1):
            args = tool_call.arguments if isinstance(tool_call.arguments, dict) else {}
            steps.append(
                {
                    "step_id": f"{index:03d}",
                    "skill": tool_call.name,
                    "args": args,
                }
            )
        return {
            "vbf_version": "2.1",
            "plan_type": "skills_plan",
            "steps": steps,
            "metadata": {
                "planning_tool_calls": True,
                "planning_tool_step_count": len(steps),
            },
        }

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
        max_tool_calls = max(1, int(self._model_config.get("max_tool_calls", 40)))
        self._log_compat_mode_once()

        def _sync_http_call(req_messages: List[Dict], req_tools: Optional[List[Dict]]) -> Any:
            """Synchronous HTTP call (runs in thread pool)."""
            client = None
            request_timeout_seconds = self._request_timeout_seconds()
            effective_protocol = self.api_protocol
            use_http_protocol = self.use_curl_http_compat or effective_protocol != "chat"
            if not use_http_protocol:
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
            max_attempts = 7
            max_empty_same_mode_retries = 2
            max_transport_same_mode_retries = 2
            empty_same_mode_retries = 0
            transport_same_mode_retries = 0
            timeout_same_mode_retries = 0
            tools_off_cards = ""
            compact_tools_off_messages: Optional[List[Dict[str, Any]]] = None
            has_tool_history = self._messages_contain_tool_history(req_messages)
            has_compact_tool_retry = self._messages_contain_compact_tool_retry(req_messages)
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
                    if has_tool_history and not has_compact_tool_retry:
                        if compact_tools_off_messages is None:
                            compact_tools_off_messages = self._build_tool_budget_exhaustion_messages(
                                req_messages
                            )
                        request_messages = compact_tools_off_messages
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
                    protocol=effective_protocol,
                )
                self._log_llm_request_payload(
                    request_body,
                    timeout_seconds=request_timeout_seconds,
                    attempt=attempt + 1,
                )

                try:
                    if use_http_protocol:
                        if allow_streaming:
                            resp = self._post_chat_completions_http_stream(
                                request_body,
                                timeout_seconds=request_timeout_seconds,
                                protocol=effective_protocol,
                            )
                        else:
                            resp = self._post_chat_completions_http(
                                request_body,
                                timeout_seconds=request_timeout_seconds,
                                protocol=effective_protocol,
                            )
                    else:
                        if allow_streaming:
                            resp = self._aggregate_streaming_response(
                                client.chat.completions.create(**request_body)
                            )
                        else:
                            resp = client.chat.completions.create(**request_body)
                except Exception as e:
                    if allow_streaming and isinstance(
                        e, (APITimeoutError, TimeoutError, APIConnectionError, ConnectionError)
                    ):
                        if transport_same_mode_retries < max_transport_same_mode_retries:
                            if has_tool_history and allow_tools:
                                allow_streaming = False
                                allow_tools = False
                                if allow_json_object:
                                    allow_json_object = False
                                transport_same_mode_retries = 0
                                print(
                                    "[VBF] fallback_mode=tool_result_timeout_compact_tools_off_retry "
                                    f"reason={type(e).__name__}",
                                    flush=True,
                                )
                                continue
                            transport_same_mode_retries += 1
                            time.sleep(min(2.0, 0.5 * transport_same_mode_retries))
                            print(
                                "[VBF] fallback_mode=stream_transport_retry_same_mode "
                                f"reason={type(e).__name__} retry={transport_same_mode_retries}",
                                flush=True,
                            )
                            continue
                        allow_streaming = False
                        transport_same_mode_retries = 0
                        print(
                            "[VBF] fallback_mode=disable_streaming_retry_nonstream "
                            f"reason={type(e).__name__}",
                            flush=True,
                        )
                        continue
                    if allow_streaming:
                        allow_streaming = False
                        transport_same_mode_retries = 0
                        print(
                            "[VBF] fallback_mode=disable_streaming_retry_nonstream "
                            f"reason={type(e).__name__}",
                            flush=True,
                        )
                        continue
                    if isinstance(e, (APITimeoutError, TimeoutError)):
                        if timeout_same_mode_retries < 1:
                            timeout_same_mode_retries += 1
                            print(
                                "[VBF] fallback_mode=timeout_retry_same_mode "
                                f"retry={timeout_same_mode_retries}",
                                flush=True,
                            )
                            continue
                        if allow_tools:
                            allow_tools = False
                            timeout_same_mode_retries = 0
                            print("[VBF] fallback_mode=timeout_local_disable_tools_retry", flush=True)
                            continue
                        raise TimeoutError("LLM call timed out") from e
                    if isinstance(e, (APIConnectionError, ConnectionError)):
                        if transport_same_mode_retries < max_transport_same_mode_retries:
                            transport_same_mode_retries += 1
                            time.sleep(min(2.0, 0.5 * transport_same_mode_retries))
                            print(
                                "[VBF] fallback_mode=transport_retry_same_mode "
                                f"reason={type(e).__name__} retry={transport_same_mode_retries}",
                                flush=True,
                            )
                            continue
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

                if self._is_empty_chunk_payload(resp):
                    self._record_empty_provider_response(
                        reason="empty_chunk_payload",
                        protocol=effective_protocol,
                        request_body=request_body,
                        response=resp,
                    )
                    force_mode_change = has_tool_history or effective_protocol == "openai_responses"
                    if (
                        not force_mode_change
                        and empty_same_mode_retries < max_empty_same_mode_retries
                    ):
                        empty_same_mode_retries += 1
                        print(
                            "[VBF] fallback_mode=empty_chunk_retry_same_mode "
                            f"retry={empty_same_mode_retries}",
                            flush=True,
                        )
                        continue
                    empty_same_mode_retries = 0
                    if allow_tools:
                        allow_tools = False
                        if force_mode_change and allow_json_object:
                            allow_json_object = False
                        print("[VBF] fallback_mode=empty_chunk_local_disable_tools_retry")
                        continue
                    if allow_json_object:
                        allow_json_object = False
                        print("[VBF] fallback_mode=empty_chunk_local_disable_json_object_retry")
                        continue
                    raise RuntimeError("LLM returned empty chunk payload with no choices")

                normalized = self._normalize_provider_response(effective_protocol, resp)
                if self._is_empty_internal_response(normalized):
                    empty_reason = (
                        "empty_responses_output"
                        if self._is_empty_responses_output(normalized)
                        else "empty_internal_response"
                    )
                    self._record_empty_provider_response(
                        reason=empty_reason,
                        protocol=effective_protocol,
                        request_body=request_body,
                        response=normalized,
                    )
                    if empty_reason == "empty_responses_output" and effective_protocol == "openai_responses":
                        effective_protocol = "chat"
                        allow_streaming = False
                        allow_json_object = False
                        allow_tools = False
                        empty_same_mode_retries = 0
                        transport_same_mode_retries = 0
                        print(
                            "[VBF] fallback_mode=empty_responses_output_retry_chat_nonstream",
                            flush=True,
                        )
                        continue
                    force_mode_change = has_tool_history or effective_protocol == "openai_responses"
                    if (
                        not force_mode_change
                        and empty_same_mode_retries < max_empty_same_mode_retries
                    ):
                        empty_same_mode_retries += 1
                        print(
                            "[VBF] fallback_mode=empty_response_retry_same_mode "
                            f"retry={empty_same_mode_retries}",
                            flush=True,
                        )
                        continue
                    empty_same_mode_retries = 0
                    if allow_tools:
                        allow_tools = False
                        if force_mode_change and allow_json_object:
                            allow_json_object = False
                        print("[VBF] fallback_mode=empty_response_local_disable_tools_retry")
                        continue
                    if allow_json_object:
                        allow_json_object = False
                        print("[VBF] fallback_mode=empty_response_local_disable_json_object_retry")
                        continue
                    raise RuntimeError("LLM returned empty response with no content or tool calls")

                if normalized.has_tool_calls():
                    return normalized
                return self.parse_response(normalized)

            raise RuntimeError("LLM provider returned no usable content after compatibility fallbacks")

        # Tool call loop
        current_messages = list(messages)  # Copy to avoid mutating original
        current_tools = tools
        max_tool_only_rounds = max(
            1,
            int(self._model_config.get("max_consecutive_tool_only_rounds", 2)),
        )
        consecutive_tool_only_rounds = 0

        for iteration in range(max_tool_calls):
            response = await asyncio.to_thread(_sync_http_call, current_messages, current_tools)

            if isinstance(response, VBFLLMResponse) and response.has_tool_calls():
                planning_tool_calls = [
                    tool_call
                    for tool_call in response.tool_calls
                    if self._is_planning_skill_tool_call(tool_call.name)
                ]
                if planning_tool_calls:
                    print(
                        "[VBF] planning_tool_calls_converted "
                        f"steps={len(planning_tool_calls)}",
                        flush=True,
                    )
                    return self._planning_tool_calls_to_plan(planning_tool_calls)

                if response.content and str(response.content).strip():
                    consecutive_tool_only_rounds = 0
                else:
                    consecutive_tool_only_rounds += 1
                executed_tools = []
                for tool_call in response.tool_calls:
                    if tool_call.name == "load_skill":
                        result = self.load_skill(tool_call.arguments.get("skill_name", ""))
                    else:
                        result = {"error": f"Unknown tool: {tool_call.name}"}
                    executed_tools.append(
                        {
                            "tool_call_id": tool_call.id,
                            "tool_name": tool_call.name,
                            "args": tool_call.arguments,
                            "result": result,
                        }
                    )

                # Add assistant message with tool calls
                current_messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        internal_tool_call_to_chat(tool_call)
                        for tool_call in response.tool_calls
                    ],
                })

                # Add tool result messages
                for tr in executed_tools:
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_call_id"],
                        "content": json.dumps(tr["result"], ensure_ascii=False, indent=2),
                    })

                if consecutive_tool_only_rounds >= max_tool_only_rounds:
                    print(
                        "[VBF] fallback_mode=tool_only_loop_local_disable_tools_retry "
                        f"rounds={consecutive_tool_only_rounds}",
                        flush=True,
                    )
                    retry_messages = self._build_tool_budget_exhaustion_messages(current_messages)
                    retry_response = await asyncio.to_thread(_sync_http_call, retry_messages, None)
                    if (
                        isinstance(retry_response, VBFLLMResponse)
                        and retry_response.has_tool_calls()
                    ):
                        raise RuntimeError(
                            "LLM stayed in a tool-calling loop after tools were disabled."
                        )
                    return retry_response

                # Continue loop
                continue

            # No tool calls - final response
            return response

        # Max iterations exceeded
        print(
            "[VBF] fallback_mode=tool_budget_exhausted_final_retry "
            f"iterations={max_tool_calls}",
            flush=True,
        )
        retry_messages = self._build_tool_budget_exhaustion_messages(current_messages)
        response = await asyncio.to_thread(_sync_http_call, retry_messages, None)
        if isinstance(response, VBFLLMResponse) and response.has_tool_calls():
            raise RuntimeError(
                f"Max tool call iterations ({max_tool_calls}) exceeded. "
                "LLM may be stuck in a tool-calling loop."
            )
        return response
