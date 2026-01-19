#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import List, Tuple

def _recompute_txid(record: dict) -> str:
    payload = dict(record)
    payload.pop("txid", None)
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def verify_ledger(path: Path) -> Tuple[int, List[str]]:
    errors: List[str] = []
    if not path.exists():
        errors.append(f"Ledger file not found: {path}")
        return 1, errors

    with path.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {line_number}: invalid JSON ({exc})")
                continue
            expected_txid = _recompute_txid(record)
            if expected_txid != record.get("txid"):
                errors.append(f"Line {line_number}: txid mismatch")

    return (0 if not errors else 1), errors


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify NBMF ledger integrity.")
    parser.add_argument("--ledger-path", type=Path, default=Path(".ledger/ledger.jsonl"))
    args = parser.parse_args(argv)
    code, errors = verify_ledger(args.ledger_path)
    if code == 0:
        print(f"✓ Ledger verified ({args.ledger_path})")
    else:
        for err in errors:
            print(f"✗ {err}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

