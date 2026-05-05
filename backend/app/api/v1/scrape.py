"""ScrapeGraphAI governed read-only API.

PR-SCRAPEGRAPH-GOVERNED-READONLY-SKILL (Sprint-10 PR-2, 2026-05-05).

Single endpoint:

  POST /api/v1/scrape/extract

Spawns the venv_daena worker via ``app.services.scrape``, returns
the extracted text capped at ``max_chars``. Every call writes a
``plugin.skill_invocation`` audit row carrying:

  * skill_id = ``scrapegraph.extract_from_url``
  * outcome = success | url_safety_block | worker_failed | worker_timeout
  * url_host (NEVER the full URL with query/fragment)
  * goal_length (chars)
  * result_length (chars)
  * truncated (bool)

Hard rules enforced here:
  * FOUNDER role only (this is a powerful primitive that can hit any
    public URL; we do not let lower roles trigger arbitrary fetches).
  * URL safety guard re-uses the same check the mcp-fetch precall
    validator uses -- one source of truth.
  * Output cap: defaults to 8000 chars, hard ceiling 32000.
  * No retries on the API path. The worker is expensive; the operator
    re-runs deliberately.
  * No URL value in audit row -- only the host.
"""

from __future__ import annotations

from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.audit import AuditService
from app.services.scrape import (
    ExtractResult,
    ScrapeError,
    extract_from_url,
)


logger = get_logger(__name__)
router = APIRouter()


class ScrapeExtractRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    goal: str = Field(..., min_length=1, max_length=2000)
    max_chars: int = Field(default=8000, ge=100, le=32000)


class ScrapeExtractResponse(BaseModel):
    success: bool
    result: str
    truncated: bool
    error: str | None
    worker_version: str
    audit_event_id: str


def _safe_host(url: str) -> str:
    """Return scheme://host[:port] with the path/query/fragment stripped.

    Used for logs + audit rows. Never carries query string (which
    could contain operator-typed search terms or tokens)."""
    try:
        parts = urlsplit(url)
        host = parts.hostname or "?"
        port = f":{parts.port}" if parts.port else ""
        return f"{(parts.scheme or 'http').lower()}://{host}{port}"
    except Exception:
        return "?"


@router.post("/extract", response_model=ScrapeExtractResponse)
async def post_scrape_extract(
    body: ScrapeExtractRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> ScrapeExtractResponse:
    audit = AuditService(db)
    safe_host = _safe_host(body.url)

    try:
        outcome: ExtractResult = await extract_from_url(
            body.url, body.goal, max_chars=body.max_chars,
        )
    except ScrapeError as exc:
        # url_safety / spawn / venv_missing -- structured failure.
        rec = await audit.log_decision(
            tenant_id=user.tenant_id,
            actor_id=user.id,
            actor_type="USER",
            action_type="plugin.skill_invocation",
            action_params={
                "plugin_id": "internal-scrape",
                "skill_id": "extract_from_url",
                "phase": "phase2_readonly",
                "outcome": "blocked",
                "blocked_reason": str(exc),
                "url_host": safe_host,
                "goal_length": len(body.goal),
            },
            result="BLOCKED",
            risk_level="LOW",
            governance_tier=2,
        )
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail={
                "code": str(exc).split(":", 1)[0],
                "message": str(exc),
                "audit_event_id": str(rec.get("id") or ""),
            },
        )

    rec = await audit.log_decision(
        tenant_id=user.tenant_id,
        actor_id=user.id,
        actor_type="USER",
        action_type="plugin.skill_invocation",
        action_params={
            "plugin_id": "internal-scrape",
            "skill_id": "extract_from_url",
            "phase": "phase2_readonly",
            "outcome": "executed" if outcome.success else "worker_failed",
            "url_host": safe_host,
            "goal_length": len(body.goal),
            "result_length": len(outcome.result),
            "truncated": bool(outcome.truncated),
            "worker_version": outcome.worker_version,
            # NEVER carry the raw URL value, the goal, or the result body.
            "blocked_reason": outcome.error or "",
        },
        result="ALLOWED" if outcome.success else "BLOCKED",
        risk_level="LOW",
        governance_tier=2,
    )
    await db.commit()

    logger.info(
        "scrape.extract.completed",
        success=outcome.success,
        truncated=outcome.truncated,
        result_length=len(outcome.result),
        url_host=safe_host,
        # NEVER log the full URL, goal text, or result body.
    )

    return ScrapeExtractResponse(
        success=outcome.success,
        result=outcome.result,
        truncated=outcome.truncated,
        error=outcome.error,
        worker_version=outcome.worker_version,
        audit_event_id=str(rec.get("id") or ""),
    )
