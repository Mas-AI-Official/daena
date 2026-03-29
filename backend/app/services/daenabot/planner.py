"""ActionPlanner: decomposes complex intents into ordered action steps.

Uses the local LLM (via Ollama) to break multi-step requests into
a sequence of DaenaBot agent actions. Falls back to single-step
if LLM is unavailable or returns unparsable output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Action:
    """A single planned action step."""

    agent: str         # "file", "terminal", "browser"
    operation: str     # "read_file", "execute_command", etc.
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    depends_on: int | None = None  # index of step this depends on


_PLANNER_PROMPT = """\
You are a task planner for Daena's DaenaBot execution system.

Break the following user request into ordered action steps.

Available agents and operations:
- FileAgent: read_file(path), list_directory(path), create_file(path, content), \
write_file(path, content), move_file(source, destination), delete_file(path)
- TerminalAgent: execute_command(command)
- BrowserAgent: navigate(url), screenshot(url), extract_text(url)

User request: {intent}

Return a JSON array of steps. Each step has:
- "agent": one of "file", "terminal", "browser"
- "operation": the operation name
- "params": dict of parameters
- "description": human-readable description

If the request is a single action, return an array with one element.
If the request requires reading something and then processing it, split into steps.

Return ONLY the JSON array. No explanation.
"""


class ActionPlanner:
    """Decomposes complex user intents into ordered action steps."""

    async def plan(self, intent: str, context: dict | None = None) -> list[Action]:
        """Break a user request into ordered action steps.

        Args:
            intent: The user's natural language request.
            context: Optional context from previous actions in the session.

        Returns:
            List of Action objects to execute in order.
        """
        settings = get_settings()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model": settings.ollama_default_model,
                        "messages": [
                            {
                                "role": "user",
                                "content": _PLANNER_PROMPT.format(intent=intent),
                            },
                        ],
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                )
                resp.raise_for_status()
                raw = resp.json().get("message", {}).get("content", "")
                return self._parse_plan(raw)
        except Exception as exc:
            logger.warning("planner.llm_unavailable", error=str(exc))
            # Fall back to single-step from IntentParser
            return self._fallback_plan(intent)

    def _parse_plan(self, raw: str) -> list[Action]:
        """Parse LLM response into Action objects."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            steps = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("planner.parse_failed", preview=text[:200])
            return []

        if not isinstance(steps, list):
            return []

        actions: list[Action] = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            actions.append(Action(
                agent=step.get("agent", "file"),
                operation=step.get("operation", ""),
                params=step.get("params", {}),
                description=step.get("description", f"Step {i + 1}"),
                depends_on=i - 1 if i > 0 else None,
            ))
        return actions

    def _fallback_plan(self, intent: str) -> list[Action]:
        """Fallback: use IntentParser for single-step plan."""
        from app.services.daenabot.intent_parser import IntentParser

        tool_call = IntentParser.parse(intent)
        if tool_call:
            return [Action(
                agent=tool_call.agent,
                operation=tool_call.operation,
                params=dict(tool_call.params),
                description=f"{tool_call.agent}.{tool_call.operation}",
            )]
        return []
