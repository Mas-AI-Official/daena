"""Fake CLI that says "I'm installed and reachable, but NOT logged in".

`--version` succeeds with rc=0; `auth status` returns JSON with
``loggedIn: false`` (rc=0, valid JSON). Used by the claude auth_failed
path test.
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
        sys.stdout.write(json.dumps({"loggedIn": False}))
        sys.stdout.write("\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
