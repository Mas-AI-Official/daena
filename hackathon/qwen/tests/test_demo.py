"""Tests for the Qwen Cloud governed multi-agent demo.

All offline (replay mode): no secret, no network, no spend. Covers the
three claims the hackathon entry makes -- governance gating, reproducible
runs, and tamper-evident auditing.
"""

from __future__ import annotations

import os
import sys

import pytest

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PKG_ROOT)

from daena_qwen_demo import policy_gate  # noqa: E402
from daena_qwen_demo.audit_chain import AuditChain  # noqa: E402
from daena_qwen_demo.qwen_client import ReplayQwenClient  # noqa: E402
from daena_qwen_demo.runner import DeterministicClock, run_review  # noqa: E402

_FIXTURES = os.path.join(_PKG_ROOT, "fixtures", "replay.json")


def _client() -> ReplayQwenClient:
    return ReplayQwenClient.from_file(_FIXTURES)


# ── governance gate ───────────────────────────────────────────

def test_governed_gates_exploit_generation():
    d = policy_gate.evaluate("GENERATE_EXPLOIT_POC", mode="GOVERNED")
    assert d.governance_tier == 4
    assert d.result == "APPROVAL_REQUIRED"
    assert d.executed is False


def test_unleashed_still_gates_tier4_exploit():
    # Shield is always on: even UNLEASHED holds the Tier 4 asset action.
    d = policy_gate.evaluate("GENERATE_EXPLOIT_POC", mode="UNLEASHED")
    assert d.result == "APPROVAL_REQUIRED"
    assert d.executed is False


def test_governed_allows_low_tier_analysis():
    d = policy_gate.evaluate("ANALYZE_CONTRACT", mode="GOVERNED")
    assert d.result == "ALLOWED"
    assert d.executed is True


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        policy_gate.evaluate("ANALYZE_CONTRACT", mode="WILD")


# ── run + reproducibility ─────────────────────────────────────

def test_run_is_reproducible():
    a = run_review(client=_client(), mode="GOVERNED", clock=DeterministicClock())
    b = run_review(client=_client(), mode="GOVERNED", clock=DeterministicClock())
    # Byte-identical audit trails (same payloads -> same hashes).
    assert a["audit_trail"] == b["audit_trail"]
    assert a["audit_trail"][-1]["entry_hash"] == b["audit_trail"][-1]["entry_hash"]


def test_run_gates_the_adversary_action():
    res = run_review(client=_client(), mode="GOVERNED", clock=DeterministicClock())
    adversary = next(r for r in res["agents"] if r["role"] == "ADVERSARY")
    assert adversary["executed"] is False
    assert adversary["content"] is None
    assert res["totals"]["gated_actions"] == 1
    # The judge still reaches a verdict from the executed members.
    assert "VERDICT" in res["synthesis"]


def test_cost_is_tracked():
    res = run_review(client=_client(), mode="GOVERNED", clock=DeterministicClock())
    assert res["totals"]["cost_usd"] > 0.0
    assert res["totals"]["audit_entries"] == 4  # 3 members + judge


# ── tamper-evident audit ──────────────────────────────────────

def test_clean_trail_verifies():
    res = run_review(client=_client(), mode="GOVERNED", clock=DeterministicClock())
    assert res["audit_verification"]["valid"] is True


def test_content_tamper_is_detected():
    res = run_review(client=_client(), mode="GOVERNED", clock=DeterministicClock())
    trail = res["audit_trail"]
    # Attacker flips a gated action to ALLOWED without re-signing.
    target = next(e for e in trail if e["result"] == "APPROVAL_REQUIRED")
    target["result"] = "ALLOWED"
    verdict = AuditChain.from_list(trail).verify()
    assert verdict["valid"] is False
    assert verdict["reason"] == "content_tamper"
    assert verdict["first_broken_index"] == target["index"]


def test_dropped_entry_breaks_chain():
    res = run_review(client=_client(), mode="GOVERNED", clock=DeterministicClock())
    trail = res["audit_trail"]
    del trail[1]  # remove the second event
    verdict = AuditChain.from_list(trail).verify()
    assert verdict["valid"] is False
    assert verdict["reason"] == "broken_link"
