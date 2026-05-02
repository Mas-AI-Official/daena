"""Fake MCP server that completes initialize + tools/list happy path.

Exposes 2 fake tools so the probe sees a non-empty list and the
capability-persist branch of ConnectionRegistryV2.probe_and_record
also gets exercised.
"""

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
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake-mcp-ok", "version": "0.0.1"},
                },
            })
        elif method == "notifications/initialized":
            # No response for notifications.
            continue
        elif method == "tools/list":
            _write({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo input back",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"text": {"type": "string"}},
                                "required": ["text"],
                            },
                        },
                        {
                            "name": "ping",
                            "description": "Return pong",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                    ],
                },
            })
            # After tools/list, exit cleanly so the probe's stdio_client
            # context manager can release without hanging on EOF.
            return
        else:
            _write({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"method not found: {method}",
                },
            })


if __name__ == "__main__":
    main()
