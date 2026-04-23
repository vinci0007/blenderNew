import argparse
import asyncio
from pathlib import Path

from .client import VBFClient
from ..core.task_state import TaskInterruptedError


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vbf", description="Vibe-Blender-Flow CLI")
    p.add_argument(
        "--prompt",
        type=str,
        nargs="+",
        default=None,
        help="Natural-language modeling prompt",
    )
    p.add_argument(
        "--prompt-file",
        type=str,
        default=None,
        metavar="PROMPT_FILE",
        help="Read modeling prompt from a UTF-8 text file",
    )
    p.add_argument(
        "--host",
        type=str,
        default=None,
        help="Blender WebSocket host (overrides VBF_WS_HOST)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=None,
        help="Blender WebSocket port (overrides VBF_WS_PORT)",
    )
    p.add_argument(
        "--blender-path",
        type=str,
        default=None,
        help="Blender executable path (overrides BLENDER_PATH)",
    )
    p.add_argument(
        "--resume",
        type=str,
        default=None,
        metavar="STATE_FILE",
        help="Resume from a saved interrupted task state",
    )
    p.add_argument(
        "--save-state",
        type=str,
        default=None,
        metavar="STATE_FILE",
        help="Path to save interrupted task state",
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
        help="Modeling style template (default: hard_surface_realistic)",
    )
    p.add_argument("--list-styles", action="store_true", help="List available style templates")

    # Closed-loop feedback control
    g = p.add_argument_group("Closed-loop feedback")
    g.add_argument(
        "--no-feedback",
        action="store_true",
        help="Disable closed-loop feedback and use legacy run_task mode",
    )
    g.add_argument(
        "--no-auto-check",
        action="store_true",
        help="Disable automatic per-skill validation",
    )
    g.add_argument(
        "--no-llm-feedback",
        action="store_true",
        help="Disable stage-boundary LLM deep analysis",
    )
    return p


def _merge_prompt_tokens(prompt_tokens: str | list[str]) -> str:
    """Merge tokenized --prompt values into a single string."""
    if isinstance(prompt_tokens, str):
        return prompt_tokens
    if not prompt_tokens:
        return ""
    if len(prompt_tokens) == 1:
        return prompt_tokens[0]
    return " ".join(prompt_tokens)


def _resolve_prompt_and_resume_arg(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> tuple[str, str]:
    """Resolve prompt text and a corresponding resume command argument."""
    if args.prompt is not None and args.prompt_file is not None:
        parser.error("--prompt and --prompt-file are mutually exclusive")

    if args.prompt_file is not None:
        try:
            prompt_text = Path(args.prompt_file).read_text(encoding="utf-8-sig")
        except OSError as exc:
            parser.error(f"failed to read --prompt-file '{args.prompt_file}': {exc}")
        return prompt_text, f'--prompt-file "{args.prompt_file}"'

    if args.prompt is not None:
        prompt_text = _merge_prompt_tokens(args.prompt)
        return prompt_text, f'--prompt "{prompt_text}"'

    parser.error("one of --prompt or --prompt-file is required (unless --list-styles)")
    return "", ""


async def _run(
    prompt: str,
    resume_prompt_arg: str,
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
        print(f'[VBF] To resume, run: vbf {resume_prompt_arg} --resume "{e.state_path}"')
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Handle --list-styles
    if args.list_styles:
        from ..runtime.style_templates import get_style_help_text

        print(get_style_help_text())
        return 0

    prompt, resume_prompt_arg = _resolve_prompt_and_resume_arg(parser, args)

    return asyncio.run(
        _run(
            prompt,
            resume_prompt_arg,
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
