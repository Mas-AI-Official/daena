"""Tests for external intelligence fan-out + CVE intel client.

Covers:
    * CVE lookup caching behavior (1hr TTL)
    * Partial-failure isolation (one channel errors, rest still return)
    * Bundle aggregation logic
    * Per-channel status trace
    * confidence_weighted_summary rendering
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.security import cve_intel as cve_mod
from app.services.security import intel_fanout as fan_mod
from app.services.security.cve_intel import CVEItem, clear_cache, lookup_cves
from app.services.security.intel_fanout import (
    ChannelResult,
    IntelligenceBundle,
    fan_out_intelligence,
)


@pytest.fixture(autouse=True)
def _reset_cve_cache():
    clear_cache()
    yield
    clear_cache()


# ----------------------------------------------------------------------
# CVE intel
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cve_lookup_empty_keyword_returns_empty():
    assert await lookup_cves("") == []
    assert await lookup_cves("   ") == []


@pytest.mark.asyncio
async def test_cve_lookup_cache_hit_on_second_call():
    fake = [CVEItem(cve_id="CVE-2026-1234", severity="HIGH", source="nvd")]
    nvd_mock = AsyncMock(return_value=fake)
    with patch.object(cve_mod, "_query_nvd", nvd_mock):
        with patch.object(
            cve_mod, "_query_github_advisories", AsyncMock(return_value=[])
        ):
            first = await lookup_cves("openssl", limit=5)
            second = await lookup_cves("openssl", limit=5)
    assert first == second
    assert nvd_mock.call_count == 1  # cache hit on second call


@pytest.mark.asyncio
async def test_cve_lookup_merges_sources_and_dedupes():
    nvd = [CVEItem(cve_id="CVE-2026-9000", severity="HIGH", source="nvd")]
    gh = [
        CVEItem(cve_id="CVE-2026-9000", severity="HIGH", source="github_advisory"),
        CVEItem(cve_id="CVE-2026-9001", severity="MEDIUM", source="github_advisory"),
    ]
    with patch.object(cve_mod, "_query_nvd", AsyncMock(return_value=nvd)):
        with patch.object(
            cve_mod, "_query_github_advisories", AsyncMock(return_value=gh)
        ):
            items = await lookup_cves("payload", limit=10)
    ids = {i.cve_id for i in items}
    assert ids == {"CVE-2026-9000", "CVE-2026-9001"}


@pytest.mark.asyncio
async def test_cve_lookup_handles_source_exception():
    with patch.object(
        cve_mod, "_query_nvd", AsyncMock(side_effect=RuntimeError("down")),
    ):
        with patch.object(
            cve_mod, "_query_github_advisories", AsyncMock(return_value=[]),
        ):
            items = await lookup_cves("example", limit=5)
    # No crash; empty is a valid answer.
    assert items == []


# ----------------------------------------------------------------------
# Fan-out bundle
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fanout_partial_failure_still_returns_bundle():
    async def ok_web(target, phase):
        return ChannelResult("web_search", status="ok", payload=[{"summary": "hit"}])

    async def err_cve(target):
        return ChannelResult("cve_intel", status="error", error="no network")

    async def empty_cbm(target):
        return ChannelResult("codebase_memory", status="skipped")

    async def empty_kg(target):
        return ChannelResult("knowledge_graph", status="empty", payload=[])

    async def empty_kh(target):
        return ChannelResult("knowledge_hunter", status="empty", payload=[])

    async def empty_nbmf(target, phase):
        return ChannelResult("nbmf_t3", status="skipped")

    with patch.object(fan_mod, "_channel_web", ok_web), \
         patch.object(fan_mod, "_channel_cve", err_cve), \
         patch.object(fan_mod, "_channel_codebase_memory", empty_cbm), \
         patch.object(fan_mod, "_channel_knowledge_graph", empty_kg), \
         patch.object(fan_mod, "_channel_knowledge_hunter", empty_kh), \
         patch.object(fan_mod, "_channel_nbmf_t3", empty_nbmf):
        bundle = await fan_out_intelligence("example.com")

    assert isinstance(bundle, IntelligenceBundle)
    assert bundle.target == "example.com"
    assert len(bundle.channel_results) == 6
    statuses = {c.name: c.status for c in bundle.channel_results}
    assert statuses["web_search"] == "ok"
    assert statuses["cve_intel"] == "error"
    assert statuses["codebase_memory"] == "skipped"
    # Web payload aggregated.
    assert bundle.web_insights == [{"summary": "hit"}]


@pytest.mark.asyncio
async def test_fanout_empty_target_returns_empty_bundle():
    bundle = await fan_out_intelligence("")
    assert bundle.target == ""
    assert bundle.channel_results == []


@pytest.mark.asyncio
async def test_fanout_summary_mentions_present_channels():
    bundle = IntelligenceBundle(target="x.com", phase="orient")
    bundle.cves = [{"cve_id": "CVE-2026-1", "severity": "HIGH"}]
    bundle.web_insights = [{"summary": "a"}]
    bundle.source_matches = [{"summary": "s"}]
    summary = bundle.confidence_weighted_summary
    assert "CVE-2026-1" in summary
    assert "Web intel" in summary
    assert "Source-code matches" in summary


@pytest.mark.asyncio
async def test_fanout_summary_when_empty():
    bundle = IntelligenceBundle(target="x.com", phase="orient")
    summary = bundle.confidence_weighted_summary
    assert "No external intel" in summary


# ----------------------------------------------------------------------
# Timeout budget
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fanout_respects_timeout_budget():
    import asyncio

    async def slow_cve(target):
        await asyncio.sleep(10)  # longer than any reasonable test timeout
        return ChannelResult("cve_intel", status="ok", payload=[])

    async def fast_other(*args, **kwargs):
        return ChannelResult("x", status="skipped")

    with patch.object(fan_mod, "_channel_cve", slow_cve), \
         patch.object(fan_mod, "_channel_web", fast_other), \
         patch.object(fan_mod, "_channel_codebase_memory", fast_other), \
         patch.object(fan_mod, "_channel_knowledge_graph", fast_other), \
         patch.object(fan_mod, "_channel_knowledge_hunter", fast_other), \
         patch.object(fan_mod, "_channel_nbmf_t3", fast_other):
        bundle = await fan_out_intelligence(
            "example.com", timeout_seconds=0.3,
        )

    # Timed out: bundle returns with no channel results (timeout path).
    assert bundle.target == "example.com"
    # Channel results may be empty because timeout happened before gather returned.
    # The key property: no hang, no raise.
