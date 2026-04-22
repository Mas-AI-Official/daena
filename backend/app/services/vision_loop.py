"""VisionLoop: screen understanding for autonomous desktop control.

This is what makes Daena an OpenClaw-class agent. The loop:
    1. Take screenshot of the desktop (pyautogui)
    2. Send image to a multimodal LLM (Claude/GPT-4o/Gemini)
    3. LLM describes what it sees + returns action coordinates
    4. Execute the action (click, type, scroll)
    5. Take another screenshot to verify
    6. Loop until the task is done or max iterations reached

The vision loop bridges Daena's brain (governance + orchestration) with
the physical desktop. Without this, desktop tools are "blind clicking."

Architecture:
    VisionLoop uses the model registry to find the best vision-capable
    model. Preference: Claude > GPT-4o > Gemini. Falls back to describing
    the task for manual execution if no vision model is available.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_VISION_ITERATIONS = 12
SCREENSHOT_MAX_DIMENSION = 1280  # Resize for token efficiency


@dataclass
class VisionAction:
    """A single action determined by the vision model."""
    action_type: str  # click, type, scroll, hotkey, wait, done, error
    x: int = 0
    y: int = 0
    text: str = ""
    keys: str = ""
    direction: str = ""
    amount: int = 3
    button: str = "left"
    description: str = ""
    confidence: float = 0.0


@dataclass
class VisionStep:
    """Record of one iteration in the vision loop."""
    iteration: int
    screenshot_size: tuple[int, int] = (0, 0)
    action: VisionAction | None = None
    observation: str = ""
    success: bool = True


class VisionLoop:
    """Autonomous desktop control via screenshot + multimodal LLM.

    Usage::

        loop = VisionLoop()
        async for step in loop.execute("Open Notepad and type Hello World"):
            print(f"Step {step.iteration}: {step.action.description}")
    """

    def __init__(
        self,
        *,
        max_iterations: int = MAX_VISION_ITERATIONS,
        model_id: str | None = None,
        provider: str | None = None,
    ) -> None:
        self._max_iterations = max_iterations
        self._model_id = model_id
        self._provider = provider
        self._steps: list[VisionStep] = []

    async def execute(
        self,
        task: str,
        *,
        context: str = "",
    ):
        """Execute a visual task on the desktop.

        Yields VisionStep objects for each iteration.

        Args:
            task: Natural language description of what to do
            context: Additional context (previous actions, etc.)
        """
        iteration = 0

        while iteration < self._max_iterations:
            iteration += 1

            # Step 1: Take screenshot
            screenshot_b64, width, height = await self._take_screenshot()
            if not screenshot_b64:
                step = VisionStep(
                    iteration=iteration,
                    observation="Failed to take screenshot",
                    success=False,
                )
                self._steps.append(step)
                yield step
                break

            # Step 2: Send to vision model
            action = await self._analyze_screenshot(
                screenshot_b64, width, height, task, context, iteration,
            )

            step = VisionStep(
                iteration=iteration,
                screenshot_size=(width, height),
                action=action,
                observation=action.description,
                success=True,
            )

            # Step 3: Check if task is complete
            if action.action_type == "done":
                self._steps.append(step)
                yield step
                break

            if action.action_type == "error":
                step.success = False
                self._steps.append(step)
                yield step
                break

            # Step 4: Execute the action
            await self._execute_action(action)
            self._steps.append(step)
            yield step

            # Brief pause for UI to update
            await asyncio.sleep(0.5)

        # Final step if we hit max iterations
        if iteration >= self._max_iterations:
            yield VisionStep(
                iteration=iteration,
                observation=f"Max iterations ({self._max_iterations}) reached",
                success=False,
            )

    async def _take_screenshot(self) -> tuple[str, int, int]:
        """Capture the desktop screen as base64 PNG."""
        try:
            import pyautogui
            from PIL import Image

            screenshot = pyautogui.screenshot()

            # Resize if too large (saves tokens)
            w, h = screenshot.size
            if max(w, h) > SCREENSHOT_MAX_DIMENSION:
                ratio = SCREENSHOT_MAX_DIMENSION / max(w, h)
                new_w, new_h = int(w * ratio), int(h * ratio)
                screenshot = screenshot.resize((new_w, new_h), Image.LANCZOS)
                w, h = new_w, new_h

            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG", optimize=True)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            return b64, w, h

        except ImportError:
            logger.warning("vision_loop.pyautogui_not_available")
            return "", 0, 0
        except Exception as exc:
            logger.error("vision_loop.screenshot_failed", error=str(exc))
            return "", 0, 0

    async def _analyze_screenshot(
        self,
        screenshot_b64: str,
        width: int,
        height: int,
        task: str,
        context: str,
        iteration: int,
    ) -> VisionAction:
        """Send screenshot to vision LLM and get next action."""
        # Build the history of previous actions
        history = ""
        for prev in self._steps[-5:]:  # Last 5 steps for context
            if prev.action:
                history += f"  Step {prev.iteration}: {prev.action.action_type} - {prev.action.description}\n"

        prompt = f"""You are Daena, an AI agent controlling a desktop computer.
You can see a screenshot of the current screen state.

TASK: {task}

{f"CONTEXT: {context}" if context else ""}

PREVIOUS ACTIONS:
{history if history else "  (none - this is the first step)"}

CURRENT ITERATION: {iteration}/{self._max_iterations}
SCREEN SIZE: {width}x{height} pixels

Analyze the screenshot and decide the next action. Respond with ONLY a JSON object:

{{
    "action_type": "click|type|scroll|hotkey|wait|done|error",
    "x": 0,          // pixel X coordinate (for click)
    "y": 0,          // pixel Y coordinate (for click)
    "text": "",       // text to type (for type)
    "keys": "",       // key combination (for hotkey, e.g. "ctrl+s")
    "direction": "",  // "up" or "down" (for scroll)
    "amount": 3,      // scroll amount
    "button": "left", // mouse button
    "description": "Brief description of what this action does and why",
    "confidence": 0.9 // 0.0-1.0 how confident you are this is correct
}}

Use "done" when the task is complete.
Use "error" if the task cannot be completed.
Use "wait" if you need to wait for something to load.

IMPORTANT: Coordinates must be precise pixel positions on the {width}x{height} screen."""

        # Try vision-capable LLM providers in priority order
        action = await self._call_vision_llm(prompt, screenshot_b64)
        return action

    async def _call_vision_llm(
        self,
        prompt: str,
        screenshot_b64: str,
    ) -> VisionAction:
        """Call a vision-capable LLM with the screenshot.

        Priority: Anthropic Claude > OpenAI GPT-4o > Ollama multimodal.
        """
        # Try Anthropic Claude (best vision model)
        try:
            action = await self._call_anthropic(prompt, screenshot_b64)
            if action:
                return action
        except Exception as exc:
            logger.debug("vision_loop.anthropic_failed", error=str(exc))

        # Try OpenAI GPT-4o
        try:
            action = await self._call_openai(prompt, screenshot_b64)
            if action:
                return action
        except Exception as exc:
            logger.debug("vision_loop.openai_failed", error=str(exc))

        # Try Ollama with a multimodal model (llava, bakllava, etc.)
        try:
            action = await self._call_ollama_vision(prompt, screenshot_b64)
            if action:
                return action
        except Exception as exc:
            logger.debug("vision_loop.ollama_vision_failed", error=str(exc))

        return VisionAction(
            action_type="error",
            description="No vision-capable LLM available. Need Anthropic, OpenAI, or Ollama with multimodal model.",
        )

    async def _call_anthropic(self, prompt: str, image_b64: str) -> VisionAction | None:
        """Call Claude with vision."""
        import httpx
        from app.core.config import get_settings

        settings = get_settings()
        api_key = settings.anthropic_api_key if hasattr(settings, "anthropic_api_key") else ""
        if not api_key:
            return None

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model_id or "claude-sonnet-4-20250514",
                    "max_tokens": 1024,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["content"][0]["text"]
                return self._parse_action(text)
        return None

    async def _call_openai(self, prompt: str, image_b64: str) -> VisionAction | None:
        """Call GPT-4o with vision."""
        import httpx
        from app.core.config import get_settings

        settings = get_settings()
        api_key = settings.openai_api_key if hasattr(settings, "openai_api_key") else ""
        if not api_key:
            return None

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o",
                    "max_tokens": 1024,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                return self._parse_action(text)
        return None

    async def _call_ollama_vision(self, prompt: str, image_b64: str) -> VisionAction | None:
        """Call Ollama with a multimodal model (llava, bakllava, etc.).

        Gated on OLLAMA_ENABLED. Ollama is deprecated in Daena (CLAUDE.md:
        llama.cpp llama-server is the local runtime). Returns None when
        disabled so the caller falls through to the runtime registry.
        """
        from app.core.config import get_settings
        _settings = get_settings()
        if not _settings.ollama_enabled:
            return None

        import httpx

        # Check for vision-capable models
        vision_models = ["llava:latest", "bakllava:latest", "llava:13b", "llava:7b"]
        base = _settings.ollama_base_url.rstrip("/")

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Find first available vision model
            try:
                tags_resp = await client.get(f"{base}/api/tags")
                if tags_resp.status_code == 200:
                    available = {m["name"] for m in tags_resp.json().get("models", [])}
                    selected = None
                    for vm in vision_models:
                        if vm in available:
                            selected = vm
                            break
                    if not selected:
                        return None
                else:
                    return None
            except Exception:
                return None

            # Call with image
            resp = await client.post(
                f"{base}/api/generate",
                json={
                    "model": selected,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                },
            )
            if resp.status_code == 200:
                text = resp.json().get("response", "")
                return self._parse_action(text)
        return None

    def _parse_action(self, text: str) -> VisionAction:
        """Parse LLM response into a VisionAction."""
        import re

        # Try to extract JSON from the response
        json_match = re.search(r'\{[^{}]*"action_type"[^{}]*\}', text, re.DOTALL)
        if not json_match:
            # Try multiline JSON
            json_match = re.search(r'\{.*?"action_type".*?\}', text, re.DOTALL)

        if json_match:
            try:
                data = json.loads(json_match.group())
                return VisionAction(
                    action_type=data.get("action_type", "error"),
                    x=int(data.get("x", 0)),
                    y=int(data.get("y", 0)),
                    text=data.get("text", ""),
                    keys=data.get("keys", ""),
                    direction=data.get("direction", ""),
                    amount=int(data.get("amount", 3)),
                    button=data.get("button", "left"),
                    description=data.get("description", ""),
                    confidence=float(data.get("confidence", 0.5)),
                )
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        return VisionAction(
            action_type="error",
            description=f"Could not parse vision response: {text[:200]}",
        )

    async def _execute_action(self, action: VisionAction) -> None:
        """Execute a vision-determined action on the desktop."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1

            if action.action_type == "click":
                clicks = 1
                pyautogui.click(action.x, action.y, clicks=clicks, button=action.button)

            elif action.action_type == "type":
                if action.text.isascii():
                    pyautogui.typewrite(action.text, interval=0.02)
                else:
                    pyautogui.write(action.text)

            elif action.action_type == "hotkey":
                keys = action.keys.split("+")
                pyautogui.hotkey(*[k.strip() for k in keys])

            elif action.action_type == "scroll":
                scroll_val = action.amount if action.direction == "up" else -action.amount
                if action.x and action.y:
                    pyautogui.scroll(scroll_val, action.x, action.y)
                else:
                    pyautogui.scroll(scroll_val)

            elif action.action_type == "wait":
                await asyncio.sleep(1.0)

            logger.info(
                "vision_loop.action_executed",
                action=action.action_type,
                description=action.description[:100],
            )

        except Exception as exc:
            logger.error("vision_loop.action_failed", error=str(exc))

    def get_summary(self) -> dict[str, Any]:
        """Get execution summary."""
        return {
            "total_steps": len(self._steps),
            "successful_steps": sum(1 for s in self._steps if s.success),
            "actions": [
                {
                    "iteration": s.iteration,
                    "action": s.action.action_type if s.action else "none",
                    "description": s.observation,
                }
                for s in self._steps
            ],
        }
