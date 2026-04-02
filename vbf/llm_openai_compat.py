import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


class LLMError(RuntimeError):
    pass


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """
    Best-effort extraction: find first '{' and last '}' and json.loads the substring.
    Providers that wrap JSON in text are handled.
    """
    if not text:
        raise LLMError("Empty LLM response")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError("No JSON object found in LLM response")

    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except Exception as e:
        raise LLMError(f"Failed to parse JSON from LLM response: {e}") from e


@dataclass
class OpenAICompatConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.2
    chat_completions_path: str = "/v1/chat/completions"
    use_response_format_json_object: bool = True


def load_openai_compat_config(config_path: Optional[str] = None) -> Optional[OpenAICompatConfig]:
    """
    Load config in priority:
    1) env vars (VBF_LLM_BASE_URL, VBF_LLM_API_KEY, VBF_LLM_MODEL, ...)
    2) config file (JSON) at:
       - config_path argument, or env VBF_LLM_CONFIG_PATH
       - default: ./vbf/config/llm.json (package-relative)
    """
    config_path = config_path or os.getenv("VBF_LLM_CONFIG_PATH")

    # Env overrides
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
        )

    if not config_path:
        # Default config candidates under package `vbf/config/`.
        base_dir = os.path.dirname(__file__)
        candidates = [
            os.path.join(base_dir, "config", "llm.json"),
            os.path.join(base_dir, "config", "llm_config.json"),
            os.path.join(base_dir, "config", "openai_compat.json"),
        ]
        for p in candidates:
            try:
                if os.path.exists(p):
                    config_path = p
                    break
            except Exception:
                continue

    if not config_path:
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise LLMError(f"Failed to load LLM config file: {config_path}: {e}") from e

    return OpenAICompatConfig(
        base_url=data["base_url"],
        api_key=data["api_key"],
        model=data["model"],
        temperature=float(data.get("temperature", 0.2)),
        chat_completions_path=data.get("chat_completions_path", "/v1/chat/completions"),
        use_response_format_json_object=bool(data.get("use_response_format_json_object", True)),
    )


class OpenAICompatLLM:
    def __init__(self, cfg: OpenAICompatConfig):
        self.cfg = cfg

    def chat_json(self, messages: list[dict[str, Any]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
        }
        if self.cfg.use_response_format_json_object:
            # Many OpenAI-compatible providers accept it.
            payload["response_format"] = {"type": "json_object"}

        url = self.cfg.base_url.rstrip("/") + self.cfg.chat_completions_path
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.cfg.api_key}",
        }

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as e:
            raise LLMError(f"HTTP request to LLM failed: {e}") from e

        try:
            outer = json.loads(raw)
        except Exception as e:
            raise LLMError(f"Failed to parse LLM outer response JSON: {e}. Raw={raw[:500]}") from e

        # OpenAI Chat Completions shape
        try:
            content = outer["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMError(f"Unexpected LLM response shape: {e}. Outer={outer}") from e

        return _extract_first_json_object(content)

