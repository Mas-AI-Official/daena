"""Send rate limit -- Sprint-19 PR-5 (2026-05-06).

Persistent per-day send counter, JSON file at
``backend/.send_rate_limit.json`` (gitignored).

Default cap: 3 sends / day per tenant. Configurable via
``DAENA_SEND_RATE_LIMIT_PER_DAY`` env var (founder-set);
NEVER raised programmatically by Daena's runtime.

The rate limit is INDEPENDENT of trust ladder. Even if all 6
trust walls passed, even if both approvals are signed, this gate
can still refuse send. This is defense in depth: each gate
checks a DIFFERENT invariant.

Hard rules:

  * Counter is per-tenant, per-UTC-date.
  * Counter increments BEFORE send is attempted (so a failed
    send still counts -- the wall is "sends attempted today",
    not "sends successful today"). This prevents retry storms
    from silently bypassing the cap.
  * Counter NEVER decrements. A send rolls into the next day's
    quota only when the day rolls over.
  * Concurrent calls may race. Best-effort consistency only;
    the file write is the source of truth. For the founder's
    single-process install, races are rare and acceptable.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_STATE_FILE = Path(__file__).resolve().parents[3] / ".send_rate_limit.json"
_DEFAULT_CAP_PER_DAY: int = 3


@dataclass
class RateLimitDecision:
    allowed: bool
    today: str  # YYYY-MM-DD UTC
    used: int
    cap: int
    reason: str | None = None


def _today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _read_state() -> dict:
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("send_rate_limit.read_failed", error=str(exc))
        return {}


def _write_state(data: dict) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps(data, indent=2), encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("send_rate_limit.write_failed", error=str(exc))


def get_cap_per_day() -> int:
    """Read cap from env or fall back to default. Founder-set only;
    Daena's runtime cannot mutate this."""
    raw = os.environ.get("DAENA_SEND_RATE_LIMIT_PER_DAY")
    if raw:
        try:
            v = int(raw)
            if v >= 0:
                return v
        except ValueError:
            pass
    return _DEFAULT_CAP_PER_DAY


def _key(tenant_id: uuid.UUID, day: str) -> str:
    return f"{tenant_id}::{day}"


def get_usage(tenant_id: uuid.UUID, *, day: str | None = None) -> int:
    """How many sends has this tenant attempted on ``day``? Defaults
    to today UTC."""
    state = _read_state()
    return int(state.get(_key(tenant_id, day or _today_utc()), 0))


def check_and_increment(tenant_id: uuid.UUID) -> RateLimitDecision:
    """Atomically (best-effort) check + increment.

    Returns RateLimitDecision; if ``allowed=False``, the counter is
    NOT incremented. If ``allowed=True``, the counter IS incremented
    and the file IS written before this function returns.

    NEVER raises.
    """
    today = _today_utc()
    cap = get_cap_per_day()
    state = _read_state()
    k = _key(tenant_id, today)
    used = int(state.get(k, 0))

    if used >= cap:
        return RateLimitDecision(
            allowed=False, today=today, used=used, cap=cap,
            reason="rate_limit_exceeded",
        )

    state[k] = used + 1
    _write_state(state)
    return RateLimitDecision(
        allowed=True, today=today, used=used + 1, cap=cap,
    )


def _reset_for_tests() -> None:
    if _STATE_FILE.exists():
        try:
            _STATE_FILE.unlink()
        except OSError:
            pass
