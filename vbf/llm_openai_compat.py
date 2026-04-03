import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI, APIError, APIConnectionError, APITimeoutError


class LLMError(RuntimeError):
    pass


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """Best-effort JSON extraction — handles providers that wrap JSON in prose."""
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
    """从 dict 中解析 bool 字段，支持类型容错。"""
    if key not in data:
        return default
    value = data[key]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    logging.warning(
        "vbf llm_config: field '%s' has unexpected type %s (value=%r), using default %s",
        key, type(value).__name__, value, default,
    )
    return default


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


def load_openai_compat_config(config_path: Optional[str] = None) -> Optional[OpenAICompatConfig]:
    """
    Load LLM config in priority order:
    1. Env vars: VBF_LLM_BASE_URL, VBF_LLM_API_KEY, VBF_LLM_MODEL
    2. Config file: VBF_LLM_CONFIG_PATH or vbf/config/llm_config.json
    """
    config_path = config_path or os.getenv("VBF_LLM_CONFIG_PATH")

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
        )

    if not config_path:
        default = os.path.join(os.path.dirname(__file__), "config", "llm_config.json")
        if os.path.exists(default):
            config_path = default

    if not config_path:
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise LLMError(f"Failed to load LLM config: {config_path}: {e}") from e

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
    )


class OpenAICompatLLM:
    def __init__(self, cfg: OpenAICompatConfig):
        self.cfg = cfg
        self._client = OpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
        )

    def chat_json(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
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
