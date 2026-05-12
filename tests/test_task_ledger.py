from vbf.core.task_ledger import TaskLedger, ledger_path_for_task


def test_task_ledger_round_trips_progress(tmp_path):
    ledger = TaskLedger(
        task_id="task/abc",
        prompt="create a complex product",
        stages=["geometry_modeling", "uv_texture_material"],
    )
    ledger.record_planned_batch(
        stage="geometry_modeling",
        batch_index=1,
        step_ids=["001", "002"],
        continue_stage=True,
        remaining_work=["add secondary details"],
        response_id="resp_1",
    )
    ledger.record_completed_batch(
        stage="geometry_modeling",
        batch_index=1,
        step_ids=["001"],
        continue_stage=True,
        remaining_work=["add secondary details"],
    )
    ledger.last_error = "timeout"

    path = ledger_path_for_task(str(tmp_path), "task/abc")
    ledger.save(path)
    restored = TaskLedger.load(path)

    assert restored.task_id == "task/abc"
    assert restored.current_stage == "geometry_modeling"
    assert restored.current_batch_index == 1
    assert restored.pending_work == ["add secondary details"]
    assert restored.last_response_id == "resp_1"
    assert restored.last_error == "timeout"
    assert restored.planned_batches[0]["step_ids"] == ["001", "002"]
    assert restored.completed_batches[0]["step_ids"] == ["001"]


def test_task_ledger_record_batch_aliases_completed_batches():
    ledger = TaskLedger(
        task_id="task_abc",
        prompt="create a complex product",
        stages=["geometry_modeling"],
    )
    ledger.record_batch(
        stage="geometry_modeling",
        batch_index=1,
        step_ids=["001", "002"],
        continue_stage=False,
    )

    assert ledger.completed_batches[0]["step_ids"] == ["001", "002"]
    assert ledger.planned_batches == []


def test_ledger_path_sanitizes_task_id(tmp_path):
    path = ledger_path_for_task(str(tmp_path), "task\\abc/def")
    assert path.endswith("task_ledger_task_abc_def.json")
