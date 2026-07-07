"""Direct unit tests for app.services.experience_ingest (VP plan item 9 / G2).

The blast-radius slice covers this module only TRANSITIVELY (through
memory.validate_quarantined and orchestrator Stage 6.1); these tests pin its
own contracts, which are exactly the kind that silently rot:

* DETERMINISM / IDEMPOTENCY -- markdown is keyed only on persisted values
  (id, created_at), never now(), so re-render yields identical bytes.
* FAIL-OPEN everywhere -- no-loop scheduling, ragx HTTP errors, ragx
  unreachable, and even an internal crash must never raise into the
  trust-promotion path (ADR-001 / Rule 17).
* MERGE SEMANTICS -- keyword lines first, normalised dedup, hard cap.

Everything here is DB-free and network-free (httpx is stubbed); the whole
file runs in well under a second. The fire-and-forget test awaits the
scheduled task explicitly -- a detached create_task leaking into loop
teardown is a known suite-hang incident class (see pyproject timeout note).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

import httpx
import pytest

from app.services import experience_ingest
from app.services.experience_ingest import (
    _content_preview,
    _render_markdown,
    merge_experience_lines,
    schedule_experience_ingest,
)
from app.services.ragx_bridge import experience_collection_name

_TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
_EXP_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
_CREATED = datetime(2026, 1, 2, 3, 4, 5)


def _kwargs(**overrides):
    base = dict(
        tenant_id=_TENANT,
        experience_id=_EXP_ID,
        content="Chose retry-with-backoff for the flaky provider; it worked.",
        summary="Retry-with-backoff beats fail-fast for provider timeouts.",
        tags=["AGENT_DECISION", "providers"],
        created_at=_CREATED,
    )
    base.update(overrides)
    return base


# -- merge_experience_lines (pure, consumed by orchestrator Stage 6.1) --


def test_merge_keyword_lines_come_first_and_semantic_fills() -> None:
    merged = merge_experience_lines(["- k1", "- k2"], ["- s1", "- s2"])
    assert merged == ["- k1", "- k2", "- s1", "- s2"]


def test_merge_dedups_case_and_whitespace_insensitively() -> None:
    merged = merge_experience_lines(["- Retry  Worked"], ["- retry worked", "- s1"])
    assert merged == ["- Retry  Worked", "- s1"]


def test_merge_caps_at_limit_and_skips_empty() -> None:
    merged = merge_experience_lines(
        ["", "- k1", "   "], ["- s1", "- s2", "- s3"], limit=3
    )
    assert merged == ["- k1", "- s1", "- s2"]


def test_merge_of_nothing_is_empty() -> None:
    assert merge_experience_lines([], []) == []


# -- _render_markdown / _content_preview (determinism contract) --


def test_render_is_deterministic_and_keyed_on_persisted_values() -> None:
    kw = _kwargs()
    once = _render_markdown(
        experience_id=kw["experience_id"], summary=kw["summary"],
        content=kw["content"], tags=kw["tags"], created_at=kw["created_at"],
    )
    twice = _render_markdown(
        experience_id=kw["experience_id"], summary=kw["summary"],
        content=kw["content"], tags=kw["tags"], created_at=kw["created_at"],
    )
    assert once == twice
    assert str(_EXP_ID) in once
    assert _CREATED.isoformat() in once
    assert "AGENT_DECISION, providers" in once
    assert "## Summary" in once and "## Detail" in once


def test_render_omits_summary_section_and_marks_empty_tags() -> None:
    body = _render_markdown(
        experience_id=_EXP_ID, summary=None, content="x", tags=[], created_at=None
    )
    assert "## Summary" not in body
    assert "- tags: (none)" in body
    assert "- created_at: \n" in body


def test_content_preview_truncates_and_handles_empty() -> None:
    assert _content_preview("") == "(empty)"
    assert _content_preview("   ") == "(empty)"
    long = "a" * 2500
    preview = _content_preview(long)
    assert preview.startswith("a" * 2000)
    assert preview.endswith("... (truncated)")
    assert _content_preview("short") == "short"


# -- schedule_experience_ingest (fire-and-forget, fail-open) --


def test_schedule_without_event_loop_fails_open() -> None:
    """Called from a sync context (no running loop) it must swallow the
    RuntimeError -- promotion has already flushed by then."""
    schedule_experience_ingest(**_kwargs())  # must not raise


async def test_schedule_runs_ingest_with_captured_scalars(monkeypatch) -> None:
    recorded: dict = {}

    async def fake_ingest(**kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr(experience_ingest, "ingest_experience", fake_ingest)
    schedule_experience_ingest(**_kwargs())

    # Drain the scheduled task INSIDE the test (never leak into teardown).
    inflight = list(experience_ingest._INFLIGHT)
    assert inflight, "schedule did not create a task"
    await asyncio.gather(*inflight)

    assert recorded["tenant_id"] == _TENANT
    assert recorded["experience_id"] == _EXP_ID
    assert recorded["tags"] == ["AGENT_DECISION", "providers"]

    # done_callback must release the strong reference (no unbounded growth)
    await asyncio.sleep(0)
    assert not experience_ingest._INFLIGHT


# -- ingest_experience (file write + index, fail-open) --


async def test_ingest_writes_deterministic_file_and_indexes(
    tmp_path, monkeypatch
) -> None:
    indexed: list = []

    async def fake_index(collection, path):
        indexed.append((collection, path))
        return True

    monkeypatch.setattr(experience_ingest, "_experience_dir", lambda: tmp_path)
    monkeypatch.setattr(experience_ingest, "_index_path", fake_index)

    await experience_ingest.ingest_experience(**_kwargs())

    collection = experience_collection_name(_TENANT)
    expected = tmp_path / collection / f"exp-{_EXP_ID}.md"
    assert expected.is_file()
    first_bytes = expected.read_bytes()
    assert indexed == [(collection, expected)]

    # Idempotency: re-ingesting the same experience yields identical bytes
    await experience_ingest.ingest_experience(**_kwargs())
    assert expected.read_bytes() == first_bytes


async def test_ingest_swallows_internal_crash(tmp_path, monkeypatch) -> None:
    async def boom(collection, path):
        raise RuntimeError("ragx exploded")

    monkeypatch.setattr(experience_ingest, "_experience_dir", lambda: tmp_path)
    monkeypatch.setattr(experience_ingest, "_index_path", boom)

    await experience_ingest.ingest_experience(**_kwargs())  # must not raise
    # The file still lands on disk for a later cron re-index (fail-open design)
    collection = experience_collection_name(_TENANT)
    assert (tmp_path / collection / f"exp-{_EXP_ID}.md").is_file()


# -- _index_path (HTTP fail-open) --


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _fake_client_factory(post_behavior):
    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc) -> bool:
            return False

        async def post(self, url, json):
            return post_behavior(url, json)

    return _FakeClient


async def test_index_path_returns_true_on_200(monkeypatch, tmp_path) -> None:
    seen: list = []

    def ok(url, json):
        seen.append((url, json))
        return _FakeResponse(200)

    monkeypatch.setattr(
        experience_ingest.httpx, "AsyncClient", _fake_client_factory(ok)
    )
    target = tmp_path / "exp.md"
    assert await experience_ingest._index_path("daena-exp-abc", target) is True
    url, payload = seen[0]
    assert url.endswith("/collections/daena-exp-abc/index")
    assert payload == {"sources": [str(target)]}


async def test_index_path_fails_open_on_http_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        experience_ingest.httpx,
        "AsyncClient",
        _fake_client_factory(lambda url, json: _FakeResponse(503)),
    )
    assert await experience_ingest._index_path("c", tmp_path / "x.md") is False


async def test_index_path_fails_open_when_unreachable(monkeypatch, tmp_path) -> None:
    def unreachable(url, json):
        raise httpx.ConnectError("ragx down")

    monkeypatch.setattr(
        experience_ingest.httpx, "AsyncClient", _fake_client_factory(unreachable)
    )
    assert await experience_ingest._index_path("c", tmp_path / "x.md") is False
