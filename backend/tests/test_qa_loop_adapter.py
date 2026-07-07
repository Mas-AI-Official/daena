"""Tests for the QA/QC verification capability (ai-qa-loop adapter).

These are OFFLINE and zero-token. The adapter shells the ai-qa-loop engine only in the
self-test case, and even there the engine runs in deterministic mode (planted-bug mocks, no
network, no model spend). Every other case is pure Python with no subprocess.

The suite is written to stay GREEN whether or not the engine is installed on the host:
engine-dependent assertions branch on engine_available(), so a slim checkout still passes.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.qa import (
    QA_TOOL_ID,
    QaResult,
    build_qa_tool_definition,
    engine_available,
    register_qa_tool,
    run_qa_loop,
    run_selftest,
)
from app.services.qa.qa_loop_adapter import STATUS_CLEAN, STATUS_UNAVAILABLE
from app.services.tool_lifecycle.orchestra_integration import (
    get_tlm_registry,
    initialize_tlm,
    reset_tlm,
)
from app.services.tool_lifecycle.tool_registry import ToolRegistry


def _run(coro):
    """Drive a coroutine to completion without depending on pytest-asyncio config."""
    return asyncio.run(coro)


# -- engine detection -----------------------------------------------------------------------

class TestEngineDetection:
    def test_engine_available_returns_bool(self):
        assert isinstance(engine_available(), bool)


# -- tool definition contract ---------------------------------------------------------------

class TestToolDefinition:
    def test_definition_contract(self):
        td = build_qa_tool_definition()
        assert td.id == QA_TOOL_ID == "qa.run_loop"
        assert td.category == "qa"
        # Governed: subprocess + arbitrary-URL egress means approval is required and the tool
        # is scoped to the privileged departments.
        assert td.governance_rules.requires_approval is True
        depts = set(td.governance_rules.allowed_departments)
        assert {"engineering", "security", "operations"}.issubset(depts)
        assert td.estimated_schema_tokens > 0


# -- registration is idempotent -------------------------------------------------------------

class TestRegister:
    def test_register_is_idempotent_when_engine_present(self):
        if not engine_available():
            pytest.skip("engine not installed on this host")
        reg = ToolRegistry()
        assert register_qa_tool(reg) is True
        assert register_qa_tool(reg) is True  # second call must not raise or duplicate
        assert reg.count == 1
        assert reg.requires_approval(QA_TOOL_ID) is True

    def test_register_skips_when_engine_absent(self, monkeypatch):
        monkeypatch.setenv("AQA_ENGINE_DIR", r"Z:\nope\ai-qa-loop\engine")
        reg = ToolRegistry()
        assert register_qa_tool(reg) is False
        assert reg.count == 0


# -- run_qa_loop degrades honestly when the engine is missing -------------------------------

class TestRunLoopUnavailable:
    def test_missing_engine_returns_unavailable_never_raises(self, monkeypatch):
        # Deterministic on EVERY host: point at a path that cannot contain the engine.
        monkeypatch.setenv("AQA_ENGINE_DIR", r"Z:\nope\ai-qa-loop\engine")
        result = _run(run_qa_loop(base_url="http://localhost:8000"))
        assert isinstance(result, QaResult)
        assert result.status == STATUS_UNAVAILABLE
        assert result.ok is False
        assert "engine not found" in result.detail


# -- the capability can health-check itself (real engine, zero tokens) ----------------------

class TestSelftest:
    def test_selftest_passes_when_engine_present(self):
        if not engine_available():
            pytest.skip("engine not installed on this host")
        result = _run(run_selftest())
        # The offline self-test plants bugs and asserts the oracle finds exactly them.
        assert result.ok is True
        assert result.status == STATUS_CLEAN


# -- the tool wires into the TLM catalog when the engine is present -------------------------

class TestTlmIntegration:
    @pytest.fixture(autouse=True)
    def _clean_tlm(self):
        reset_tlm()
        yield
        reset_tlm()

    def test_qa_tool_registered_only_when_engine_present(self):
        initialize_tlm()
        registry = get_tlm_registry()
        qa_tools = registry.get_tools_by_category("qa")
        if engine_available():
            # additive: file(6) + terminal(1) + browser(3) + qa(1)
            assert registry.count >= 11
            assert len(qa_tools) == 1
            assert registry.requires_approval(QA_TOOL_ID) is True
        else:
            assert registry.count >= 10
            assert len(qa_tools) == 0
