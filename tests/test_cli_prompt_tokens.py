import pytest

from vbf.app.cli import _build_parser, _merge_prompt_tokens, _resolve_prompt_and_resume_arg


def test_merge_prompt_tokens_keeps_single_string():
    prompt = "line1\nline2"
    assert _merge_prompt_tokens(prompt) == prompt


def test_merge_prompt_tokens_joins_token_list():
    assert _merge_prompt_tokens(["Create", "a", "phone"]) == "Create a phone"


def test_parser_accepts_split_prompt_tokens_and_other_flags():
    parser = _build_parser()
    args = parser.parse_args([
        "--port",
        "28006",
        "--prompt",
        "Create",
        "a",
        "production-ready",
        "phone",
        "--no-llm-feedback",
    ])

    assert args.port == 28006
    assert args.no_llm_feedback is True
    assert _merge_prompt_tokens(args.prompt) == "Create a production-ready phone"
    prompt, resume_arg = _resolve_prompt_and_resume_arg(parser, args)
    assert prompt == "Create a production-ready phone"
    assert resume_arg == '--prompt "Create a production-ready phone"'


def test_parser_keeps_single_multiline_prompt_token():
    parser = _build_parser()
    raw_prompt = "line1\nline2\n- bullet"
    args = parser.parse_args(["--prompt", raw_prompt])

    assert _merge_prompt_tokens(args.prompt) == raw_prompt


def test_prompt_file_is_loaded_as_raw_text(tmp_path):
    parser = _build_parser()
    raw_prompt = "line1\n--mock-flag should stay text\nline3"
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(raw_prompt, encoding="utf-8")

    args = parser.parse_args(["--prompt-file", str(prompt_file)])
    prompt, resume_arg = _resolve_prompt_and_resume_arg(parser, args)

    assert prompt == raw_prompt
    assert resume_arg == f'--prompt-file "{prompt_file}"'


def test_prompt_and_prompt_file_are_mutually_exclusive(tmp_path):
    parser = _build_parser()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hello", encoding="utf-8")
    args = parser.parse_args(["--prompt", "hello", "--prompt-file", str(prompt_file)])

    with pytest.raises(SystemExit):
        _resolve_prompt_and_resume_arg(parser, args)


def test_prompt_or_prompt_file_required_when_not_listing_styles():
    parser = _build_parser()
    args = parser.parse_args([])

    with pytest.raises(SystemExit):
        _resolve_prompt_and_resume_arg(parser, args)


def test_list_styles_does_not_require_prompt_inputs():
    parser = _build_parser()
    args = parser.parse_args(["--list-styles"])

    assert args.list_styles is True
    assert args.prompt is None
    assert args.prompt_file is None
