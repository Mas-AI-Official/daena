"""Fake CLI that ECHOES a sentinel secret on stderr.

`--version` succeeds; `auth status` returns rc=0 with valid JSON BUT
its stderr emits a sentinel secret (e.g. "ANTHROPIC_API_KEY=sk-..."
diagnostic noise). Used by the no-leak test to prove the probe never
echoes captured stderr into ``failure_reason`` or capabilities.

The probe's contract: stderr is captured for server-side logs ONLY,
never for UI / DB.
"""

from __future__ import annotations

import json
import sys


SENTINEL_SECRET = "sk-cli-do-not-leak-9999999999999999"


def main() -> int:
    argv = sys.argv[1:]
    # ALWAYS emit the sentinel on stderr regardless of subcommand --
    # the probe should never let it escape into structured outputs.
    sys.stderr.write(f"diagnostic: token={SENTINEL_SECRET}\n")
    if argv == ["--version"]:
        sys.stdout.write("fake-cli 1.2.3\n")
        return 0
    if argv == ["auth", "status"]:
        sys.stdout.write(json.dumps({"loggedIn": True, "apiProvider": "firstParty"}))
        sys.stdout.write("\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
