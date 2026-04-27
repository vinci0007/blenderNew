"""Tests for closed-loop feedback system (Phase 1)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio
import copy

from vbf.app.client import VBFClient
from vbf.core.scene_state import SceneState
from vbf.feedback.geometry_capture import (
    CaptureLevel, ObjectGeometry, GeometryDelta,
    IncrementalSceneCapture, ValidationResult,
)
from vbf.feedback.rules import (
    ValidationRuleRegistry, BuiltinValidationRules,
    register_custom_rule,
)
from vbf.feedback.llm import GeometryFeedbackAnalyzer


class TestGeometryDelta:
    """Tests for GeometryDelta calculation."""

    def test_added_objects(self):
        """Detect newly added objects."""
        before = {}
        after = {"Cube": ObjectGeometry(
            name="Cube", obj_type="MESH",
            location=[0, 0, 0], dimensions=[1, 1, 1]
        )}
        delta = GeometryDelta.diff(before, after)
        assert "Cube" in delta.added
        assert len(delta.removed) == 0

    def test_removed_objects(self):
        """Detect removed objects."""
        before = {"Cube": ObjectGeometry(
            name="Cube", obj_type="MESH",
            location=[0, 0, 0], dimensions=[1, 1, 1]
        )}
        after = {}
        delta = GeometryDelta.diff(before, after)
        assert "Cube" in delta.removed
        assert len(delta.added) == 0

    def test_modified_objects(self):
        """Detect modified objects."""
        before = {"Cube": ObjectGeometry(
            name="Cube", obj_type="MESH", location=[0, 0, 0],
            dimensions=[1, 1, 1], vertices=8, polygons=6
        )}
        after = {"Cube": ObjectGeometry(
            name="Cube", obj_type="MESH", location=[1, 0, 0],
            dimensions=[2, 1, 1], vertices=8, polygons=12  # modified
        )}
        delta = GeometryDelta.diff(before, after)
        assert "Cube" in delta.modified
        assert len(delta.added) == 0
        assert len(delta.removed) == 0

    def test_delta_to_dict(self):
        """Test delta serialization."""
        before = {}
        after = {"Cube": ObjectGeometry(
            name="Cube", obj_type="MESH",
            location=[0, 0, 0], dimensions=[1, 1, 1]
        )}
        delta = GeometryDelta.diff(before, after)
        d = delta.to_dict()
        assert "added" in d
        assert "removed" in d
        assert "modified" in d
        assert d["added_count"] == 1


class TestValidationRules:
    """Tests for built-in validation rules."""

    def test_validate_create_primitive_success(self):
        """validate_create_primitive passes for valid result."""
        result = {"ok": True, "data": {"object_name": "Cube"}}
        delta = GeometryDelta(
            before={},
            after={"Cube": ObjectGeometry(
                name="Cube", obj_type="MESH",
                location=[0, 0, 0], dimensions=[1, 1, 1]
            )},
            added={"Cube"}, removed=set(), modified=set()
        )
        validation = BuiltinValidationRules.validate_create_primitive({}, delta, result)
        assert validation.status == "passed"

    def test_validate_create_primitive_no_object(self):
        """validate_create_primitive fails when no object created."""
        result = {"ok": True, "data": {}}
        delta = GeometryDelta(
            before={}, after={}, added=set(), removed=set(), modified=set()
        )
        validation = BuiltinValidationRules.validate_create_primitive({}, delta, result)
        assert validation.status == "failed"

    def test_validate_boolean_difference(self):
        """validate_boolean_operation for DIFFERENCE."""
        args = {"target": "Main", "operation": "DIFFERENCE"}
        result = {"ok": True, "data": {}}
        delta = GeometryDelta(
            before={"Main": ObjectGeometry(
                name="Main", obj_type="MESH", location=[0, 0, 0],
                dimensions=[1, 1, 1], polygons=100
            )},
            after={"Main": ObjectGeometry(
                name="Main", obj_type="MESH", location=[0, 0, 0],
                dimensions=[1, 1, 1], polygons=80  # decreased
            )},
        )
        validation = BuiltinValidationRules.validate_boolean_operation(args, delta, result)
        assert validation.status == "passed"

    def test_validate_boolean_difference_no_change(self):
        """validate_boolean_operation fails when DIFF doesnt change poly count."""
        args = {"target": "Main", "operation": "DIFFERENCE"}
        result = {"ok": True, "data": {}}
        delta = GeometryDelta(
            before={"Main": ObjectGeometry(
                name="Main", obj_type="MESH", location=[0, 0, 0],
                dimensions=[1, 1, 1], polygons=100
            )},
            after={"Main": ObjectGeometry(
                name="Main", obj_type="MESH", location=[0, 0, 0],
                dimensions=[1, 1, 1], polygons=100  # unchanged - bad!
            )},
        )
        validation = BuiltinValidationRules.validate_boolean_operation(args, delta, result)
        assert validation.status == "failed"

    def test_validate_add_modifier_bevel_passes_when_modifier_added(self):
        """Adding a bevel modifier need not change raw mesh edge counts immediately."""
        delta = GeometryDelta(
            before={
                "Ring": ObjectGeometry(
                    name="Ring", obj_type="MESH",
                    location=[0, 0, 0], dimensions=[1, 1, 1],
                    edges=96,
                )
            },
            after={
                "Ring": ObjectGeometry(
                    name="Ring", obj_type="MESH",
                    location=[0, 0, 0], dimensions=[1, 1, 1],
                    edges=0,
                )
            },
        )
        validation = BuiltinValidationRules.validate_add_modifier_bevel(
            {"object_name": "Ring"},
            delta,
            {"ok": True, "data": {"modifier_name": "VBF_Bevel"}},
        )
        assert validation.status == "passed"

    def test_validate_delete_object_accepts_object_name_arg(self):
        """delete_object skill uses object_name, not name."""
        before = {
            "CUT_Lens": ObjectGeometry(
                name="CUT_Lens", obj_type="MESH",
                location=[0, 0, 0], dimensions=[1, 1, 1],
            )
        }
        delta = GeometryDelta.diff(before, {})
        validation = BuiltinValidationRules.validate_delete_object(
            {"object_name": "CUT_Lens"},
            delta,
            {"ok": True, "data": {"deleted": True}},
        )
        assert validation.status == "passed"


class TestValidationRuleRegistry:
    """Tests for ValidationRuleRegistry."""

    def test_exact_match(self):
        """Exact skill name match."""
        validator = ValidationRuleRegistry.get_rule("create_primitive")
        assert validator is not None

    def test_glob_pattern_match(self):
        """Glob pattern matching."""
        validator = ValidationRuleRegistry.get_rule("create_beveled_box")
        assert validator is not None

    def test_no_match(self):
        """No validator for unknown skill."""
        validator = ValidationRuleRegistry.get_rule("unknown_skill_xyz")
        assert validator is None

    def test_register_custom_rule(self):
        """Register and use custom rule."""
        def custom_validator(args, delta, result):
            return ValidationResult.passed("custom", "Custom rule works")

        ValidationRuleRegistry.register("custom_*", custom_validator)
        validator = ValidationRuleRegistry.get_rule("custom_test")
        assert validator is not None


class TestCaptureLevel:
    """Tests for CaptureLevel enum."""

    def test_capture_levels_exist(self):
        """All capture levels defined."""
        assert CaptureLevel.LIGHT is not None
        assert CaptureLevel.GEOMETRY is not None
        assert CaptureLevel.TOPOLOGY is not None
        assert CaptureLevel.FULL is not None


class TestTaskSceneIsolation:
    def test_task_scene_context_hides_preexisting_meshes(self):
        client = VBFClient()
        client._task_scene_policy = "isolate"
        client._task_include_environment_objects = True
        client._task_object_names = {"GEO_Sofa_Base"}

        scene = SceneState()
        scene.add_object("GEO_Phone_Chassis", "MESH", [0, 0, 0], [1, 1, 1])
        scene.add_object("GEO_Sofa_Base", "MESH", [1, 0, 0], [2, 1, 1])
        scene.add_object("Camera", "CAMERA", [0, -4, 2], [0, 0, 0])

        filtered = client._filter_scene_for_task_context(scene)
        names = {obj["name"] for obj in filtered.get_objects()}

        assert names == {"GEO_Sofa_Base", "Camera"}
        assert filtered.statistics["original_object_count"] == 3
        assert filtered.statistics["context_object_count"] == 2


class TestAnalyzerFallback:
    @pytest.mark.asyncio
    async def test_analyzer_parse_failure_recovers_quality_from_last_raw_response(self, tmp_path):
        fail_path = tmp_path / "last_gen_fail.txt"
        fail_path.write_text(
            """
{
  "raw_content": "{\\"quality\\": \\"bad\\", \\"reason\\": \\"scene contaminated\\", \\"suggestions\\": [\\"clean old objects\\"], \\"score\\": 0.2"
}
""".strip(),
            encoding="utf-8",
        )

        class _FakeClient:
            _runtime_paths = {"last_gen_fail_file": str(fail_path)}

            async def _ensure_adapter(self):
                return object()

            async def _adapter_call(self, messages):
                raise ValueError("LLM parse error (parse_stage=strict_json_loads)")

        analyzer = GeometryFeedbackAnalyzer(_FakeClient())
        analysis = await analyzer.analyze_geometry_quality(
            stage="blockout",
            scene=SceneState(),
            step_results={},
            task_prompt="make a sofa",
        )

        assert analysis.quality == "bad"
        assert analysis.score == 0.2
        assert "scene contaminated" in analysis.reason


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_factory_methods(self):
        """Test ValidationResult factory methods."""
        passed = ValidationResult.passed("test", "OK")
        assert passed.status == "passed"

        failed = ValidationResult.failed("test", "Error")
        assert failed.status == "failed"

        warning = ValidationResult.warning("test", "Warning")
        assert warning.status == "warning"

        skipped = ValidationResult.skipped("test", "Skip")
        assert skipped.status == "skipped"


class TestIncrementalSceneCaptureEvents:
    """Tests for event-driven scene capture + fallback."""

    @pytest.mark.asyncio
    async def test_capture_single_object_uses_len_token(self):
        """Geometry capture should use {'len': True} token instead of __len__ attr."""

        class _FakeClient:
            async def execute_skill(self, skill, args):
                return {"ok": False}

        capture = IncrementalSceneCapture(_FakeClient())
        calls = []

        async def _fake_py_get(path_steps):
            calls.append(path_steps)
            if path_steps[-1] == {"attr": "type"}:
                return "MESH"
            if path_steps[-1] == {"attr": "location"}:
                return [0.0, 0.0, 0.0]
            if path_steps[-1] == {"attr": "dimensions"}:
                return [1.0, 2.0, 3.0]
            if path_steps[-1] == {"len": True}:
                if {"attr": "vertices"} in path_steps:
                    return 8
                if {"attr": "polygons"} in path_steps:
                    return 12
                if {"attr": "edges"} in path_steps:
                    return 18
                if {"attr": "material_slots"} in path_steps:
                    return 1
            return None

        capture._py_get = _fake_py_get
        obj = await capture._capture_single_object("Cube", CaptureLevel.GEOMETRY)

        assert obj is not None
        assert obj.vertices == 8
        assert obj.polygons == 12
        assert obj.edges == 18
        assert obj.materials == 1
        assert any(step == {"len": True} for path in calls for step in path)

    @pytest.mark.asyncio
    async def test_sync_from_events_applies_delta(self):
        """Event sync should bootstrap snapshot then apply delta updates."""

        class _FakeClient:
            async def get_scene_snapshot(self):
                return {
                    "ok": True,
                    "data": {
                        "seq": 1,
                        "objects": {
                            "Cube": {
                                "type": "MESH",
                                "location": [0, 0, 0],
                                "dimensions": [1, 1, 1],
                                "vertices": 8,
                                "polygons": 6,
                                "edges": 12,
                                "materials": 0,
                            }
                        },
                    },
                }

            async def get_scene_delta(self, since_seq):
                assert since_seq == 1
                return {
                    "ok": True,
                    "data": {
                        "latest_seq": 2,
                        "deltas": {
                            "Cube": {
                                "type": "MESH",
                                "location": [1, 0, 0],
                                "dimensions": [2, 1, 1],
                                "vertices": 16,
                                "polygons": 12,
                                "edges": 24,
                                "materials": 1,
                            }
                        },
                        "dropped": False,
                    },
                }

            async def execute_skill(self, skill, args):
                return {"ok": False}

        capture = IncrementalSceneCapture(_FakeClient())
        synced = await capture.sync_from_events()
        assert synced is True
        assert capture._event_seq == 2
        assert "Cube" in capture._cache
        assert capture._cache["Cube"].vertices == 16
        assert capture._cache["Cube"].location[0] == 1

    @pytest.mark.asyncio
    async def test_sync_from_events_dropped_triggers_snapshot_resync(self):
        """Dropped deltas should trigger full snapshot resync."""

        class _FakeClient:
            def __init__(self):
                self.snapshot_calls = 0

            async def get_scene_snapshot(self):
                self.snapshot_calls += 1
                if self.snapshot_calls == 1:
                    return {
                        "ok": True,
                        "data": {
                            "seq": 1,
                            "objects": {
                                "Cube": {
                                    "type": "MESH",
                                    "location": [0, 0, 0],
                                    "dimensions": [1, 1, 1],
                                    "vertices": 8,
                                    "polygons": 6,
                                    "edges": 12,
                                    "materials": 0,
                                }
                            },
                        },
                    }
                return {
                    "ok": True,
                    "data": {
                        "seq": 5,
                        "objects": {
                            "Sphere": {
                                "type": "MESH",
                                "location": [2, 0, 0],
                                "dimensions": [1, 1, 1],
                                "vertices": 32,
                                "polygons": 30,
                                "edges": 60,
                                "materials": 1,
                            }
                        },
                    },
                }

            async def get_scene_delta(self, since_seq):
                return {
                    "ok": True,
                    "data": {"latest_seq": 4, "deltas": {}, "dropped": True},
                }

            async def execute_skill(self, skill, args):
                return {"ok": False}

        client = _FakeClient()
        capture = IncrementalSceneCapture(client)
        synced = await capture.sync_from_events()
        assert synced is True
        assert capture._event_seq == 5
        assert "Sphere" in capture._cache
        assert "Cube" not in capture._cache
        assert client.snapshot_calls >= 2

    @pytest.mark.asyncio
    async def test_capture_objects_falls_back_when_event_api_missing(self):
        """When event APIs are unavailable, capture should fallback to py_get path."""

        class _FakeClient:
            async def get_scene_snapshot(self):
                return {"ok": False, "method_not_found": True}

            async def get_scene_delta(self, since_seq):
                return {"ok": False, "method_not_found": True}

            async def execute_skill(self, skill, args):
                return {"ok": False}

        capture = IncrementalSceneCapture(_FakeClient())

        async def _fake_capture_single(name, level):
            return ObjectGeometry(
                name=name,
                obj_type="MESH",
                location=[0, 0, 0],
                dimensions=[1, 1, 1],
                vertices=8,
                polygons=6,
                edges=12,
                materials=0,
            )

        capture._capture_single_object = _fake_capture_single
        result = await capture.capture_objects(["Cube"], use_cache=True)
        assert "Cube" in result
        assert capture._event_stream_available is False

    @pytest.mark.asyncio
    async def test_capture_objects_silently_skips_missing_deleted_objects(self, capsys):
        """Deleted objects are expected during cleanup and should not spam logs."""

        class _FakeClient:
            async def execute_skill(self, skill, args):
                return {"ok": False}

        capture = IncrementalSceneCapture(_FakeClient())
        capture._event_stream_available = False

        async def _missing_object(name, level):
            raise RuntimeError(
                "py_get failed: 'bpy_prop_collection[key]: key "
                f"\"{name}\" not found'"
            )

        capture._capture_single_object = _missing_object
        result = await capture.capture_objects(["CUT_Lens_UR"], use_cache=False)

        assert result == {}
        assert "Failed to capture" not in capsys.readouterr().out


class TestClosedLoopCheckpointRollback:
    """Regression tests for checkpoint rollback + replan cleanup."""

    @pytest.mark.asyncio
    async def test_checkpoint_rolls_back_and_prunes_step_results(self, monkeypatch):
        """Checkpoint should rollback stage and prune stale step results before replan."""
        client = VBFClient()

        initial_steps = [
            {"step_id": "step_001", "skill": "create_primitive", "args": {}, "stage": "blockout"},
            {"step_id": "step_002", "skill": "scale_object", "args": {}, "stage": "blockout"},
            {"step_id": "step_003", "skill": "bevel", "args": {}, "stage": "detail"},
        ]
        replanned_steps = [
            {"step_id": "step_010", "skill": "create_primitive", "args": {}, "stage": "blockout"},
            {"step_id": "step_011", "skill": "bevel", "args": {}, "stage": "detail"},
        ]

        class _Decision:
            def __init__(self, action, detail=None):
                self.action = action
                self.detail = detail or {}

        class _FakeClosedLoopControl:
            def __init__(self, *args, **kwargs):
                pass

            async def execute_with_feedback(self, step, step_results, scene_capture):
                step_id = step["step_id"]
                if step_id in {"step_001", "step_002", "step_010", "step_011"}:
                    step_results[step_id] = {"ok": True, "data": {"_skill": step["skill"]}}
                    return _Decision("continue", {"step_id": step_id}), None
                if step_id == "step_003":
                    return _Decision(
                        "checkpoint",
                        {
                            "reason": "quality_poor",
                            "rollback_step_id": "step_001",
                            "stage_step_ids": ["step_001", "step_002"],
                        },
                    ), None
                return _Decision("continue", {"step_id": step_id}), None

        class _FakeCapture:
            instances = []

            def __init__(self, _client):
                self._cache = {}
                self.invalidated = False
                _FakeCapture.instances.append(self)

            def invalidate_cache(self, object_names=None):
                self.invalidated = True

        replan_calls = []

        async def _fake_replan_from_step(**kwargs):
            replan_calls.append(copy.deepcopy(kwargs))
            return {"steps": replanned_steps, "execution": {"max_replans": 5}}, replanned_steps

        monkeypatch.setattr(client, "ensure_connected", AsyncMock())
        monkeypatch.setattr(client, "_is_llm_enabled", lambda: True)
        monkeypatch.setattr(client, "list_skills", AsyncMock(return_value=["create_primitive", "scale_object", "bevel"]))
        monkeypatch.setattr(client, "capture_scene_state", AsyncMock(return_value=SceneState()))
        monkeypatch.setattr(
            client,
            "_plan_skill_task_auto",
            AsyncMock(return_value=({"steps": initial_steps, "execution": {"max_replans": 5}}, initial_steps)),
        )
        monkeypatch.setattr(client, "_replan_from_step", _fake_replan_from_step)
        rollback_mock = AsyncMock(return_value={"ok": True, "data": {"undone_steps": 2}})
        monkeypatch.setattr(client, "rollback_to_step", rollback_mock)

        monkeypatch.setattr("vbf.feedback.control.ClosedLoopControl", _FakeClosedLoopControl)
        monkeypatch.setattr("vbf.feedback.geometry_capture.IncrementalSceneCapture", _FakeCapture)

        result = await client.run_task_with_feedback(prompt="create a coherent product model")

        rollback_mock.assert_awaited_once_with("step_001")
        assert replan_calls
        assert replan_calls[0]["fail_idx"] == 0
        assert replan_calls[0]["step_results"] == {}
        assert replan_calls[0]["feedback_detail"]["rolled_back_to_step"] == "step_001"
        assert replan_calls[0]["feedback_detail"]["rolled_back_count"] == 2
        assert _FakeCapture.instances and _FakeCapture.instances[0].invalidated is True

        # Old blockout artifacts should be pruned from final execution state.
        assert "step_001" not in result["step_results"]
        assert "step_002" not in result["step_results"]
        assert set(result["step_results"].keys()) == {"step_010", "step_011"}
