import argparse
import asyncio

from .client import VBFClient
from .task_state import TaskInterruptedError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vbf", description="Vibe-Blender-Flow CLI")
    p.add_argument("--prompt", type=str, required=True, help="自然语言建模需求")
    p.add_argument("--host", type=str, default=None, help="Blender WebSocket host（覆盖 VBF_WS_HOST）")
    p.add_argument("--port", type=int, default=None, help="Blender WebSocket port（覆盖 VBF_WS_PORT）")
    p.add_argument("--blender-path", type=str, default=None, help="Blender 可执行文件路径（覆盖 BLENDER_PATH）")
    p.add_argument("--resume", type=str, default=None, metavar="STATE_FILE",
                   help="从中断状态文件续做（由上次中断时自动保存）")
    p.add_argument("--save-state", type=str, default=None, metavar="STATE_FILE",
                   help="中断时保存状态到指定路径（默认 ./vbf_task_state.json）")
    return p


async def _run(
    prompt: str,
    host: str | None,
    port: int | None,
    blender_path: str | None,
    resume: str | None,
    save_state: str | None,
) -> int:
    client = VBFClient(host=host, port=port, blender_path=blender_path)
    try:
        result = await client.run_task(
            prompt=prompt,
            resume_state_path=resume,
            save_state_path=save_state,
        )
        print(result)
        return 0
    except TaskInterruptedError as e:
        print(f"[VBF] Task interrupted: {e}")
        print(f"[VBF] To resume, run: vbf --prompt \"{prompt}\" --resume \"{e.state_path}\"")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(
        args.prompt,
        args.host,
        args.port,
        args.blender_path,
        args.resume,
        args.save_state,
    ))


if __name__ == "__main__":
    raise SystemExit(main())
