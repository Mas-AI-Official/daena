from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scan_store(path: Path) -> Dict[str, Any]:
    issues = []
    total = 0
    for file in sorted(path.glob("*.json")):
        total += 1
        try:
            text = file.read_text(encoding="utf-8")
            json.loads(text)
        except Exception as exc:  # noqa: BLE001
            issues.append({"file": str(file), "error": str(exc)})
    return {"total": total, "issues": issues, "path": str(path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consistency scan for NBMF stores.")
    parser.add_argument("--l2", type=Path, default=Path(".l2_store"))
    parser.add_argument("--l3", type=Path, default=Path(".l3_store"))
    args = parser.parse_args(argv)

    report = {
        "l2": scan_store(args.l2),
        "l3": scan_store(args.l3),
    }
    report["checksum"] = sha256_text(json.dumps(report, sort_keys=True))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

