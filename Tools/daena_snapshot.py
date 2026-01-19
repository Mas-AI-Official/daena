#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

from memory_service.ledger import log_event


def _hash_store(root: Path) -> Tuple[int, str]:
    if not root.exists():
        return 0, ""
    digest = hashlib.sha256()
    count = 0
    for path in sorted(root.glob("**/*.json")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
        count += 1
    return count, digest.hexdigest()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create integrity snapshot of NBMF stores.")
    parser.add_argument("--l2", type=Path, default=Path(".l2_store/records"))
    parser.add_argument("--l3", type=Path, default=Path(".l3_store/records"))
    parser.add_argument("--label", default="snapshot", help="Reference label for the snapshot event.")
    args = parser.parse_args(argv)

    summary: Dict[str, Dict[str, str]] = {}
    for name, root in (("l2", args.l2), ("l3", args.l3)):
        count, digest = _hash_store(root)
        summary[name] = {"count": count, "hash": digest}

    log_event(
        action="snapshot",
        ref=args.label,
        store="nbmf",
        route="governance",
        extra=summary,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

