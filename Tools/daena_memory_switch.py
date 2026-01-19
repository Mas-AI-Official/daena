from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

from memory_service.memory_bootstrap import load_config, save_config

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "memory_config.yaml"


def _apply_mode(flags: Dict[str, Any], mode: str) -> None:
    if mode == "legacy":
        flags.update({"nbmf_enabled": False, "read_mode": "legacy", "dual_write": True, "canary_percent": 0})
    elif mode == "hybrid":
        flags.update({"nbmf_enabled": True, "read_mode": "hybrid", "dual_write": True})
    elif mode == "nbmf":
        flags.update({"nbmf_enabled": True, "read_mode": "nbmf", "dual_write": False, "canary_percent": 100})
    elif mode == "cutover":
        flags.update({"nbmf_enabled": True, "read_mode": "nbmf", "dual_write": False, "canary_percent": 100})
    elif mode == "rollback":
        flags.update({"nbmf_enabled": False, "read_mode": "legacy", "dual_write": True, "canary_percent": 0})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daena NBMF memory switch utility.")
    parser.add_argument("--mode", choices=["legacy", "hybrid", "nbmf", "cutover", "rollback"], required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--canary", type=int)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    flags = cfg.setdefault("flags", {})

    if args.status:
        print(json.dumps(flags, indent=2))
        return 0

    _apply_mode(flags, args.mode)
    if args.canary is not None:
        flags["canary_percent"] = max(0, min(100, args.canary))

    save_config(cfg, args.config)

    os.environ["DAENA_READ_MODE"] = flags.get("read_mode", "legacy")
    os.environ["DAENA_NBMF_ENABLED"] = str(flags.get("nbmf_enabled", False))
    os.environ["DAENA_DUAL_WRITE"] = str(flags.get("dual_write", True))
    os.environ["DAENA_CANARY_PERCENT"] = str(flags.get("canary_percent", 0))

    print(json.dumps({"effective_flags": flags}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

