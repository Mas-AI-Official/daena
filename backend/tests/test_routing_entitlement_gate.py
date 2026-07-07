"""Integration tests for the COUNCIL / QUINTESSENCE routing entitlement gate.

COUNCIL and QUINTESSENCE are PAID routing tiers (entitlements.FEATURE_MIN_PLAN:
COUNCIL -> PRO, QUINTESSENCE -> MAX). The gate in
``app/api/v1/chat.py::_stream_message_response`` enforces them ONLY on the user's
EXPLICIT request (``body.routing_mode`` or the saved ``default_routing_mode``) --
never on the orchestrator's internal complexity+risk auto-escalation, which is
free governance (locked decision: charging for the safety router's own
escalation is a governance break and dishonest).

Honest surfacing (Rule 13 / Rule 17): the chat stream is opened by a raw inline
fetch that turns any non-2xx into an opaque toast (the axios 402 -> billing
interceptor never sees the stream response). So instead of a pre-stream 402, a
sub-tier explicit request DEGRADES GRACEFULLY to STANDARD and emits a visible
``governance_notice`` SSE event -- the same "insufficient capability -> STANDARD
with a notice" fallback Rule 13 already uses when fewer than 2 models are
available. The stream still succeeds in STANDARD and the user is told exactly how
to unlock the requested tier.

These tests assert BOTH halves of that contract:
  1. The user-visible signal: a ``governance_notice`` event is (or is not) on the
     wire, carrying the upgrade message.
  2. The actual routing handed to the orchestrator: ``routing_mode_override`` is
     forced to "STANDARD" on downgrade, and passed through unchanged when the
     plan entitles the tier.

Plan/feature matrix covered:
  FREE       + COUNCIL      -> downgrade (COUNCIL needs PRO)
  FREE       + QUINTESSENCE -> downgrade (QUINTESSENCE needs MAX)
  FREE       + STANDARD     -> no gate (STANDARD is free; orchestrator gets STANDARD)
  PRO        + COUNCIL      -> allowed
  PRO        + QUINTESSENCE -> downgrade (PRO does NOT unlock QUINTESSENCE -- per
                              feature, not "any paid plan unlocks any tier")
  MAX        + QUINTESSENCE -> allowed
  FOUNDER    + COUNCIL      -> allowed (resolve_effective_plan short-circuits)

The orchestrator and the model registry are stubbed: the gate's decision is made
entirely from the JWT role + the tenant's ACTIVE subscription, so no live model
is needed. The FK-bearing ChatSession + ChatMessage writes run BEFORE the gate on
every request, so every case seeds Tenant(flush) + User (mirroring conftest's
seed order) regardless of the expected outcome.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.core.security import create_access_token
from app.models.financial import Subscription
from app.models.identity import Tenant, User


def _headers(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> dict[str, str]:
    """A valid JWT for the given principal. get_current_user builds CurrentUser
    purely from the token, so the role here is exactly the role the gate sees."""
    token = create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id), role=role
    )
    return {"Authorization": f"Bearer {token}"}


def _parse_sse(text: str) -> list[dict]:
    """Parse an SSE body into the list of JSON event payloads it carried."""
    events: list[dict] = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[len("data: ") :]))
                except json.JSONDecodeError:
                    pass
    return events


def _governance_notice(events: list[dict]) -> dict | None:
    for event in events:
        if event.get("type") == "governance_notice":
            return event
    return None


@pytest.fixture
def routing_capture(monkeypatch):
    """Stub the orchestrator + model registry and capture the routing override.

    ``ChatOrchestrator`` is imported LOCALLY inside ``_stream_message_response``
    (``from app.services.chat_orchestrator import ChatOrchestrator``), so the name
    is resolved from the module at call time -- patching the module attribute
    swaps in the stub. ``get_model_registry`` runs (line 180) BEFORE the gate and
    reads ``request.app.state.model_registry``, which is unset under ASGITransport
    (no lifespan); patch it to a dummy so the request reaches the gate.

    The stub records the ``routing_mode_override`` the gate hands it -- the single
    fact that proves the gate forced STANDARD (downgrade) or passed the request
    through (allowed).
    """
    holder: dict = {"called": False, "routing_mode_override": None}

    class _StubOrchestrator:
        def __init__(self, db, registry):
            pass

        async def stream_reply(self, **kwargs):
            holder["called"] = True
            holder["routing_mode_override"] = kwargs.get("routing_mode_override")
            yield {"type": "chunk", "content": "ok"}
            yield {"type": "done", "model_id": "stub", "provider": "DAENA"}

    import app.services.chat_orchestrator as _orch_mod

    monkeypatch.setattr(_orch_mod, "ChatOrchestrator", _StubOrchestrator)

    import app.api.v1.chat as _chat_mod

    monkeypatch.setattr(_chat_mod, "get_model_registry", lambda request: object())

    return holder


async def _seed_principal(
    db_session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    plan: str | None = None,
) -> None:
    """Seed Tenant (flushed first so it is a valid FK target) + User, and an
    ACTIVE Subscription when a paid plan is given. Mirrors the FK-safe seed order
    used by conftest's seed_auth_principal and the org gate tests."""
    db_session.add(
        Tenant(
            id=tenant_id,
            name="Co",
            slug=f"co-{tenant_id.hex[:12]}",
            settings={},
        )
    )
    await db_session.flush()
    db_session.add(
        User(
            id=user_id,
            tenant_id=tenant_id,
            email=f"{user_id.hex[:12]}@example.com",
            password_hash="x",
            role=role,
            is_active=True,
            settings={},
        )
    )
    if plan is not None:
        db_session.add(Subscription(tenant_id=tenant_id, plan=plan, status="ACTIVE"))
    await db_session.flush()


async def _send(client, headers, routing_mode: str):
    """POST the canonical first-turn stream with an explicit routing request."""
    return await client.post(
        "/api/v1/chat/messages/stream",
        headers=headers,
        json={"content": "hello", "routing_mode": routing_mode},
    )


# -- Downgrade: sub-tier tenant requesting a paid routing tier --


@pytest.mark.asyncio
async def test_free_tenant_council_downgrades_to_standard(
    client, db_session, routing_capture
):
    """FREE explicit COUNCIL -> visible governance_notice + orchestrator runs STANDARD."""
    tenant_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user_id = uuid.UUID("11111111-1111-1111-1111-1111111111aa")
    await _seed_principal(db_session, tenant_id=tenant_id, user_id=user_id, role="ADMIN")

    resp = await _send(client, _headers(user_id, tenant_id, "ADMIN"), "COUNCIL")
    assert resp.status_code == 200, resp.text

    notice = _governance_notice(_parse_sse(resp.text))
    assert notice is not None, "expected a governance_notice on the wire"
    assert notice["tier"] == 0
    assert "Council" in notice["message"]
    assert "PRO" in notice["message"]
    assert "Standard" in notice["message"]

    # The actual routing the orchestrator received was forced down to STANDARD.
    assert routing_capture["called"] is True
    assert routing_capture["routing_mode_override"] == "STANDARD"


@pytest.mark.asyncio
async def test_free_tenant_quintessence_downgrades_to_standard(
    client, db_session, routing_capture
):
    """FREE explicit QUINTESSENCE -> governance_notice (needs MAX) + STANDARD run."""
    tenant_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    user_id = uuid.UUID("22222222-2222-2222-2222-2222222222aa")
    await _seed_principal(db_session, tenant_id=tenant_id, user_id=user_id, role="ADMIN")

    resp = await _send(client, _headers(user_id, tenant_id, "ADMIN"), "QUINTESSENCE")
    assert resp.status_code == 200, resp.text

    notice = _governance_notice(_parse_sse(resp.text))
    assert notice is not None
    assert notice["tier"] == 0
    assert "Quintessence" in notice["message"]
    assert "MAX" in notice["message"]

    assert routing_capture["routing_mode_override"] == "STANDARD"


@pytest.mark.asyncio
async def test_pro_tenant_quintessence_downgrades_to_standard(
    client, db_session, routing_capture
):
    """PRO does NOT unlock QUINTESSENCE: the gate is per-feature, not "any paid plan".

    QUINTESSENCE needs MAX; a PRO tenant requesting it still degrades to STANDARD
    with the upgrade notice. This is the test that proves the gate keys on the
    specific feature, not on "is the tenant paying anything".
    """
    tenant_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    user_id = uuid.UUID("33333333-3333-3333-3333-3333333333aa")
    await _seed_principal(
        db_session, tenant_id=tenant_id, user_id=user_id, role="ADMIN", plan="PRO"
    )

    resp = await _send(client, _headers(user_id, tenant_id, "ADMIN"), "QUINTESSENCE")
    assert resp.status_code == 200, resp.text

    notice = _governance_notice(_parse_sse(resp.text))
    assert notice is not None
    assert "Quintessence" in notice["message"]
    assert "MAX" in notice["message"]
    assert routing_capture["routing_mode_override"] == "STANDARD"


# -- No gate: STANDARD is free, paid plans entitle their tier --


@pytest.mark.asyncio
async def test_free_tenant_standard_is_never_gated(
    client, db_session, routing_capture
):
    """STANDARD routing carries no entitlement: no notice, orchestrator gets STANDARD."""
    tenant_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    user_id = uuid.UUID("44444444-4444-4444-4444-4444444444aa")
    await _seed_principal(db_session, tenant_id=tenant_id, user_id=user_id, role="ADMIN")

    resp = await _send(client, _headers(user_id, tenant_id, "ADMIN"), "STANDARD")
    assert resp.status_code == 200, resp.text

    assert _governance_notice(_parse_sse(resp.text)) is None
    assert routing_capture["routing_mode_override"] == "STANDARD"


@pytest.mark.asyncio
async def test_pro_tenant_council_allowed(client, db_session, routing_capture):
    """An ACTIVE PRO subscription entitles COUNCIL: no notice, COUNCIL passes through."""
    tenant_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    user_id = uuid.UUID("55555555-5555-5555-5555-5555555555aa")
    await _seed_principal(
        db_session, tenant_id=tenant_id, user_id=user_id, role="ADMIN", plan="PRO"
    )

    resp = await _send(client, _headers(user_id, tenant_id, "ADMIN"), "COUNCIL")
    assert resp.status_code == 200, resp.text

    assert _governance_notice(_parse_sse(resp.text)) is None
    assert routing_capture["routing_mode_override"] == "COUNCIL"


@pytest.mark.asyncio
async def test_max_tenant_quintessence_allowed(client, db_session, routing_capture):
    """An ACTIVE MAX subscription entitles QUINTESSENCE: no notice, passes through."""
    tenant_id = uuid.UUID("66666666-6666-6666-6666-666666666666")
    user_id = uuid.UUID("66666666-6666-6666-6666-6666666666aa")
    await _seed_principal(
        db_session, tenant_id=tenant_id, user_id=user_id, role="ADMIN", plan="MAX"
    )

    resp = await _send(client, _headers(user_id, tenant_id, "ADMIN"), "QUINTESSENCE")
    assert resp.status_code == 200, resp.text

    assert _governance_notice(_parse_sse(resp.text)) is None
    assert routing_capture["routing_mode_override"] == "QUINTESSENCE"


@pytest.mark.asyncio
async def test_founder_council_allowed(client, db_session, routing_capture):
    """FOUNDER short-circuits resolve_effective_plan -> every routing tier unlocked.

    No ACTIVE subscription is seeded, proving the FOUNDER role (not a paid plan)
    is what opens the gate -- the same short-circuit that keeps the org-gate
    FOUNDER tests green.
    """
    tenant_id = uuid.UUID("77777777-7777-7777-7777-777777777777")
    user_id = uuid.UUID("77777777-7777-7777-7777-7777777777aa")
    await _seed_principal(
        db_session, tenant_id=tenant_id, user_id=user_id, role="FOUNDER"
    )

    resp = await _send(client, _headers(user_id, tenant_id, "FOUNDER"), "COUNCIL")
    assert resp.status_code == 200, resp.text

    assert _governance_notice(_parse_sse(resp.text)) is None
    assert routing_capture["routing_mode_override"] == "COUNCIL"
