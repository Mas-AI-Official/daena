"""Guard tests for the workstream list pagination bounds (Phase-12 hardening).

Both ``GET /workstreams`` (``list_workstreams``) and
``GET /workstreams/{id}/events`` (``list_workstream_events``) previously
declared a bare ``limit: int = N``. The handlers clamped only the upper
side via ``min(limit, N)``, so a *negative* ``?limit=-1`` slipped through to
``WorkstreamService.list_for_tenant`` / ``list_events`` and reached
``.limit(-1)`` -- which in SQLite means "no limit" (returns every owned
row) and in PostgreSQL raises (500). Every sibling list endpoint bounds its
limit declaratively via ``Query(default, ge=..., le=...)`` (house
convention, e.g. ``projects.py``/``pipeline.py``/``research.py``), which
makes FastAPI reject out-of-range values with a 422 before the handler
runs. These tests pin that both workstream endpoints now match it.

Pure introspection -- no DB, auth, or network -- so they run under the
deterministic Rule-10 oracle. They discriminate the fix: before it the
default was a bare ``int`` with no constraint metadata, so the
``isinstance(..., params.Query)`` assertion fails RED.
"""

from __future__ import annotations

import inspect

from fastapi import params

from app.api.v1.workstreams import list_workstream_events, list_workstreams


def _limit_default(handler):
    return inspect.signature(handler).parameters["limit"].default


def _constraint(metadata, name):
    """Return the numeric value of the first annotated_types constraint of
    ``name`` (e.g. 'Ge'/'Le') found in a FieldInfo metadata list, else None.
    """
    for m in metadata:
        if type(m).__name__ == name:
            # annotated_types.Ge stores .ge, Le stores .le
            return getattr(m, name.lower(), None)
    return None


def test_list_workstreams_limit_uses_query():
    """``list_workstreams`` limit must be a FastAPI Query, not a bare int,
    so FastAPI enforces the range before the handler runs."""
    default = _limit_default(list_workstreams)
    assert isinstance(default, params.Query), (
        "workstreams list `limit` must be declared as Query(...) so the "
        "bound is enforced; got a bare default instead"
    )


def test_list_workstreams_limit_is_bounded():
    """``list_workstreams`` limit must declare ge=1 and le=200, matching the
    handler's existing ``min(limit, 200)`` ceiling."""
    metadata = getattr(_limit_default(list_workstreams), "metadata", [])
    ge = _constraint(metadata, "Ge")
    le = _constraint(metadata, "Le")
    assert ge == 1, f"workstreams list `limit` lower bound must be ge=1, got {ge!r}"
    assert le == 200, f"workstreams list `limit` upper bound must be le=200, got {le!r}"


def test_list_workstream_events_limit_uses_query():
    """``list_workstream_events`` limit must be a FastAPI Query, not a bare
    int, so FastAPI enforces the range before the handler runs."""
    default = _limit_default(list_workstream_events)
    assert isinstance(default, params.Query), (
        "workstream events `limit` must be declared as Query(...) so the "
        "bound is enforced; got a bare default instead"
    )


def test_list_workstream_events_limit_is_bounded():
    """``list_workstream_events`` limit must declare ge=1 and le=1000,
    matching the handler's existing ``min(limit, 1000)`` ceiling."""
    metadata = getattr(_limit_default(list_workstream_events), "metadata", [])
    ge = _constraint(metadata, "Ge")
    le = _constraint(metadata, "Le")
    assert ge == 1, f"workstream events `limit` lower bound must be ge=1, got {ge!r}"
    assert le == 1000, (
        f"workstream events `limit` upper bound must be le=1000, got {le!r}"
    )
