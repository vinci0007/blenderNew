import json
import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

from openai import OpenAI, APIError, APIConnectionError, APITimeoutError
from ..config_runtime import get_default_config_path, load_full_config


class LLMError(RuntimeError):
    pass


_RESERVED_REQUEST_HEADERS = {"authorization", "content-type", "host"}


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """Best-effort JSON extraction 閳?handles providers that wrap JSON in prose."""
    if not text:
        raise LLMError("Empty LLM response")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError("No JSON object found in LLM response")
    try:
        return json.loads(text[start: end + 1])
    except Exception as e:
        raise LLMError(f"Failed to parse JSON from LLM response: {e}") from e


def _parse_bool_field(data: dict, key: str, default: bool) -> bool:
    """Parse a boolean-like field from config data."""
    if key not in data:
        return default
    value = data[key]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    logging.warning(
        "vbf config llm section: field '%s' has unexpected type %s (value=%r), using default %s",
        key, type(value).__name__, value, default,
    )
    return default


def _extract_llm_payload(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Accept either full config schema or llm-only schema."""
    llm_section = raw_data.get("llm")
    if isinstance(llm_section, dict):
        return llm_section
    return raw_data


def _sanitize_request_headers(raw_headers: Any) -> Dict[str, str]:
    """Normalize optional extra request headers for OpenAI-compatible gateways."""
    if raw_headers is None:
        return {}
    if not isinstance(raw_headers, dict):
        logging.warning(
            "vbf config llm section: field 'request_headers' has unexpected type %s, using empty dict",
            type(raw_headers).__name__,
        )
        return {}

    sanitized: Dict[str, str] = {}
    for raw_key, raw_value in raw_headers.items():
        key = str(raw_key).strip()
        if not key:
            continue
        if key.lower() in _RESERVED_REQUEST_HEADERS:
            logging.warning(
                "vbf config llm section: reserved request header %r ignored",
                key,
            )
            continue
        sanitized[key] = str(raw_value)
    return sanitized


def _resolve_request_headers(
    raw_headers: Any,
    *,
    is_proxy_api: bool,
    enable_extra_request_headers: bool,
) -> Dict[str, str]:
    """Return effective extra headers based on proxy/header feature flags."""
    if not is_proxy_api or not enable_extra_request_headers:
        return {}
    return _sanitize_request_headers(raw_headers)


def _build_chat_completions_url(base_url: str, chat_completions_path: str) -> str:
    """Join base_url + chat_completions_path while avoiding duplicate /v1 segments."""
    parsed = urlsplit(str(base_url or "").strip())
    endpoint_path = str(chat_completions_path or "/chat/completions").strip() or "/chat/completions"
    if not endpoint_path.startswith("/"):
        endpoint_path = f"/{endpoint_path}"

    base_segments = [segment for segment in parsed.path.split("/") if segment]
    endpoint_segments = [segment for segment in endpoint_path.split("/") if segment]
    if base_segments and endpoint_segments and base_segments[-1].lower() == endpoint_segments[0].lower():
        endpoint_segments = endpoint_segments[1:]

    merged_path = "/" + "/".join(base_segments + endpoint_segments)
    return urlunsplit((parsed.scheme, parsed.netloc, merged_path, "", ""))


def _assert_supported_config_name(config_path: str) -> None:
    path = Path(config_path)
    if path.name.lower() in {"llm_config.json", "config.json"}:
        raise LLMError(
            f"Legacy config filename '{path.name}' is no longer supported. "
            "Use 'config.toml' instead."
        )
    if path.suffix.lower() != ".toml":
        raise LLMError(
            f"Unsupported config format '{path.suffix or path.name}'. "
            "Use a TOML config file such as 'config.toml'."
        )


@dataclass
class OpenAICompatConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.2
    chat_completions_path: str = "/v1/chat/completions"
    use_response_format_json_object: bool = True
    use_llm: bool = True
    allow_low_level_gateway: bool = False
    auto_allow_low_level_gateway: bool = True
    is_proxy_api: bool = False
    enable_extra_request_headers: bool = False
    use_curl_http_compat: bool = False
    http_timeout_seconds: float = 60.0
    request_headers: Dict[str, str] | None = None


def load_openai_compat_config(config_path: Optional[str] = None) -> Optional[OpenAICompatConfig]:
    """
    Load LLM config in priority order:
    1. Env vars: VBF_LLM_BASE_URL, VBF_LLM_API_KEY, VBF_LLM_MODEL
    2. Config file: VBF_CONFIG_PATH or vbf/config/config.toml
    """
    config_path = config_path or os.getenv("VBF_CONFIG_PATH")

    base_url = os.getenv("VBF_LLM_BASE_URL")
    api_key = os.getenv("VBF_LLM_API_KEY")
    model = os.getenv("VBF_LLM_MODEL")

    if base_url and api_key and model:
        return OpenAICompatConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=float(os.getenv("VBF_LLM_TEMPERATURE", "0.2")),
            chat_completions_path=os.getenv("VBF_LLM_CHAT_COMPLETIONS_PATH", "/v1/chat/completions"),
            use_response_format_json_object=os.getenv("VBF_LLM_JSON_OBJECT", "1") != "0",
            use_llm=os.getenv("VBF_LLM_ENABLED", "1") != "0",
            allow_low_level_gateway=os.getenv("VBF_ALLOW_LOW_LEVEL_GATEWAY", "0") == "1",
            auto_allow_low_level_gateway=os.getenv("VBF_AUTO_ALLOW_LOW_LEVEL_GATEWAY", "1") == "1",
            is_proxy_api=False,
            enable_extra_request_headers=False,
            use_curl_http_compat=os.getenv("VBF_USE_CURL_HTTP_COMPAT", "0") == "1",
            http_timeout_seconds=float(os.getenv("VBF_LLM_HTTP_TIMEOUT_SECONDS", "60.0")),
            request_headers={},
        )

    data: Dict[str, Any]
    if config_path:
        _assert_supported_config_name(config_path)
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                data = _extract_llm_payload(tomllib.loads(f.read()))
        except Exception as e:
            raise LLMError(f"Failed to load config: {config_path}: {e}") from e
    else:
        try:
            full = load_full_config(get_default_config_path())
        except Exception as e:
            raise LLMError(f"Failed to load config: {get_default_config_path()}: {e}") from e
        data = full.get("llm", {})

    if not isinstance(data, dict) or not data:
        return None

    return OpenAICompatConfig(
        base_url=data["base_url"],
        api_key=data["api_key"],
        model=data["model"],
        temperature=float(data.get("temperature", 0.2)),
        chat_completions_path=data.get("chat_completions_path", "/v1/chat/completions"),
        use_response_format_json_object=bool(data.get("use_response_format_json_object", True)),
        use_llm=bool(data.get("use_llm", True)),
        allow_low_level_gateway=_parse_bool_field(data, "allow_low_level_gateway", False),
        auto_allow_low_level_gateway=_parse_bool_field(data, "auto_allow_low_level_gateway", True),
        is_proxy_api=_parse_bool_field(data, "is_proxy_api", False),
        enable_extra_request_headers=_parse_bool_field(data, "enable_extra_request_headers", False),
        use_curl_http_compat=_parse_bool_field(data, "use_curl_http_compat", False),
        http_timeout_seconds=float(
            data.get("llm_api_throttling", {}).get("call_timeout_seconds", 60.0)
        ),
        request_headers=_resolve_request_headers(
            data.get("request_headers"),
            is_proxy_api=_parse_bool_field(data, "is_proxy_api", False),
            enable_extra_request_headers=_parse_bool_field(data, "enable_extra_request_headers", False),
        ),
    )


class OpenAICompatLLM:
    def __init__(self, cfg: OpenAICompatConfig):
        self.cfg = cfg
        self._client = None
        if not cfg.use_curl_http_compat:
            self._client = OpenAI(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                default_headers=cfg.request_headers or None,
            )

    def _build_http_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        if self.cfg.request_headers:
            headers.update(self.cfg.request_headers)
        return headers

    def _chat_json_via_curl_http(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        import httpx

        kwargs: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
        }
        if self.cfg.use_response_format_json_object:
            kwargs["response_format"] = {"type": "json_object"}

        url = _build_chat_completions_url(self.cfg.base_url, self.cfg.chat_completions_path)
        try:
            with httpx.Client(timeout=self.cfg.http_timeout_seconds) as client:
                response = client.post(
                    url,
                    headers=self._build_http_headers(),
                    json=kwargs,
                )
                response.raise_for_status()
        except httpx.TimeoutException as e:
            raise LLMError(f"LLM request timed out: {e}") from e
        except httpx.RequestError as e:
            raise LLMError(f"LLM connection failed: {e}") from e
        except httpx.HTTPStatusError as e:
            message = e.response.text.strip() or str(e)
            raise LLMError(f"LLM API error ({e.response.status_code}): {message}") from e

        try:
            payload: Any = response.json()
        except Exception:
            payload = response.text

        if isinstance(payload, dict) and isinstance(payload.get("steps"), list):
            return payload
        if isinstance(payload, str):
            return _extract_first_json_object(payload)

        content = None
        if isinstance(payload, dict):
            choices = payload.get("choices")
            if isinstance(choices, list) and choices:
                choice = choices[0]
                if isinstance(choice, dict):
                    message = choice.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")

        if content is None:
            raise LLMError("LLM returned empty content")

        return _extract_first_json_object(str(content))

    def chat_json(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.cfg.use_curl_http_compat:
            return self._chat_json_via_curl_http(messages)

        kwargs: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
        }
        if self.cfg.use_response_format_json_object:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except APIConnectionError as e:
            raise LLMError(f"LLM connection failed: {e}") from e
        except APITimeoutError as e:
            raise LLMError(f"LLM request timed out: {e}") from e
        except APIError as e:
            raise LLMError(f"LLM API error ({e.status_code}): {e.message}") from e

        choice = resp.choices[0]
        content = choice.message.content

        if content is None:
            raise LLMError(f"LLM returned empty content (finish_reason={choice.finish_reason})")

        return _extract_first_json_object(content)
