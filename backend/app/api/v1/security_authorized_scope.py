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

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser, require_role
from app.core.logging import get_logger
from app.services.security.yellow_runtime_gate import (
    AuthorizedScope,
    load_authorized_scope,
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
