"""Governance integration for interactive prompts.

Two responsibilities:
1. Audit trail: every prompt and response is logged
2. AGI mode: auto-respond to non-sensitive prompts when autopilot is ON

Security invariant: CREDENTIAL and VERIFICATION prompts ALWAYS require
human interaction, even in full AGI mode. Passwords are never auto-filled
and external verification actions require human presence.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.agent_core.interactive_prompts import (
    InteractivePromptManager,
    PromptType,
)

logger = get_logger(__name__)

# Prompt types that ALWAYS require human interaction
HUMAN_REQUIRED_TYPES = frozenset({
    PromptType.CREDENTIAL,
    PromptType.VERIFICATION,
})

# Default auto-responses for AGI mode
AGI_AUTO_RESPONSES: dict[PromptType, dict[str, Any]] = {
    PromptType.CHOICE: {"selected": "1"},  # Pick first (fastest)
    PromptType.APPROVAL: {"selected": "approve"},  # Auto-approve non-critical
    PromptType.PROGRESS: {"selected": "continue"},  # Keep going
    PromptType.CONFIRM: {"selected": "yes"},  # Auto-confirm
    PromptType.TEXT_INPUT: {"text": ""},  # Skip text input
}


class GovernedPromptManager:
    """Wraps InteractivePromptManager with governance awareness.

    In governed mode (autopilot OFF): all prompts show to user.
    In AGI mode (autopilot ON): non-sensitive prompts auto-respond.
    """

    def __init__(
        self,
        prompt_manager: InteractivePromptManager,
        autopilot: bool = False,
    ) -> None:
        self._pm = prompt_manager
        self._autopilot = autopilot

    @property
    def autopilot(self) -> bool:
        return self._autopilot

    @autopilot.setter
    def autopilot(self, value: bool) -> None:
        self._autopilot = value
        logger.info("governed_prompt.autopilot_changed", autopilot=value)

    async def ask_choice(
        self,
        title: str,
        message: str,
        options: list[str],
        context: dict[str, Any] | None = None,
    ) -> str:
        """Choice prompt -- auto-picks first option in AGI mode."""
        if self._autopilot:
            self._audit_auto("choice", title, "auto: first option")
            return options[0] if options else ""
        return await self._pm.ask_choice(title, message, options, context)

    async def ask_credential(
        self,
        title: str,
        message: str,
        fields: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Credential prompt -- ALWAYS asks user, even in AGI mode."""
        # Security invariant: never auto-fill credentials
        return await self._pm.ask_credential(title, message, fields, context)

    async def ask_approval(
        self,
        title: str,
        message: str,
        preview_content: str | None = None,
        context: dict[str, Any] | None = None,
        critical: bool = False,
    ) -> str:
        """Approval prompt -- auto-approves in AGI mode unless critical."""
        if self._autopilot and not critical:
            self._audit_auto("approval", title, "auto: approved")
            return "approve"
        return await self._pm.ask_approval(title, message, preview_content, context)

    async def ask_verification(
        self,
        title: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Verification prompt -- ALWAYS asks user (requires human action)."""
        # Security invariant: always requires human
        return await self._pm.ask_verification(title, message, context)

    async def show_progress(
        self,
        title: str,
        message: str,
        current: int,
        total: int,
        cost: float = 0,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Progress prompt -- auto-continues in AGI mode."""
        if self._autopilot:
            return "continue"
        return await self._pm.show_progress(title, message, current, total, cost, context)

    async def ask_confirm(
        self,
        title: str,
        message: str,
        critical: bool = False,
    ) -> bool:
        """Confirm prompt -- auto-yes in AGI mode unless critical."""
        if self._autopilot and not critical:
            self._audit_auto("confirm", title, "auto: yes")
            return True
        return await self._pm.ask_confirm(title, message)

    async def ask_text(
        self,
        title: str,
        message: str,
        placeholder: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:
        """Text input -- always asks user (no sensible auto-response)."""
        return await self._pm.ask_text(title, message, placeholder, context)

    # -- Audit --

    def _audit_auto(self, prompt_type: str, title: str, action: str) -> None:
        """Log an auto-response for audit trail."""
        logger.info(
            "governed_prompt.auto_response",
            prompt_type=prompt_type,
            title=title,
            action=action,
            autopilot=True,
        )

    @staticmethod
    def audit_prompt_response(
        prompt_id: str,
        prompt_type: str,
        title: str,
        response: dict[str, Any] | None,
        response_time_ms: int = 0,
        user_id: str = "",
    ) -> None:
        """Log a human response for audit trail.

        Called after every user interaction with a prompt.
        Credential values are NEVER logged -- only the fact
        that credentials were provided.
        """
        sanitized = response
        if prompt_type == "credential" and response:
            sanitized = {
                "fields": {k: "***provided***" for k in response.get("fields", {})}
            }

        logger.info(
            "governed_prompt.user_response",
            prompt_id=prompt_id,
            prompt_type=prompt_type,
            title=title,
            response=sanitized,
            response_time_ms=response_time_ms,
            user_id=user_id,
        )
