"""BUILD-NOW #9 gate: ragx retrieval transparency surfacing (C3).

Locks the abstain-surfacing contract from
Doc/best_version_20260708/master.md #9:

Stage 6.55 queries ragx and injects citations, but a FULL abstain (no
citations) or an offline ragx was silently dropped -- only a ``logger.debug``.
The user never learned the answer was ungrounded. This wires
``ChatOrchestrator._summarize_retrieval`` and locks four honesty contracts:

1. Positive citation-flash: when ragx returns citations, a compact retrieval
   verdict is surfaced for ANY intent -- the sources consulted are transparent.

2. Honest abstain: when ragx abstains (returns but with no citations) on a
   grounding-eligible intent (SEARCH / ANALYSIS), the verdict is surfaced with
   ``abstained=True`` and the consulted collections listed. It is NOT a
   fabricated grounded pass (Rule 17 / ADR-001).

3. Honest offline: when ragx is unreachable (available=False) on an eligible
   intent, the verdict is surfaced with ``available=False`` + a reason.

4. No noise: an abstain / offline on a NON-eligible intent (chit-chat) with no
   citations surfaces nothing (return None) -- a down ragx never spams offline
   events on "hi".

The surfaced dict is what the early SSE ``retrieval`` event and the persisted
``ChatMessage.retrieval`` column carry. Zero model tokens: pure mapping over a
``RagxResult``.

RED anchor (before the wiring): ChatOrchestrator has no ``_summarize_retrieval``
attribute, so every test errors with AttributeError.
"""

import pytest

from app.services.chat_orchestrator import ChatOrchestrator
from app.services.ragx_bridge import RagxCitation, RagxResult


# -- Helpers -----------------------------------------------------------


def _orch() -> ChatOrchestrator:
    # _summarize_retrieval touches no DB/registry state; db=None is safe
    # (BaseService.__init__ only stores the handle, never dereferences it).
    return ChatOrchestrator(db=None, registry=None)


def _cite(collection: str, path: str, score: float = 0.9) -> RagxCitation:
    return RagxCitation(
        chunk_id=f"{collection}:{path}",
        source_path=path,
        score=score,
        snippet="evidence snippet",
        collection=collection,
    )


# -- 1. Emit gate: no noise on ineligible intents ----------------------


class TestEmitGate:
    def test_abstain_on_ineligible_intent_surfaces_nothing(self):
        # ragx abstained, but the turn is chit-chat -> stay silent.
        result = RagxResult(
            citations=[],
            abstained_collections=["daena-docs", "wiki"],
            elapsed_ms=12.0,
            available=True,
        )
        out = _orch()._summarize_retrieval(result, "SIMPLE")
        assert out is None

    def test_offline_on_ineligible_intent_surfaces_nothing(self):
        result = RagxResult(
            citations=[], abstained_collections=[], elapsed_ms=3.0, available=False,
        )
        out = _orch()._summarize_retrieval(result, "CREATIVE")
        assert out is None


# -- 2. Honest abstain: eligible intent, ragx returned no citations ----


class TestHonestAbstain:
    def test_abstain_on_eligible_intent_is_surfaced_with_collections(self):
        result = RagxResult(
            citations=[],
            abstained_collections=["daena-docs", "wiki"],
            elapsed_ms=15.0,
            available=True,
        )
        out = _orch()._summarize_retrieval(result, "SEARCH")

        assert out is not None
        assert out["checked"] is True
        assert out["available"] is True
        assert out["abstained"] is True
        assert out["citation_count"] == 0
        # The gate contract: metadata lists the collections consulted.
        assert out["collections"] == ["daena-docs", "wiki"]
        assert out["abstained_collections"] == ["daena-docs", "wiki"]
        assert any("abstain" in r.lower() for r in out["reasons"])

    def test_empty_result_on_eligible_intent_is_honest_not_fabricated(self):
        # ragx responded but surfaced nothing and named no abstained collection.
        result = RagxResult(
            citations=[], abstained_collections=[], elapsed_ms=8.0, available=True,
        )
        out = _orch()._summarize_retrieval(result, "ANALYSIS")

        assert out is not None
        assert out["available"] is True
        assert out["abstained"] is True
        assert out["citation_count"] == 0
        assert out["collections"] == []


# -- 3. Honest offline: ragx unreachable -------------------------------


class TestHonestOffline:
    def test_offline_on_eligible_intent_reports_unavailable(self):
        result = RagxResult(
            citations=[], abstained_collections=[], elapsed_ms=2.0, available=False,
        )
        out = _orch()._summarize_retrieval(result, "SEARCH")

        assert out is not None
        assert out["checked"] is True
        assert out["available"] is False
        assert out["abstained"] is True
        assert out["citation_count"] == 0
        assert any("offline" in r.lower() or "unreach" in r.lower() for r in out["reasons"])


# -- 4. Positive citation-flash: fires on ANY intent -------------------


class TestCitationFlash:
    def test_citations_surface_on_any_intent(self):
        result = RagxResult(
            citations=[_cite("daena-docs", "a.md", 0.8123456)],
            abstained_collections=[],
            elapsed_ms=20.0,
            available=True,
        )
        # SIMPLE is NOT a grounding-eligible intent, yet real citations were
        # injected -> transparency still surfaces them.
        out = _orch()._summarize_retrieval(result, "SIMPLE")

        assert out is not None
        assert out["abstained"] is False
        assert out["citation_count"] == 1
        assert out["collections"] == ["daena-docs"]
        assert out["citations"][0]["collection"] == "daena-docs"
        assert out["citations"][0]["source_path"] == "a.md"
        # Score is rounded for transport.
        assert out["citations"][0]["score"] == pytest.approx(0.8123, abs=1e-4)

    def test_citations_capped_and_collections_unioned(self):
        cites = [_cite("wiki", f"p{i}.md", 0.7) for i in range(8)]
        cites.append(_cite("daena-code", "z.py", 0.6))
        result = RagxResult(
            citations=cites,
            abstained_collections=["shared-memory"],
            elapsed_ms=30.0,
            available=True,
        )
        out = _orch()._summarize_retrieval(result, "ANALYSIS")

        assert out["citation_count"] == 9
        # Transport list is capped.
        assert len(out["citations"]) <= 5
        # collections = union of citation collections + abstained collections.
        assert out["collections"] == ["daena-code", "shared-memory", "wiki"]
        assert out["abstained"] is False
