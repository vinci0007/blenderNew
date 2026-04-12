"""Tests for LLM integration utilities."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from vbf.llm_integration import (
    load_llm,
    load_llm_config,
    is_llm_enabled,
    call_llm_json,
    build_skill_plan_messages,
    build_skill_repair_messages,
    generate_skill_plan,
)
from vbf.llm_cache import get_cache


@pytest.fixture(autouse=True)
def clear_llm_cache():
    """每个测试前清空 LLM 缓存。"""
    cache = get_cache()
    cache.clear()


class TestLoadLLM:
    """Tests for load_llm function."""

    @patch('vbf.llm_integration.load_openai_compat_config')
    def test_returns_none_when_not_configured(self, mock_load):
        """Should return None if LLM not configured."""
        mock_load.return_value = None
        result = load_llm()
        assert result is None

    @patch('vbf.llm_integration.load_openai_compat_config')
    def test_returns_none_when_disabled(self, mock_load):
        """Should return None if use_llm is False."""
        mock_config = Mock()
        mock_config.use_llm = False
        mock_load.return_value = mock_config

        result = load_llm()
        assert result is None

    @patch('vbf.llm_integration.load_openai_compat_config')
    @patch('vbf.llm_integration.OpenAICompatLLM')
    def test_returns_llm_instance(self, mock_llm_class, mock_load):
        """Should return LLM instance when configured."""
        mock_config = Mock()
        mock_config.use_llm = True
        mock_load.return_value = mock_config

        mock_instance = Mock()
        mock_llm_class.return_value = mock_instance

        result = load_llm()
        assert result == mock_instance


class TestIsLLMEnabled:
    """Tests for is_llm_enabled function."""

    @patch('vbf.llm_integration.load_openai_compat_config')
    def test_false_when_not_configured(self, mock_load):
        """Should return False if not configured."""
        mock_load.return_value = None
        assert is_llm_enabled() is False

    @patch('vbf.llm_integration.load_openai_compat_config')
    def test_false_when_disabled(self, mock_load):
        """Should return False if use_llm is False."""
        mock_config = Mock()
        mock_config.use_llm = False
        mock_load.return_value = mock_config

        assert is_llm_enabled() is False

    @patch('vbf.llm_integration.load_openai_compat_config')
    def test_true_when_enabled(self, mock_load):
        """Should return True if enabled."""
        mock_config = Mock()
        mock_config.use_llm = True
        mock_load.return_value = mock_config

        assert is_llm_enabled() is True


class TestCallLLMJson:
    """Tests for call_llm_json function."""

    @pytest.mark.asyncio
    async def test_calls_chat_json_in_thread(self):
        """Should call llm.chat_json in a thread."""
        mock_llm = Mock()
        mock_llm.chat_json = Mock(return_value={"test": "data"})

        messages = [{"role": "user", "content": "test"}]
        result = await call_llm_json(mock_llm, messages, use_cache=False)

        assert result == {"test": "data"}
        mock_llm.chat_json.assert_called_once_with(messages)


class TestBuildSkillPlanMessages:
    """Tests for build_skill_plan_messages function."""

    def test_returns_message_list(self):
        """Should return list of messages."""
        messages = build_skill_plan_messages(
            prompt="test prompt",
            allowed_skills=["create_primitive"]
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_includes_allowed_skills(self):
        """Should include allowed_skills in user message."""
        messages = build_skill_plan_messages(
            prompt="test",
            allowed_skills=["skill1", "skill2"]
        )

        user_content = messages[1]["content"]
        assert "skill1" in user_content
        assert "skill2" in user_content

    def test_includes_skill_schemas(self):
        """Should include skill schemas if provided."""
        skill_schemas = {
            "create_primitive": {"parameters": {"name": "string"}}
        }

        messages = build_skill_plan_messages(
            prompt="test",
            allowed_skills=["create_primitive"],
            skill_schemas=skill_schemas
        )

        user_content = messages[1]["content"]
        assert "create_primitive" in user_content


class TestBuildSkillRepairMessages:
    """Tests for build_skill_repair_messages function."""

    def test_returns_repair_messages(self):
        """Should return repair messages."""
        messages = build_skill_repair_messages(
            prompt="test",
            failed_step_id="step1",
            error_message="error",
            error_traceback="trace",
            original_plan={"plan_id": "test", "steps": []},
            step_results={},
            allowed_skills=["skill1"]
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_includes_error_info(self):
        """Should include error information."""
        messages = build_skill_repair_messages(
            prompt="test",
            failed_step_id="step1",
            error_message="test error",
            error_traceback="test trace",
            original_plan={"plan_id": "p1", "steps": []},
            step_results={},
            allowed_skills=[]
        )

        user_content = messages[1]["content"]
        assert "step1" in user_content
        assert "test error" in user_content

    def test_low_level_gateway_hint(self):
        """Should add gateway hint when requested."""
        messages = build_skill_repair_messages(
            prompt="test",
            failed_step_id="step1",
            error_message="error",
            error_traceback="trace",
            original_plan={"plan_id": "p1", "steps": []},
            step_results={},
            allowed_skills=[],
            low_level_gateway_hint=True
        )

        user_content = messages[1]["content"]
        assert "py_call" in user_content or "py_set" in user_content


class TestGenerateSkillPlan:
    """Tests for generate_skill_plan function."""

    @pytest.mark.asyncio
    @patch('vbf.llm_integration.load_llm')
    async def test_raises_without_llm(self, mock_load_llm):
        """Should raise ValueError if LLM not available."""
        mock_load_llm.return_value = None
        with pytest.raises(ValueError, match="LLM is not configured"):
            await generate_skill_plan(
                prompt="test",
                allowed_skills=["skill1"],
                describe_skills_func=AsyncMock(),
                llm=None  # Explicitly pass None to trigger the check
            )

    @pytest.mark.asyncio
    async def test_generates_normalized_plan(self):
        """Should generate and normalize plan."""
        # Mock LLM
        mock_llm = Mock()
        mock_llm.chat_json = Mock(return_value={
            "steps": [
                {
                    "step_id": "create",
                    "skill": "create_primitive",
                    "params": {"type": "cube"}
                }
            ]
        })

        # Mock describe_skills
        async def mock_describe(skills):
            return None

        plan, steps = await generate_skill_plan(
            prompt="test",
            allowed_skills=["create_primitive"],
            describe_skills_func=mock_describe,
            llm=mock_llm
        )

        assert "steps" in plan
        assert len(steps) == 1
        # Check normalization: params -> args, type -> primitive_type
        assert steps[0]["args"]["primitive_type"] == "cube"

    @pytest.mark.asyncio
    async def test_rejects_invalid_plan(self):
        """Should raise ValueError for invalid plan structure."""
        mock_llm = Mock()
        # Mock returns a valid structure but missing 'steps'
        mock_llm.chat_json = Mock(return_value={"plan_id": "test", "not_steps": []})

        async def mock_describe(skills):
            return None

        # This should raise ValueError because 'steps' is missing
        with pytest.raises(ValueError):
            await generate_skill_plan(
                prompt="test",
                allowed_skills=["skill1"],
                describe_skills_func=mock_describe,
                llm=mock_llm
            )
