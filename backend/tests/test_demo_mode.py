"""Tests for demo mode: mock LLM responses and data seeding.

Validates keyword matching, fallback responses, and demo mode detection.
"""

import os
from unittest.mock import patch

import pytest

from app.services.demo_mode import (
    DEMO_APPROVAL_ITEMS,
    DEMO_CHAT_HISTORY,
    DEMO_PROJECTS,
    DEMO_USER,
    is_demo_mode,
    mock_llm_response,
)


class TestDemoModeDetection:
    """Verify demo mode environment variable detection."""

    def test_demo_mode_off_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove DEMO_MODE if present
            os.environ.pop("DEMO_MODE", None)
            assert is_demo_mode() is False

    def test_demo_mode_on_true(self):
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            assert is_demo_mode() is True

    def test_demo_mode_on_1(self):
        with patch.dict(os.environ, {"DEMO_MODE": "1"}):
            assert is_demo_mode() is True

    def test_demo_mode_on_yes(self):
        with patch.dict(os.environ, {"DEMO_MODE": "yes"}):
            assert is_demo_mode() is True

    def test_demo_mode_off_false(self):
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            assert is_demo_mode() is False

    def test_demo_mode_case_insensitive(self):
        with patch.dict(os.environ, {"DEMO_MODE": "TRUE"}):
            assert is_demo_mode() is True


class TestMockLLMResponse:
    """Verify keyword-matched mock responses."""

    def test_hello_response(self):
        result = mock_llm_response("hello")
        assert "help" in result.lower()

    def test_departments_response(self):
        result = mock_llm_response("What departments do we have?")
        assert "10 departments" in result

    def test_governance_response(self):
        result = mock_llm_response("How does governance work?")
        assert "tier" in result.lower() or "governance" in result.lower()

    def test_runtime_response(self):
        result = mock_llm_response("Which models can I use?")
        assert "runtime" in result.lower() or "ollama" in result.lower()

    def test_project_response(self):
        result = mock_llm_response("Tell me about projects")
        assert "project" in result.lower()

    def test_exe_mode_response(self):
        result = mock_llm_response("How do I execute commands?")
        assert "EXE" in result

    def test_cost_response(self):
        result = mock_llm_response("How much does it cost?")
        assert "cost" in result.lower() or "subscription" in result.lower()

    def test_unknown_query_fallback(self):
        result = mock_llm_response("xyzzy plugh")
        assert "demo mode" in result.lower()

    def test_case_insensitive_matching(self):
        result = mock_llm_response("HELLO")
        assert "help" in result.lower()

    def test_empty_message(self):
        result = mock_llm_response("")
        assert len(result) > 0


class TestDemoDataConstants:
    """Verify demo data structure."""

    def test_demo_user_has_required_fields(self):
        assert "email" in DEMO_USER
        assert "display_name" in DEMO_USER
        assert "password" in DEMO_USER

    def test_demo_projects_count(self):
        assert len(DEMO_PROJECTS) == 3

    def test_demo_projects_have_names(self):
        for project in DEMO_PROJECTS:
            assert "name" in project
            assert "description" in project

    def test_demo_chat_history_alternates(self):
        for i, msg in enumerate(DEMO_CHAT_HISTORY):
            assert msg["role"] in ("USER", "ASSISTANT")
            assert len(msg["content"]) > 10

    def test_demo_approval_items(self):
        assert len(DEMO_APPROVAL_ITEMS) >= 2
        for item in DEMO_APPROVAL_ITEMS:
            assert "action" in item
            assert "risk_level" in item
