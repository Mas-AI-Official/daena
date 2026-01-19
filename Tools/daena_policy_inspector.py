#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from memory_service.policy_summary import build_policy_summary


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected structure in {path}")
    return data


def _fidelity_for_class(memory_cfg: Dict[str, Any], cls: str) -> Optional[str]:
    fidelity = memory_cfg.get("memory_policy", {}).get("fidelity", {})
    for key, definition in fidelity.items():
        parts = [name.strip() for name in key.split("|")]
        if cls in parts:
            if isinstance(definition, dict):
                return str(definition.get("mode"))
            return str(definition)
    return None


def build_summary(
    policy_cfg: Dict[str, Any],
    memory_cfg: Dict[str, Any],
    classes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "default_allow": bool(policy_cfg.get("default", {}).get("allow", True)),
        "classes": {},
    }
    classes_cfg = policy_cfg.get("classes", {}) or {}
    selected = classes or list(classes_cfg.keys())
    for cls in selected:
        rules = classes_cfg.get(cls, {})
        summary["classes"][cls] = {
            "allow_roles": rules.get("allow_roles", []),
            "deny_roles": rules.get("deny_roles", []),
            "allow_tenants": rules.get("allow_tenants", []),
            "deny_tenants": rules.get("deny_tenants", []),
            "fidelity": _fidelity_for_class(memory_cfg, cls),
        }
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect Daena ABAC and memory fidelity settings.")
    parser.add_argument("--policy", type=Path, default=Path("config/policy_config.yaml"))
    parser.add_argument("--memory", type=Path, default=Path("config/memory_config.yaml"))
    parser.add_argument("--class", dest="classes", action="append", help="Limit output to specific memory class")

    args = parser.parse_args(argv)

    policy_cfg = _load_yaml(args.policy)
    memory_cfg = _load_yaml(args.memory)

    summary = build_policy_summary(policy_cfg, memory_cfg, args.classes)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
