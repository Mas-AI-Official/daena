"""Fake MCP server that writes received env names to a side file.

Used by the no-leak test to assert (a) the probe DOES pass declared
env names through to the subprocess, and (b) the probe NEVER logs the
values back to the operator. We write to a temp file (not stderr or
stdout) so the test can inspect what the server saw without coupling
to the probe's logging behavior.

Path is taken from the env var FAKE_MCP_ENV_DUMP (set by the test).
"""

from __future__ import annotations

import json
import os
import sys


def _write(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _dump_env() -> None:
    dump_path = os.environ.get("FAKE_MCP_ENV_DUMP")
    if not dump_path:
        return
    # Capture both NAMES and VALUES so the test can verify the
    # subprocess received expected names + values, while separately
    # asserting the probe's own logs / failure_reason carry NO values.
    payload = {
        name: value
        for name, value in os.environ.items()
        if name.startswith(("FAKE_PROBE_", "DAENA_TEST_"))
    }
    with open(dump_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def main() -> None:
    _dump_env()
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
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake-mcp-echo-env", "version": "0.0.1"},
                },
            })
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            _write({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {"name": "ok", "description": "ok", "inputSchema": {"type": "object"}}
                    ],
                },
            })
            return


if __name__ == "__main__":
    main()
