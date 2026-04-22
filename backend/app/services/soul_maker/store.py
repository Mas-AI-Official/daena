"""Proposal store for soul refinements (founder-gated promotion).

A refinement run produces a pending proposal, not a live update. This
module persists proposals to disk (JSON files under var/soul_proposals/)
and exposes list / get / approve / reject for the REST API.

**Approval = the only write path to the live soul file.** This is the T3
promotion gate per Daena's governance rules -- no runtime, heartbeat, or
auto-refiner can overwrite a soul. Only an explicit founder action can.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.soul_engine import (
    SoulEngine,
    _DEPARTMENT_SOUL_PATH,
    _load_department_soul,
)

logger = get_logger(__name__)


def _proposals_dir() -> Path:
    """Resolve the proposals directory, creating it if needed.

    Respects ``SOUL_PROPOSALS_DIR`` env if set, otherwise uses the
    repo's ``backend/var/soul_proposals/`` convention that matches how
    other artifacts (scan reports, skill store) are persisted.
    """
    override = os.getenv("SOUL_PROPOSALS_DIR")
    if override:
        base = Path(override)
    else:
        # backend/app/services/soul_maker/store.py -> backend/var/soul_proposals
        base = Path(__file__).resolve().parents[3] / "var" / "soul_proposals"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_proposal(
    *,
    slug: str,
    mind_name: str,
    original_body: str,
    proposed_body: str,
    gap_report: dict[str, Any],
    improvement_notes: list[str],
    critic_report: dict[str, Any],
    evidence_sources: list[dict[str, Any]],
    confidence: float,
    verdict: str,
) -> str:
    """Persist a pending proposal. Returns the proposal id.

    Proposals are immutable once saved; approve / reject only updates
    their status field, never their body. This gives a founder a clean
    audit trail of every refinement decision.
    """
    proposal_id = str(uuid.uuid4())
    record = {
        "id": proposal_id,
        "slug": slug,
        "mind_name": mind_name,
        "status": "pending",
        "verdict": verdict,
        "confidence": confidence,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "decided_at": None,
        "decided_by": None,
        "decision_notes": None,
        "original_body": original_body,
        "proposed_body": proposed_body,
        "gap_report": gap_report,
        "improvement_notes": improvement_notes,
        "critic_report": critic_report,
        "evidence_sources": evidence_sources,
    }
    path = _proposals_dir() / f"{proposal_id}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    logger.info("soul_maker.proposal_saved", id=proposal_id, slug=slug, verdict=verdict)
    return proposal_id


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    """Fetch one proposal by id."""
    path = _proposals_dir() / f"{proposal_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("soul_maker.proposal_corrupt", id=proposal_id, error=str(exc))
        return None


def list_proposals(
    *,
    slug: str | None = None,
    status: str | None = "pending",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List proposals, optionally filtered by department or status.

    Newest-first. Default filters to ``pending`` so the UI shows only
    actionable proposals; pass ``status=None`` for the full history.
    """
    records: list[dict[str, Any]] = []
    for path in _proposals_dir().glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if slug and rec.get("slug") != slug:
            continue
        if status and rec.get("status") != status:
            continue
        records.append(rec)
    records.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return records[:limit]


def _update_status(
    proposal_id: str,
    *,
    new_status: str,
    decided_by: str,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Internal: flip status + attach decision metadata."""
    rec = get_proposal(proposal_id)
    if rec is None:
        return None
    if rec.get("status") != "pending":
        logger.warning(
            "soul_maker.proposal_already_decided",
            id=proposal_id,
            status=rec.get("status"),
        )
        return rec
    rec["status"] = new_status
    rec["decided_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    rec["decided_by"] = decided_by
    rec["decision_notes"] = notes
    path = _proposals_dir() / f"{proposal_id}.json"
    path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def approve_proposal(
    proposal_id: str,
    *,
    decided_by: str,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Promote a pending proposal to the live soul file.

    Writes the new body to ``backend/app/soul/departments/<slug>.md``,
    preserving the original frontmatter block. Reloads the SoulEngine
    cache so the next chat request picks up the refined soul.

    Only callers with FOUNDER tier should invoke this -- the REST
    endpoint enforces that gate. Returns the updated proposal record.
    """
    rec = get_proposal(proposal_id)
    if rec is None or rec.get("status") != "pending":
        return _update_status(
            proposal_id,
            new_status="error",
            decided_by=decided_by,
            notes="already_decided_or_missing",
        )

    slug = rec["slug"]
    target = _DEPARTMENT_SOUL_PATH / f"{slug}.md"
    if not target.exists():
        logger.error("soul_maker.live_file_missing", slug=slug, path=str(target))
        return _update_status(
            proposal_id,
            new_status="error",
            decided_by=decided_by,
            notes=f"live_soul_file_missing:{target}",
        )

    # Preserve frontmatter, replace only the body below the second ``---``.
    original_file = target.read_text(encoding="utf-8")
    if original_file.startswith("---"):
        parts = original_file.split("---", 2)
        if len(parts) >= 3:
            frontmatter = f"---{parts[1]}---\n\n"
            new_file = frontmatter + rec["proposed_body"].lstrip() + "\n"
        else:
            new_file = rec["proposed_body"]
    else:
        new_file = rec["proposed_body"]

    target.write_text(new_file, encoding="utf-8")
    SoulEngine.reload()
    # Verify the reload picked up the change -- if the file became
    # unreadable somehow, surface that in the decision notes.
    _, reloaded_body = _load_department_soul(slug)
    verified = bool(reloaded_body and rec["proposed_body"].strip()[:80] in reloaded_body)

    updated = _update_status(
        proposal_id,
        new_status="approved" if verified else "approved_unverified",
        decided_by=decided_by,
        notes=notes,
    )
    logger.info(
        "soul_maker.proposal_approved",
        id=proposal_id,
        slug=slug,
        verified=verified,
        decided_by=decided_by,
    )
    return updated


def reject_proposal(
    proposal_id: str,
    *,
    decided_by: str,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Mark a proposal rejected. Never touches the live soul file."""
    updated = _update_status(
        proposal_id,
        new_status="rejected",
        decided_by=decided_by,
        notes=notes,
    )
    if updated is not None:
        logger.info(
            "soul_maker.proposal_rejected",
            id=proposal_id,
            decided_by=decided_by,
        )
    return updated
