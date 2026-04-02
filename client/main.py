"""
兼容入口（不建议新项目继续依赖 /client）。

推荐改用：
- `python -m vbf --prompt "..."`
- 或安装后 `vbf --prompt "..."`
"""

from __future__ import annotations

import sys

from vbf.cli import main as vbf_main


if __name__ == "__main__":
    # Keep compatibility for existing scripts.
    raise SystemExit(vbf_main(sys.argv[1:]))

