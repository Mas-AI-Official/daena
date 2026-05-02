"""Fake CLI whose `--version` hangs forever (timeout test).

Reads a token from stdin (never sent) so the process blocks until the
probe's per-step timeout fires. Used to prove the probe enforces the
version timeout instead of waiting indefinitely.
"""

from __future__ import annotations

import time


def main() -> int:
    # Sleep well past any reasonable test timeout so wait_for fires.
    time.sleep(60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
