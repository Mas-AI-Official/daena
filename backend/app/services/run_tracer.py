"""Local run tracer -- safe, fail-open chat-run spans (benchmark adopt).

``record_trace_event`` persists one RunTraceEvent row per pipeline step so the
founder/operator gets OpenAI-Agents-SDK-style run visibility WITHOUT an external
telemetry SaaS. Like error_sink it is BEST-EFFORT and MUST NEVER raise into its
caller (it runs on the hot chat path): a failure to record degrades silently.

Gated by the TRACE_ENABLED env flag (default OFF), read ONCE at import so the
hot path only checks a module-global bool. When off, record_trace_event returns
immediately -- no DB hit, no cost. Opens a FRESH async_session_factory session.

SAFE ONLY: callers pass redacted values. As defense in depth the recorder caps
long strings and strips secret-looking keys from metadata before storage. Never
store prompts, responses, system prompts, request bodies, credentials, or raw
provider error text.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Read once at import: the hot path checks a bool, not the environment.
_TRACE_ENABLED = os.getenv("TRACE_ENABLED", "false").strip().lower() in (
    "1", "true", "yes", "on",
)

_MAX_SUMMARY = 500  # cap so a span row stays small
_MAX_VAL = 200      # cap per metadata value
# Keys whose VALUES must never be persisted even if a caller slips up.
_DENY_SUBSTR = (
    "key", "secret", "token", "password", "passwd", "authorization", "auth",
    "credential", "cred", "prompt", "body", "content", "message", "response",
    "cookie", "session_token", "bearer",
)


def is_enabled() -> bool:
    """Whether tracing is on (module-global, set once at import)."""
    return _TRACE_ENABLED


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except (ValueError, AttributeError):
            return None
    return None


def _safe_metadata(meta: Any) -> dict | None:
    """Drop secret-looking keys and cap value sizes. Defense in depth."""
    if not isinstance(meta, dict):
        return None
    out: dict[str, Any] = {}
    for k, v in meta.items():
        key = str(k)
        if any(s in key.lower() for s in _DENY_SUBSTR):
            continue  # never persist a value under a secret-looking key
        if isinstance(v, str):
            out[key] = v[:_MAX_VAL]
        elif isinstance(v, (int, float, bool)) or v is None:
            out[key] = v
        else:
            out[key] = str(v)[:_MAX_VAL]
    return out or None


async def record_trace_event(
    *,
    event_type: str,
    request_id: str | None = None,
    run_id: str | None = None,
    session_id: Any = None,
    tenant_id: Any = None,
    user_id: Any = None,
    stage: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    governance_mode: str | None = None,
    status: str = "ok",
    safe_summary: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Persist one safe RunTraceEvent. No-op when TRACE_ENABLED is off. Never raises."""
    if not _TRACE_ENABLED:
        return
    try:
        from app.core.database import async_session_factory
        from app.models.run_trace_event import RunTraceEvent

        row = RunTraceEvent(
            event_type=str(event_type)[:48],
            request_id=(request_id or None) and str(request_id)[:64],
            run_id=(run_id or None) and str(run_id)[:64],
            session_id=_coerce_uuid(session_id),
            tenant_id=_coerce_uuid(tenant_id),
            user_id=_coerce_uuid(user_id),
            stage=(stage or None) and str(stage)[:48],
            provider=(provider or None) and str(provider)[:32],
            model=(model or None) and str(model)[:96],
            governance_mode=(governance_mode or None) and str(governance_mode)[:24],
            status=str(status)[:16],
            safe_summary=(safe_summary or None) and str(safe_summary)[:_MAX_SUMMARY],
            metadata_json=_safe_metadata(metadata),
        )
        async with async_session_factory() as session:
            session.add(row)
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - best-effort; never propagate into chat
        logger.warning("run_tracer.record_failed", error=str(exc), event_type=event_type)
