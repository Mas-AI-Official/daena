"""Interactive prompt system for agent-to-user communication.

When the AgentLoop hits a decision point (needs credentials, needs user
choice, needs approval), it pauses execution, sends a structured prompt
to the frontend via SSE, and waits for the user's response before
continuing.

Flow:
1. AgentLoop calls prompt_manager.ask_choice/ask_credential/etc.
2. Prompt is broadcast to frontend via SSE event ("interactive_prompt")
3. Frontend renders the prompt (modal, inline card, or toast)
4. User responds
5. Response sent back via POST /api/v1/prompts/{id}/respond
6. AgentLoop receives the response and continues

Thread-safe via asyncio.Event. No polling. No busy-wait.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class PromptType(Enum):
    CHOICE = "choice"
    CREDENTIAL = "credential"
    APPROVAL = "approval"
    VERIFICATION = "verification"
    PROGRESS = "progress"
    TEXT_INPUT = "text_input"
    CONFIRM = "confirm"


@dataclass
class PromptOption:
    id: str
    label: str
    icon: str = ""
    style: str = "default"  # default, primary, danger, success


@dataclass
class InteractivePrompt:
    id: str
    type: PromptType
    title: str
    message: str
    options: list[PromptOption] = field(default_factory=list)
    fields: list[dict[str, Any]] = field(default_factory=list)
    default_value: str = ""
    timeout_seconds: int = 3600
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    responded: bool = False
    response: Optional[dict[str, Any]] = None
    expired: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "message": self.message,
            "options": [
                {"id": o.id, "label": o.label, "icon": o.icon, "style": o.style}
                for o in self.options
            ],
            "fields": self.fields,
            "default_value": self.default_value,
            "context": self.context,
            "created_at": self.created_at,
            "responded": self.responded,
            "expired": self.expired,
        }


class InteractivePromptManager:
    """Manages the prompt queue between AgentLoop and the frontend.

    Singleton per process. Each prompt gets a unique ID and an
    asyncio.Event. The agent awaits the Event; the API handler
    sets it when the user responds.
    """

    _instance: Optional["InteractivePromptManager"] = None

    def __init__(self) -> None:
        self._pending: dict[str, InteractivePrompt] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._history: list[dict[str, Any]] = []
        self._sse_callbacks: list[Any] = []

    @classmethod
    def get_instance(cls) -> "InteractivePromptManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -- High-level prompt helpers --

    async def ask_choice(
        self,
        title: str,
        message: str,
        options: list[str],
        context: dict[str, Any] | None = None,
    ) -> str:
        """Ask user to pick from numbered options. Returns chosen label."""
        prompt = InteractivePrompt(
            id=self._generate_id(),
            type=PromptType.CHOICE,
            title=title,
            message=message,
            options=[
                PromptOption(id=str(i + 1), label=opt)
                for i, opt in enumerate(options)
            ],
            context=context or {},
        )
        response = await self._send_and_wait(prompt)
        selected_id = response.get("selected", "1")
        # Map ID back to label
        opt_map = {str(i + 1): opt for i, opt in enumerate(options)}
        return opt_map.get(selected_id, options[0])

    async def ask_credential(
        self,
        title: str,
        message: str,
        fields: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Ask user for credentials. Returns field values dict."""
        prompt = InteractivePrompt(
            id=self._generate_id(),
            type=PromptType.CREDENTIAL,
            title=title,
            message=message,
            fields=fields,
            context=context or {},
        )
        response = await self._send_and_wait(prompt)
        return response.get("fields", {})

    async def ask_approval(
        self,
        title: str,
        message: str,
        preview_content: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Ask user to approve an action. Returns 'approve', 'cancel', or 'preview'."""
        options = [
            PromptOption(id="approve", label="Approve", icon="check", style="success"),
            PromptOption(id="cancel", label="Cancel", icon="x", style="danger"),
        ]
        if preview_content:
            options.insert(
                0,
                PromptOption(id="preview", label="Preview First", icon="eye", style="default"),
            )
        ctx = {**(context or {})}
        if preview_content:
            ctx["preview_content"] = preview_content

        prompt = InteractivePrompt(
            id=self._generate_id(),
            type=PromptType.APPROVAL,
            title=title,
            message=message,
            options=options,
            context=ctx,
        )
        response = await self._send_and_wait(prompt)
        return response.get("selected", "cancel")

    async def ask_verification(
        self,
        title: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Wait for user to complete external action. Returns 'verified', 'resend', 'skip', or 'cancel'."""
        prompt = InteractivePrompt(
            id=self._generate_id(),
            type=PromptType.VERIFICATION,
            title=title,
            message=message,
            options=[
                PromptOption(id="verified", label="I've Verified", icon="check-circle", style="success"),
                PromptOption(id="resend", label="Resend", icon="refresh-cw", style="default"),
                PromptOption(id="skip", label="Skip This", icon="skip-forward", style="default"),
                PromptOption(id="cancel", label="Cancel", icon="x", style="danger"),
            ],
            context=context or {},
        )
        response = await self._send_and_wait(prompt)
        return response.get("selected", "cancel")

    async def show_progress(
        self,
        title: str,
        message: str,
        current: int,
        total: int,
        cost: float = 0,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Show progress and let user decide to continue or stop."""
        prompt = InteractivePrompt(
            id=self._generate_id(),
            type=PromptType.PROGRESS,
            title=title,
            message=f"{message}\n\nProgress: {current}/{total} | Cost: ${cost:.4f}",
            options=[
                PromptOption(id="continue", label="Continue All", icon="play", style="success"),
                PromptOption(id="pause", label="Pause", icon="pause", style="default"),
                PromptOption(id="skip_next", label="Skip Next", icon="skip-forward", style="default"),
                PromptOption(id="stop", label="Stop", icon="square", style="danger"),
            ],
            context={**(context or {}), "current": current, "total": total, "cost": cost},
            timeout_seconds=30,
        )
        try:
            response = await self._send_and_wait(prompt)
            return response.get("selected", "continue")
        except asyncio.TimeoutError:
            return "continue"

    async def ask_text(
        self,
        title: str,
        message: str,
        placeholder: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:
        """Ask user for free-form text input."""
        prompt = InteractivePrompt(
            id=self._generate_id(),
            type=PromptType.TEXT_INPUT,
            title=title,
            message=message,
            default_value=placeholder,
            context=context or {},
        )
        response = await self._send_and_wait(prompt)
        return response.get("text", "")

    async def ask_confirm(self, title: str, message: str) -> bool:
        """Simple yes/no confirmation."""
        prompt = InteractivePrompt(
            id=self._generate_id(),
            type=PromptType.CONFIRM,
            title=title,
            message=message,
            options=[
                PromptOption(id="yes", label="Yes", style="success"),
                PromptOption(id="no", label="No", style="danger"),
            ],
        )
        response = await self._send_and_wait(prompt)
        return response.get("selected") == "yes"

    # -- Core send/receive --

    async def _send_and_wait(self, prompt: InteractivePrompt) -> dict[str, Any]:
        """Send prompt to frontend and wait for response."""
        self._pending[prompt.id] = prompt
        self._events[prompt.id] = asyncio.Event()

        logger.info(
            "prompt.sent",
            prompt_id=prompt.id,
            prompt_type=prompt.type.value,
            title=prompt.title,
        )

        # Broadcast via SSE
        await self._broadcast_prompt(prompt)

        # Wait for response
        try:
            await asyncio.wait_for(
                self._events[prompt.id].wait(),
                timeout=prompt.timeout_seconds,
            )
            self._log_history(prompt)
            return prompt.response or {}
        except asyncio.TimeoutError:
            prompt.expired = True
            self._log_history(prompt)
            logger.warning("prompt.expired", prompt_id=prompt.id)
            raise
        finally:
            self._pending.pop(prompt.id, None)
            self._events.pop(prompt.id, None)

    def respond(self, prompt_id: str, response: dict[str, Any]) -> bool:
        """Called by API when user responds to a prompt."""
        if prompt_id not in self._pending:
            logger.warning("prompt.respond_not_found", prompt_id=prompt_id)
            return False

        self._pending[prompt_id].response = response
        self._pending[prompt_id].responded = True

        if prompt_id in self._events:
            self._events[prompt_id].set()

        logger.info(
            "prompt.responded",
            prompt_id=prompt_id,
            response_keys=list(response.keys()),
        )
        return True

    # -- Query methods --

    def get_pending(self) -> list[dict[str, Any]]:
        """Get all pending prompts for frontend display."""
        return [p.to_dict() for p in self._pending.values()]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent prompt history."""
        return self._history[-limit:]

    # -- SSE integration --

    def register_sse_callback(self, callback: Any) -> None:
        """Register a callback that broadcasts prompts via SSE."""
        self._sse_callbacks.append(callback)

    def unregister_sse_callback(self, callback: Any) -> None:
        self._sse_callbacks = [c for c in self._sse_callbacks if c is not callback]

    async def _broadcast_prompt(self, prompt: InteractivePrompt) -> None:
        """Send prompt to all connected frontend clients via SSE."""
        event_data = {
            "type": "interactive_prompt",
            **prompt.to_dict(),
        }
        for callback in self._sse_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_data)
                else:
                    callback(event_data)
            except Exception as exc:
                logger.warning("prompt.broadcast_error", error=str(exc))

    # -- Helpers --

    def _log_history(self, prompt: InteractivePrompt) -> None:
        """Log prompt to history (capped at 200 entries)."""
        entry = {
            "prompt_id": prompt.id,
            "type": prompt.type.value,
            "title": prompt.title,
            "responded": prompt.responded,
            "expired": prompt.expired,
            "created_at": prompt.created_at,
            "responded_at": datetime.utcnow().isoformat() if prompt.responded else None,
        }
        # Sanitize: never log credential values
        if prompt.type == PromptType.CREDENTIAL and prompt.response:
            entry["response"] = {
                k: "***provided***" for k in prompt.response.get("fields", {})
            }
        else:
            entry["response"] = prompt.response

        self._history.append(entry)
        if len(self._history) > 200:
            self._history = self._history[-200:]

    @staticmethod
    def _generate_id() -> str:
        return f"prompt-{uuid.uuid4().hex[:12]}"
