from typing import Any, Dict, List


class LLMAdapter:
    """
    Interface for LLM planning.
    For now we keep a stub so the project is runnable without an LLM provider.
    """

    async def plan(self, prompt: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class DeterministicPlanner(LLMAdapter):
    async def plan(self, prompt: str) -> List[Dict[str, Any]]:
        # This stub is intentionally deterministic for demo purposes.
        return [{"task": "radio", "prompt": prompt}]

