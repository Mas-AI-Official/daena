"""Trust Ladder Foundation -- Sprint-14 PR-5 (2026-05-06).

Records approval / rejection history per (tool_id, template_id)
pair. PR-5 is record-only -- a future sprint reads these counters
to graduate trust (e.g. auto-approve a Gmail draft template after
N successful approvals with zero rejections in M days).

PR-5 deliberately does NOT:

* Auto-execute anything.
* Reduce approval friction.
* Skip a gate based on history.

The module is the foundation those follow-up flows read from.

Persistence: JSON file at ``backend/.trust_ladder.json`` (gitignored).
Single-file is fine for the founder install. Multi-tenant cloud
will move this to a DB table; migration is a future concern.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

_LADDER_FILE = Path(__file__).resolve().parents[2] / ".trust_ladder.json"


Decision = Literal["approved", "rejected"]


# Future trust tiers. PR-5 stores them as opaque strings -- consumers
# define what each tier means.
DEFAULT_MAX_AUTO_TIER: str = "none"


@dataclass
class TrustLadderEntry:
    """Per (tool_id, template_id) ledger row."""

    tool_id: str
    template_id: str
    approvals_count: int = 0
    rejection_count: int = 0
    last_approved_at: str | None = None
    last_rejected_at: str | None = None
    # Operator can manually raise this for a tool/template pair the
    # they trust. PR-5 never raises it automatically.
    max_auto_tier: str = DEFAULT_MAX_AUTO_TIER

    @property
    def key(self) -> str:
        return f"{self.tool_id}::{self.template_id}"


def _read_all() -> dict[str, TrustLadderEntry]:
    if not _LADDER_FILE.exists():
        return {}
    try:
        raw = json.loads(_LADDER_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("trust_ladder.read_failed", error=str(exc))
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, TrustLadderEntry] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        try:
            entry = TrustLadderEntry(
                tool_id=str(val.get("tool_id", "")),
                template_id=str(val.get("template_id", "")),
                approvals_count=int(val.get("approvals_count", 0)),
                rejection_count=int(val.get("rejection_count", 0)),
                last_approved_at=val.get("last_approved_at"),
                last_rejected_at=val.get("last_rejected_at"),
                max_auto_tier=str(
                    val.get("max_auto_tier", DEFAULT_MAX_AUTO_TIER),
                ),
            )
            out[entry.key] = entry
        except (TypeError, ValueError) as exc:
            logger.warning("trust_ladder.entry_skip", key=key, error=str(exc))
    return out


def _write_all(entries: dict[str, TrustLadderEntry]) -> None:
    payload = {k: asdict(v) for k, v in entries.items()}
    try:
        _LADDER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LADDER_FILE.write_text(
            json.dumps(payload, indent=2), encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("trust_ladder.write_failed", error=str(exc))


def record_decision(
    *,
    tool_id: str,
    template_id: str,
    decision: Decision,
) -> TrustLadderEntry:
    """Record one approval / rejection. Returns the updated entry.

    Idempotent across process boundaries -- the JSON file is the
    source of truth; concurrent writers may overwrite each other,
    but the worst case is a lost update, not a corrupt ladder.
    For founder-install single-process this is acceptable.
    """
    if tool_id is None or template_id is None:
        raise ValueError("tool_id and template_id are required")
    if decision not in ("approved", "rejected"):
        raise ValueError(
            f"decision={decision!r}; expected 'approved' or 'rejected'"
        )

    entries = _read_all()
    key = f"{tool_id}::{template_id}"
    entry = entries.get(key) or TrustLadderEntry(
        tool_id=tool_id, template_id=template_id,
    )
    now_iso = datetime.now(UTC).isoformat()
    if decision == "approved":
        entry.approvals_count += 1
        entry.last_approved_at = now_iso
    else:
        entry.rejection_count += 1
        entry.last_rejected_at = now_iso
    entries[key] = entry
    _write_all(entries)

    logger.info(
        "trust_ladder.decision_recorded",
        tool_id=tool_id,
        template_id=template_id,
        decision=decision,
        approvals_count=entry.approvals_count,
        rejection_count=entry.rejection_count,
    )
    return entry


def get_entry(
    *, tool_id: str, template_id: str,
) -> TrustLadderEntry | None:
    return _read_all().get(f"{tool_id}::{template_id}")


def list_entries() -> list[TrustLadderEntry]:
    return list(_read_all().values())


# ─────────────────────────────────────────────────────────────────────
# Test helper: explicit reset. Only used by tests.
# ─────────────────────────────────────────────────────────────────────


def _reset_for_tests() -> None:
    if _LADDER_FILE.exists():
        try:
            _LADDER_FILE.unlink()
        except OSError:
            pass
