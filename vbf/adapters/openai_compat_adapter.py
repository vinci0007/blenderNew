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

from .base_adapter import VBFModelAdapter

if TYPE_CHECKING:
    from ..client import VBFClient


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
    _COMPAT_MODE_CACHE: Dict[str, Dict[str, bool]] = {}

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

        # Progressive disclosure: use function calling for on-demand skill loading
        self.use_function_calling = model_config.get(
            "use_function_calling", True  # Default: enabled (progressive disclosure)
        )

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

        # Runtime compatibility mode (provider-specific, cached in-process).
        self._compat_mode_key = f"{self.base_url}|{self.default_model}"
        default_allow_json = self.response_format.get("type") == "json_object"
        default_allow_tools = bool(self.use_function_calling)
        cached = self._COMPAT_MODE_CACHE.get(self._compat_mode_key, {})
        self._allow_json_object = bool(cached.get("allow_json_object", default_allow_json))
        self._allow_tools = bool(cached.get("allow_tools", default_allow_tools))
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

        # Add response_format if supported and not streaming
        if not stream and self.response_format.get("type") == "json_object":
            request["response_format"] = {"type": "json_object"}

        # Add streaming flag if supported
        if stream and self.supports_streaming:
            request["stream"] = True

        return request

    def _persist_compat_mode(self) -> None:
        self._COMPAT_MODE_CACHE[self._compat_mode_key] = {
            "allow_json_object": bool(self._allow_json_object),
            "allow_tools": bool(self._allow_tools),
        }

    def _build_api_request_with_mode(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]],
        allow_tools: bool,
        allow_json_object: bool,
    ) -> Dict[str, Any]:
        effective_tools = tools if allow_tools else None
        request = self.build_api_request(messages, tools=effective_tools)
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
            f"json_object={'on' if self._allow_json_object else 'off'}"
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
            "model": self.default_model,
            "base_url": self.base_url,
        }

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

        tools = self.build_tools_for_llm() if self.use_function_calling else None
        max_tool_calls = 10
        self._log_compat_mode_once()

        def _sync_http_call(req_messages: List[Dict], req_tools: Optional[List[Dict]]) -> Any:
            """Synchronous HTTP call (runs in thread pool)."""
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            allow_tools = bool(req_tools) and bool(self._allow_tools)
            allow_json_object = bool(self._allow_json_object)
            max_attempts = 4

            for attempt in range(max_attempts):
                request_body = self._build_api_request_with_mode(
                    req_messages,
                    req_tools,
                    allow_tools=allow_tools,
                    allow_json_object=allow_json_object,
                )

                try:
                    resp = client.chat.completions.create(**request_body)
                except APITimeoutError as e:
                    raise TimeoutError("LLM call timed out") from e
                except APIConnectionError as e:
                    raise ConnectionError(f"LLM connection failed: {e}") from e
                except APIError as e:
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

                choice = resp.choices[0]
                finish_reason = choice.finish_reason
                message = choice.message

                # Handle function calling
                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_results = []
                    for tc in message.tool_calls:
                        tool_name = tc.function.name
                        arguments = tc.function.arguments
                        tool_call_id = tc.id

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
                content = message.content
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
                current_messages.append({
                    "role": "assistant",
                    "content": raw_message.content,
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
