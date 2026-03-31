"""Tests for VisionLoop and DepartmentPrompts.

Covers:
- VisionLoop action parsing
- VisionLoop screenshot handling (mocked)
- Department prompt generation for all 60 agents
- Agent prompt specialization
"""

from __future__ import annotations

import pytest


class TestVisionLoop:
    """Tests for VisionLoop service."""

    def test_parse_action_valid_json(self):
        from app.services.vision_loop import VisionLoop
        loop = VisionLoop()
        action = loop._parse_action('{"action_type": "click", "x": 100, "y": 200, "description": "Click button"}')
        assert action.action_type == "click"
        assert action.x == 100
        assert action.y == 200

    def test_parse_action_with_surrounding_text(self):
        from app.services.vision_loop import VisionLoop
        loop = VisionLoop()
        text = 'I see a button. Here is the action: {"action_type": "type", "text": "hello", "description": "Type greeting"} Let me explain...'
        action = loop._parse_action(text)
        assert action.action_type == "type"
        assert action.text == "hello"

    def test_parse_action_done(self):
        from app.services.vision_loop import VisionLoop
        loop = VisionLoop()
        action = loop._parse_action('{"action_type": "done", "description": "Task completed successfully"}')
        assert action.action_type == "done"

    def test_parse_action_invalid_json(self):
        from app.services.vision_loop import VisionLoop
        loop = VisionLoop()
        action = loop._parse_action("This is not valid JSON at all")
        assert action.action_type == "error"

    def test_parse_action_scroll(self):
        from app.services.vision_loop import VisionLoop
        loop = VisionLoop()
        action = loop._parse_action('{"action_type": "scroll", "direction": "down", "amount": 5, "description": "Scroll down"}')
        assert action.action_type == "scroll"
        assert action.direction == "down"
        assert action.amount == 5

    def test_parse_action_hotkey(self):
        from app.services.vision_loop import VisionLoop
        loop = VisionLoop()
        action = loop._parse_action('{"action_type": "hotkey", "keys": "ctrl+s", "description": "Save file"}')
        assert action.action_type == "hotkey"
        assert action.keys == "ctrl+s"

    def test_get_summary_empty(self):
        from app.services.vision_loop import VisionLoop
        loop = VisionLoop()
        summary = loop.get_summary()
        assert summary["total_steps"] == 0
        assert summary["successful_steps"] == 0

    @pytest.mark.asyncio
    async def test_execute_no_pyautogui(self):
        """Vision loop should handle missing pyautogui gracefully."""
        from unittest.mock import patch
        from app.services.vision_loop import VisionLoop

        loop = VisionLoop(max_iterations=1)

        # Mock pyautogui as unavailable
        with patch.dict("sys.modules", {"pyautogui": None}):
            steps = []
            async for step in loop.execute("Test task"):
                steps.append(step)

            # Should fail gracefully
            assert len(steps) >= 1
            assert steps[-1].success is False


class TestDepartmentPrompts:
    """Tests for department agent prompt generation."""

    def test_get_agent_prompt_engineering_hands(self):
        from app.services.department_prompts import get_agent_prompt
        prompt = get_agent_prompt("Engineering", "HANDS")
        assert "Engineering" in prompt
        assert "HANDS" in prompt
        assert "code" in prompt.lower()

    def test_get_agent_prompt_research_eyes(self):
        from app.services.department_prompts import get_agent_prompt
        prompt = get_agent_prompt("Research", "EYES")
        assert "Research" in prompt
        assert "EYES" in prompt
        assert "research" in prompt.lower()

    def test_get_agent_prompt_security_shield(self):
        from app.services.department_prompts import get_agent_prompt
        prompt = get_agent_prompt("Security Operations", "SHIELD")
        assert "Security" in prompt
        assert "SHIELD" in prompt

    def test_get_agent_prompt_unknown_department(self):
        """Unknown department should still return a valid prompt."""
        from app.services.department_prompts import get_agent_prompt
        prompt = get_agent_prompt("NonExistent", "MIND")
        assert "NonExistent" in prompt
        assert "MIND" in prompt
        assert len(prompt) > 20

    def test_all_60_agents_have_prompts(self):
        """Every department + sub_capability combination should have a prompt."""
        from app.services.department_prompts import get_all_agent_prompts
        all_prompts = get_all_agent_prompts()

        assert len(all_prompts) == 10  # 10 departments
        for dept, subs in all_prompts.items():
            assert len(subs) == 6, f"{dept} has {len(subs)} sub-capabilities, expected 6"
            for sub, prompt in subs.items():
                assert len(prompt) > 50, f"{dept}.{sub} prompt too short: {prompt}"
                assert dept in prompt, f"{dept} not in {dept}.{sub} prompt"

    def test_sub_capabilities_are_correct(self):
        """All 6 sub-capabilities should be present."""
        from app.services.department_prompts import get_all_agent_prompts
        expected_subs = {"MIND", "EYES", "HANDS", "VOICE", "SHIELD", "MEMORY"}
        all_prompts = get_all_agent_prompts()
        for dept, subs in all_prompts.items():
            assert set(subs.keys()) == expected_subs, f"{dept} missing sub-capabilities"

    def test_prompts_are_unique(self):
        """Each agent should have a unique prompt."""
        from app.services.department_prompts import get_all_agent_prompts
        all_prompts = get_all_agent_prompts()
        all_texts = []
        for dept, subs in all_prompts.items():
            for sub, prompt in subs.items():
                all_texts.append(prompt)
        # All 60 should be unique
        assert len(set(all_texts)) == 60, "Some agent prompts are duplicated"


class TestToolSchemaVisionTool:
    """Tests for computer_use tool in schema."""

    def test_computer_use_in_schema(self):
        from app.services.tool_schema_builder import build_tool_schema
        schema = build_tool_schema(include_desktop=True, include_system=False, include_integrations=False, include_workflows=False, include_daenabot=False)
        names = {t["name"] for t in schema}
        assert "computer_use" in names

    def test_computer_use_dispatch(self):
        from app.services.tool_schema_builder import resolve_tool_call
        qualified, params = resolve_tool_call("computer_use", {"task": "Open notepad"})
        assert qualified == "vision.execute_task"
