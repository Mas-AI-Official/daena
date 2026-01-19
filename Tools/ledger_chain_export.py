#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional
from urllib import request, error

from memory_service.ledger import Ledger


def _post_manifest(url: str, manifest: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(manifest).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return {"status": resp.status, "body": body}
    except error.URLError as exc:  # pragma: no cover - depends on network availability
        return {"status": "error", "error": str(exc)}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute ledger Merkle root and export manifest.")
    parser.add_argument("--ledger-path", type=Path, default=Path(".ledger/ledger.jsonl"))
    parser.add_argument("--out", type=Path, default=Path(".ledger/ledger_manifest.json"))
    parser.add_argument("--note", type=str, default=None, help="Optional note to embed in manifest")
    parser.add_argument("--post", type=str, default=None, help="Optional blockchain endpoint to POST manifest")
    parser.add_argument("--extra", type=str, default=None, help="Optional JSON string of extra metadata")
    parser.add_argument("--print", dest="should_print", action="store_true", help="Print manifest to stdout")

    args = parser.parse_args(argv)
    extra: Dict[str, Any] = {}
    if args.extra:
        try:
            extra = json.loads(args.extra)
        except json.JSONDecodeError:
            parser.error("--extra must be valid JSON")

    ledger = Ledger(args.ledger_path)
    manifest = ledger.generate_manifest(note=args.note, extra=extra or None)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.should_print:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))

    if args.post:
        response = _post_manifest(args.post, manifest)
        print(json.dumps({"post_result": response}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
