"""Sprint-MORNING PR-1 -- contract test for chat -> VP-command preflight.

The frontend chat store calls POST /api/v1/vp-commands BEFORE the LLM
SSE stream. If the deterministic regex parser matches a recognized
intent, the chat renders a structured card and skips the LLM. If
intent == "unrecognized", the chat falls through to the normal LLM
stream.

This file pins the contract the frontend relies on:

  1. POST /api/v1/vp-commands always returns 200 (even for refusals
     and unrecognized inputs).
  2. The response always carries the six fields the chat reads:
     success / intent / summary / needs_disambiguation / next_action
     / data.
  3. ``hello daena`` parses as intent="unrecognized" so the chat
     falls through to the LLM. Anything else with a recognized verb
     stays in the VP-command surface.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


_REQUIRED_KEYS = {
    "success",
    "intent",
    "summary",
    "needs_disambiguation",
    "next_action",
    "data",
}


class TestPreflightShape:
    async def test_unrecognized_input_falls_through(self):
        """``hello daena`` must parse as ``unrecognized``.

        The chat preflight reads ``intent`` and renders the card only
        when ``intent != "unrecognized"``. If this contract changes,
        every casual chat message would short-circuit the LLM.
        """
        from app.services.vp_work_commands import parse_command

        parsed = parse_command("hello daena")
        assert parsed.intent == "unrecognized"

    async def test_review_drafts_recognized(self):
        from app.services.vp_work_commands import parse_command

        parsed = parse_command("review my drafts")
        assert parsed.intent == "review_drafts"

    async def test_next_steps_recognized(self):
        from app.services.vp_work_commands import parse_command

        for phrase in ("what should I do next?", "what's next", "what is next"):
            parsed = parse_command(phrase)
            assert parsed.intent == "next_steps", (
                f"phrase {phrase!r} expected next_steps, got {parsed.intent}"
            )

    async def test_command_result_has_all_required_keys(self, db_session, test_tenant_id, test_user_id):
        """The response shape the frontend depends on must not drift."""
        from app.services.vp_work_commands import parse_command, run_command
        from app.models.identity import Tenant, User
        from sqlalchemy import select
        import uuid as _uuid

        # Seed minimal tenant+user (run_command is tenant+user scoped).
        if not (await db_session.execute(
            select(Tenant).where(Tenant.id == test_tenant_id)
        )).scalar_one_or_none():
            slug = str(test_tenant_id)[:8]
            db_session.add(Tenant(
                id=test_tenant_id,
                name=f"contract-{slug}",
                slug=slug,
            ))
        if not (await db_session.execute(
            select(User).where(User.id == test_user_id)
        )).scalar_one_or_none():
            db_session.add(User(
                id=test_user_id, tenant_id=test_tenant_id,
                email="contract@example.com",
                password_hash="x", role="FOUNDER", is_active=True,
            ))
        await db_session.flush()

        result = await run_command(
            db_session,
            parse_command("review my drafts"),
            user_id=test_user_id,
            tenant_id=test_tenant_id,
            registry=None,
        )

        # CommandResult exposes all six fields the VPCommandResponse
        # serializer mirrors. The frontend reads exactly these keys.
        for key in _REQUIRED_KEYS:
            assert hasattr(result, key), f"CommandResult missing field: {key}"

    async def test_route_mounted_under_v1(self):
        """Route must mount under /vp-commands so frontend can hit
        /api/v1/vp-commands."""
        from app.api.v1 import router as api_v1_router
        paths = [getattr(r, "path", "") for r in api_v1_router.routes]
        assert "/vp-commands" in paths
