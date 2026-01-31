from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULT_POLICY = {
    "default": {"allow": True},
    "classes": {},
}

DEFAULT_POLICY_PATH = Path("config/policy_config.yaml")


class AccessPolicy:
    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or self._resolve_path()
        self._policy: Dict[str, Any] = DEFAULT_POLICY.copy()
        self.refresh()

    def _resolve_path(self) -> Path:
        override = os.getenv("DAENA_POLICY_CONFIG")
        if override:
            return Path(override)
        return DEFAULT_POLICY_PATH

    def refresh(self) -> None:
        if not self._path.exists():
            self._policy = DEFAULT_POLICY.copy()
            return
        with self._path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        merged = DEFAULT_POLICY.copy()
        merged.update(data)
        merged["classes"] = merged.get("classes") or {}
        self._policy = merged

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _class_policy(self, cls: str) -> Dict[str, Any]:
        classes = self._policy.get("classes", {})
        return classes.get(cls, {})

    def _default_allow(self) -> bool:
        default = self._policy.get("default") or {}
        return bool(default.get("allow", True))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_allowed(self, action: str, cls: str, context: Optional[Dict[str, Any]]) -> bool:
        ctx = context or {}
        policy = self._class_policy(cls)
        allow_roles = set(policy.get("allow_roles") or [])
        deny_roles = set(policy.get("deny_roles") or [])
        allow_tenants = set(policy.get("allow_tenants") or [])
        deny_tenants = set(policy.get("deny_tenants") or [])

        role = ctx.get("role")
        tenant = ctx.get("tenant")

        if role and role in deny_roles:
            return False
        if tenant and tenant in deny_tenants:
            return False

        if allow_roles:
            if role not in allow_roles:
                return False
                
        if allow_tenants:
            if tenant not in allow_tenants:
                return False
                
        # If we passed all defined allow constraints, and at least one was defined, grant access
        if allow_roles or allow_tenants:
            return True

        return self._default_allow()

    def require(self, action: str, cls: str, context: Optional[Dict[str, Any]]) -> None:
        if not self.is_allowed(action, cls, context):
            raise PermissionError(f"Access denied for {action} on class {cls} with context {context}")

