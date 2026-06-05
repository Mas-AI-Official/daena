#!/usr/bin/env python3
"""Daena on Qwen Cloud -- governed multi-agent demo runner.

Default (no flags): offline REPLAY mode -- deterministic, no secret, no
spend. Reproduces the governed security-review council and emits a
tamper-evident audit trail.

    python run_demo.py                 # replay, GOVERNED mode
    python run_demo.py --mode UNLEASHED
    python run_demo.py --tamper        # also demo audit tamper-detection
    python run_demo.py --live          # founder-gated: real Qwen Cloud spend

Live mode needs QWEN_CLOUD_API_KEY in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from daena_qwen_demo.qwen_client import LiveQwenClient, ReplayQwenClient  # noqa: E402
from daena_qwen_demo.runner import DeterministicClock, RealClock, run_review  # noqa: E402


def _build_client(live: bool):
    if live:
        return LiveQwenClient(), RealClock()
    fixtures = os.path.join(_HERE, "fixtures", "replay.json")
    return ReplayQwenClient.from_file(fixtures), DeterministicClock()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daena on Qwen Cloud demo")
    parser.add_argument(
        "--mode",
        default="GOVERNED",
        choices=["UNLEASHED", "BALANCED", "GOVERNED"],
    )
    parser.add_argument("--live", action="store_true", help="real Qwen Cloud (founder-gated)")
    parser.add_argument("--tamper", action="store_true", help="demo audit tamper-detection")
    parser.add_argument("--out", default="", help="write audit_trail.json to this path")
    args = parser.parse_args(argv)

    client, clock = _build_client(args.live)
    result = run_review(client=client, mode=args.mode, clock=clock)

    print(f"\n=== Daena on Qwen Cloud -- mode={result['mode']} ===\n")
    for rec in result["agents"]:
        flag = "RUN " if rec["executed"] else "GATE"
        print(
            f"[{flag}] {rec['role']:<9} t{rec['governance_tier']} "
            f"{rec['risk_level']:<8} {rec['gate_result']:<17} {rec['rationale']}"
        )
    gated = result["totals"]["gated_actions"]
    print(f"\nGated (capability withheld pending approval): {gated} action(s)")
    print(f"\n--- VERDICT ---\n{result['synthesis']}\n")

    verify = result["audit_verification"]
    print(
        f"Audit trail: {verify['total_entries']} entries, "
        f"valid={verify['valid']} "
        f"(cost ${result['totals']['cost_usd']:.6f}, "
        f"{result['totals']['latency_ms']} ms)"
    )

    if args.tamper:
        trail = result["audit_trail"]
        # Flip a recorded gate result without re-signing -- simulates an
        # attacker editing the ledger to hide that an action was gated.
        target = next(
            (e for e in trail if e["result"] == "APPROVAL_REQUIRED"),
            trail[0],
        )
        original = target["result"]
        target["result"] = "ALLOWED"
        from daena_qwen_demo.audit_chain import AuditChain

        tampered = AuditChain.from_list(trail).verify()
        print(
            f"\nTamper demo: flipped entry #{target['index']} "
            f"{original} -> ALLOWED (without re-signing).\n"
            f"Re-verify: valid={tampered['valid']} "
            f"reason={tampered['reason']} "
            f"first_broken_index={tampered['first_broken_index']}"
        )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"\nWrote {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
