"""Smoke/integration test for the shared-brain write -> promote -> recall loop.

Phase 3 item 7 (Doc/DAENA_VP_UPGRADE_PLAN_20260701.md, G1): VERIFY -- do NOT
rebuild -- the experience write-back loop that
``chat.py:_run_memory_writeback`` drives as a background task after every chat
turn. This test pins the full contract end to end so a silent regression in any
of the three legs fails loudly in CI. It guards Daena Rule 14 (keep the
chat_orchestrator memory enrichment extendable) by proving the recall leg the
orchestrator's Stage 6 depends on still gates strictly on trust.

Three legs under test (backend/app/services/memory.py):
  1. store_experience(...) -> auto-quarantine (is_quarantined=True, trust 0.0)
  2. validate_quarantined(...) -> single-success trust bump (+0.1 per pass),
     promotes when trust_score >= TRUST_PROMOTE_THRESHOLD (0.7)
  3. recall_experiences(...) -> returns ONLY promoted experiences
     (is_quarantined=False AND trust_score >= 0.7)

Promotion-path note: store()'s CAS dedup collapses identical content to a
single row, so the "3+ identical siblings -> trust 0.8" fast path is
unreachable via store_experience alone. The reachable, deterministic public
path is the single-success +0.1 bump, iterated until trust crosses 0.7. The
loop below is bounded and float-rounding tolerant on purpose: it asserts
"promotes within N validations", not "exactly 7 validations".
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.memory import MemoryEntry
from app.services.memory import MemoryService, TRUST_PROMOTE_THRESHOLD

# Bound for the promotion loop. Single-success bumps trust by +0.1 from 0.0, so
# ~7 validations reach 0.7; 15 leaves generous headroom for float rounding
# without ever masking a real regression (an un-promotable entry still fails).
_MAX_VALIDATIONS = 15


@pytest.mark.asyncio
async def test_writeback_full_loop_store_promote_recall(
    db_session,
    seed_auth_principal,
) -> None:
    """store_experience -> validate_quarantined -> recall_experiences round trip.

    Asserts the quarantine gate holds on write, that repeated single-success
    validation promotes the experience, and that recall only surfaces it once
    promoted.
    """
    tenant_id = seed_auth_principal["tenant_id"]
    user_id = seed_auth_principal["user_id"]
    mem = MemoryService(db_session)

    # ── Leg 1: store an agent experience -> must land quarantined at trust 0.0
    stored = await mem.store_experience(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=user_id,  # matches _run_memory_writeback: agent_id=uid
        content="Chose model gemini-flash for the governance summary; founder accepted the draft.",
        content_type="AGENT_DECISION",
        summary="model-choice-governance",
        success_flag=True,
        confidence=0.6,
        tags=["writeback", "smoke"],
    )
    entry_id = uuid.UUID(stored["id"])

    row = (
        await db_session.execute(
            select(MemoryEntry).where(MemoryEntry.id == entry_id)
        )
    ).scalar_one()
    assert row.is_quarantined is True, "new experience must be quarantined (L2Q)"
    assert row.trust_score == 0.0, "quarantined experience must start at trust 0.0"
    assert row.content_type == "AGENT_DECISION"

    # ── Negative leg: a quarantined experience is invisible to recall
    recalled = await mem.recall_experiences(tenant_id=tenant_id)
    assert not any(r["id"] == stored["id"] for r in recalled), (
        "recall_experiences must NOT return quarantined (unpromoted) experiences"
    )

    # ── Leg 2: drive promotion via repeated single-success validation
    validations = 0
    promoted = False
    for _ in range(_MAX_VALIDATIONS):
        validations += 1
        await mem.validate_quarantined(tenant_id=tenant_id)
        recalled = await mem.recall_experiences(tenant_id=tenant_id)
        if any(r["id"] == stored["id"] for r in recalled):
            promoted = True
            break

    assert promoted, (
        "experience never promoted after "
        f"{_MAX_VALIDATIONS} single-success validations"
    )
    # First validation only bumps trust to 0.1 (< 0.7), so promotion MUST take
    # more than one pass. If it promoted on pass 1 the quarantine gate is broken.
    assert validations > 1, (
        "experience promoted on first validation -- quarantine trust gate not enforced"
    )

    # ── Leg 3: promoted state is persisted correctly
    row = (
        await db_session.execute(
            select(MemoryEntry).where(MemoryEntry.id == entry_id)
        )
    ).scalar_one()
    assert row.is_quarantined is False, "promoted experience must leave quarantine"
    assert row.trust_score >= TRUST_PROMOTE_THRESHOLD, (
        "promoted experience must meet the trust threshold"
    )


@pytest.mark.asyncio
async def test_recall_returns_promoted_only(
    db_session,
    seed_auth_principal,
) -> None:
    """recall surfaces the promoted experience while an unvalidated one stays hidden.

    Control B has success_flag=None, so validate_quarantined never advances it
    (neither the sibling nor the single-success branch fires). This isolates the
    "promoted-only" filter: A crosses the trust threshold, B never does.
    """
    tenant_id = seed_auth_principal["tenant_id"]
    user_id = seed_auth_principal["user_id"]
    mem = MemoryService(db_session)

    exp_a = await mem.store_experience(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=user_id,
        content="Retry with exponential backoff resolved the flaky provider timeout.",
        content_type="SKILL_OUTCOME",
        summary="retry-backoff-works",
        success_flag=True,
        tags=["skill", "smoke"],
    )
    exp_b = await mem.store_experience(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=user_id,
        content="Considered switching the vector store but reached no conclusion this turn.",
        content_type="AGENT_DECISION",
        summary="undecided-vector-store",
        success_flag=None,  # never advances -> permanent quarantine control
        tags=["decision", "smoke"],
    )

    # Drive A to promotion; B rides along through the same batches unchanged.
    for _ in range(_MAX_VALIDATIONS):
        await mem.validate_quarantined(tenant_id=tenant_id)
        recalled = await mem.recall_experiences(tenant_id=tenant_id)
        if any(r["id"] == exp_a["id"] for r in recalled):
            break

    recalled_ids = {r["id"] for r in recalled}
    assert exp_a["id"] in recalled_ids, "promoted experience A must be recallable"
    assert exp_b["id"] not in recalled_ids, (
        "unvalidated experience B (success_flag=None) must stay quarantined"
    )

    # Confirm B is genuinely still quarantined in the DB, not merely out-ranked.
    row_b = (
        await db_session.execute(
            select(MemoryEntry).where(MemoryEntry.id == uuid.UUID(exp_b["id"]))
        )
    ).scalar_one()
    assert row_b.is_quarantined is True
    assert row_b.trust_score < TRUST_PROMOTE_THRESHOLD
