"""
兼容占位模块。

当前 Vibe Protocol 的核心实现已迁移到 `vbf/` 包内（可被外部项目复用）。
`client/` 仅保留为历史入口与示例目录。
"""

from typing import Any, Dict, List


def build_radio_task_plan(prompt: str) -> List[Dict[str, Any]]:
    """
    Stub: return a high-level plan.

    Note:
    - The actual spatial_query dependence is handled by the client execution loop
      (because spatial_query returns dynamic coordinates).
    """
    # This is a placeholder for future LLM planning.
    return [{"task": "radio", "prompt": prompt}]

