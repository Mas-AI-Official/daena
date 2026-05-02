"""Fake MCP server that never responds to initialize (timeout test)."""

from __future__ import annotations

import sys
import time


def main() -> None:
    # Read the request but never write the response. Sleep long enough
    # that any reasonable test timeout fires.
    sys.stdin.readline()
    time.sleep(60)


if __name__ == "__main__":
    main()
