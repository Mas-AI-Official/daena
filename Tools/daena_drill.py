#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict

from memory_service.ledger import ledger_summary, log_event
from memory_service.migration import finalize_backfill
from memory_service.policy_summary import load_policy_summary
from memory_service.router import MemoryRouter
from memory_service.stats import collect_memory_stats


def _snapshot(l2_root: Path, l3_root: Path) -> Dict[str, Any]:
    stats = {}
    for tier, root in ("l2", l2_root), ("l3", l3_root):
        tier_stats = collect_memory_stats(l2_root=str(root.parent / "records") if root.name != "records" else str(root))
        stats[tier] = tier_stats.get(tier, tier_stats)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NBMF disaster-recovery drill utility.")
    parser.add_argument("--limit", type=int, default=None, help="Backfill limit during verification.")
    parser.add_argument("--l2", type=Path, default=Path(".l2_store/records"))
    parser.add_argument("--l3", type=Path, default=Path(".l3_store/records"))
    args = parser.parse_args(argv)

    router = MemoryRouter()
    start = time.time()
    backfill_report = finalize_backfill(router, limit=args.limit)
    snapshot_report = _snapshot(args.l2, args.l3)
    ledger_report = ledger_summary()
    policy_report = load_policy_summary()

    drill_report = {
        "timestamp": time.time(),
        "duration_sec": time.time() - start,
        "backfill": backfill_report,
        "snapshot": snapshot_report,
        "ledger": ledger_report,
        "policy": policy_report,
    }

    log_event(action="drill", ref="nbmf_drill", store="nbmf", route="governance", extra=drill_report)
    print(json.dumps(drill_report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
