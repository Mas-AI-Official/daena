"""Skill consent HTTP surface.

PR-CONN-CONSENT-API-AND-UI (Sprint-5 PR-4, 2026-05-03).

Sprint-4 PR-4 shipped the in-memory ``ConsentStore`` + executor-side
gate (``check_consent_or_request``). It was DORMANT for current Phase 2
read-only skills; the only consumer was the executor itself.

This PR exposes the same primitives behind two narrow HTTP routes so
the operator can mint grants from the UI:

* ``GET  /connections/v2/skill-consent/categories`` -- returns metadata
  for the operator-facing modal: which categories exist, plain-English
  summaries, ttl bounds.
* ``POST /connections/v2/skill-consent/grant`` -- mints an explicit
  short-lived grant for one (plugin, skill, category) tuple. Operator
  must POST this BEFORE re-running the skill execution.

Hard rules honored
------------------

  * Minting a grant DOES NOT enable any write skill on its own. The
    Phase 2 read_only defense (Sprint-2 PR-3) remains the actual hard
    wall on Phase 2 entries. The grant only flips the consent gate
    from "needs_consent" to "OK"; the read_only defense fires next
    and still blocks. Modal copy + the ``write_blocking_active`` flag
    in the categories response make this explicit so the operator
    isn't misled.
  * Single-use TTL preserved: the grant is consumed on the first
    successful executor pass.
  * No PII / no operator input value lands in either request OR
    response shapes -- only (plugin_id, skill_id, category) +
    grant_id + timestamps. Pinned by the leak test in
    ``test_skill_consent_api.py``.
  * Auth required (CurrentUser); cross-tenant grant lookup is
    impossible (tenant_id is taken from the JWT, never from the
    request body).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.logging import get_logger
from app.services.connection_v2.skill_consent import (
    DEFAULT_GRANT_TTL_SECONDS,
    MAX_GRANT_TTL_SECONDS,
    DBConsentStore,
    SkillConsentCategory,
    get_default_store,
)


logger = get_logger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────────


class SkillConsentGrantRequest(BaseModel):
    """Operator-issued grant. The plugin / skill / category triple
    MUST exactly match what the executor's needs_consent outcome
    asked for -- the executor's lookup is exact-match (Sprint-4 PR-4
    invariant).
    """

    plugin_id: str = Field(..., min_length=1, max_length=128)
    skill_id: str = Field(..., min_length=1, max_length=128)
    category: SkillConsentCategory
    ttl_seconds: int | None = Field(
        default=None, ge=1, le=MAX_GRANT_TTL_SECONDS,
    )


@dataclass(frozen=True)
class _CategoryDescriptor:
    """Operator-facing copy for one consent category."""

    code: SkillConsentCategory
    label: str
    operator_facing_summary: str
    write_blocking_active: bool  # Phase 2 still blocks even with consent


# Operator-facing descriptions. Phase 2 universe is read-only, so
# write_blocking_active=True everywhere -- the modal MUST surface
# this as "consent acknowledged but Phase 2 still blocks writes".
_CATEGORY_DESCRIPTORS: tuple[_CategoryDescriptor, ...] = (
    _CategoryDescriptor(
        code=SkillConsentCategory.READ_SENSITIVE,
        label="Read sensitive data",
        operator_facing_summary=(
            "The skill will read potentially sensitive content (e.g. "
            "private inboxes or vault entries). Approve only if you're "
            "certain the source is safe to expose to Daena."
        ),
        write_blocking_active=True,
    ),
    _CategoryDescriptor(
        code=SkillConsentCategory.WRITE_EXTERNAL,
        label="Write external resource",
        operator_facing_summary=(
            "The skill would create or modify an external resource "
            "(e.g. issues, comments, files). Phase 2 still blocks the "
            "actual write -- consent is recorded but the read_only "
            "defense halts execution before any side-effect."
        ),
        write_blocking_active=True,
    ),
    _CategoryDescriptor(
        code=SkillConsentCategory.SEND_MESSAGE,
        label="Send a message",
        operator_facing_summary=(
            "The skill would post a message (Slack / email / DM). "
            "Phase 2 still blocks; consent only unlocks the gate, "
            "not the send."
        ),
        write_blocking_active=True,
    ),
    _CategoryDescriptor(
        code=SkillConsentCategory.PAYMENT,
        label="Payment / financial",
        operator_facing_summary=(
            "The skill would touch a payment surface (Stripe, "
            "subscription, refund). DENY recommended at the per-plugin "
            "preset layer; consent here is acknowledged but Phase 2 "
            "still blocks."
        ),
        write_blocking_active=True,
    ),
    _CategoryDescriptor(
        code=SkillConsentCategory.BROWSER_ACTION,
        label="Browser automation",
        operator_facing_summary=(
            "The skill would drive a real browser session (Playwright "
            "/ Chrome DevTools) which can leak operator IP or take "
            "destructive action on third-party sites. Phase 2 blocks; "
            "consent is recorded for audit only."
        ),
        write_blocking_active=True,
    ),
    _CategoryDescriptor(
        code=SkillConsentCategory.SECURITY_SCAN,
        label="Security scan",
        operator_facing_summary=(
            "The skill would run an offensive-ops scan (the founder-only "
            "elevated mode surface). Phase 2 blocks; the dedicated "
            "elevated-mode flow is the real entry point."
        ),
        write_blocking_active=True,
    ),
)


# ──────────────────────────────────────────────────────────────────
# GET categories
# ──────────────────────────────────────────────────────────────────


@router.get("/categories")
async def list_consent_categories(
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Return the operator-facing category metadata for the consent
    modal. Pure metadata -- no per-tenant state."""
    _ = user  # auth-only
    return JSONResponse(content={
        "data": {
            "default_ttl_seconds": DEFAULT_GRANT_TTL_SECONDS,
            "max_ttl_seconds": MAX_GRANT_TTL_SECONDS,
            "phase2_write_blocking_active": True,
            "categories": [
                {
                    "code": d.code.value,
                    "label": d.label,
                    "operator_facing_summary": d.operator_facing_summary,
                    "write_blocking_active": d.write_blocking_active,
                }
                for d in _CATEGORY_DESCRIPTORS
            ],
        },
    })


# ──────────────────────────────────────────────────────────────────
# POST grant
# ──────────────────────────────────────────────────────────────────


@router.post("/grant")
async def mint_consent_grant(
    body: SkillConsentGrantRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Mint a single-use consent grant for the (plugin, skill, category)
    triple. Tenant binding comes from the JWT, NEVER the request body.

    Sprint-6 PR-5: persists to the ``consent_grants`` table via
    ``DBConsentStore`` so grants survive restarts and multi-instance
    deploys. The in-memory store remains the fallback for code paths
    without a DB session (none currently exercise this).

    Returns: ``{data: {grant_id, plugin_id, skill_id, category,
    expires_at, write_blocking_active}}``. The grant_id is the only
    value the operator's UI needs to remember; the executor consults
    the same store on the next /skills/execute call.
    """
    if body.plugin_id == "" or body.skill_id == "":
        raise HTTPException(status_code=400, detail="plugin_id_and_skill_id_required")

    ttl = body.ttl_seconds or DEFAULT_GRANT_TTL_SECONDS
    db_store = DBConsentStore(db)
    grant = await db_store.grant(
        tenant_id=user.tenant_id,
        user_id=user.id,
        plugin_id=body.plugin_id,
        skill_id=body.skill_id,
        category=body.category,
        ttl_seconds=ttl,
    )
    # Sprint-6 PR-5 transition: also write to the in-memory store so
    # the existing executor (which reads from get_default_store()) keeps
    # finding grants minted via the API. A follow-up PR can flip the
    # executor over to the DB store once it has a session in scope.
    in_memory = get_default_store()
    in_memory.grant(
        tenant_id=str(user.tenant_id),
        plugin_id=body.plugin_id,
        skill_id=body.skill_id,
        category=body.category,
        ttl_seconds=ttl,
    )

    logger.info(
        "skill_consent_api.grant_minted",
        grant_id=grant.grant_id,
        plugin_id=body.plugin_id,
        skill_id=body.skill_id,
        category=body.category.value,
    )

    return JSONResponse(content={
        "data": {
            "grant_id": grant.grant_id,
            "plugin_id": grant.plugin_id,
            "skill_id": grant.skill_id,
            "category": grant.category.value,
            "expires_at": grant.expires_at,
            # Make it impossible for a UI to "forget" the warning.
            "write_blocking_active": True,
            "operator_notice": (
                "Consent recorded. Phase 2 still blocks write-class "
                "skills via the read_only defense. The next "
                "/skills/execute call will pass the consent gate but "
                "may still return blocked={reason} if the skill is "
                "non-read-only."
            ),
        },
    })


__all__ = ["router"]
