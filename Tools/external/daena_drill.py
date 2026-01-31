#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from memory_service.migration import finalize_backfill
from memory_service.router import MemoryRouter
from Tools.daena_ledger_verify import verify_ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run NBMF disaster recovery drill: backfill + ledger verification.")
    parser.add_argument("--ledger-path", type=Path, default=Path(".ledger/ledger.jsonl"))
    parser.add_argument("--limit", type=int, help="Optional limit of records to backfill.")
    parser.add_argument("--dry-run", action="store_true", help="Print steps without modifying NBMF store.")
    args = parser.parse_args(argv)

    router = MemoryRouter()
    result: Dict[str, Any] = {}

    if args.dry_run:
        result["backfill"] = {"dry_run": True, "limit": args.limit}
    else:
        backfill_summary = finalize_backfill(router, limit=args.limit)
        result["backfill"] = backfill_summary

    code, errors = verify_ledger(args.ledger_path)
    result["ledger"] = {"verified": code == 0, "errors": errors}

    print(json.dumps(result, indent=2))
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
