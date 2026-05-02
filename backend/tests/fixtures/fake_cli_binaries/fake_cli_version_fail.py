"""Fake CLI whose `--version` exits with rc=2 (binary present but broken).

Used by the version_failed test. Mimics e.g. a CLI installed but with
missing dependencies that crashes on the first subcommand.
"""

from __future__ import annotations

import sys


def main() -> int:
    sys.stderr.write("fake-cli: missing optional dependency 'foo'\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
