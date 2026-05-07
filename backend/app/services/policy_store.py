"""Plain-English policy YAML store.

Phase 2 F8 (2026-04-24). Masoud's mandate: governance policies are
authored in plain English; Daena compiles them into structured YAML
that SecurityGate can evaluate at request time.

Storage layout:
    backend/app/config/policies/
      <tenant_id>/
        <policy_id>.yaml      -- one file per policy
        _index.json           -- order + enabled flags + metadata cache

A policy file looks like:

    ---
    id: pol_<uuid>
    name: "Twitter post review"
    plain_english: "Daena should never post to my Twitter without showing me the draft first."
    version: 1
    trigger: EXTERNAL_COMMS:twitter.post
    condition: "platform == 'twitter' AND action == 'post'"
    action: REQUIRE_APPROVAL  # BLOCK | APPROVE | LOG | REDACT | REQUIRE_APPROVAL
    enforcement_mode: ALWAYS  # ALWAYS | BALANCED_ONLY | GOVERNED_ONLY
    governance_tier: 3
    enabled: true
    created_at: "2026-04-24T22:30:00Z"
    compiled_at: "2026-04-24T22:30:00Z"
    compiled_by: "claude-code-cli"
    confidence: 0.92
    ---
    # Twitter post review
    Daena should never post to my Twitter without showing me the draft first.

The body of the markdown file is a human-readable rendering of the
plain-English policy; the frontmatter is the machine-evaluable form.
SecurityGate watches the per-tenant directory and reloads on change.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from app.core.logging import get_logger

logger = get_logger(__name__)


PolicyAction = Literal["BLOCK", "APPROVE", "LOG", "REDACT", "REQUIRE_APPROVAL"]
PolicyEnforcementMode = Literal["ALWAYS", "BALANCED_ONLY", "GOVERNED_ONLY"]


@dataclass
class Policy:
    """In-memory policy representation."""

    id: str
    name: str
    plain_english: str
    trigger: str
    condition: str
    action: str
    enforcement_mode: str
    governance_tier: int
    enabled: bool
    version: int
    created_at: str
    compiled_at: str
    compiled_by: str
    confidence: float
    notes: str = ""
    matched_intents: list[str] = field(default_factory=list)
    department_id: str | None = None  # None = global policy; set = scoped to one dept

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "plain_english": self.plain_english,
            "trigger": self.trigger,
            "condition": self.condition,
            "action": self.action,
            "enforcement_mode": self.enforcement_mode,
            "governance_tier": self.governance_tier,
            "enabled": self.enabled,
            "version": self.version,
            "created_at": self.created_at,
            "compiled_at": self.compiled_at,
            "compiled_by": self.compiled_by,
            "confidence": self.confidence,
            "notes": self.notes,
            "matched_intents": list(self.matched_intents),
            "department_id": self.department_id,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root_dir() -> Path:
    """Resolve backend/app/config/policies/."""
    here = Path(__file__).resolve()
    # services/policy_store.py -> app/services/ -> app/ -> backend/app/config/policies
    return here.parent.parent / "config" / "policies"


def _tenant_dir(tenant_id: str) -> Path:
    """Per-tenant policy directory."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tenant_id)
    return _root_dir() / safe


class PolicyStore:
    """File-backed CRUD + tenant isolation + cache."""

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Policy]] = {}  # tenant_id -> {policy_id: Policy}
        self._lock = threading.RLock()

    def _ensure_dir(self, tenant_id: str) -> Path:
        d = _tenant_dir(tenant_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _hydrate(self, tenant_id: str) -> None:
        """Walk tenant directory and load every <id>.yaml into cache."""
        d = _tenant_dir(tenant_id)
        if not d.exists():
            self._cache[tenant_id] = {}
            return
        loaded: dict[str, Policy] = {}
        for path in d.glob("*.yaml"):
            try:
                policy = _parse_policy_file(path)
                if policy:
                    loaded[policy.id] = policy
            except Exception as exc:
                logger.warning(
                    "policy_store.parse_failed",
                    path=str(path),
                    error=str(exc),
                )
        self._cache[tenant_id] = loaded
        logger.info(
            "policy_store.hydrated",
            tenant_id=tenant_id,
            count=len(loaded),
        )

    def list(
        self,
        tenant_id: str,
        *,
        only_enabled: bool = False,
        department_id: str | None = None,
    ) -> list[Policy]:
        with self._lock:
            if tenant_id not in self._cache:
                self._hydrate(tenant_id)
            policies = list(self._cache.get(tenant_id, {}).values())
            if only_enabled:
                policies = [p for p in policies if p.enabled]
            if department_id is not None:
                policies = [p for p in policies if p.department_id == department_id]
            return sorted(policies, key=lambda p: (p.created_at, p.name))

    def get(self, tenant_id: str, policy_id: str) -> Policy | None:
        with self._lock:
            if tenant_id not in self._cache:
                self._hydrate(tenant_id)
            return self._cache.get(tenant_id, {}).get(policy_id)

    def create(self, tenant_id: str, policy_data: dict[str, Any]) -> Policy:
        with self._lock:
            self._ensure_dir(tenant_id)
            now = _now_iso()
            pid = policy_data.get("id") or f"pol_{uuid.uuid4().hex[:12]}"
            policy = Policy(
                id=pid,
                name=str(policy_data.get("name", "Unnamed Policy")),
                plain_english=str(policy_data.get("plain_english", "")),
                trigger=str(policy_data.get("trigger", "")),
                condition=str(policy_data.get("condition", "")),
                action=str(policy_data.get("action", "LOG")),
                enforcement_mode=str(policy_data.get("enforcement_mode", "ALWAYS")),
                governance_tier=int(policy_data.get("governance_tier", 1)),
                enabled=bool(policy_data.get("enabled", True)),
                version=int(policy_data.get("version", 1)),
                created_at=str(policy_data.get("created_at", now)),
                compiled_at=str(policy_data.get("compiled_at", now)),
                compiled_by=str(policy_data.get("compiled_by", "manual")),
                confidence=float(policy_data.get("confidence", 1.0)),
                notes=str(policy_data.get("notes", "")),
                matched_intents=list(policy_data.get("matched_intents") or []),
                department_id=policy_data.get("department_id") or None,
            )
            self._write(tenant_id, policy)
            self._cache.setdefault(tenant_id, {})[policy.id] = policy
            logger.info(
                "policy_store.created",
                tenant_id=tenant_id,
                policy_id=policy.id,
                name=policy.name,
            )
            return policy

    def update(self, tenant_id: str, policy_id: str, patch: dict[str, Any]) -> Policy:
        with self._lock:
            current = self.get(tenant_id, policy_id)
            if current is None:
                raise KeyError(f"policy not found: {policy_id}")
            merged = current.to_dict()
            merged.update(patch)
            merged["version"] = current.version + 1
            merged["compiled_at"] = patch.get("compiled_at", _now_iso())
            updated = Policy(**{
                k: merged[k] for k in [
                    "id", "name", "plain_english", "trigger", "condition", "action",
                    "enforcement_mode", "governance_tier", "enabled", "version",
                    "created_at", "compiled_at", "compiled_by", "confidence",
                    "notes", "matched_intents", "department_id",
                ]
            })
            self._write(tenant_id, updated)
            self._cache.setdefault(tenant_id, {})[updated.id] = updated
            logger.info(
                "policy_store.updated",
                tenant_id=tenant_id,
                policy_id=updated.id,
                version=updated.version,
            )
            return updated

    def delete(self, tenant_id: str, policy_id: str) -> bool:
        with self._lock:
            current = self.get(tenant_id, policy_id)
            if current is None:
                return False
            path = _tenant_dir(tenant_id) / f"{policy_id}.yaml"
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("policy_store.delete_failed", error=str(exc))
                return False
            self._cache.get(tenant_id, {}).pop(policy_id, None)
            logger.info(
                "policy_store.deleted",
                tenant_id=tenant_id,
                policy_id=policy_id,
            )
            return True

    def _write(self, tenant_id: str, policy: Policy) -> None:
        path = _tenant_dir(tenant_id) / f"{policy.id}.yaml"
        frontmatter = yaml.safe_dump(
            policy.to_dict(),
            sort_keys=True,
            allow_unicode=True,
            default_flow_style=False,
        ).strip()
        body = f"# {policy.name}\n\n{policy.plain_english}\n"
        path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")


def _parse_policy_file(path: Path) -> Policy | None:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return None
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        logger.warning("policy_store.yaml_error", path=str(path), error=str(exc))
        return None
    if not isinstance(data, dict):
        return None
    try:
        return Policy(
            id=str(data.get("id") or path.stem),
            name=str(data.get("name", "")),
            plain_english=str(data.get("plain_english", "")),
            trigger=str(data.get("trigger", "")),
            condition=str(data.get("condition", "")),
            action=str(data.get("action", "LOG")),
            enforcement_mode=str(data.get("enforcement_mode", "ALWAYS")),
            governance_tier=int(data.get("governance_tier", 1)),
            enabled=bool(data.get("enabled", True)),
            version=int(data.get("version", 1)),
            created_at=str(data.get("created_at", _now_iso())),
            compiled_at=str(data.get("compiled_at", _now_iso())),
            compiled_by=str(data.get("compiled_by", "manual")),
            confidence=float(data.get("confidence", 1.0)),
            notes=str(data.get("notes", "")),
            matched_intents=list(data.get("matched_intents") or []),
            department_id=data.get("department_id") or None,
        )
    except Exception as exc:
        logger.warning("policy_store.bad_shape", path=str(path), error=str(exc))
        return None


# Singleton.
policy_store = PolicyStore()


# ── Pre-seed templates for "Load defaults" button ─────────────────

POLICY_SEEDS: list[dict[str, Any]] = [
    {
        "name": "Block all money transfers",
        "plain_english": (
            "Block any send-money or transfer-funds action regardless of mode. "
            "Daena should never move money on my behalf."
        ),
        "trigger": "FINANCIAL:transfer",
        "condition": "action_type IN ('send_money','transfer_funds','wire','crypto_send')",
        "action": "BLOCK",
        "enforcement_mode": "ALWAYS",
        "governance_tier": 4,
    },
    {
        "name": "Redact founder PII outbound",
        "plain_english": (
            "Redact my home address, SSN, bank account, and personal email "
            "from any outbound message before it leaves Daena."
        ),
        "trigger": "OUTBOUND:any",
        "condition": "matches_pii_blocklist(payload, scope='founder_private')",
        "action": "REDACT",
        "enforcement_mode": "ALWAYS",
        "governance_tier": 0,
    },
    {
        "name": "Approve before LinkedIn autopilot post",
        "plain_english": (
            "Require my approval before posting on LinkedIn from autopilot. "
            "Manually-triggered chat sends are fine; only block the unattended pipeline."
        ),
        "trigger": "EXTERNAL_COMMS:linkedin.post",
        "condition": "initiator == 'autopilot' AND platform == 'linkedin'",
        "action": "REQUIRE_APPROVAL",
        "enforcement_mode": "ALWAYS",
        "governance_tier": 3,
    },
    {
        "name": "Allow file edits under D:\\Ideas only",
        "plain_english": (
            "Allow Daena to write any file under D:\\Ideas\\ but block everything "
            "outside, especially under C:\\Users\\masou\\.ssh and other secret paths."
        ),
        "trigger": "FS:write",
        "condition": "path NOT STARTSWITH 'D:\\\\Ideas\\\\'",
        "action": "BLOCK",
        "enforcement_mode": "ALWAYS",
        "governance_tier": 4,
    },
    {
        "name": "Log every external API call",
        "plain_english": (
            "Log every external API call in the audit trail with cost and "
            "latency. This is observability, not gating."
        ),
        "trigger": "EXTERNAL_API:any",
        "condition": "true",
        "action": "LOG",
        "enforcement_mode": "ALWAYS",
        "governance_tier": 0,
    },
    {
        "name": "Never delete files in Daena-Mind vault",
        "plain_english": (
            "Never delete or overwrite files in D:\\Ideas\\Daena-Mind\\. "
            "That vault is founder-private memory and must be append-only."
        ),
        "trigger": "FS:delete_or_overwrite",
        "condition": "path STARTSWITH 'D:\\\\Ideas\\\\Daena-Mind\\\\'",
        "action": "BLOCK",
        "enforcement_mode": "ALWAYS",
        "governance_tier": 4,
    },
]


def list_seeds() -> list[dict[str, Any]]:
    return [dict(s) for s in POLICY_SEEDS]
