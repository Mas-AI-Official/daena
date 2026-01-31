#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import List

import urllib.request
import urllib.error

def _load_ledger(path: Path) -> List[dict]:
    if not path.exists():
        return []
    entries: List[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _merkle_root(entries: List[dict]) -> str:
    if not entries:
        return ""
    layer = [hashlib.sha256(json.dumps(entry, sort_keys=True).encode("utf-8")).hexdigest() for entry in entries]
    while len(layer) > 1:
        next_layer = []
        for i in range(0, len(layer), 2):
            left = layer[i]
            right = layer[i + 1] if i + 1 < len(layer) else left
            combined = (left + right).encode("utf-8")
            next_layer.append(hashlib.sha256(combined).hexdigest())
        layer = next_layer
    return layer[0]


def _post_to_chain(endpoint: str, payload: dict, token: str | None = None) -> str:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(endpoint, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export ledger merkle root and optionally post to blockchain endpoint.")
    parser.add_argument("--ledger", type=Path, default=Path(".ledger/ledger.jsonl"))
    parser.add_argument("--output", type=Path, help="Write merkle summary to JSON file.")
    parser.add_argument("--chain-endpoint", help="Blockchain relay endpoint to post merkle root.")
    parser.add_argument("--chain-token", help="Optional bearer token for blockchain relay.")
    parser.add_argument("--label", default="nbmf-ledger", help="Label for the merkle root event.")
    args = parser.parse_args(argv)

    entries = _load_ledger(args.ledger)
    root = _merkle_root(entries)
    summary = {"label": args.label, "merkle_root": root, "entries": len(entries)}

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    endpoint = args.chain_endpoint or os.getenv("DAENA_CHAIN_ENDPOINT")
    token = args.chain_token or os.getenv("DAENA_CHAIN_TOKEN")
    if endpoint and root:
        try:
            response = _post_to_chain(endpoint, summary, token)
            summary["chain_response"] = response
        except urllib.error.URLError as exc:
            summary["chain_error"] = str(exc)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
