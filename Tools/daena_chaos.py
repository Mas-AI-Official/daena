#!/usr/bin/env python
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path
from typing import Dict, List

from memory_service.ledger import log_event
from memory_service.router import MemoryRouter


def _scenario_l2_disconnect(l2_root: Path, execute: bool) -> Dict[str, str]:
    records = l2_root / "records"
    backup = records.with_name("records.offline")
    status = "skipped"
    if not records.exists():
        return {"status": status, "message": "records directory not found"}
    if not execute:
        return {"status": "dry-run", "message": "no action taken"}
    try:
        records.rename(backup)
        status = "disconnected"
    finally:
        if backup.exists():
            backup.rename(records)
            status = "restored"
    return {"status": status}


def _scenario_read_surge(iterations: int) -> Dict[str, str]:
    router = MemoryRouter()
    for i in range(iterations):
        key = f"chaos-{i}"
        router.write(key, "chat", {"note": f"load {i}"})
        router.read(key, "chat")
    return {"status": "completed", "iterations": str(iterations)}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NBMF chaos toolkit (use with caution).")
    parser.add_argument("--scenario", choices=["l2_disconnect", "read_surge"], required=True)
    parser.add_argument("--execute", action="store_true", help="Perform destructive steps (otherwise dry-run).")
    parser.add_argument("--l2", type=Path, default=Path(".l2_store"), help="Path to L2 store root.")
    parser.add_argument("--iterations", type=int, default=25, help="Iterations for read_surge scenario.")
    args = parser.parse_args(argv)

    log_event(
        action="chaos_start",
        ref=args.scenario,
        store="nbmf",
        route="chaos",
        extra={"execute": args.execute, "timestamp": time.time()},
    )

    if args.scenario == "l2_disconnect":
        result = _scenario_l2_disconnect(args.l2, args.execute)
    else:
        result = _scenario_read_surge(args.iterations)

    log_event(
        action="chaos_result",
        ref=args.scenario,
        store="nbmf",
        route="chaos",
        extra=result,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

