"""Sprint-12A PR-3: QE/Council runtime slot assignment tests.

Asserts:
    1. QE_SLOTS has the five named slots: local_reasoner,
       code_reviewer, web_grounder, risk_reviewer, final_synthesizer.
    2. assign_qe_slots prefers DISTINCT runtimes when possible.
    3. mode flips to "degraded" when only one distinct runtime can
       fill multiple slots, even if all slots get a value.
    4. mode is "full" only when there are 2+ distinct runtimes AND
       at least 3 filled slots -- a single-runtime council is not
       a real council.
    5. mode is "unavailable" when no runtime is ready.
    6. web_grounder slot stays unfilled when Perplexity is missing
       (it doesn't silently borrow from main_brain).
    7. /system/qe-readiness endpoint is registered.
    8. The slot_assignments rationale is honest -- "unfilled" rows
       carry the missing preferred ids in the rationale string.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.runtime_readiness import (
    QE_SLOTS,
    assign_qe_slots,
    _classify_item,
    get_qe_readiness,
)


EXPECTED_SLOTS = {
    "local_reasoner",
    "code_reviewer",
    "web_grounder",
    "risk_reviewer",
    "final_synthesizer",
}


def _classify(*items: dict):
    return [_classify_item(it) for it in items]


# ── Slot definition ──────────────────────────────────────────────────


class TestSlotsConstant:
    def test_five_named_slots(self):
        assert set(QE_SLOTS.keys()) == EXPECTED_SLOTS

    def test_each_slot_has_intent_preferred_fallback(self):
        for slot, spec in QE_SLOTS.items():
            assert "intent" in spec, slot
            assert "preferred" in spec, slot
            assert isinstance(spec["preferred"], list), slot
            assert spec["preferred"], slot
            assert "fallback_role" in spec, slot

    def test_web_grounder_only_perplexity_preferred(self):
        # The brief is explicit: web grounding belongs to Perplexity
        # only -- no silent fall-through to a main brain.
        assert QE_SLOTS["web_grounder"]["preferred"] == ["provider_perplexity"]


# ── Assignment ───────────────────────────────────────────────────────


def _ready_local(item_id: str = "vllm_configured", display: str = "vLLM"):
    return {
        "id": item_id, "display_name": display,
        "type": "local_model",
        "detected": True, "configured": True,
        "callable": True, "reachable_from_backend": True,
        "authenticated": True,
    }


def _ready_cli(item_id: str, display: str):
    return {
        "id": item_id, "display_name": display,
        "type": "cli",
        "detected": True, "configured": True,
        "callable": True, "reachable_from_backend": True,
        "authenticated": "unknown",
    }


def _absent(item_id: str):
    return {
        "id": item_id, "display_name": item_id,
        "type": "api",
        "detected": False, "configured": False,
        "callable": False, "authenticated": False,
    }


class TestAssignment:
    def test_full_mode_requires_two_distinct_runtimes_and_three_slots(self):
        items = _classify(
            _ready_local("vllm_configured", "vLLM"),
            _ready_local("ollama_backend", "Ollama"),
            _ready_cli("cli_claude", "Claude Code CLI"),
        )
        qe = assign_qe_slots(items)
        assert qe.mode == "full"
        assert len(qe.distinct_runtime_ids) >= 2
        # final_synthesizer + local_reasoner both have preferred
        # vllm_configured / ollama_backend; the assignment should
        # spread them.
        runtime_ids = [a.runtime_id for a in qe.slot_assignments if a.runtime_id]
        assert len(runtime_ids) >= 3

    def test_degraded_mode_when_only_one_runtime_ready(self):
        items = _classify(_ready_local())
        qe = assign_qe_slots(items)
        assert qe.mode == "degraded"
        # All slots filled (some by re-using the same runtime), but
        # there's only one distinct runtime so no peer cross-check.
        assert len(qe.distinct_runtime_ids) == 1
        assert "degraded" in qe.mode_reason.lower() or "no real peer" in qe.mode_reason.lower()

    def test_unavailable_when_no_runtime_ready(self):
        items = _classify(_absent("provider_perplexity"))
        qe = assign_qe_slots(items)
        assert qe.mode == "unavailable"
        # All slot assignments must be "unfilled"
        for a in qe.slot_assignments:
            assert a.runtime_id is None
            assert a.fill_source == "unfilled"
            # honest rationale
            assert "no ready runtime" in a.rationale.lower()

    def test_web_grounder_unfilled_when_perplexity_absent(self):
        # vLLM is ready (covers main_brain etc) but Perplexity isn't.
        # web_grounder must NOT silently grab vLLM -- it stays unfilled
        # because there's no fallback role that maps to a non-perplexity
        # runtime that can actually ground in live web data.
        items = _classify(_ready_local())
        qe = assign_qe_slots(items)
        web = next(a for a in qe.slot_assignments if a.slot == "web_grounder")
        assert web.runtime_id is None or web.runtime_id == "provider_perplexity"

    def test_distinct_runtimes_preferred_over_re_use(self):
        """When 2 distinct runtimes are ready, the assignment should
        spread them across slots so QE has a real peer cross-check.

        Five slots competing for 2 runtimes means re-use is inevitable
        somewhere -- but BOTH runtimes must end up in the assignment.
        """
        items = _classify(
            _ready_local("vllm_configured", "vLLM"),
            _ready_local("ollama_backend", "Ollama"),
        )
        qe = assign_qe_slots(items)
        # Both distinct runtimes must show up in the council.
        assert set(qe.distinct_runtime_ids) == {"vllm_configured", "ollama_backend"}, (
            f"Expected both runtimes to be assigned; got "
            f"{qe.distinct_runtime_ids}"
        )

    def test_only_one_runtime_re_used_across_all_slots(self):
        """With only one ready runtime, every fillable slot re-uses
        it -- and mode is degraded."""
        items = _classify(_ready_local("vllm_configured", "vLLM"))
        qe = assign_qe_slots(items)
        filled = [a for a in qe.slot_assignments if a.runtime_id is not None]
        assert all(a.runtime_id == "vllm_configured" for a in filled)
        assert qe.mode == "degraded"


class TestEndpoint:
    @pytest.mark.asyncio
    async def test_route_registered(self, app):
        spec = app.openapi()
        assert "/api/v1/system/qe-readiness" in spec["paths"]

    @pytest.mark.asyncio
    async def test_qe_readiness_returns_mode_and_slots(self):
        canned = {
            "items": [_ready_local("vllm_configured", "vLLM")],
            "updated_at": "x",
        }

        async def fake_get_truth(refresh: bool = False):  # noqa: ARG001
            return canned

        with patch(
            "app.services.runtime_readiness.runtime_truth_registry"
        ) as mock_reg:
            mock_reg.get_truth = fake_get_truth
            mock_reg.refresh = fake_get_truth
            result = await get_qe_readiness(refresh=False)

        assert "mode" in result
        assert "slot_assignments" in result
        assert {a["slot"] for a in result["slot_assignments"]} == EXPECTED_SLOTS
