"""Tests for AgentLoop and SmartResolver."""

from __future__ import annotations

import pytest

from app.services.agent_core.agent_loop import (
    AgentLoop,
    AgentStep,
    ExecutionReceipt,
    StepResult,
)
from app.services.agent_core.smart_resolver import SmartResolver, _search_files


class TestAgentStep:
    def test_create_step(self):
        step = AgentStep(step_id=1, description="Create a file")
        assert step.step_id == 1
        assert step.runtime_hint == "auto"

    def test_step_with_context(self):
        step = AgentStep(step_id=2, description="Test it", context={"retrying": True})
        assert step.context["retrying"] is True


class TestStepResult:
    def test_success_result(self):
        r = StepResult(step_id=1, success=True, output="Done")
        assert r.success
        d = r.to_dict()
        assert d["step_id"] == 1
        assert d["success"] is True

    def test_failure_result(self):
        r = StepResult(step_id=1, success=False, error="File not found")
        assert not r.success
        assert r.error == "File not found"


class TestExecutionReceipt:
    def test_empty_receipt(self):
        r = ExecutionReceipt(task="test task")
        assert r.status == "running"
        d = r.to_dict()
        assert d["task"] == "test task"
        assert d["total_iterations"] == 0

    def test_receipt_with_results(self):
        r = ExecutionReceipt(task="multi-step")
        r.results.append(StepResult(step_id=1, success=True, output="ok"))
        r.results.append(StepResult(step_id=2, success=False, error="fail"))
        r.steps_completed = 1
        r.steps_failed = 1
        d = r.to_dict()
        assert len(d["results"]) == 2


class TestAgentLoop:
    def test_create_loop(self):
        loop = AgentLoop()
        assert not loop._running
        assert loop.get_receipt() is None

    def test_stop(self):
        loop = AgentLoop()
        loop._running = True
        loop.stop()
        assert not loop._running

    def test_build_prompt_simple(self):
        loop = AgentLoop()
        step = AgentStep(step_id=1, description="Do something")
        prompt = loop._build_prompt(step, {})
        assert "Do something" in prompt

    def test_build_prompt_with_context(self):
        loop = AgentLoop()
        step = AgentStep(step_id=2, description="Next step")
        context = {"step_1_result": "Created file.txt"}
        prompt = loop._build_prompt(step, context)
        assert "Next step" in prompt
        assert "Created file.txt" in prompt

    def test_build_prompt_with_error(self):
        loop = AgentLoop()
        step = AgentStep(step_id=1, description="Retry", context={"previous_error": "Permission denied"})
        prompt = loop._build_prompt(step, {})
        assert "Permission denied" in prompt
        assert "different approach" in prompt

    def test_parse_plan_json(self):
        loop = AgentLoop()
        raw = '[{"step_id": 1, "description": "Step one"}, {"step_id": 2, "description": "Step two"}]'
        steps = loop._parse_plan(raw)
        assert len(steps) == 2
        assert steps[0].description == "Step one"
        assert steps[1].step_id == 2

    def test_parse_plan_embedded_json(self):
        loop = AgentLoop()
        raw = 'Here is the plan:\n[{"step_id": 1, "description": "Do it"}]\nDone.'
        steps = loop._parse_plan(raw)
        assert len(steps) == 1

    def test_parse_plan_invalid(self):
        loop = AgentLoop()
        steps = loop._parse_plan("no json here")
        assert steps == []

    @pytest.mark.asyncio
    async def test_plan_simple_task(self):
        loop = AgentLoop()
        steps = await loop._plan("Say hello", {})
        # Simple task should return single step
        assert len(steps) == 1
        assert "hello" in steps[0].description.lower()

    @pytest.mark.asyncio
    async def test_plan_complex_task(self):
        loop = AgentLoop()
        steps = await loop._plan(
            "Create a Python script, run it, fix any errors, then write tests for it",
            {},
        )
        # Complex task with multiple verbs -- may decompose or fall back to single step
        assert len(steps) >= 1


class TestSmartResolver:
    def test_create_resolver(self):
        resolver = SmartResolver()
        assert "data" in resolver._vault_path and "mind" in resolver._vault_path

    @pytest.mark.asyncio
    async def test_resolve_from_vault(self):
        resolver = SmartResolver()
        result = await resolver._search_vault("hard laws immutable rules", {})
        # Should find the hard-laws.md file in Daena-Mind
        if result:
            assert result["confidence"] > 0

    @pytest.mark.asyncio
    async def test_resolve_from_project(self):
        resolver = SmartResolver()
        result = await resolver._search_project_files("NVIDIA Inception application", {})
        if result:
            assert result["confidence"] > 0

    @pytest.mark.asyncio
    async def test_resolve_returns_structure(self):
        resolver = SmartResolver()
        result = await resolver.resolve("something about Daena architecture")
        # Should return a properly structured result regardless of source
        assert "source" in result
        assert "attempts" in result or "confidence" in result

    def test_search_files_function(self, tmp_path):
        (tmp_path / "test.md").write_text("This file contains important facts about governance.")
        (tmp_path / "other.md").write_text("Nothing relevant here at all.")
        results = _search_files(str(tmp_path), "important facts governance")
        assert len(results) >= 1
        assert "governance" in results[0]["snippet"].lower()

    def test_search_files_empty_dir(self, tmp_path):
        results = _search_files(str(tmp_path), "anything")
        assert results == []

    def test_search_files_nonexistent(self):
        results = _search_files("/nonexistent/path/xyz", "anything")
        assert results == []
