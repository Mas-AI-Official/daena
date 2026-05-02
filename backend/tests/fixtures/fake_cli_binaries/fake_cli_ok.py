"""Fake CLI that supports `--version` and `auth status` (Claude shape).

Runs with rc=0 and prints a version string OR a JSON envelope mirroring
the real Claude CLI's `auth status` output. Used by the happy-path test
for the claude_status_cmd auth strategy.

Argv contract:
  --version          -> prints "fake-cli 1.2.3" + exit 0
  auth status        -> prints {"loggedIn": true, "apiProvider": "firstParty"} + exit 0
  any other argv     -> exit 2 (probe must never invoke unknown subcommands)
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    argv = sys.argv[1:]
    if argv == ["--version"]:
        sys.stdout.write("fake-cli 1.2.3\n")
        return 0
    if argv == ["auth", "status"]:
        sys.stdout.write(json.dumps({
            "loggedIn": True,
            "apiProvider": "firstParty",
        }))
        sys.stdout.write("\n")
        return 0
    sys.stderr.write(f"unknown argv: {argv}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
