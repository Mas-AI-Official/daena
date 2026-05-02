"""Fake MCP server that fails initialize with a JSON-RPC error."""

from __future__ import annotations

import json
import sys


def _write(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        req_id = req.get("id")

        if method == "initialize":
            _write({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": "internal error: missing required env DATABASE_URL",
                },
            })
            return


if __name__ == "__main__":
    main()
