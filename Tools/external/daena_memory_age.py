from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from memory_service.aging import apply_aging
from memory_service.memory_bootstrap import load_config
from memory_service.router import MemoryRouter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply NBMF aging policies")
    parser.add_argument("--config", type=Path, help="Optional memory config override", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Report actions without writing")
    args = parser.parse_args(argv)

    config: Dict[str, Any] | None = None
    if args.config:
        config = load_config(args.config)
    router = MemoryRouter(config=config)

    if args.dry_run:
        report = apply_aging(router, dry_run=True)
        print(json.dumps({"dry_run": True, "actions": report}, indent=2))
        return 0

    report = apply_aging(router)
    print(json.dumps({"dry_run": False, "actions": report}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
