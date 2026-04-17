import argparse
import asyncio

from .client import VBFClient
from .task_state import TaskInterruptedError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vbf", description="Vibe-Blender-Flow CLI")
    p.add_argument("--prompt", type=str, required=True, help="自然语言建模需求")
    p.add_argument(
        "--host", type=str, default=None, help="Blender WebSocket host（覆盖 VBF_WS_HOST）"
    )
    p.add_argument(
        "--port", type=int, default=None, help="Blender WebSocket port（覆盖 VBF_WS_PORT）"
    )
    p.add_argument(
        "--blender-path", type=str, default=None, help="Blender 可执行文件路径（覆盖 BLENDER_PATH）"
    )
    p.add_argument(
        "--resume",
        type=str,
        default=None,
        metavar="STATE_FILE",
        help="从中断状态文件续做（由上次中断时自动保存）",
    )
    p.add_argument(
        "--save-state",
        type=str,
        default=None,
        metavar="STATE_FILE",
        help="中断时保存状态到指定路径（默认 ./vbf_task_state.json）",
    )
    p.add_argument(
        "--style",
        type=str,
        default="hard_surface_realistic",
        choices=[
            "hard_surface_realistic",
            "stylized_low_poly",
            "organic_character",
            "prop_industrial",
        ],
        help="建模风格模板 (默认: hard_surface_realistic)",
    )
    p.add_argument("--list-styles", action="store_true", help="列出可用风格模板")
    # Closed-loop feedback control
    g = p.add_argument_group("闭环反馈控制")
    g.add_argument(
        "--no-feedback",
        action="store_true",
        help="禁用闭环反馈（使用原有的 run_task）",
    )
    g.add_argument(
        "--no-auto-check",
        action="store_true",
        help="禁用每个 skill 后的自动验证",
    )
    g.add_argument(
        "--no-llm-feedback",
        action="store_true",
        help="禁用 stage 边界的 LLM 深度分析",
    )
    return p


async def _run(
    prompt: str,
    host: str | None,
    port: int | None,
    blender_path: str | None,
    resume: str | None,
    save_state: str | None,
    style: str,
    no_feedback: bool = False,
    no_auto_check: bool = False,
    no_llm_feedback: bool = False,
) -> int:
    client = VBFClient(host=host, port=port, blender_path=blender_path)
    try:
        if no_feedback:
            # Legacy mode: no closed-loop feedback
            result = await client.run_task(
                prompt=prompt,
                resume_state_path=resume,
                save_state_path=save_state,
                style=style,
            )
        else:
            # Closed-loop mode with feedback
            result = await client.run_task_with_feedback(
                prompt=prompt,
                resume_state_path=resume,
                save_state_path=save_state,
                style=style,
                enable_auto_check=not no_auto_check,
                enable_llm_feedback=not no_llm_feedback,
            )
        print(result)
        return 0
    except TaskInterruptedError as e:
        print(f"[VBF] Task interrupted: {e}")
        print(f'[VBF] To resume, run: vbf --prompt "{prompt}" --resume "{e.state_path}"')
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Handle --list-styles
    if args.list_styles:
        from .style_templates import get_style_help_text

        print(get_style_help_text())
        return 0

    return asyncio.run(
        _run(
            args.prompt,
            args.host,
            args.port,
            args.blender_path,
            args.resume,
            args.save_state,
            args.style,
            args.no_feedback,
            args.no_auto_check,
            args.no_llm_feedback,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
