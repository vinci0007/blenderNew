"""
鍏煎鍏ュ彛锛堜笉寤鸿鏂伴」鐩户缁緷璧?/client锛夈€?
鎺ㄨ崘鏀圭敤锛?- `python -m vbf --prompt "..."`
- 鎴栧畨瑁呭悗 `vbf --prompt "..."`
"""

from __future__ import annotations

import sys

from vbf.app.cli import main as vbf_main


if __name__ == "__main__":
    # Keep compatibility for existing scripts.
    raise SystemExit(vbf_main(sys.argv[1:]))

