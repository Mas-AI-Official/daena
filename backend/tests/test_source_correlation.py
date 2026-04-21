"""Tests for source-to-finding correlator + Zero-FP gate.

Covers:
    * Correlator returns None when no signal.
    * Correlator returns None when MCP is unavailable.
    * Zero-FP gate passes SCOUT / ANALYST unchanged.
    * Zero-FP gate rejects OPERATOR findings without evidence.
    * Founder override forces inclusion + logs as override.
    * Heuristic fix suggestions match common vulnerability classes.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.security import source_correlator as sc
from app.services.security.report_tiers import ReportTier
from app.services.security.zero_fp_gate import apply_gate


# ----------------------------------------------------------------------
# Source correlator
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_correlator_returns_none_for_empty_finding():
    result = await sc.correlate_finding_to_source({"id": ""})
    assert result is None


@pytest.mark.asyncio
async def test_correlator_returns_none_when_no_signal():
    result = await sc.correlate_finding_to_source({"id": "F1"})
    assert result is None


@pytest.mark.asyncio
async def test_correlator_returns_none_on_mcp_error():
    """When MCPAgent.call_tool raises, correlator degrades gracefully."""

    class BoomAgent:
        async def call_tool(self, **kwargs):
            raise RuntimeError("mcp down")

    with patch("app.services.daenabot.mcp_agent.MCPAgent", BoomAgent):
        result = await sc.correlate_finding_to_source(
            {"id": "F2", "location": "api/search.py"},
        )
    assert result is None


@pytest.mark.asyncio
async def test_correlator_normalizes_mcp_hit():
    """Real-shape MCP hit produces a populated SourceCorrelation."""

    class FakeAgent:
        async def call_tool(self, **kwargs):
            return {
                "file": "app/api/search.py",
                "line": 42,
                "symbol": "search_users",
                "confidence": 0.85,
                "project": "daena",
            }

    with patch("app.services.daenabot.mcp_agent.MCPAgent", FakeAgent):
        result = await sc.correlate_finding_to_source(
            {
                "id": "F3",
                "title": "SQL injection",
                "location": "api/search.py",
                "endpoint": "/api/search",
            },
        )
    assert result is not None
    assert result.source_file == "app/api/search.py"
    assert result.source_line == 42
    assert result.symbol_name == "search_users"
    assert result.confidence == pytest.approx(0.85)
    assert "parameterized" in result.fix_suggestion.lower()


def test_heuristic_fix_suggestion_known_classes():
    sugg = sc._heuristic_fix_suggestion({"title": "Reflected XSS in search form"})
    assert "escape" in sugg.lower() or "sanitize" in sugg.lower()

    sugg = sc._heuristic_fix_suggestion({"title": "CSRF on settings endpoint"})
    assert "csrf" in sugg.lower() or "samesite" in sugg.lower()

    sugg = sc._heuristic_fix_suggestion({"title": "SSRF via preview URL"})
    assert "allow-list" in sugg.lower() or "private" in sugg.lower()

    sugg = sc._heuristic_fix_suggestion({"title": "Some custom finding"})
    assert "validate" in sugg.lower()


# ----------------------------------------------------------------------
# Zero-FP gate
# ----------------------------------------------------------------------


def test_gate_passes_scout_unchanged():
    findings = [{"id": "F1"}, {"id": "F2"}]
    result = apply_gate(findings, ReportTier.SCOUT)
    assert result.accepted_count == 2
    assert result.rejected_count == 0


def test_gate_passes_analyst_unchanged():
    findings = [{"id": "F1"}, {"id": "F2"}]
    result = apply_gate(findings, ReportTier.ANALYST)
    assert result.accepted_count == 2
    assert result.rejected_count == 0


def test_gate_rejects_operator_finding_without_evidence():
    findings = [
        {"id": "F1", "title": "Hypothetical SQL injection"},
    ]
    result = apply_gate(findings, ReportTier.OPERATOR)
    assert result.rejected_count == 1
    assert result.accepted_count == 0
    assert "No EvidenceChain" in result.rejected[0]["rejection_reason"]


def test_gate_accepts_finding_with_evidence_chain_id():
    findings = [
        {"id": "F1", "title": "SQL injection", "evidence_chain_id": "E-123"},
    ]
    result = apply_gate(findings, ReportTier.ARCHITECT)
    assert result.accepted_count == 1


def test_gate_accepts_finding_with_evidence_dict():
    findings = [
        {
            "id": "F1",
            "title": "SQL injection",
            "evidence": {"screenshot_path": "/var/evidence/s.png"},
        },
    ]
    result = apply_gate(findings, ReportTier.ARCHITECT)
    assert result.accepted_count == 1


def test_gate_accepts_when_falsification_survived():
    findings = [
        {
            "id": "F1",
            "title": "SQL injection",
            "falsification_survived": True,
        },
    ]
    result = apply_gate(findings, ReportTier.OPERATOR)
    assert result.accepted_count == 1


def test_gate_founder_override_moves_finding_to_overrides():
    findings = [
        {"id": "F1", "title": "Hypothetical finding"},
        {"id": "F2", "title": "Another hypothetical"},
    ]
    result = apply_gate(
        findings, ReportTier.EVILBOB,
        founder_override_ids={"F1"},
    )
    assert result.override_count == 1
    assert result.rejected_count == 1
    assert result.overrides[0]["id"] == "F1"
    assert result.rejected[0]["id"] == "F2"


def test_gate_empty_evidence_dict_still_rejects():
    findings = [
        {"id": "F1", "title": "SQL injection", "evidence": {}},
    ]
    result = apply_gate(findings, ReportTier.OPERATOR)
    assert result.rejected_count == 1
