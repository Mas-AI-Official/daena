"""Outbound telephony: VAPI-first provider-plugin.

Phase I.5 of Roadmap V2. Lets Daena place outbound phone calls from
agent workflows (Sales call play, Support escalation, Founder ops).
Every call ties back to a ChatSession so the transcript lands in the
existing audit chain.

Provider architecture mirrors :mod:`voice.stt_pipeline` and
:mod:`voice.tts_pipeline`. VAPI ships first because it is the fastest
path to a live demo. Retell and Vocode (self-host, SOVEREIGN)
register later behind the same interface without call-site churn.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CallHandle:
    """Opaque handle to a placed call."""

    id: str
    provider: str
    to_number: str
    from_number: str
    conversation_id: UUID | None = None
    status: str = "initiated"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundError:
    """Returned (not raised) on provider failure."""

    provider: str
    reason: str
    recoverable: bool = False


class OutboundProvider:
    """Abstract outbound-call provider."""

    name: str = "abstract"

    async def place_call(
        self,
        *,
        to_number: str,
        from_number: str,
        conversation_id: UUID | None = None,
        agent_id: str | None = None,
        recording_consent: str = "two_party_safe",
        metadata: dict[str, Any] | None = None,
    ) -> CallHandle | OutboundError:
        raise NotImplementedError

    async def end_call(self, handle: CallHandle) -> None:
        raise NotImplementedError


class VapiProvider(OutboundProvider):
    """VAPI (vapi.ai) adapter.

    Reads ``VAPI_API_KEY`` and ``VAPI_PHONE_NUMBER_ID`` from env by
    default. Lazy-imports ``httpx`` at call time so the module loads
    cleanly even when the VAPI credentials are not configured.
    """

    name = "vapi"
    BASE_URL = "https://api.vapi.ai"

    def __init__(
        self,
        api_key: str | None = None,
        phone_number_id: str | None = None,
        assistant_id: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("VAPI_API_KEY", "")
        self.phone_number_id = phone_number_id or os.getenv("VAPI_PHONE_NUMBER_ID", "")
        self.assistant_id = assistant_id or os.getenv("VAPI_ASSISTANT_ID", "")

    async def place_call(
        self,
        *,
        to_number: str,
        from_number: str,
        conversation_id: UUID | None = None,
        agent_id: str | None = None,
        recording_consent: str = "two_party_safe",
        metadata: dict[str, Any] | None = None,
    ) -> CallHandle | OutboundError:
        if not self.api_key:
            return OutboundError(
                provider=self.name,
                reason="VAPI_API_KEY not set. Configure before placing calls.",
                recoverable=False,
            )
        if not self.phone_number_id:
            return OutboundError(
                provider=self.name,
                reason="VAPI_PHONE_NUMBER_ID not set.",
                recoverable=False,
            )

        try:
            import httpx  # type: ignore
        except ImportError:
            return OutboundError(
                provider=self.name,
                reason="httpx not installed. Run: pip install httpx",
                recoverable=False,
            )

        body = {
            "phoneNumberId": self.phone_number_id,
            "customer": {"number": to_number},
            "assistantId": agent_id or self.assistant_id or None,
            "metadata": {
                "conversation_id": str(conversation_id) if conversation_id else None,
                "recording_consent": recording_consent,
                **(metadata or {}),
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/call/phone",
                    json={k: v for k, v in body.items() if v is not None},
                    headers=headers,
                )
            if resp.status_code >= 400:
                return OutboundError(
                    provider=self.name,
                    reason=f"VAPI returned {resp.status_code}: {resp.text[:200]}",
                    recoverable=resp.status_code >= 500,
                )
            data = resp.json()
            return CallHandle(
                id=data.get("id", ""),
                provider=self.name,
                to_number=to_number,
                from_number=from_number,
                conversation_id=conversation_id,
                status=data.get("status", "initiated"),
                metadata={"raw": data},
            )
        except Exception as exc:
            logger.warning("outbound.vapi.place_call_failed", error=str(exc))
            return OutboundError(
                provider=self.name,
                reason=f"VAPI request failed: {exc}",
                recoverable=True,
            )

    async def end_call(self, handle: CallHandle) -> None:
        if not self.api_key or not handle.id:
            return
        try:
            import httpx  # type: ignore
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.patch(
                    f"{self.BASE_URL}/call/{handle.id}",
                    json={"status": "ended"},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
        except Exception as exc:
            logger.warning("outbound.vapi.end_call_failed", error=str(exc))


class DryRunProvider(OutboundProvider):
    """No-carrier provider for tests and governance-blocked tenants.

    Logs the call attempt and returns a deterministic CallHandle. The
    Sales agent uses this by default for the first 90 days of any new
    customer so outbound cannot accidentally place a real call before
    deliverability and consent checks are cleared.
    """

    name = "dry_run"

    async def place_call(
        self,
        *,
        to_number: str,
        from_number: str,
        conversation_id: UUID | None = None,
        agent_id: str | None = None,
        recording_consent: str = "two_party_safe",
        metadata: dict[str, Any] | None = None,
    ) -> CallHandle | OutboundError:
        logger.info(
            "outbound.dry_run.place_call",
            to=to_number, from_number=from_number,
            conversation_id=str(conversation_id) if conversation_id else None,
        )
        import uuid
        return CallHandle(
            id=f"dry-{uuid.uuid4().hex[:10]}",
            provider=self.name,
            to_number=to_number,
            from_number=from_number,
            conversation_id=conversation_id,
            status="dry_run",
            metadata={"consent": recording_consent, **(metadata or {})},
        )

    async def end_call(self, handle: CallHandle) -> None:
        logger.info("outbound.dry_run.end_call", id=handle.id)


# ── Pipeline orchestrator ────────────────────────────────────────


class OutboundPipeline:
    """Dispatches to the selected provider."""

    def __init__(self, default_provider: OutboundProvider | None = None) -> None:
        self._providers: dict[str, OutboundProvider] = {}
        self._default: OutboundProvider = default_provider or DryRunProvider()
        self._providers[self._default.name] = self._default

    def register(self, provider: OutboundProvider) -> None:
        self._providers[provider.name] = provider

    def available(self) -> list[str]:
        return sorted(self._providers)

    async def place_call(
        self,
        *,
        to_number: str,
        from_number: str,
        provider: str | None = None,
        **kwargs: Any,
    ) -> CallHandle | OutboundError:
        p = self._providers.get(provider) if provider else self._default
        if p is None:
            return OutboundError(
                provider=provider or "unknown",
                reason=f"Provider {provider!r} not registered.",
                recoverable=False,
            )
        return await p.place_call(
            to_number=to_number, from_number=from_number, **kwargs,
        )

    async def end_call(
        self, handle: CallHandle, *, provider: str | None = None,
    ) -> None:
        p = self._providers.get(provider or handle.provider)
        if p is not None:
            await p.end_call(handle)
