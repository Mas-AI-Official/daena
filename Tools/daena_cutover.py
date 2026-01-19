from __future__ import annotations

import argparse
import json
import sys

from memory_service.migration import finalize_backfill
from memory_service.router import MemoryRouter
from Tools.daena_memory_switch import main as switch_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run final NBMF cutover.")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)

    summary = finalize_backfill(MemoryRouter())
    print(json.dumps({"backfill": summary}, indent=2))

    if args.verify_only or summary.get("mismatches"):
        return 0

    sys.argv = ["daena_memory_switch.py", "--mode", "cutover"]
    switch_main()
    print("✅ CUTOVER DONE — NBMF is primary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
