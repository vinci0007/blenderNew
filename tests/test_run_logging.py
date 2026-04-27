import json

import pytest

from vbf.app.client import VBFClient
from vbf.runtime.run_logging import (
    append_run_event,
    create_task_log_context,
    summarize_task_result,
    tee_console_to_task_log,
    write_task_result_log,
)


def test_summarize_task_result_counts_steps_without_payload_dump():
    result = {
        "prompt": "create a phone",
        "step_results": {
            "001": {"ok": True, "data": {"object_name": "Body"}},
            "002": {"ok": False, "error": "boom"},
            "003": {"data": {"note": "unknown"}},
        },
        "plan": {
            "vbf_version": "2.1",
            "plan_type": "skills_plan",
            "steps": [{"step_id": "001"}, {"step_id": "002"}],
        },
    }

    summary = summarize_task_result(result)

    assert summary["steps"] == 3
    assert summary["ok"] == 1
    assert summary["failed"] == 1
    assert summary["unknown"] == 1
    assert summary["plan_steps"] == 2
    assert summary["failed_step_ids"] == ["002"]
    assert summary["prompt_chars"] == len("create a phone")


def test_write_task_result_log_persists_full_result_and_summary(tmp_path):
    result = {
        "prompt": "full prompt should be in the log",
        "step_results": {"001": {"ok": True}},
        "plan": {"steps": [{"step_id": "001"}]},
    }

    path = write_task_result_log(result, tmp_path, task_id="task_0426-120000_abcd1234")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "task_result_task_0426-120000_abcd1234.json"
    assert payload["event"] == "task_result"
    assert payload["task_id"] == "task_0426-120000_abcd1234"
    assert payload["summary"]["steps"] == 1
    assert payload["result"] == result


def test_append_run_event_writes_text_record(tmp_path):
    path = append_run_event(
        "task_completed",
        {"task_id": "task_0426-120000_abcd1234", "steps": 3, "ok": 3},
        tmp_path,
    )
    line = path.read_text(encoding="utf-8").strip()

    assert path.name.startswith("run_events_")
    assert path.suffix == ".log"
    assert line.startswith("task_0426-120000_abcd1234 task_completed")
    assert "task_completed" in line
    assert "steps=3" in line
    assert "ok=3" in line


def test_tee_console_to_task_log_mirrors_stdout_and_stderr(tmp_path, capsys):
    context = create_task_log_context(tmp_path)

    with tee_console_to_task_log(context):
        print("hello stdout")
        print("hello stderr", file=__import__("sys").stderr)

    captured = capsys.readouterr()
    log_text = context.transcript_path.read_text(encoding="utf-8")
    assert context.task_id in context.transcript_path.name
    assert context.task_id.startswith("task_")
    assert "/" not in context.task_id
    assert ":" not in context.task_id
    assert "hello stdout" in captured.out
    assert "hello stderr" in captured.err
    assert "hello stdout" in log_text
    assert "hello stderr" in log_text
    assert "task_log_opened" in log_text
    assert "task_log_closed" in log_text


@pytest.mark.asyncio
async def test_client_direct_run_gets_fresh_task_log_each_time(monkeypatch, tmp_path):
    async def _fake_run_task_impl(client, *args, **kwargs):
        print("inner task console")
        return {
            "prompt": "direct prompt",
            "step_results": {"001": {"ok": True}},
            "plan": {"steps": [{"step_id": "001"}]},
        }

    monkeypatch.setattr("vbf.app.client.run_task_impl", _fake_run_task_impl)
    client = VBFClient()
    client._runtime_paths["logs_dir"] = str(tmp_path)

    await client.run_task("direct prompt")
    await client.run_task("direct prompt")

    task_logs = sorted(tmp_path.glob("task_*.log"))
    result_logs = sorted(tmp_path.glob("task_result_task_*.json"))
    assert len(task_logs) == 2
    assert len(result_logs) == 2
    assert task_logs[0].name != task_logs[1].name
    assert "inner task console" in task_logs[0].read_text(encoding="utf-8")
    assert "inner task console" in task_logs[1].read_text(encoding="utf-8")
