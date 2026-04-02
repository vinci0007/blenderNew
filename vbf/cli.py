import argparse
import asyncio

from .client import VBFClient


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vbf", description="Vibe-Blender-Flow CLI")
    p.add_argument("--prompt", type=str, required=True, help="自然语言建模需求")
    p.add_argument("--host", type=str, default=None, help="Blender WebSocket host（覆盖 VBF_WS_HOST）")
    p.add_argument("--port", type=int, default=None, help="Blender WebSocket port（覆盖 VBF_WS_PORT）")
    p.add_argument("--blender-path", type=str, default=None, help="Blender 可执行文件路径（覆盖 BLENDER_PATH）")
    return p


async def _run(prompt: str, host: str | None, port: int | None, blender_path: str | None) -> int:
    client = VBFClient(host=host, port=port, blender_path=blender_path)
    result = await client.run_task(prompt=prompt)
    print(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.prompt, args.host, args.port, args.blender_path))


if __name__ == "__main__":
    raise SystemExit(main())

