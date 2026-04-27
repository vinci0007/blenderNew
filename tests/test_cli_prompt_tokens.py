import pytest

from vbf.app.cli import _build_parser, _merge_prompt_tokens, _resolve_prompt_and_resume_arg, _run


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


@pytest.mark.asyncio
async def test_cli_run_saves_full_result_without_printing_payload(monkeypatch, tmp_path, capsys):
    result = {
        "prompt": "secret full prompt",
        "step_results": {"001": {"ok": True, "data": {"object_name": "Body"}}},
        "plan": {"steps": [{"step_id": "001", "skill": "create_primitive"}]},
    }

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self._runtime_paths = {"logs_dir": str(tmp_path)}

        async def run_task_with_feedback(self, **kwargs):
            return result

    monkeypatch.setattr("vbf.app.cli.load_project_paths", lambda: {"logs_dir": str(tmp_path)})
    monkeypatch.setattr("vbf.app.cli.VBFClient", _FakeClient)

    exit_code = await _run(
        prompt="secret full prompt",
        resume_prompt_arg='--prompt "secret full prompt"',
        host=None,
        port=None,
        blender_path=None,
        resume=None,
        save_state=None,
        style="hard_surface_realistic",
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "[VBF] Task ID: task_" in out
    assert "[VBF] Task log:" in out
    assert "[VBF] Result saved:" in out
    assert "[VBF] Summary: steps=1 ok=1 failed=0 unknown=0 plan_steps=1" in out
    assert "{'prompt':" not in out
    assert "secret full prompt" not in out

    task_logs = list(tmp_path.glob("task_*.log"))
    result_logs = list(tmp_path.glob("task_result_task_*.json"))
    assert len(result_logs) == 1
    assert len(task_logs) == 1
    assert task_logs[0].stem in result_logs[0].stem
    task_log_text = task_logs[0].read_text(encoding="utf-8")
    assert "[VBF] Summary: steps=1 ok=1 failed=0 unknown=0 plan_steps=1" in task_log_text
    assert "secret full prompt" in result_logs[0].read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_cli_run_reports_missing_blender_executable(monkeypatch, tmp_path, capsys):
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self._runtime_paths = {"logs_dir": str(tmp_path)}

        async def run_task_with_feedback(self, **kwargs):
            raise FileNotFoundError(
                "Blender executable not found: blender. Set BLENDER_PATH or pass --blender-path."
            )

    monkeypatch.setattr("vbf.app.cli.load_project_paths", lambda: {"logs_dir": str(tmp_path)})
    monkeypatch.setattr("vbf.app.cli.VBFClient", _FakeClient)

    exit_code = await _run(
        prompt="create a chair",
        resume_prompt_arg='--prompt "create a chair"',
        host=None,
        port=None,
        blender_path=None,
        resume=None,
        save_state=None,
        style="hard_surface_realistic",
    )

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "[VBF] Startup failed:" in out
    assert "BLENDER_PATH" in out
