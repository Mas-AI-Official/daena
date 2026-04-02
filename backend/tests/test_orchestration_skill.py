"""Tests for Claude Code orchestration skill.

Covers:
- Runtime capability scoring
- Task decomposition for parallel execution
- Runtime selection logic
- Orchestration system prompt generation
"""

from __future__ import annotations

import pytest

from app.services.skills.claude_code_orchestration import (
    RUNTIME_CAPABILITIES,
    select_best_runtime,
    decompose_for_parallel_execution,
    get_orchestration_system_prompt,
)


class TestRuntimeCapabilities:
    """Tests for the runtime capability matrix."""

    def test_all_runtimes_have_capabilities(self):
        assert "claude_code" in RUNTIME_CAPABILITIES
        assert "codex" in RUNTIME_CAPABILITIES
        assert "gemini_cli" in RUNTIME_CAPABILITIES
        assert "ollama" in RUNTIME_CAPABILITIES

    def test_scores_are_valid(self):
        for rid, caps in RUNTIME_CAPABILITIES.items():
            for task_type, score in caps.items():
                assert 0.0 <= score <= 1.0, f"{rid}.{task_type} = {score} is out of range"

    def test_each_runtime_has_a_strength(self):
        """Every runtime should have at least one capability >= 0.9."""
        for rid, caps in RUNTIME_CAPABILITIES.items():
            max_score = max(caps.values())
            assert max_score >= 0.9, f"{rid} has no strong capability (max={max_score})"


class TestSelectBestRuntime:
    """Tests for runtime selection."""

    def test_claude_code_best_for_architecture(self):
        result = select_best_runtime("architecture", ["claude_code", "codex", "ollama"])
        assert result == "claude_code"

    def test_codex_best_for_sandbox_execution(self):
        result = select_best_runtime("sandbox_execution", ["claude_code", "codex", "ollama"])
        assert result == "codex"

    def test_gemini_best_for_web_research(self):
        result = select_best_runtime("web_research", ["claude_code", "gemini_cli", "ollama"])
        assert result == "gemini_cli"

    def test_ollama_best_for_cheap_tasks(self):
        result = select_best_runtime("cheap_tasks", ["claude_code", "ollama"])
        assert result == "ollama"

    def test_fallback_to_ollama_for_unknown(self):
        result = select_best_runtime("unknown_task_type", ["claude_code", "ollama"])
        assert result == "ollama"

    def test_single_runtime_always_selected(self):
        result = select_best_runtime("code_generation", ["ollama"])
        assert result == "ollama"


class TestDecomposeForParallelExecution:
    """Tests for task decomposition."""

    def test_research_task_detected(self):
        tasks = decompose_for_parallel_execution(
            "Research the latest AI governance frameworks",
            ["claude_code", "gemini_cli", "ollama"],
        )
        assert any(t.task_type == "web_research" for t in tasks)

    def test_code_task_detected(self):
        tasks = decompose_for_parallel_execution(
            "Implement a REST API for user management",
            ["claude_code", "codex", "ollama"],
        )
        assert any(t.task_type == "code_generation" for t in tasks)

    def test_multi_type_task_creates_parallel_subtasks(self):
        tasks = decompose_for_parallel_execution(
            "Research best practices and implement a caching layer with tests",
            ["claude_code", "codex", "gemini_cli", "ollama"],
        )
        types = {t.task_type for t in tasks}
        assert "web_research" in types
        assert "code_generation" in types
        assert "testing" in types
        assert len(tasks) >= 3

    def test_simple_task_single_subtask(self):
        tasks = decompose_for_parallel_execution(
            "What is the meaning of life?",
            ["ollama"],
        )
        assert len(tasks) == 1
        assert tasks[0].task_type == "complex_reasoning"

    def test_documentation_task_detected(self):
        tasks = decompose_for_parallel_execution(
            "Update the README documentation",
            ["claude_code", "ollama"],
        )
        assert any(t.task_type == "documentation" for t in tasks)

    def test_each_subtask_has_fallback(self):
        tasks = decompose_for_parallel_execution(
            "Research and implement a feature",
            ["claude_code", "gemini_cli"],
        )
        for t in tasks:
            assert t.fallback_runtime == "ollama"


class TestOrchestrationPrompt:
    """Tests for the system prompt generator."""

    def test_prompt_lists_runtimes(self):
        prompt = get_orchestration_system_prompt(
            ["claude_code", "codex", "ollama"],
        )
        assert "claude_code" in prompt
        assert "codex" in prompt
        assert "ollama" in prompt

    def test_prompt_includes_rules(self):
        prompt = get_orchestration_system_prompt(["claude_code"])
        assert "ORCHESTRATION RULES" in prompt
        assert "parallel" in prompt.lower()

    def test_agi_mode_adds_autonomy(self):
        prompt = get_orchestration_system_prompt(
            ["claude_code"],
            agi_mode=True,
        )
        assert "AGI MODE ACTIVE" in prompt

    def test_non_agi_mode_no_autonomy(self):
        prompt = get_orchestration_system_prompt(
            ["claude_code"],
            agi_mode=False,
        )
        assert "AGI MODE ACTIVE" not in prompt
