"""Smoke tests for the soul-maker research fan-out adapter.

``fetch_domain_best_practices`` calls the real ``fan_out_intelligence``
(6-channel background fan-out) and flattens its ``IntelligenceBundle`` into
the flat ``{source, title, text, date}`` snippet shape refinement consumes.
These tests pin that mapping offline: they stub ``fan_out_intelligence`` so
no network / LLM / graph calls fire. They guard the exact bug that shipped
before this adapter -- a phantom ``run_multi_source`` import that silently
degraded every research pass to empty evidence.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def _fake_bundle(**channels):
    """Build an IntelligenceBundle stand-in with just the fields the adapter reads."""
    default_channel_results = [
        SimpleNamespace(status="ok"),
        SimpleNamespace(status="empty"),
    ]
    return SimpleNamespace(
        web_insights=channels.get("web_insights", []),
        source_matches=channels.get("source_matches", []),
        historical_patterns=channels.get("historical_patterns", []),
        graph_paths=channels.get("graph_paths", []),
        channel_results=channels.get("channel_results", default_channel_results),
    )


@pytest.mark.asyncio
async def test_unknown_department_returns_empty() -> None:
    from app.services.soul_maker.research import fetch_domain_best_practices

    assert await fetch_domain_best_practices("ghost_dept") == []


@pytest.mark.asyncio
async def test_fanout_bundle_flattens_to_snippets(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.security import intel_fanout
    from app.services.soul_maker.research import fetch_domain_best_practices

    async def fake_fanout(target, phase="orient", **kw):
        # Mirror the real bundle: the web channel emits {"summary": ...} items,
        # so the adapter must fall back to the summary key for title + text.
        return _fake_bundle(
            web_insights=[{"summary": "best practice hit"}],
            source_matches=[{"title": "code", "text": "snippet"}],
            historical_patterns=[{"content": "prior decision", "published_at": "2026-05-01"}],
            graph_paths=[{"summary": "path A"}],
        )

    monkeypatch.setattr(intel_fanout, "fan_out_intelligence", fake_fanout)

    snippets = await fetch_domain_best_practices("engineering", max_snippets=8)

    sources = {s["source"] for s in snippets}
    assert sources == {"web_search", "codebase_memory", "nbmf_t3", "knowledge_graph"}

    # summary-key fallback: the web item carries no title/text, only summary.
    web = next(s for s in snippets if s["source"] == "web_search")
    assert web["title"] == "best practice hit"
    assert web["text"] == "best practice hit"

    # content + published_at fallbacks map onto text + date.
    hist = next(s for s in snippets if s["source"] == "nbmf_t3")
    assert hist["text"] == "prior decision"
    assert hist["date"] == "2026-05-01"

    # every snippet is exactly the flat contract refinement expects
    for s in snippets:
        assert set(s) == {"source", "title", "text", "date"}


@pytest.mark.asyncio
async def test_fanout_caps_at_max_snippets(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.security import intel_fanout
    from app.services.soul_maker.research import fetch_domain_best_practices

    async def fake_fanout(target, phase="orient", **kw):
        return _fake_bundle(web_insights=[{"summary": f"s{i}"} for i in range(20)])

    monkeypatch.setattr(intel_fanout, "fan_out_intelligence", fake_fanout)

    snippets = await fetch_domain_best_practices("engineering", max_snippets=5)
    assert len(snippets) == 5


@pytest.mark.asyncio
async def test_fanout_failure_soft_fails_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.security import intel_fanout
    from app.services.soul_maker.research import fetch_domain_best_practices

    async def boom(target, phase="orient", **kw):
        raise RuntimeError("fanout down")

    monkeypatch.setattr(intel_fanout, "fan_out_intelligence", boom)

    # Degraded, not fatal: refinement still runs on empty evidence (soft-fail).
    assert await fetch_domain_best_practices("engineering") == []
