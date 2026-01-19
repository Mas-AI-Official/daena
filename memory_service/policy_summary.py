from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .memory_bootstrap import load_config
from .policy import AccessPolicy


def _fidelity_for_class(memory_cfg: Dict[str, Any], cls: str) -> Optional[str]:
    fidelity = memory_cfg.get("memory_policy", {}).get("fidelity", {})
    for key, definition in fidelity.items():
        candidates = [name.strip() for name in key.split("|")]
        if cls in candidates:
            if isinstance(definition, dict):
                return str(definition.get("mode"))
            return str(definition)
    return None


def build_policy_summary(
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


def load_policy_summary(classes: Optional[List[str]] = None) -> Dict[str, Any]:
    policy = AccessPolicy()
    policy.refresh()
    policy_cfg = policy._policy  # type: ignore[attr-defined]
    memory_cfg = load_config()
    return build_policy_summary(policy_cfg, memory_cfg, classes)


def load_policy_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected policy format in {path}")
    return data
