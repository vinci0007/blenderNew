"""Test script for VBF four-layer system."""

import sys
import pytest
from vbf.client import VBFClient
from vbf.task_state import TaskState, TaskInterruptedError
from vbf.scene_state import SceneState, FeedbackContext
from vbf.llm_integration import (
    is_llm_enabled, load_llm, generate_skill_plan, call_llm_json
)
from vbf.plan_normalization import normalize_plan


class TestModuleImports:
    """Test that all modules import correctly."""

    def test_client_import(self):
        """VBFClient should import without error."""
        from vbf.client import VBFClient
        assert VBFClient is not None

    def test_task_state_import(self):
        """TaskState and TaskInterruptedError should import."""
        from vbf.task_state import TaskState, TaskInterruptedError
        assert TaskState is not None
        assert TaskInterruptedError is not None

    def test_scene_state_import(self):
        """SceneState and FeedbackContext should import."""
        from vbf.scene_state import SceneState, FeedbackContext
        assert SceneState is not None
        assert FeedbackContext is not None

    def test_llm_integration_import(self):
        """LLM integration functions should import."""
        from vbf.llm_integration import (
            generate_skill_plan, call_llm_json, is_llm_enabled
        )
        assert generate_skill_plan is not None
        assert call_llm_json is not None
        assert is_llm_enabled is not None

    def test_plan_normalization_import(self):
        """normalize_plan should import."""
        from vbf.plan_normalization import normalize_plan
        assert normalize_plan is not None


class TestVBFClient:
    """Test VBFClient instantiation and properties."""

    def test_client_creation(self):
        """VBFClient should instantiate without error."""
        client = VBFClient()
        assert client is not None
        assert client._default_save_path is not None

    def test_save_path_exists(self):
        """Default save path should be valid."""
        client = VBFClient()
        # Path should contain 'task_state.json'
        assert 'task_state.json' in client._default_save_path


class TestTaskState:
    """Test TaskState serialization."""

    def test_task_state_creation(self):
        """TaskState should serialize correctly."""
        state = TaskState(
            prompt="create cube",
            plan={"steps": [{"step_id": "test"}]},
            steps=[{"step_id": "test"}],
            step_results={"test": {"ok": True}},
            current_step_index=1,
            allowed_skills=["create_primitive"],
        )
        data = state.to_dict()
        assert data["prompt"] == "create cube"
        assert data["current_step_index"] == 1

    def test_task_state_roundtrip(self):
        """TaskState should support save/load roundtrip."""
        import tempfile
        import os

        state = TaskState(
            prompt="roundtrip test",
            plan={"steps": []},
            steps=[],
            step_results={},
            current_step_index=0,
            allowed_skills=["test"],
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            state.save(temp_path)
            loaded = TaskState.load(temp_path)
            assert loaded.prompt == "roundtrip test"
            assert loaded.current_step_index == 0
        finally:
            os.unlink(temp_path)


class TestSceneState:
    """Test SceneState creation and text generation."""

    def test_scene_state_creation(self):
        """SceneState should work correctly."""
        scene = SceneState()
        scene.scene_name = "TestScene"
        scene.add_object("cube", "MESH", [0, 0, 0], [1, 1, 1])

        data = scene.to_dict()
        assert data["scene_name"] == "TestScene"
        assert len(data["objects"]) == 1

    def test_scene_text_generation(self):
        """SceneState should generate prompt text."""
        scene = SceneState()
        scene.scene_name = "TestScene"
        scene.add_object("cube", "MESH", [0, 0, 0], [1, 1, 1])

        text = scene.to_prompt_text()
        assert "cube" in text.lower()
        assert "TestScene" in text

    def test_scene_with_warnings(self):
        """SceneState should handle warnings."""
        scene = SceneState()
        scene.add_warning("Test warning")
        assert len(scene.warnings) == 1
        assert "Test warning" in scene.to_prompt_text()


class TestPlanNormalization:
    """Test plan normalization logic."""

    def test_basic_normalization(self):
        """Basic plan should normalize correctly."""
        raw_plan = {
            "skills_plan": {
                "steps": [
                    {
                        "step_id": "create",
                        "skill": "create_primitive",
                        "params": {"type": "cube"},
                        "on_success": {"store_as": "obj"}
                    }
                ]
            }
        }
        plan = normalize_plan(raw_plan)
        # params -> args, type -> primitive_type
        assert plan["steps"][0]["args"]["primitive_type"] == "cube"
        assert plan["steps"][0]["on_success"]["step_return_json_path"] == "data.object_name"

    def test_empty_plan_rejection(self):
        """Empty plan should raise ValueError."""
        with pytest.raises(ValueError):
            normalize_plan({})


class TestFourLayerSystem:
    """Test core four-layer methods exist."""

    @pytest.fixture
    def client(self):
        return VBFClient()

    def test_run_task_exists(self, client):
        """run_task method should exist."""
        assert hasattr(client, 'run_task')

    def test_execute_skill_exists(self, client):
        """execute_skill method should exist."""
        assert hasattr(client, 'execute_skill')

    def test_rollback_exists(self, client):
        """rollback_to_step method should exist."""
        assert hasattr(client, 'rollback_to_step')

    def test_capture_scene_exists(self, client):
        """capture_scene_state method should exist."""
        assert hasattr(client, 'capture_scene_state')

    def test_request_replan_exists(self, client):
        """request_replan method should exist."""
        assert hasattr(client, 'request_replan')

    def test_interrupt_exists(self, client):
        """_create_interrupt method should exist."""
        assert hasattr(client, '_create_interrupt')

    def test_llm_enabled_function(self):
        """is_llm_enabled function should exist."""
        assert callable(is_llm_enabled)


class TestFeedbackContext:
    """Test FeedbackContext."""

    def test_context_creation(self):
        """FeedbackContext should create prompt text."""
        context = FeedbackContext(
            step_id="test",
            skill="create_primitive",
            args={"name": "cube"},
            result={"ok": True, "data": {"object_name": "cube"}}
        )
        text = context.to_plan_analysis_prompt()
        assert "create_primitive" in text
        assert "test" in text
