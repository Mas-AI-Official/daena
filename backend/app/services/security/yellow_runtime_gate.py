"""YELLOW-tier security tool runtime gate.

When a security tool has `tier=YELLOW` (dual-use -- nmap, sqlmap,
BloodHound, nuclei, etc.), Daena will not execute it blindly. This
module provides the runtime gate that callers (scan_workflow,
execution_service, DaenaBot security router) check before dispatch.

## Design

- **Pure function.** `check_yellow_runtime()` takes every input as an
  argument. No DB reads, no global state. That keeps the gate trivial
  to test and safe to call from anywhere in the pipeline without
  worrying about async sessions or request scope.
- **Deny-first.** If any check fails, return a Decision with
  `allow=False` and a human-readable reason. Callers should surface
  the reason verbatim.
- **Defense in depth.** Even if a RED tool somehow reaches runtime
  (e.g. a bypass via a future MCP-provided tool), the gate re-checks
  the hackingtool RED denylist and blocks.
- **No secret-leakage in reasons.** Reasons are safe to show the user
  even on the OSS build. They describe the policy, not any tenant
  data.

## Authorized-scope model

Each tenant keeps a list of `authorized_scope` entries describing
what targets the tenant is allowed to probe. An entry can be:
- an exact domain (`example.com`)
- a wildcard subdomain (`*.example.com`)
- an IPv4 CIDR (`10.0.0.0/24`)
- an IPv4 literal (`192.168.1.42`)
- a source-hosted path (`github.com/mas-ai/*`) -- for repos the
  tenant owns

`parse_target()` normalizes a raw target string (URL, IP, hostname)
to a matchable form; `target_matches_scope()` returns True when the
normalized target falls inside any scope entry.

## Storage for the initial commit

We deliberately do NOT add an `authorized_scope` column to the
`Tenant` table yet. Schema changes deserve their own migration
ticket. Instead, authorized scopes live in a JSON file at
`backend/app/data/authorized_scopes.json` (gitignored via the
`backend/app/data/authorized_scopes.json` pattern). The tenant_id
is the dict key. `load_authorized_scope()` is the helper.

When the Tenant-table migration ticket lands, swap
`load_authorized_scope()`'s body to query the DB and the rest of
this file stays unchanged.

## Rate limit

Not in this initial commit. `check_yellow_runtime()` returns a
`rate_limit_key` that callers can feed into an existing rate-limit
service (or a future one). Centralizing the key generation here
keeps the policy-in-one-place.

## Approval-queue entry on first-run

Not in this initial commit either. The gate surfaces
`requires_approval=True` when it sees a first-run-per-project
signal (`is_first_run=True`), and the caller is expected to create
the approval record. The gate itself never writes to the DB.

Follow-up ticket: TICKET-HACKINGTOOL-YELLOW-WIRING wires this gate
into scan_workflow + execution_service + the approval queue.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from app.core.logging import get_logger
from app.services.security.tool_catalog import (
    SecurityTier,
    ToolCatalog,
    is_red_denylisted,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GateDecision:
    """Result of a runtime gate check.

    `allow` is the only field callers need to look at for a yes/no.
    Everything else is diagnostic + downstream enforcement context.
    """
    allow: bool
    reason: str
    tier: SecurityTier | None
    # Caller should (if allow=True) enforce rate limit using this key,
    # and surface/archive the audit log bundle. None when allow=False.
    rate_limit_key: str | None = None
    audit_log: dict[str, Any] = field(default_factory=dict)
    # If True, the tool should not run until an approval-queue entry
    # is created and approved. Caller writes the approval record.
    requires_approval: bool = False


@dataclass(frozen=True, slots=True)
class AuthorizedScope:
    """Normalized set of targets a tenant has declared they are
    authorized to probe. All entries were explicitly declared by the
    tenant in their project settings.
    """
    exact_domains: frozenset[str] = frozenset()
    wildcard_domains: frozenset[str] = frozenset()     # e.g. "example.com" for "*.example.com"
    ipv4_cidrs: tuple[ipaddress.IPv4Network, ...] = ()
    source_paths: frozenset[str] = frozenset()         # e.g. "github.com/mas-ai/"

    @property
    def is_empty(self) -> bool:
        return (
            not self.exact_domains
            and not self.wildcard_domains
            and not self.ipv4_cidrs
            and not self.source_paths
        )


_TOOLS_REQUIRING_FOUNDER: frozenset[str] = frozenset(
    {
        # Active-exploitation subset (audit Q2: AD + active DAST)
        "sqlmap",
        "commix",
        "impacket",
        "netexec",
        "bloodhound",
        "certipy",
        "kerbrute",
        "responder",
        "evil-winrm",
        "sliver",
        "havoc",
        "mythic",
        "pwncat-cs",
        # Any owasp-zap *active* mode falls here too -- callers pass
        # the subcommand in `tool_subcommand` if the distinction matters.
    }
)


# ---------------------------------------------------------------------------
# Target normalization + scope matching
# ---------------------------------------------------------------------------


_IP_LITERAL_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def parse_target(raw: str) -> tuple[Literal["domain", "ipv4", "path", "unknown"], str]:
    """Normalize a raw target string to (kind, canonical_form).

    Accepts URLs (https://...), bare hostnames, IPs, or repo paths.
    Deliberately conservative: ambiguous input returns ("unknown", raw).
    """
    if not raw or not raw.strip():
        return ("unknown", raw)
    s = raw.strip()

    # URL form: strip scheme + path, keep host
    if "://" in s:
        parsed = urlparse(s)
        host = (parsed.hostname or "").lower()
        if not host:
            return ("unknown", s)
        if _IP_LITERAL_RE.match(host):
            return ("ipv4", host)
        # Source-path URLs like https://github.com/mas-ai/daena/... keep the full path
        if parsed.netloc.lower() in ("github.com", "gitlab.com", "bitbucket.org"):
            path_norm = parsed.path.lstrip("/").rstrip("/")
            return ("path", f"{parsed.netloc.lower()}/{path_norm}")
        return ("domain", host)

    # Bare IP literal
    if _IP_LITERAL_RE.match(s):
        return ("ipv4", s)

    # Bare hostname (contains a dot, no spaces, no slashes)
    if "." in s and " " not in s and "/" not in s:
        return ("domain", s.lower())

    # Source path without scheme (e.g. "github.com/mas-ai/daena")
    if s.lower().startswith(("github.com/", "gitlab.com/", "bitbucket.org/")):
        return ("path", s.lower().rstrip("/"))

    return ("unknown", s)


def target_matches_scope(raw_target: str, scope: AuthorizedScope) -> bool:
    """True when `raw_target` falls inside any entry in `scope`."""
    kind, normalized = parse_target(raw_target)

    if kind == "domain":
        if normalized in scope.exact_domains:
            return True
        # wildcard check: "*.example.com" stored as "example.com".
        # Match if target is that domain OR any subdomain of it.
        parts = normalized.split(".")
        for i in range(len(parts)):
            candidate = ".".join(parts[i:])
            if candidate in scope.wildcard_domains:
                return True
        return False

    if kind == "ipv4":
        try:
            ip = ipaddress.ip_address(normalized)
        except ValueError:
            return False
        return any(ip in cidr for cidr in scope.ipv4_cidrs)

    if kind == "path":
        for prefix in scope.source_paths:
            # prefix stored like "github.com/mas-ai/"; normalized is
            # "github.com/mas-ai/daena/subdir" -> match by startswith
            if normalized.startswith(prefix.rstrip("/") + "/") or normalized == prefix.rstrip("/"):
                return True
        return False

    return False


# ---------------------------------------------------------------------------
# Authorized-scope storage (JSON-file backed; swap to DB later)
# ---------------------------------------------------------------------------


_SCOPES_JSON_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "authorized_scopes.json"
)


def load_authorized_scope(tenant_id: str) -> AuthorizedScope:
    """Return the tenant's declared scope, or an empty AuthorizedScope
    when the tenant has not configured one.

    Empty scope means "this tenant cannot run any YELLOW tool until
    they declare what they own." Deny-by-default.
    """
    if not _SCOPES_JSON_PATH.exists():
        return AuthorizedScope()
    try:
        data = json.loads(_SCOPES_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error(
            "yellow_gate.scopes_read_failed",
            path=str(_SCOPES_JSON_PATH),
            error=str(exc),
        )
        return AuthorizedScope()

    raw = data.get(str(tenant_id))
    if not raw or not isinstance(raw, dict):
        return AuthorizedScope()

    exact = frozenset(str(d).lower() for d in raw.get("exact_domains", []) if d)
    wildcard = frozenset(str(d).lower() for d in raw.get("wildcard_domains", []) if d)
    cidrs_in = raw.get("ipv4_cidrs", []) or []
    cidrs: list[ipaddress.IPv4Network] = []
    for c in cidrs_in:
        try:
            cidrs.append(ipaddress.IPv4Network(str(c), strict=False))
        except (ValueError, TypeError):
            logger.warning("yellow_gate.bad_cidr", cidr=str(c), tenant=str(tenant_id))
            continue
    paths = frozenset(str(p).lower() for p in raw.get("source_paths", []) if p)

    return AuthorizedScope(
        exact_domains=exact,
        wildcard_domains=wildcard,
        ipv4_cidrs=tuple(cidrs),
        source_paths=paths,
    )


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def check_yellow_runtime(
    tool_name: str,
    target: str,
    *,
    user_role: str,
    tenant_id: str,
    user_id: str,
    session_id: str | None = None,
    is_first_run_in_project: bool = False,
    tool_subcommand: str | None = None,
    catalog: ToolCatalog | None = None,
    authorized_scope: AuthorizedScope | None = None,
) -> GateDecision:
    """Decide whether a security-tool invocation may proceed.

    Call sites: scan_workflow._dispatch_tool, execution_service.execute_tool,
    DaenaBot security router.

    Parameters
    ----------
    tool_name      -- the catalog name of the tool (e.g. "sqlmap")
    target         -- raw target string (URL, IP, hostname, repo path)
    user_role      -- "FOUNDER" / "ADMIN" / "MANAGER" / "OPERATOR" / "VIEWER" / "AUDITOR"
    tenant_id      -- caller's tenant (for scope lookup)
    user_id        -- caller's user id (for audit log)
    session_id     -- optional session id (for audit log)
    is_first_run_in_project
                   -- caller should pass True when this is the first
                      time the user runs this tool in this project.
                      Triggers `requires_approval=True`.
    tool_subcommand
                   -- optional subcommand (for tools like owasp-zap
                      where "active scan" differs from "passive proxy").
    catalog        -- optional ToolCatalog instance; when omitted a
                      fresh one is built. Pass yours if you already
                      have one (faster).
    authorized_scope
                   -- optional scope override. When omitted,
                      `load_authorized_scope(tenant_id)` is called.

    Returns
    -------
    GateDecision: see dataclass docstring.
    """
    # 1. Hard RED deny -- even if a future caller mutates the catalog
    #    in-memory, the denylist wins. Matches the register-time gate
    #    in tool_catalog.register_tool.
    if is_red_denylisted(tool_name):
        return GateDecision(
            allow=False,
            reason=(
                f"'{tool_name}' is on the hackingtool RED denylist. "
                "Daena does not offer phishing kits, DDoS weapons, RATs, "
                "rootkits, silent keyloggers, wifi jammers, or Android "
                "payload generators. See docs/HACKINGTOOL_INTEGRATION.md."
            ),
            tier=SecurityTier.RED,
        )

    # 2. Look up the tool in the catalog
    cat = catalog or ToolCatalog()
    tool = cat.get_tool(tool_name) if hasattr(cat, "get_tool") else cat._tools.get(tool_name)
    if tool is None:
        return GateDecision(
            allow=False,
            reason=(
                f"Unknown security tool '{tool_name}'. Daena only dispatches "
                "catalog-listed tools. Propose adding the tool to "
                "backend/app/data/hackingtool_catalog.json."
            ),
            tier=None,
        )

    tier = tool.tier

    # 3. GREEN -- always allowed. Still audit-logged.
    if tier == SecurityTier.GREEN:
        return GateDecision(
            allow=True,
            reason=f"GREEN-tier tool '{tool_name}' -- auto-approved.",
            tier=SecurityTier.GREEN,
            rate_limit_key=f"sec:green:{user_id}:{tool_name}",
            audit_log={
                "event": "security_tool_allowed",
                "tier": "green",
                "tool": tool_name,
                "target": target,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "subcommand": tool_subcommand,
            },
        )

    # 4. YELLOW gate. (RED cannot reach here -- catalog register-time
    #    gate blocks RED at load, and step 1 blocks by name.)
    if tier != SecurityTier.YELLOW:
        return GateDecision(
            allow=False,
            reason=f"Unexpected tier {tier!r} for '{tool_name}'.",
            tier=tier,
        )

    # 4a. Role check -- FOUNDER always allowed; ADMIN + MANAGER allowed
    #     for the general YELLOW pool but NOT for active-exploitation
    #     subset (AD + DAST + C2); lower roles denied.
    allowed_roles = {"FOUNDER"}
    if tool_name.lower() not in _TOOLS_REQUIRING_FOUNDER:
        allowed_roles |= {"ADMIN", "MANAGER"}
    if user_role.upper() not in allowed_roles:
        return GateDecision(
            allow=False,
            reason=(
                f"YELLOW-tier tool '{tool_name}' requires role "
                f"{sorted(allowed_roles)}. Your role is '{user_role}'."
            ),
            tier=SecurityTier.YELLOW,
        )

    # 4b. Authorized-scope check -- target must match tenant's
    #     declared scope. Empty scope = no YELLOW tool may run.
    scope = authorized_scope if authorized_scope is not None else load_authorized_scope(tenant_id)
    if scope.is_empty:
        return GateDecision(
            allow=False,
            reason=(
                f"YELLOW-tier tool '{tool_name}' requires the tenant to have "
                "at least one entry in authorized_scope. Declare the domains "
                "or IP ranges this tenant owns in project settings, then "
                "retry."
            ),
            tier=SecurityTier.YELLOW,
        )
    if not target_matches_scope(target, scope):
        return GateDecision(
            allow=False,
            reason=(
                f"Target '{target}' is outside the tenant's authorized_scope. "
                "YELLOW-tier security tools may only be run against targets "
                "the tenant has declared they own. Add the target (or its "
                "parent domain/CIDR) to authorized_scope and retry."
            ),
            tier=SecurityTier.YELLOW,
        )

    # 4c. First-run-in-project -> requires an approval record. Gate
    #     itself does not write the record; caller does.
    requires_approval = is_first_run_in_project

    return GateDecision(
        allow=True,
        reason=(
            f"YELLOW-tier tool '{tool_name}' approved: role={user_role}, "
            "target in authorized_scope"
            + (", first-run approval needed" if requires_approval else "")
            + "."
        ),
        tier=SecurityTier.YELLOW,
        rate_limit_key=f"sec:yellow:{user_id}:{tool_name}",
        audit_log={
            "event": "security_tool_yellow_allowed",
            "tier": "yellow",
            "tool": tool_name,
            "target": target,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "session_id": session_id,
            "subcommand": tool_subcommand,
            "scope_matched": True,
            "requires_approval": requires_approval,
        },
        requires_approval=requires_approval,
    )
