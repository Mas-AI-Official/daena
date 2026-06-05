"""Orchestrator: run the governed council and emit a signed audit trail.

Wires three shipped ideas together on Qwen Cloud:
  1. a multi-agent council (heterogeneous Qwen models),
  2. a governance policy gate evaluated before every action, and
  3. a tamper-evident hash-chained audit trail recording every decision.

The output dict is the demo's product: the synthesis a normal multi-agent
demo would show, PLUS the audit trail and gate decisions a normal demo
omits. The front-end (hackathon_demo_consensus_public) consumes this dict.
"""

from __future__ import annotations

from typing import Protocol

from . import policy_gate
from .audit_chain import AuditChain
from .scenario import AGENTS, JUDGE, build_judge_prompt, build_member_prompt


class _Client(Protocol):
    def complete(
        self, role: str, model: str, system: str, user: str
    ) -> object: ...


class _Clock(Protocol):
    def now(self) -> str: ...


class DeterministicClock:
    """Monotonic, reproducible timestamps for replay/test runs."""

    def __init__(self, base: str = "2026-07-01T00:00:") -> None:
        self._base = base
        self._n = 0

    def now(self) -> str:
        ts = f"{self._base}{self._n:02d}"
        self._n += 1
        return ts


class RealClock:
    def now(self) -> str:
        from datetime import datetime

        return datetime.utcnow().isoformat()


def run_review(
    *,
    client: _Client,
    mode: str = "GOVERNED",
    clock: _Clock | None = None,
) -> dict:
    """Execute the governed security-review council.

    Args:
        client: A ReplayQwenClient (default/offline) or LiveQwenClient.
        mode: Governance mode (UNLEASHED / BALANCED / GOVERNED).
        clock: Timestamp source. Defaults to DeterministicClock so a
            replay run is byte-reproducible (stable audit hashes).

    Returns:
        Dict with mode, per-agent records (incl. gate decision), the
        judge synthesis, the full audit_trail, its verification result,
        and aggregate cost/latency.
    """
    clk = clock or DeterministicClock()
    chain = AuditChain()
    agent_records: list[dict] = []
    member_outputs: list[dict] = []
    total_cost = 0.0
    total_latency = 0

    for agent in AGENTS:
        decision = policy_gate.evaluate(agent.action_type, mode=mode)
        ts = clk.now()

        record: dict = {
            "role": agent.role,
            "model": agent.model,
            "action_type": agent.action_type,
            "governance_tier": decision.governance_tier,
            "risk_level": decision.risk_level,
            "gate_result": decision.result,
            "executed": decision.executed,
            "rationale": decision.rationale,
        }

        if decision.executed:
            comp = client.complete(
                agent.role,
                agent.model,
                agent.system,
                build_member_prompt(agent),
            )
            record["content"] = comp.content
            record["cost_usd"] = comp.cost_usd
            record["latency_ms"] = comp.latency_ms
            total_cost += comp.cost_usd
            total_latency += comp.latency_ms
            member_outputs.append({"role": agent.role, "content": comp.content})
        else:
            # Gated: recorded but not executed. The capability exists;
            # the governance layer withholds it pending human approval.
            record["content"] = None
            record["cost_usd"] = 0.0
            record["latency_ms"] = 0

        chain.append(
            actor_type="AGENT",
            actor_id=agent.role,
            action_type=agent.action_type,
            result=decision.result,
            risk_level=decision.risk_level,
            governance_tier=decision.governance_tier,
            timestamp=ts,
        )
        agent_records.append(record)

    # Judge synthesis over the executed members.
    judge_decision = policy_gate.evaluate(JUDGE.action_type, mode=mode)
    ts = clk.now()
    synthesis = ""
    if judge_decision.executed and member_outputs:
        comp = client.complete(
            JUDGE.role,
            JUDGE.model,
            JUDGE.system,
            build_judge_prompt(member_outputs),
        )
        synthesis = comp.content
        total_cost += comp.cost_usd
        total_latency += comp.latency_ms
    chain.append(
        actor_type="AGENT",
        actor_id=JUDGE.role,
        action_type=JUDGE.action_type,
        result=judge_decision.result,
        risk_level=judge_decision.risk_level,
        governance_tier=judge_decision.governance_tier,
        timestamp=ts,
    )

    return {
        "mode": mode,
        "agents": agent_records,
        "judge": {
            "role": JUDGE.role,
            "model": JUDGE.model,
            "gate_result": judge_decision.result,
            "executed": judge_decision.executed,
        },
        "synthesis": synthesis,
        "audit_trail": chain.to_list(),
        "audit_verification": chain.verify(),
        "totals": {
            "cost_usd": round(total_cost, 6),
            "latency_ms": total_latency,
            "audit_entries": len(chain.entries),
            "gated_actions": sum(
                1 for r in agent_records if not r["executed"]
            ),
        },
    }
