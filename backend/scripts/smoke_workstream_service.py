"""smoke_workstream_service.py

End-to-end smoke for the Workstream + WorkstreamEvent stack:

1. Boots the dev DB (assumes migrations 003 + 004 already ran).
2. Creates a synthetic tenant + user + department row.
3. Drives WorkstreamService through start -> transition -> redirect ->
   complete with the parser, asserting each step.
4. Lists events; confirms the timeline contains every emitted kind.

Run from D:\\Ideas\\Daena\\backend with the project venv:

    .\\venv_daena\\Scripts\\python.exe scripts\\smoke_workstream_service.py

Exits 0 on success, 1 on any assertion failure with a short report.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.database import async_session_factory  # noqa: E402
from app.models.identity import Tenant, User  # noqa: E402
from app.models.organization import Department  # noqa: E402
from app.models.workstream import (  # noqa: E402
    WorkstreamEscalationLevel,
    WorkstreamEventKind,
    WorkstreamStatus,
)
from app.services.workstream_redirect_parser import (  # noqa: E402
    RedirectActionKind,
    parse_redirect,
)
from app.services.workstream_service import (  # noqa: E402
    StartParams,
    WorkstreamService,
    WorkstreamTransitionError,
)


async def _seed_minimal(db) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Insert a throwaway tenant + user + dept; return their ids."""
    _slug = uuid.uuid4().hex[:8]
    t = Tenant(
        id=uuid.uuid4(),
        name=f"smoke-tenant-{_slug}",
        slug=f"smoke-{_slug}",
    )
    db.add(t)
    await db.flush()

    u = User(
        id=uuid.uuid4(),
        tenant_id=t.id,
        email=f"smoke-{uuid.uuid4().hex[:6]}@example.com",
        password_hash="x",
        role="FOUNDER",
    )
    db.add(u)
    await db.flush()

    d = Department(
        id=uuid.uuid4(),
        tenant_id=t.id,
        name="Engineering (smoke)",
        description="smoke",
        sunflower_index=0,
        cell_id="hex_0",
        config={},
        is_active=True,
    )
    db.add(d)
    await db.flush()
    await db.commit()
    return t.id, u.id, d.id


async def main() -> int:
    print("=" * 78)
    print("Workstream service smoke test")
    print("=" * 78)

    async with async_session_factory() as db:
        tenant_id, user_id, dept_id = await _seed_minimal(db)

    async with async_session_factory() as db:
        svc = WorkstreamService(db)

        # 1. start
        ws = await svc.start(
            StartParams(
                tenant_id=tenant_id,
                user_id=user_id,
                department_id=dept_id,
                goal="ship the workstreams console MVP",
                initial_context={"initiator": "smoke-test"},
                next_step_text="wire orchestrator + UI",
            ),
        )
        assert ws.status == WorkstreamStatus.RUNNING, ws.status
        assert ws.escalation_level == WorkstreamEscalationLevel.STANDARD
        print(f"  start          OK  ws_id={ws.id}")

        # 2. illegal transition guard (terminal -> ?)
        try:
            await svc.transition(
                ws.id,
                WorkstreamStatus.WAITING_APPROVAL,
                tenant_id=tenant_id,
                reason="ok-transition",
            )
            print("  transition>WA  OK")
        except WorkstreamTransitionError as exc:
            raise AssertionError(f"unexpected illegal: {exc}") from exc

        # 3. transition WA -> RUNNING (granted)
        ws2 = await svc.transition(
            ws.id, WorkstreamStatus.RUNNING,
            tenant_id=tenant_id, reason="approval granted",
        )
        assert ws2.status == WorkstreamStatus.RUNNING

        # 4. escalate up
        ws3 = await svc.escalate(
            ws.id, tenant_id=tenant_id,
            new_level=WorkstreamEscalationLevel.COUNCIL,
            reason="founder asked for council",
        )
        assert ws3.escalation_level == WorkstreamEscalationLevel.COUNCIL
        print(f"  escalate       OK  level={ws3.escalation_level.value}")

        # 5. redirect with the canonical R3 example
        instr = "pause file edits, ask Council, only produce a migration plan"
        parsed = await parse_redirect(instr)
        # NOTE: under the new LLM-based parser (Council R5, 2026-04-26)
        # this requires a live LLM provider (Gemini Flash / Sonar /
        # Anthropic / OpenAI / Ollama). If no provider is configured in
        # the dev env, the parser surfaces a clarification rather than
        # raising. We tolerate either outcome here so the smoke test
        # works regardless of LLM availability in the dev sandbox.
        if parsed.fully_understood:
            print(f"  parse_redirect OK  actions={len(parsed.actions)}")
        else:
            print(
                f"  parse_redirect SKIPPED (no LLM provider live): "
                f"clarification={parsed.clarifying_question!r}",
            )
        ws4 = await svc.redirect(
            ws.id, tenant_id=tenant_id,
            new_goal=None,
            scope_constraints=[
                a.payload.get("constraint", "")
                for a in parsed.actions
                if a.kind == RedirectActionKind.NARROW_SCOPE
            ],
            raw_instruction=instr,
        )
        assert "scope_constraints" in ws4.context
        print(
            f"  redirect       OK  constraints={ws4.context.get('scope_constraints')}"
        )

        # 6. pause autopilot
        await svc.pause_autopilot(ws.id, tenant_id=tenant_id)

        # 7. complete (terminal)
        ws_done = await svc.complete(
            ws.id, tenant_id=tenant_id,
            summary="migration plan delivered",
            artifact_refs=["doc://plan.md"],
        )
        assert ws_done.status == WorkstreamStatus.COMPLETE

        # 8. illegal transition out of terminal
        try:
            await svc.transition(
                ws.id, WorkstreamStatus.RUNNING,
                tenant_id=tenant_id, reason="should be blocked",
            )
            raise AssertionError("expected illegal-transition error")
        except WorkstreamTransitionError:
            print("  illegal-block  OK  (terminal -> RUNNING refused)")

        # 9. event log
        events = await svc.list_events(ws.id, tenant_id=tenant_id, limit=100)
        kinds = [e.kind for e in events]
        expected_kinds = [
            WorkstreamEventKind.STARTED,
            WorkstreamEventKind.APPROVAL_REQUESTED,
            WorkstreamEventKind.UNBLOCKED,  # WAITING_APPROVAL -> RUNNING
            WorkstreamEventKind.ESCALATED,
            WorkstreamEventKind.REDIRECTED,
            WorkstreamEventKind.PAUSED,
            WorkstreamEventKind.COMPLETED,
        ]
        for k in expected_kinds:
            assert k in kinds, f"missing event kind: {k.value} (got {[x.value for x in kinds]})"
        print(f"  event-log      OK  ({len(events)} events: {[k.value for k in kinds]})")

    print("=" * 78)
    print("ALL OK")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
