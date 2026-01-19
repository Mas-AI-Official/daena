from __future__ import annotations

import argparse
import json
from typing import Optional

from memory_service.backfill_job import backfill
from memory_service.caching_cas import CAS
from memory_service.llm_exchange import LLMExchangeRecord


def _load_records(cas_path: str, limit: int) -> list[LLMExchangeRecord]:
    path = CAS(root=cas_path).root
    if not path.exists():
        return []
    records: list[LLMExchangeRecord] = []
    for idx, file in enumerate(sorted(path.iterdir(), reverse=True)):
        if idx >= limit:
            break
        payload = json.loads(file.read_text(encoding="utf-8"))
        records.append(LLMExchangeRecord(**payload))
    return records


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="NBMF replay/backfill helper.")
    parser.add_argument("--last", type=int, default=1000, help="Number of recent events to backfill.")
    parser.add_argument("--tenant", help="Tenant identifier for scoped backfill.")
    parser.add_argument("--cas", default=".llm_cas", help="Optional CAS directory (for inspection).")
    parser.add_argument("--inspect", action="store_true", help="Inspect CAS entries instead of queueing backfill.")
    args = parser.parse_args(argv)

    if args.inspect:
        records = _load_records(args.cas, args.last)
        print(json.dumps([record.to_dict() for record in records], indent=2))
        return 0

    report = backfill(last_n=args.last, tenant=args.tenant)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

