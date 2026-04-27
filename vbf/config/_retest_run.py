import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vbf.app.client import VBFClient
from vbf.config_runtime import load_project_paths
from vbf.runtime.run_logging import (
    append_run_event,
    create_task_log_context,
    summarize_task_result,
    tee_console_to_task_log,
    write_task_result_log,
)

async def main():
    runtime_paths = load_project_paths()
    log_context = create_task_log_context(runtime_paths["logs_dir"])
    with tee_console_to_task_log(log_context):
        print(f"[VBF-Retest] Task ID: {log_context.task_id}")
        print(f"[VBF-Retest] Task created: {log_context.created_at}")
        print(f"[VBF-Retest] Task log: {log_context.transcript_path}")
        prompt = Path('assets/prompt_test.md').read_text(encoding='utf-8')
        client = VBFClient(port=28006)
        client._task_id = log_context.task_id
        client._task_log_path = str(log_context.transcript_path)
        client._task_logging_managed = True
        result = await client.run_task_with_feedback(
            prompt=prompt,
            style='hard_surface_realistic',
            enable_auto_check=True,
            enable_llm_feedback=True,
        )
        logs_dir = str(log_context.logs_dir)
        result_path = write_task_result_log(
            result,
            logs_dir,
            prefix="retest_task_result",
            task_id=log_context.task_id,
        )
        summary = summarize_task_result(result)
        event_path = append_run_event(
            "retest_task_result_saved",
            {
                "task_id": log_context.task_id,
                "steps": summary["steps"],
                "ok": summary["ok"],
                "failed": summary["failed"],
                "unknown": summary["unknown"],
                "plan_steps": summary["plan_steps"],
                "result_file": str(result_path),
                "task_log_file": str(log_context.transcript_path),
            },
            logs_dir,
        )
        print(f"[VBF-Retest] Result saved: {result_path}")
        print(f"[VBF-Retest] Event log: {event_path}")
        print(
            "[VBF-Retest] Summary: "
            f"steps={summary['steps']} "
            f"ok={summary['ok']} "
            f"failed={summary['failed']} "
            f"unknown={summary['unknown']} "
            f"plan_steps={summary['plan_steps']}"
        )

if __name__ == '__main__':
    asyncio.run(main())
