"""Safe runtime-error sink (DEP-007).

``record_error_event`` persists one ErrorEvent row for post-hoc founder
review. It is BEST-EFFORT and MUST NEVER raise into its caller: it runs
on paths that are already failing (the catch-all exception handler, the
SSE fallback-exhausted branch), so a failure to record must degrade
silently (log + swallow), never turn a handled 500 into an unhandled one.

It opens a FRESH DB session via async_session_factory rather than reusing
the request session, which may already be in a rolled-back / unusable
state when the error fired.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_MAX_MSG = 2000  # cap to keep rows small + avoid accidental blob storage


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except (ValueError, AttributeError):
            return None
    return None


async def record_error_event(
    *,
    source: str,
    severity: str = "error",
    route: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
    error_code: str | None = None,
    error_type: str | None = None,
    safe_message: str | None = None,
    request_id: str | None = None,
    user_id: Any = None,
    tenant_id: Any = None,
    run_id: str | None = None,
    provider: str | None = None,
    metadata_json: dict | None = None,
) -> None:
    """Persist one safe ErrorEvent. Never raises.

    Callers pass ONLY safe values: error_type is the exception class name
    (not its message), safe_message is the generic user-facing text. Do
    NOT pass secrets, tokens, raw exception strings, or request bodies.
    """
    try:
        from app.core.database import async_session_factory
        from app.models.error_event import ErrorEvent

        row = ErrorEvent(
            source=str(source)[:64],
            severity=str(severity)[:16],
            route=(route or None) and str(route)[:256],
            method=(method or None) and str(method)[:8],
            status_code=status_code,
            error_code=(error_code or None) and str(error_code)[:64],
            error_type=(error_type or None) and str(error_type)[:128],
            safe_message=(safe_message or None) and str(safe_message)[:_MAX_MSG],
            request_id=(request_id or None) and str(request_id)[:64],
            user_id=_coerce_uuid(user_id),
            tenant_id=_coerce_uuid(tenant_id),
            run_id=(run_id or None) and str(run_id)[:64],
            provider=(provider or None) and str(provider)[:32],
            metadata_json=metadata_json if isinstance(metadata_json, dict) else None,
        )
        async with async_session_factory() as session:
            session.add(row)
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - best-effort; never propagate
        # Last-resort: log and swallow. The error we were trying to record
        # is already in the structured logs via the caller's logger.
        logger.warning("error_sink.record_failed", error=str(exc), source=source)
