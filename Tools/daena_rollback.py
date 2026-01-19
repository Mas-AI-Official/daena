from __future__ import annotations

import sys

from Tools.daena_memory_switch import main as switch_main


def main(argv: list[str] | None = None) -> int:
    sys.argv = ["daena_memory_switch.py", "--mode", "rollback"]
    switch_main()
    print("↩️  ROLLBACK DONE — Legacy is primary again")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
