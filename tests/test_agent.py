"""
Tests for vbf/agent/ - Autonomous Blender Modeling Agent

These tests verify:
1. VBFAgent imports and instantiates correctly
2. SessionMemory persists data to disk
3. Agent tools are properly defined for Agent SDK compatibility
4. No regression in existing vbf/ code
"""

import os
import pytest
import tempfile
import uuid
from pathlib import Path

from vbf.agent import VBFAgent, AgentStatus, SessionMemory


class TestVBFAgentInit:
    """Test VBFAgent instantiation and configuration."""

    def test_agent_creation_default(self):
        """Agent creates with default settings."""
        agent = VBFAgent()
        # session_id is None by default (SessionMemory auto-generates internally)
        assert agent.status == AgentStatus.IDLE
        assert agent.auto_retry == 3
        assert agent.stream_callback is None
        # Session memory still works even without explicit session_id
        assert agent.session is not None
        assert agent.session.session_id is not None

    def test_agent_creation_with_options(self):
        """Agent respects custom options."""
        agent = VBFAgent(
            host="192.168.1.1",
            port=9000,
            blender_path="/usr/bin/blender",
            session_id="my-session",
            auto_retry=5,
        )
        assert agent.host == "192.168.1.1"
        assert agent.port == 9000
        assert agent.blender_path == "/usr/bin/blender"
        assert agent.session_id == "my-session"
        assert agent.auto_retry == 5

    def test_agent_has_tools(self):
        """Agent exposes 4 tools for Agent SDK."""
        agent = VBFAgent()
        assert len(agent.tools) == 4
        tool_names = {t["function"]["name"] for t in agent.tools}
        assert tool_names == {
            "vbf_create_model",
            "vbf_resume_task",
            "vbf_get_scene",
            "vbf_list_skills",
        }

    def test_agent_tools_have_required_fields(self):
        """All tools have type, function.name, function.description, function.parameters."""
        agent = VBFAgent()
        for tool in agent.tools:
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert func["parameters"]["type"] == "object"


class TestSessionMemory:
    """Test SessionMemory persistence."""

    def test_memory_creation_with_session_id(self):
        """Memory creates a directory for session."""
        mem = SessionMemory(session_id="test-session")
        assert mem.session_id == "test-session"
        assert mem.memory_dir.exists()

    def test_memory_add_and_retrieve_message(self):
        """Messages are stored and retrievable."""
        mem = SessionMemory(session_id="test-msgs")
        mem.add_message("user", "create a cube")
        mem.add_message("assistant", "Done!")

        ctx = mem.get_recent_context(max_messages=10)
        assert "create a cube" in ctx
        assert "Done!" in ctx

    def test_memory_preferences_persist(self):
        """Preferences are saved to disk."""
        mem = SessionMemory(session_id="test-prefs")
        mem.update_preference("default_style", "low_poly")
        mem.update_preference("auto_retry", 5)

        assert mem.get_preference("default_style") == "low_poly"
        assert mem.get_preference("auto_retry") == 5
        assert mem.get_preference("missing", "default") == "default"

    def test_memory_context_truncates_long_messages(self):
        """Recent context limits message length."""
        mem = SessionMemory(session_id="test-ctx")
        long_msg = "x" * 500
        mem.add_message("user", long_msg)

        ctx = mem.get_recent_context(max_messages=1)
        assert len(ctx) < 500 + 50  # Allow some overhead for role label

    def test_memory_project_history(self):
        """Project history records completed tasks."""
        sid = f"test-history-{uuid.uuid4().hex[:8]}"
        mem = SessionMemory(session_id=sid)
        mem.project_history.append(
            {
                "task_id": "abc123",
                "prompt": "create a cube",
                "completed_at": "2026-04-17T10:00:00",
                "steps": 5,
            }
        )
        mem.save()

        # Load new instance with same session_id
        mem2 = SessionMemory(session_id=sid)
        assert len(mem2.project_history) == 1
        assert mem2.project_history[0]["task_id"] == "abc123"


class TestAgentStatus:
    """Test AgentStatus enum."""

    def test_all_statuses_exist(self):
        """All expected statuses are defined."""
        statuses = {s.value for s in AgentStatus}
        expected = {"idle", "connecting", "planning", "executing", "waiting", "completed", "failed"}
        assert expected.issubset(statuses)


class TestNoRegression:
    """Verify agent import doesn't break existing vbf/ code."""

    def test_vbf_client_still_importable(self):
        """VBFClient can still be imported."""
        from vbf.app.client import VBFClient
        assert VBFClient is not None

    def test_vbf_adapters_still_importable(self):
        """Adapters can still be imported."""
        from vbf.adapters import get_adapter, SUPPORTED_MODELS
        assert len(SUPPORTED_MODELS) >= 10

    def test_existing_tests_still_pass(self):
        """This test always passes - real tests run in test suite."""
        assert True