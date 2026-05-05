"""REST API for per-tenant authorized_scope management.

Background: YELLOW-tier security tools (nmap, sqlmap, nuclei,
BloodHound, ...) can only run against targets the tenant has
explicitly declared they own. The declaration lives in
backend/app/data/authorized_scopes.json (gitignored; tenant-private).
Migrates to Tenant.settings JSONB in TICKET-HACKINGTOOL-YELLOW-
RUNTIME. This module is the founder-facing CRUD surface over that
JSON.

Endpoints (all founder-gated):
    GET  /security/authorized-scope
        Returns the tenant's current scope as a structured object.
    PUT  /security/authorized-scope
        Replaces the tenant's scope with the submitted body.
    POST /security/authorized-scope/test
        Given a target, returns whether it matches the current scope.
        Useful for the frontend "try before you save" UX.
"""

from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Any

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db, require_role
from app.core.logging import get_logger
from app.services.audit import AuditService
from app.services.security.yellow_runtime_gate import (
    AuthorizedScope,
    load_authorized_scope,
    parse_target,
    target_matches_scope,
    _SCOPES_JSON_PATH,  # noqa: SLF001 -- single source of truth for the path
)

logger = get_logger(__name__)

router = APIRouter()


# ── Request / response shapes ─────────────────────────────────────


class AuthorizedScopeBody(BaseModel):
    """Scope declaration written by the founder.

    Lists MUST be all strings, each entry matching the expected shape
    for its bucket (validated below). Unknown buckets are rejected.
    """

    exact_domains: list[str] = Field(default_factory=list)
    wildcard_domains: list[str] = Field(default_factory=list)
    ipv4_cidrs: list[str] = Field(default_factory=list)
    source_paths: list[str] = Field(default_factory=list)

    @field_validator("exact_domains", "wildcard_domains", mode="before")
    @classmethod
    def _strip_lowercase(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(s).strip().lower() for s in v if str(s).strip()]

    @field_validator("ipv4_cidrs")
    @classmethod
    def _validate_cidrs(cls, v: list[str]) -> list[str]:
        result: list[str] = []
        for c in v:
            s = str(c).strip()
            if not s:
                continue
            try:
                ipaddress.IPv4Network(s, strict=False)
            except ValueError as exc:
                raise ValueError(f"Invalid IPv4 CIDR '{s}': {exc}") from exc
            result.append(s)
        return result

    @field_validator("source_paths", mode="before")
    @classmethod
    def _normalize_source_paths(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            return []
        # Always store lowercase + trailing slash so prefix-match in
        # the gate works predictably.
        out: list[str] = []
        for p in v:
            s = str(p).strip().lower()
            if not s:
                continue
            if not s.endswith("/"):
                s = s + "/"
            out.append(s)
        return out


class AuthorizedScopeResponse(BaseModel):
    exact_domains: list[str]
    wildcard_domains: list[str]
    ipv4_cidrs: list[str]
    source_paths: list[str]
    has_any_entry: bool


class ScopeTestRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=512)


class ScopeTestResponse(BaseModel):
    target: str
    in_scope: bool
    reason: str


# PR-SCAN-ADD-TO-SCOPE-INLINE-CTA (Sprint-9 PR-1):
# append-only single-target add for the founder-only "Add this target
# to Scan Scope" CTA on the /scan page. Distinct from the PUT-replaces-
# all endpoint so a CTA click can never accidentally wipe other entries
# (two-tab race).
class ScopeAddRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=512)
    scope_type: Literal["exact_url", "domain", "wildcard_subdomain"] = "exact_url"


class ScopeAddResponse(BaseModel):
    target: str
    scope_type: str
    bucket: str  # which AuthorizedScope list received the entry
    stored_value: str
    already_present: bool
    scope: AuthorizedScopeResponse


# ── JSON read/write helpers ───────────────────────────────────────


def _read_all_scopes() -> dict[str, Any]:
    if not _SCOPES_JSON_PATH.exists():
        return {}
    try:
        return json.loads(_SCOPES_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(
            "authorized_scope.read_failed",
            path=str(_SCOPES_JSON_PATH),
            error=str(exc),
        )
        return {}


def _write_all_scopes(data: dict[str, Any]) -> None:
    _SCOPES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: stage then rename. Avoids half-written JSON if
    # the process dies mid-write.
    tmp = _SCOPES_JSON_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(_SCOPES_JSON_PATH)


def _scope_to_response(scope: AuthorizedScope) -> AuthorizedScopeResponse:
    return AuthorizedScopeResponse(
        exact_domains=sorted(scope.exact_domains),
        wildcard_domains=sorted(scope.wildcard_domains),
        ipv4_cidrs=[str(c) for c in scope.ipv4_cidrs],
        source_paths=sorted(scope.source_paths),
        has_any_entry=not scope.is_empty,
    )


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("/security/authorized-scope", response_model=AuthorizedScopeResponse)
async def get_authorized_scope(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> AuthorizedScopeResponse:
    """Return the tenant's current authorized_scope for YELLOW tools."""
    scope = load_authorized_scope(str(user.tenant_id))
    return _scope_to_response(scope)


@router.put("/security/authorized-scope", response_model=AuthorizedScopeResponse)
async def put_authorized_scope(
    body: AuthorizedScopeBody,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> AuthorizedScopeResponse:
    """Replace the tenant's authorized_scope. Idempotent.

    Founder-gated. Any non-empty declaration enables YELLOW tool use
    against targets that match. Empty declaration disables ALL YELLOW
    tool execution for the tenant (deny-by-default).
    """
    tenant_key = str(user.tenant_id)
    all_scopes = _read_all_scopes()
    all_scopes[tenant_key] = {
        "exact_domains": body.exact_domains,
        "wildcard_domains": body.wildcard_domains,
        "ipv4_cidrs": body.ipv4_cidrs,
        "source_paths": body.source_paths,
    }
    try:
        _write_all_scopes(all_scopes)
    except OSError as exc:
        logger.error(
            "authorized_scope.write_failed",
            tenant=tenant_key,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="scope_write_failed") from exc
    logger.info(
        "authorized_scope.updated",
        tenant=tenant_key,
        domain_count=len(body.exact_domains) + len(body.wildcard_domains),
        cidr_count=len(body.ipv4_cidrs),
        path_count=len(body.source_paths),
    )
    # Re-read via the gate helper so the response reflects exactly
    # what the gate will see on the next YELLOW-tool call.
    scope = load_authorized_scope(tenant_key)
    return _scope_to_response(scope)


@router.post("/security/authorized-scope/test", response_model=ScopeTestResponse)
async def test_authorized_scope(
    body: ScopeTestRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> ScopeTestResponse:
    """Check whether a target would be allowed under the current scope.

    Frontend uses this for a "try before you save" UX: founder types
    a candidate target, UI pings this endpoint, shows green / red
    before the founder commits.
    """
    scope = load_authorized_scope(str(user.tenant_id))
    if scope.is_empty:
        return ScopeTestResponse(
            target=body.target,
            in_scope=False,
            reason=(
                "No scope declared yet. Add at least one domain or CIDR, then "
                "test again."
            ),
        )
    matched = target_matches_scope(body.target, scope)
    return ScopeTestResponse(
        target=body.target,
        in_scope=matched,
        reason=(
            "Target matches the tenant's authorized_scope. YELLOW tools "
            "can run against it."
            if matched
            else "Target is outside the tenant's authorized_scope. YELLOW "
            "tools will be blocked. Add the target's parent domain or CIDR "
            "to the scope if you own it."
        ),
    )


@router.post("/security/authorized-scope/add", response_model=ScopeAddResponse)
async def add_to_authorized_scope(
    body: ScopeAddRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> ScopeAddResponse:
    """Append a single target to the tenant's authorized_scope.

    PR-SCAN-ADD-TO-SCOPE-INLINE-CTA (Sprint-9 PR-1). Powers the founder-
    only "Add this target to Scan Scope" CTA on the /scan page when a
    scan is blocked by ``target_not_in_scope``.

    Founder-gated. Append-only (read-modify-write). Idempotent: re-add
    on an existing entry returns ``already_present=True`` without a
    duplicate write.

    Hard rules honored from the brief:
      * Never auto-runs a scan after the add. Caller must re-POST to
        ``/scans/start`` explicitly.
      * Never defaults to wildcard scope -- ``scope_type`` defaults to
        ``exact_url`` (host-only).
      * Never weakens ``target_matches_scope``; this endpoint only
        edits the input data the gate consumes.
      * Audits every add as ``security.scope.added_from_scan`` with
        the target + scope_type but NO secrets.
    """
    raw = body.target.strip()
    kind, normalized = parse_target(raw)

    # Reject targets the gate cannot classify; otherwise the operator
    # could land an entry that never matches the gate's parse step.
    if kind == "unknown":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "target_unparseable",
                "target": raw,
                "hint": "Provide a URL, bare hostname, IPv4 address, or "
                "github.com / gitlab.com / bitbucket.org repo path.",
            },
        )

    # Only domain-kind targets accept the wildcard option. Refusing
    # wildcard for IP / path keeps the gate's semantics intact (a CIDR
    # already covers a network; ``wildcard_domains`` does not match IPs).
    if body.scope_type == "wildcard_subdomain" and kind != "domain":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "scope_type_mismatch",
                "target": raw,
                "kind": kind,
                "hint": "Wildcard subdomain only applies to domain targets.",
            },
        )

    tenant_key = str(user.tenant_id)
    all_scopes = _read_all_scopes()
    current = all_scopes.get(tenant_key) or {
        "exact_domains": [],
        "wildcard_domains": [],
        "ipv4_cidrs": [],
        "source_paths": [],
    }

    bucket: str
    stored_value: str
    if kind == "domain":
        if body.scope_type == "wildcard_subdomain":
            bucket = "wildcard_domains"
            stored_value = normalized
        else:
            bucket = "exact_domains"
            stored_value = normalized
    elif kind == "ipv4":
        bucket = "ipv4_cidrs"
        stored_value = f"{normalized}/32"
    elif kind == "path":
        bucket = "source_paths"
        stored_value = normalized.rstrip("/") + "/"
    else:  # pragma: no cover -- guarded above
        raise HTTPException(status_code=400, detail={"code": "target_unparseable"})

    existing = list(current.get(bucket, []))
    already_present = stored_value in existing
    if not already_present:
        existing.append(stored_value)
        current[bucket] = existing
        all_scopes[tenant_key] = current
        try:
            _write_all_scopes(all_scopes)
        except OSError as exc:
            logger.error(
                "authorized_scope.add_write_failed",
                tenant=tenant_key, error=str(exc),
            )
            raise HTTPException(status_code=500, detail="scope_write_failed") from exc

    # Audit-log the add. NEVER include secrets; target + scope_type are
    # already part of the founder's intent.
    try:
        audit = AuditService(db)
        await audit.log_decision(
            tenant_id=user.tenant_id,
            actor_id=user.id,
            actor_type="FOUNDER",
            action_type="security.scope.added_from_scan",
            action_params={
                "target": raw,
                "kind": kind,
                "scope_type": body.scope_type,
                "bucket": bucket,
                "stored_value": stored_value,
                "already_present": already_present,
            },
            result="ALLOWED",
            risk_level="HIGH",
            governance_tier=4,
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001 -- audit failure must not block the operator
        logger.error(
            "authorized_scope.audit_failed",
            tenant=tenant_key, error=str(exc),
        )

    logger.info(
        "authorized_scope.added_from_scan",
        tenant=tenant_key,
        kind=kind,
        scope_type=body.scope_type,
        bucket=bucket,
        already_present=already_present,
    )

    refreshed = load_authorized_scope(tenant_key)
    return ScopeAddResponse(
        target=raw,
        scope_type=body.scope_type,
        bucket=bucket,
        stored_value=stored_value,
        already_present=already_present,
        scope=_scope_to_response(refreshed),
    )
