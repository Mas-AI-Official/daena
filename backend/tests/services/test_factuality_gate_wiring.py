"""BUILD-NOW #8 gate: FactualityGate wiring into ChatOrchestrator (C1).

Locks the grounding-honesty contract from
Doc/best_version_20260708/master.md #8:

The FactualityGate service is fully implemented but was NEVER called by the
orchestrator -- an orphaned anti-hallucination layer. This wires it in via
``ChatOrchestrator._run_factuality_gate`` and locks four honesty contracts:

1. It runs ONLY for grounding-eligible intents (SEARCH, ANALYSIS). Chit-chat
   and other intents skip it entirely (return None) -- zero cost, zero noise.

2. An empty / whitespace-only answer is never sent to the gate (return None).
   There is nothing to ground.

3. On an available verdict it returns a compact, persistable dict: checked,
   available, abstain, confidence, citation_count, a trimmed citations list,
   reasons, latency_ms. This is what the SSE ``grounding`` event and the
   persisted ``ChatMessage.grounding`` column carry.

4. On ragx outage / timeout / error it is HONEST (Rule 17 / ADR-001):
   ``available=False`` with a reason -- it does NOT fabricate a grounded pass.
   The gate itself never raises; a budget timeout or unexpected error is
   caught and reported as an honest unavailable verdict.

Zero model tokens: FactualityGate.verify hits ragx with generate=False.

RED anchors (before the wiring): ChatOrchestrator has no
``_run_factuality_gate`` attribute, so every test errors with AttributeError.
"""

import asyncio

import pytest

import app.services.factuality_gate as fg_module
from app.services.chat_orchestrator import ChatOrchestrator
from app.services.factuality_gate import Citation, FactualityVerdict


# -- Helpers -----------------------------------------------------------


def _orch() -> ChatOrchestrator:
    # _run_factuality_gate touches no DB/registry state; db=None is safe
    # (BaseService.__init__ only stores the handle, never dereferences it).
    return ChatOrchestrator(db=None, registry=None)


def _patch_verify(monkeypatch, fake) -> None:
    # The helper does `from app.services.factuality_gate import FactualityGate`
    # then calls FactualityGate.verify(...). Patching the class attribute on
    # the shared class object is seen by that local import.
    monkeypatch.setattr(fg_module.FactualityGate, "verify", fake)


# -- 1. Eligibility gate -----------------------------------------------


class TestEligibilityGate:
    @pytest.mark.asyncio
    async def test_ineligible_intent_returns_none_without_calling_gate(
        self, monkeypatch,
    ):
        called = {"hit": False}

        async def _should_not_run(query, candidate_answer, collections=None, k=8):
            called["hit"] = True
            return FactualityVerdict(available=True, abstain=False, confidence=1.0)

        _patch_verify(monkeypatch, _should_not_run)

        out = await _orch()._run_factuality_gate(
            query="hi there", answer="hello", intent_name="SIMPLE",
        )

        assert out is None
        assert called["hit"] is False

    @pytest.mark.asyncio
    async def test_empty_answer_returns_none(self, monkeypatch):
        called = {"hit": False}

        async def _should_not_run(query, candidate_answer, collections=None, k=8):
            called["hit"] = True
            return FactualityVerdict(available=True, abstain=False, confidence=1.0)

        _patch_verify(monkeypatch, _should_not_run)

        out = await _orch()._run_factuality_gate(
            query="what is X?", answer="   ", intent_name="SEARCH",
        )

        assert out is None
        assert called["hit"] is False


# -- 2. Available verdict -> compact persistable dict ------------------


class TestAvailableVerdict:
    @pytest.mark.asyncio
    async def test_available_verdict_maps_to_compact_dict(self, monkeypatch):
        citations = [
            Citation(chunk_id="c1", source_path="a.py", score=0.912345, snippet="s1"),
            Citation(chunk_id="c2", source_path="b.py", score=0.7, snippet="x" * 500),
        ]

        async def _fake(query, candidate_answer, collections=None, k=8):
            return FactualityVerdict(
                available=True,
                abstain=False,
                confidence=0.912345,
                citations=citations,
                reasons=[],
                candidate=candidate_answer,
                latency_ms=42.7,
            )

        _patch_verify(monkeypatch, _fake)

        out = await _orch()._run_factuality_gate(
            query="how does Shield enforce policy?",
            answer="Shield enforces policy via ...",
            intent_name="ANALYSIS",
        )

        assert out is not None
        assert out["checked"] is True
        assert out["available"] is True
        assert out["abstain"] is False
        assert out["confidence"] == pytest.approx(0.9123, abs=1e-4)
        assert out["citation_count"] == 2
        assert out["latency_ms"] == 42
        # Citations are trimmed for transport: snippet capped, score rounded.
        assert len(out["citations"]) == 2
        assert out["citations"][0]["source_path"] == "a.py"
        assert len(out["citations"][1]["snippet"]) <= 240

    @pytest.mark.asyncio
    async def test_available_but_abstained_is_reported_honestly(self, monkeypatch):
        async def _fake(query, candidate_answer, collections=None, k=8):
            return FactualityVerdict(
                available=True,
                abstain=True,
                confidence=0.1,
                citations=[],
                reasons=["daena-code: weak evidence"],
                candidate=candidate_answer,
                latency_ms=10.0,
            )

        _patch_verify(monkeypatch, _fake)

        out = await _orch()._run_factuality_gate(
            query="q", answer="a", intent_name="SEARCH",
        )

        assert out["checked"] is True
        assert out["available"] is True
        assert out["abstain"] is True
        assert out["citation_count"] == 0
        assert out["reasons"] == ["daena-code: weak evidence"]


# -- 3. Outage / timeout / error -> honest unavailable -----------------


class TestHonestUnavailable:
    @pytest.mark.asyncio
    async def test_ragx_outage_reports_unavailable(self, monkeypatch):
        async def _fake(query, candidate_answer, collections=None, k=8):
            # Mirrors FactualityGate's own outage verdict (ragx unreachable).
            return FactualityVerdict(
                available=False,
                abstain=True,
                confidence=0.0,
                reasons=["ragx unreachable at http://127.0.0.1:8100"],
                candidate=candidate_answer,
                latency_ms=5.0,
            )

        _patch_verify(monkeypatch, _fake)

        out = await _orch()._run_factuality_gate(
            query="q", answer="a", intent_name="SEARCH",
        )

        assert out["checked"] is True
        assert out["available"] is False
        assert out["abstain"] is True
        assert out["citation_count"] == 0

    @pytest.mark.asyncio
    async def test_gate_timeout_reports_unavailable_not_fabricated_pass(
        self, monkeypatch,
    ):
        async def _slow(query, candidate_answer, collections=None, k=8):
            await asyncio.sleep(1.0)
            return FactualityVerdict(available=True, abstain=False, confidence=1.0)

        _patch_verify(monkeypatch, _slow)

        orch = _orch()
        orch.FACTUALITY_GATE_BUDGET_SECONDS = 0.05  # instance override
        out = await orch._run_factuality_gate(
            query="q", answer="a", intent_name="SEARCH",
        )

        assert out["checked"] is True
        assert out["available"] is False
        assert out["abstain"] is True
        assert any("tim" in r.lower() for r in out["reasons"])

    @pytest.mark.asyncio
    async def test_unexpected_error_is_caught_and_reported(self, monkeypatch):
        async def _boom(query, candidate_answer, collections=None, k=8):
            raise RuntimeError("ragx client exploded")

        _patch_verify(monkeypatch, _boom)

        out = await _orch()._run_factuality_gate(
            query="q", answer="a", intent_name="SEARCH",
        )

        assert out["checked"] is True
        assert out["available"] is False
        assert out["abstain"] is True
        assert any("error" in r.lower() for r in out["reasons"])
