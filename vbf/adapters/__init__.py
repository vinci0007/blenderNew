# VBF Adapters - Multi-model LLM support
"""Model adapters for various LLM APIs.

Provides unified interface for:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic Claude
- Chinese models (GLM-4, Kimi, Qwen, MiniMax)
- Local models (Ollama)
- Any OpenAI-compatible API

Usage:
    from vbf import get_adapter
    from vbf.app.client import VBFClient

    client = VBFClient()
    await client.connect()

    adapter = get_adapter("glm-4", client=client)
    await adapter.init()  # Loads skills from Blender

    messages = adapter.format_messages("Create a cube")
    # Send to LLM API...
    plan = adapter.parse_response(llm_response)
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..config_runtime import load_llm_section

if TYPE_CHECKING:
    from ..app.client import VBFClient

# Load model configuration from vbf/config/config.toml -> llm section.
def _load_model_config() -> Dict[str, Any]:
    return load_llm_section()


_MODEL_CONFIG = _load_model_config()

# Response content extraction paths (configurable, not hardcoded)
# Use dot notation for nested paths: "choices[0].message.content"
RESPONSE_CONTENT_PATHS: List[Dict[str, Any]] = [
    # Standard OpenAI format
    {"paths": ["choices[0].message.content", "choices.0.message.content"], "priority": 1},
    # Chinese models format (data wrapper)
    {"paths": ["data.choices[0].content", "data.choices.0.content"], "priority": 2},
    # Direct fields
    {"paths": ["result", "content", "text"], "priority": 3},
]

# Map model names to adapter configurations
SUPPORTED_MODELS: Dict[str, Dict[str, Any]] = {
    # OpenAI models
    "openai": {
        "provider": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": ["OPENAI_API_KEY"],
        "default_model": "gpt-4o",
        "supports_streaming": True,
        "response_content_path": "choices[0].message.content",
    },
    "gpt-4": {
        "provider": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": ["OPENAI_API_KEY"],
        "default_model": "gpt-4",
        "supports_streaming": True,
        "response_content_path": "choices[0].message.content",
    },
    "gpt-4o": {
        "provider": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": ["OPENAI_API_KEY"],
        "default_model": "gpt-4o",
        "supports_streaming": True,
        "response_content_path": "choices[0].message.content",
    },
    "gpt-3.5": {
        "provider": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": ["OPENAI_API_KEY"],
        "default_model": "gpt-3.5-turbo",
        "supports_streaming": True,
        "response_content_path": "choices[0].message.content",
    },

    # Chinese models (OpenAI compatible)
    "glm-4": {
        "provider": "openai_compat",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": ["ZHIPU_API_KEY", "GLM_API_KEY"],
        "default_model": "glm-4",
        "supports_streaming": True,
        "response_content_path": "choices[0].message.content",
    },
    "kimi": {
        "provider": "openai_compat",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": ["KIMI_API_KEY", "MOONSHOT_API_KEY"],
        "default_model": "moonshot-v1-8k",
        "supports_streaming": True,
        "response_content_path": "choices[0].message.content",
    },
    "qwen": {
        "provider": "openai_compat",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": ["DASHSCOPE_API_KEY", "QWEN_API_KEY"],
        "default_model": "qwen-plus",
        "supports_streaming": True,
        "response_content_path": "choices[0].message.content",
    },
    "minimax": {
        "provider": "openai_compat",
        "base_url": "https://api.minimax.chat/v1",
        "api_key_env": ["MINIMAX_API_KEY"],
        "default_model": "abab6-chat",
        "supports_streaming": True,
        "response_content_path": "choices[0].message.content",
    },

    # Local models
    "ollama": {
        "provider": "openai_compat",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": [],
        "default_model": "llama3",
        "supports_streaming": False,
        "few_shot_required": True,
        "skills_subset_limit": 50,
        "response_content_path": "choices[0].message.content",
    },

    # Default: use llm section from config.toml
    "default": {
        "provider": "openai_compat",
        # API settings from config.toml -> llm
        "base_url": _MODEL_CONFIG.get("base_url", "https://api.openai.com/v1"),
        "api_key": _MODEL_CONFIG.get("api_key"),  # Direct API key from config
        "api_key_env": ["VBF_LLM_API_KEY"],  # Fallback env var
        "default_model": _MODEL_CONFIG.get("model", "gpt-4o-mini"),
        "supports_streaming": _MODEL_CONFIG.get("supports_streaming", True),
        "chat_completions_path": _MODEL_CONFIG.get(
            "chat_completions_path", "/chat/completions"
        ),
        "response_format": {"type": "json_object"}
        if _MODEL_CONFIG.get("use_response_format_json_object", False)
        else {},
        "use_function_calling": _MODEL_CONFIG.get("use_function_calling", True),
        "use_streaming": _MODEL_CONFIG.get("use_streaming", "auto"),
        "temperature": _MODEL_CONFIG.get("temperature", 0.2),
        "is_proxy_api": _MODEL_CONFIG.get("is_proxy_api", False),
        "enable_extra_request_headers": _MODEL_CONFIG.get("enable_extra_request_headers", False),
        "use_curl_http_compat": _MODEL_CONFIG.get("use_curl_http_compat", False),
        "http_timeout_seconds": _MODEL_CONFIG.get("llm_api_throttling", {}).get("call_timeout_seconds", 60.0),
        "planning_context": _MODEL_CONFIG.get("planning_context", {}),
        "planning_capability_probe": _MODEL_CONFIG.get("planning_capability_probe", {}),
        "request_headers": _MODEL_CONFIG.get("request_headers", {}),
        "response_content_path": "choices[0].message.content",
    },
}


def get_adapter(
    model_name: str,
    client: Optional["VBFClient"] = None,
    config_override: Optional[Dict[str, Any]] = None,
) -> "VBFModelAdapter":
    """Factory function to create appropriate adapter for the model.

    Args:
        model_name: Model identifier (openai, glm-4, kimi, etc.)
        client: VBFClient instance for RPC communication with Blender.
                REQUIRED for skill loading.
        config_override: Optional config to override defaults

    Returns:
        Configured VBFModelAdapter instance

    Raises:
        ValueError: If model not supported or client not provided

    Example:
        client = VBFClient()
        await client.connect()
        adapter = get_adapter("glm-4", client=client)
        await adapter.init()  # Loads skills from Blender
    """
    name = model_name.lower()

    # Get model config
    model_config = SUPPORTED_MODELS.get(name)
    if model_config is None:
        raise ValueError(
            f"Unsupported model: {model_name}. "
            f"Available: {', '.join(SUPPORTED_MODELS.keys())}"
        )

    # Merge with overrides
    if config_override:
        model_config = {**model_config, **config_override}

    # Validate client is provided
    if client is None:
        raise ValueError(
            f"VBFClient required for adapter. "
            f"Use: get_adapter('{model_name}', client=client)"
        )

    # Use unified OpenAI compatible adapter for all
    from .openai_compat_adapter import OpenAICompatAdapter
    return OpenAICompatAdapter(
        model_name=name,
        model_config=model_config,
        client=client,
    )


def list_supported_models() -> List[str]:
    """Return list of supported model names."""
    return list(SUPPORTED_MODELS.keys())


# Re-export classes
from .base_adapter import VBFModelAdapter
from .openai_compat_adapter import OpenAICompatAdapter

# Re-export SkillRegistry
from .skill_registry import SkillRegistry, get_registry

__all__ = [
    "VBFModelAdapter",
    "OpenAICompatAdapter",
    "SkillRegistry",
    "get_registry",
    "get_adapter",
    "list_supported_models",
    "SUPPORTED_MODELS",
    "RESPONSE_CONTENT_PATHS",
]
