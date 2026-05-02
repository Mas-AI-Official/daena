"""Fake CLI whose `auth status` prints garbage instead of JSON.

`--version` succeeds; `auth status` returns rc=0 but stdout is plain
text. Used by the auth_unknown path test (probe must NOT crash and
must NOT pretend the CLI is authenticated when it cannot parse).
"""

from __future__ import annotations

import sys


def main() -> int:
    argv = sys.argv[1:]
    if argv == ["--version"]:
        sys.stdout.write("fake-cli 1.2.3\n")
        return 0
    if argv == ["auth", "status"]:
        sys.stdout.write("not-json output -- legacy CLI without JSON status\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
