"""Skill-level Asset Shield consent gate.

PR-CONN-ASSET-SHIELD-CONSENT-DESIGN (Sprint-4 PR-3, 2026-05-03)
ships the FOUNDATION for the consent layer that will gate Phase 3
write actions. NO write skill exists in PHASE2_ALLOWLIST today, so
the gate is dormant by design -- but the test suite includes a
synthetic-write fixture that proves the gate WOULD block it.

Distinction from the existing ``app.services.security.asset_shield.
consent_token`` module: that one mints one-shot CREDENTIAL leases
for offensive-security pivots (a Founder-only surface). This one
gates skill EXECUTION, asks the operator for explicit approval
before a Phase 3 write fires, and is part of the regular skill
flow.

Concepts
--------

* **SkillConsentCategory** -- coarse categorization of risk classes.
  ``write_external``, ``send_message``, ``payment``,
  ``browser_action``, ``security_scan``, ``read_sensitive``.
* **SkillConsentRequest** -- "the executor wants to run X with category
  Y, please confirm". Crafted by the executor; surfaced to the
  operator via the approval queue UI.
* **SkillConsentGrant** -- operator's approval. Bound to (tenant_id,
  plugin_id, skill_id, category). Single-use by default; the executor
  consumes and discards.
* **categorize_skill(entry)** -- pure function. Classifies a
  ``SkillToolMapping`` into a category, or returns None for skills
  that need no consent (current Phase 2 read-only catalog -> all None).
* **check_consent_or_request(entry, ...)** -- the executor-side
  gate. Returns ``None`` if no consent needed (proceed), else returns
  a ``SkillConsentRequest`` the executor surfaces as a needs_consent
  outcome.
* **ConsentStore** -- in-memory grant store with TTL + single-use
  semantics. Future PR can swap to DB-backed.

Honesty rules
-------------

* The gate is OFF for read_only=True skills today. There is NO
  currently-live skill that requires consent. The
  ``test_no_phase2_skill_currently_requires_consent`` invariant pins
  this: if a future PR adds a write skill, it MUST also wire the
  consent flow OR explicitly opt out (rare, audit-logged).
* Grant matching is exact: (tenant, plugin_id, skill_id, category).
  An operator approval for ``app-gmail:summarize_unread / read_sensitive``
  does NOT carry over to ``app-gmail:draft_reply / send_message``.
* Single-use by default. ``acknowledge_grant()`` returns the grant
  AND deletes it -- so a follow-up call requires fresh consent.
* TTL default 5 minutes, hard cap 30 minutes. The grant carries an
  ``expires_at`` and is rejected after that.
* No token, no body, no operator input value lives in the consent
  request OR grant -- only the (plugin, skill, category) tuple
  + a UUID + timestamps.

What this PR DOES NOT do
------------------------

* No write skill is enabled in PHASE2_ALLOWLIST.
* No global governance mode is changed.
* No new HTTP route is added (the executor consumes the in-memory
  store directly; the future approval-queue UI will write to it).
* No frontend modal is wired -- a skeleton component lands separately.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.services.connection_v2.skill_executor import SkillToolMapping

logger = get_logger(__name__)


# Hard caps -- mirrors the existing offensive-ops consent_token shape.
DEFAULT_GRANT_TTL_SECONDS = 5 * 60         # 5 minutes
MAX_GRANT_TTL_SECONDS = 30 * 60            # 30 minutes hard cap


# ──────────────────────────────────────────────────────────────────
# Categories
# ──────────────────────────────────────────────────────────────────


class SkillConsentCategory(str, Enum):
    """Coarse-grained risk class. Each category triggers a different
    operator-facing message + audit-trail entry.

    Adding a new category MUST:
      1. Add the enum value here (lowercase snake_case).
      2. Update ``categorize_skill`` to map the relevant skills.
      3. Update the operator-facing copy in the frontend modal.
      4. Pin via test invariant if the new category should fire on
         specific (plugin, skill) pairs.
    """

    READ_SENSITIVE = "read_sensitive"
    WRITE_EXTERNAL = "write_external"
    SEND_MESSAGE = "send_message"
    PAYMENT = "payment"
    BROWSER_ACTION = "browser_action"
    SECURITY_SCAN = "security_scan"


# ──────────────────────────────────────────────────────────────────
# Errors -- safe by design (no operator data in the message)
# ──────────────────────────────────────────────────────────────────


class SkillConsentError(Exception):
    """Base error for the consent gate."""


class SkillConsentExpired(SkillConsentError):
    pass


class SkillConsentScopeMismatch(SkillConsentError):
    pass


# ──────────────────────────────────────────────────────────────────
# Request / Grant shapes
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SkillConsentRequest:
    """Crafted by the executor; surfaced to the operator.

    The request is the question: "the operator wants to run X with
    risk category Y, do they approve?". The frontend renders this
    as a modal (Sprint-4 PR-3 ships the design only, not the wiring).
    """

    request_id: str
    tenant_id: str
    plugin_id: str
    skill_id: str
    category: SkillConsentCategory
    requested_at: float
    operator_facing_summary: str


@dataclass
class SkillConsentGrant:
    """Operator's approval. Stored short-term + single-use."""

    grant_id: str
    tenant_id: str
    plugin_id: str
    skill_id: str
    category: SkillConsentCategory
    granted_at: float
    expires_at: float
    consumed: bool = False


# ──────────────────────────────────────────────────────────────────
# Categorization
# ──────────────────────────────────────────────────────────────────


# Plugin id prefixes / specific plugin ids that imply a category for
# any non-read_only skill on that plugin. Mapping keeps the rule
# table small + auditable. Order: most specific first.
_PLUGIN_CATEGORY_HINTS: tuple[tuple[str, SkillConsentCategory], ...] = (
    # Payment surfaces -- highest risk, never auto-approve.
    ("mcp-stripe", SkillConsentCategory.PAYMENT),
    ("app-stripe-oauth", SkillConsentCategory.PAYMENT),
    # Communication -- explicit message-sending category.
    ("mcp-slack", SkillConsentCategory.SEND_MESSAGE),
    ("app-slack", SkillConsentCategory.SEND_MESSAGE),
    ("app-gmail", SkillConsentCategory.SEND_MESSAGE),
    # Browser automation -- can navigate to ANY url, including
    # external; needs explicit approval.
    ("mcp-playwright", SkillConsentCategory.BROWSER_ACTION),
    ("mcp-chrome-devtools", SkillConsentCategory.BROWSER_ACTION),
    # Security scans -- destructive category for offensive ops.
    ("mcp-security-scanner", SkillConsentCategory.SECURITY_SCAN),
)


# Skill id substrings that strongly imply a category regardless of
# plugin. Matches AFTER the plugin hint table.
_SKILL_NAME_CATEGORY_HINTS: tuple[tuple[str, SkillConsentCategory], ...] = (
    ("send", SkillConsentCategory.SEND_MESSAGE),
    ("post", SkillConsentCategory.SEND_MESSAGE),
    ("draft", SkillConsentCategory.SEND_MESSAGE),
    ("reply", SkillConsentCategory.SEND_MESSAGE),
    ("create_pull_request", SkillConsentCategory.WRITE_EXTERNAL),
    ("merge_pull_request", SkillConsentCategory.WRITE_EXTERNAL),
    ("create_issue", SkillConsentCategory.WRITE_EXTERNAL),
    ("update", SkillConsentCategory.WRITE_EXTERNAL),
    ("delete", SkillConsentCategory.WRITE_EXTERNAL),
    ("upload", SkillConsentCategory.WRITE_EXTERNAL),
    ("payment", SkillConsentCategory.PAYMENT),
    ("refund", SkillConsentCategory.PAYMENT),
    ("charge", SkillConsentCategory.PAYMENT),
)


def categorize_skill(entry: "SkillToolMapping") -> SkillConsentCategory | None:
    """Pure: classify a skill into a consent category, or None.

    Rule order:
      1. read_only=True -> None (no consent needed; this is the
         current Phase 2 universe).
      2. Plugin-id hint table (Stripe/Slack/Gmail/Playwright/etc.).
      3. Skill-id substring hint (send / draft / delete / etc.).
      4. Default for any non-read-only skill -> WRITE_EXTERNAL.

    Honesty: a future write skill that escapes all of these tables
    STILL gets WRITE_EXTERNAL by default -- the gate is conservative
    by construction.
    """
    if entry.read_only:
        return None

    for prefix, category in _PLUGIN_CATEGORY_HINTS:
        if entry.plugin_id == prefix or entry.plugin_id.startswith(prefix + ":"):
            return category

    for substring, category in _SKILL_NAME_CATEGORY_HINTS:
        if substring in entry.skill_id.lower():
            return category

    return SkillConsentCategory.WRITE_EXTERNAL


# ──────────────────────────────────────────────────────────────────
# Store -- in-memory, single-process. Future PR can swap to DB.
# ──────────────────────────────────────────────────────────────────


class ConsentStore:
    """Per-process, in-memory grant store.

    Single-process is intentional for the foundation -- multi-instance
    deployment is gated on the V2 production rollout, which gets its
    own consent storage PR. For dev + tests this is sufficient.

    The store survives the lifetime of the FastAPI process. Grants
    expire on read (lazy GC).
    """

    def __init__(self) -> None:
        self._grants: dict[str, SkillConsentGrant] = {}

    # ── Public API ──

    def grant(
        self,
        *,
        tenant_id: str,
        plugin_id: str,
        skill_id: str,
        category: SkillConsentCategory,
        ttl_seconds: int = DEFAULT_GRANT_TTL_SECONDS,
    ) -> SkillConsentGrant:
        """Record an operator grant. Returns the grant object."""
        ttl = max(1, min(MAX_GRANT_TTL_SECONDS, ttl_seconds))
        now = time.time()
        grant = SkillConsentGrant(
            grant_id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            plugin_id=plugin_id,
            skill_id=skill_id,
            category=category,
            granted_at=now,
            expires_at=now + ttl,
        )
        self._grants[grant.grant_id] = grant
        logger.info(
            "skill_consent.grant_recorded",
            grant_id=grant.grant_id,
            tenant_id=str(tenant_id),
            plugin_id=plugin_id,
            skill_id=skill_id,
            category=category.value,
            ttl_seconds=ttl,
        )
        return grant

    def find_active(
        self,
        *,
        tenant_id: str,
        plugin_id: str,
        skill_id: str,
        category: SkillConsentCategory,
    ) -> SkillConsentGrant | None:
        """Return an active (unconsumed, unexpired) grant matching
        (tenant, plugin, skill, category) -- or None."""
        now = time.time()
        for g in list(self._grants.values()):
            if g.expires_at < now:
                # Lazy GC.
                self._grants.pop(g.grant_id, None)
                continue
            if g.consumed:
                continue
            if (
                g.tenant_id == str(tenant_id)
                and g.plugin_id == plugin_id
                and g.skill_id == skill_id
                and g.category == category
            ):
                return g
        return None

    def acknowledge(self, grant_id: str) -> SkillConsentGrant | None:
        """Mark grant consumed + return it. None if not found / expired."""
        g = self._grants.get(grant_id)
        if g is None:
            return None
        if g.expires_at < time.time():
            self._grants.pop(grant_id, None)
            raise SkillConsentExpired(
                f"Grant {grant_id} expired at {g.expires_at:.0f}"
            )
        if g.consumed:
            return None
        g.consumed = True
        logger.info(
            "skill_consent.grant_consumed",
            grant_id=grant_id,
            plugin_id=g.plugin_id,
            skill_id=g.skill_id,
            category=g.category.value,
        )
        return g

    # ── Test helpers ──

    def clear(self) -> None:
        self._grants.clear()


# Module singleton -- single per-process store.
_DEFAULT_STORE = ConsentStore()


def get_default_store() -> ConsentStore:
    """Public accessor; tests inject their own via SkillExecutor."""
    return _DEFAULT_STORE


# ──────────────────────────────────────────────────────────────────
# Executor-side gate
# ──────────────────────────────────────────────────────────────────


def check_consent_or_request(
    entry: "SkillToolMapping",
    *,
    tenant_id: UUID,
    store: ConsentStore | None = None,
) -> tuple[bool, SkillConsentCategory | None, SkillConsentRequest | None]:
    """Gate function the executor calls before running a skill.

    Returns ``(allowed, category, request)``:

      * ``allowed=True, category=None, request=None`` -- skill needs
        no consent (current Phase 2 universe).
      * ``allowed=True, category=<X>, request=None`` -- skill needs
        consent AND a matching grant was found + consumed.
      * ``allowed=False, category=<X>, request=<request>`` -- skill
        needs consent and NO matching grant exists; the executor
        surfaces ``request`` to the operator via needs_consent outcome.

    The returned ``request`` carries an opaque ``request_id`` that the
    operator's approval queue uses to mint a grant via
    ``ConsentStore.grant``. The executor on the next call finds that
    grant and proceeds.
    """
    category = categorize_skill(entry)
    if category is None:
        return True, None, None

    s = store or _DEFAULT_STORE
    grant = s.find_active(
        tenant_id=str(tenant_id),
        plugin_id=entry.plugin_id,
        skill_id=entry.skill_id,
        category=category,
    )
    if grant is None:
        request = SkillConsentRequest(
            request_id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            plugin_id=entry.plugin_id,
            skill_id=entry.skill_id,
            category=category,
            requested_at=time.time(),
            operator_facing_summary=(
                f"Daena wants to run {entry.plugin_id}:{entry.skill_id} "
                f"which falls under risk category '{category.value}'. "
                f"Approve to proceed once."
            ),
        )
        return False, category, request

    # Found a matching grant -- consume it.
    consumed = s.acknowledge(grant.grant_id)
    if consumed is None:
        # Race: someone else acknowledged it between find and ack.
        # Treat as no grant.
        return False, category, SkillConsentRequest(
            request_id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            plugin_id=entry.plugin_id,
            skill_id=entry.skill_id,
            category=category,
            requested_at=time.time(),
            operator_facing_summary=(
                f"The previous consent was already used. Approve "
                f"again to run {entry.plugin_id}:{entry.skill_id}."
            ),
        )
    return True, category, None


__all__ = [
    "DEFAULT_GRANT_TTL_SECONDS",
    "MAX_GRANT_TTL_SECONDS",
    "ConsentStore",
    "SkillConsentCategory",
    "SkillConsentError",
    "SkillConsentExpired",
    "SkillConsentGrant",
    "SkillConsentRequest",
    "SkillConsentScopeMismatch",
    "categorize_skill",
    "check_consent_or_request",
    "get_default_store",
]
