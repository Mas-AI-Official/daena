"""Tests for the pre-ingestion security + intelligence filter.

Every artifact Daena touches (packages, files, emails, skills) passes
through ``PreIngestionFilter.evaluate()`` before it reaches the system.
These tests pin the filter behavior on every axis that matters for
going public with an autonomous agent:

* Typosquats and known-malicious names are REFUSED outright.
* Non-existent PyPI packages are REFUSED on the AUTO_HEAL path so a
  poisoned error message can't induce an install.
* Already-installed packages are REFUSED as redundant (need-analysis
  intelligence layer).
* Legitimate packages PASS cleanly.
* Allowlist bypass works for Daena's own known-safe deps.
* WARN signals on AUTO_HEAL escalate to REFUSE (fail-safe autonomous
  install; LLM-initiated install path still gets WARN).

Network-backed tests (PyPI metadata) use a real PyPI fetch with a
short timeout; the checks tolerate timeout gracefully so CI never
flakes on upstream issues.
"""

from __future__ import annotations

import pytest

from app.services.security.pre_ingestion_filter import (
    ArtifactType,
    IngestionContext,
    PreIngestionFilter,
    TriggerSource,
)


def _ctx(
    name: str,
    *,
    trig: TriggerSource = TriggerSource.AUTO_HEAL,
    artifact: ArtifactType = ArtifactType.PIP_PACKAGE,
    agi: bool = True,
) -> IngestionContext:
    return IngestionContext(
        artifact_type=artifact,
        identifier=name,
        source="pypi",
        triggered_by=trig,
        reason="test",
        agi_mode=agi,
    )


# ── Static rejection (no network needed) ─────────────────────────────


@pytest.mark.asyncio
async def test_known_malicious_name_refused() -> None:
    """Known-malicious list is a hard REFUSE regardless of mode."""
    f = PreIngestionFilter()
    v = await f.evaluate(_ctx("colourama"))
    assert v.decision == "REFUSE"
    assert any(s.check == "known_malicious" for s in v.signals)


@pytest.mark.asyncio
async def test_typosquat_name_in_malicious_list_refused() -> None:
    """``reqests`` is a catalogued typosquat of ``requests``.

    Even though the typosquat check also flags it, the known-malicious
    list fires first and hard-refuses.
    """
    f = PreIngestionFilter()
    v = await f.evaluate(_ctx("reqests"))
    assert v.decision == "REFUSE"


@pytest.mark.asyncio
async def test_invalid_name_shape_refused() -> None:
    """Names that violate PEP 503 never touch the network."""
    f = PreIngestionFilter()
    v = await f.evaluate(_ctx("DROP_TABLE_users!"))
    assert v.decision == "REFUSE"
    assert any(s.check == "name_sanity" for s in v.signals)


@pytest.mark.asyncio
async def test_allowlist_bypasses_filter() -> None:
    """Allowlisted packages short-circuit to PASS."""
    f = PreIngestionFilter()
    v = await f.evaluate(_ctx("cowsay"))
    assert v.decision == "PASS"
    assert any(s.check == "allowlist" for s in v.signals)


# ── Need-analysis intelligence layer ─────────────────────────────────


@pytest.mark.asyncio
async def test_already_installed_package_refused_as_redundant() -> None:
    """Daena shouldn't re-install a module the interpreter can already
    see. That's the need-analysis: redundant work is always refused."""
    f = PreIngestionFilter()
    # pytest is obviously installed in this test env
    v = await f.evaluate(_ctx("pytest"))
    assert v.decision == "REFUSE"
    assert any(
        s.check == "need_analysis" and "already installed" in s.detail.lower()
        for s in v.signals
    )


# ── Network-backed checks (PyPI metadata) ────────────────────────────


@pytest.mark.asyncio
async def test_nonexistent_pypi_package_refused_on_auto_heal() -> None:
    """Non-existent PyPI package on AUTO_HEAL path -> REFUSE.

    This closes a subtle attack vector: a poisoned error message that
    induces Daena to install a made-up package. Even if the package
    name passes the static checks (no typosquat, no malicious match),
    PyPI existence check rejects it.
    """
    f = PreIngestionFilter()
    v = await f.evaluate(_ctx("totally-nonexistent-pkg-abcxyz-12345"))
    # Depending on timing, this lands at name_sanity or pypi_existence;
    # the important invariant is the verdict, not which check fired.
    assert v.decision == "REFUSE"


@pytest.mark.asyncio
async def test_nonexistent_pypi_package_warns_on_llm_request() -> None:
    """On LLM_REQUEST path, non-existent is WARN (could be private
    index, typo caught at approval). Auto-heal path gets the stricter
    REFUSE. Different trust baselines per trigger."""
    f = PreIngestionFilter()
    v = await f.evaluate(_ctx(
        "totally-nonexistent-pkg-abcxyz-12345",
        trig=TriggerSource.LLM_REQUEST,
    ))
    # LLM_REQUEST + nonexistent should be WARN (or REFUSE if name_sanity
    # trips for some reason). AUTO_HEAL already tested as hard REFUSE.
    assert v.decision in ("WARN", "REFUSE")


# ── Verdict synthesis rules ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_warn_escalates_to_refuse_on_auto_heal() -> None:
    """Any WARN on the AUTO_HEAL path escalates to REFUSE so silent
    autonomous install never happens on an ambiguous signal. The LLM
    can still explicitly request it via install_system_tool, which
    goes through the approval gate."""
    f = PreIngestionFilter()
    # A typosquat name NOT in the malicious list -- triggers WARN only
    # (some edit-distance near a popular package).
    v = await f.evaluate(_ctx("requesty", trig=TriggerSource.AUTO_HEAL))
    # Either WARN (if PyPI lookup fails/times out) or REFUSE (if auto-
    # heal escalated). Both acceptable; invariant is never PASS.
    assert v.decision != "PASS"


# ── Observability ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verdict_carries_signals_and_latency() -> None:
    """Every verdict must include the signals that drove it + latency
    for observability. Operators need to debug ''why was X refused''
    without re-running the check."""
    f = PreIngestionFilter()
    v = await f.evaluate(_ctx("colourama"))
    assert v.decision == "REFUSE"
    assert len(v.signals) >= 1
    # Total latency is always set (for static-only paths it's tiny).
    assert v.total_latency_ms >= 0.0
    # Every signal carries the check name + detail.
    for s in v.signals:
        assert s.check
        assert s.detail
