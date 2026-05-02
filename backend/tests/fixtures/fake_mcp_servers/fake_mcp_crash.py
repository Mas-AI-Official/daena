"""Fake MCP server that exits immediately before any I/O (command_failed)."""

from __future__ import annotations

import sys


def main() -> None:
    # Print a startup error to stderr (mimics e.g. `npx -y bad-pkg`
    # printing "module not found") and exit non-zero.
    sys.stderr.write("fake-mcp-crash: missing dependency 'foo'\n")
    sys.exit(2)


if __name__ == "__main__":
    main()
