"""Trust Policy Engine -- Sprint-18 PR-1 (2026-05-06).

Layer ON TOP of ``trust_ladder`` (record-only counters) that applies
POLICY: which (tool, template_class) pairs are eligible to graduate,
which are forbidden forever, what tier the operator has granted,
and what auto-approval decision the dispatcher should reach for a
given incoming request.

Walls (every one of these MUST pass for auto-approval to fire):

  1. tool_id not in TRUST_FORBIDDEN_TOOLS
     (send_existing_draft / file_change_proposal.apply /
      git_commit_approved_patch never graduate, ever).
  2. initiator == DispatchInitiator.OPERATOR
     (scheduler / self-healing / delegated dispatches always pay
      full approval freight, regardless of tier).
  3. tool_id in TRUST_ELIGIBLE_TOOLS
     (only the three low-risk draft-class tools graduate).
  4. policy.max_auto_tier == AUTO_APPROVE_LOW_RISK
     (founder MUST explicitly grant; default is NONE).
  5. trust_ladder.rejection_count == 0
     (any rejection wipes graduation).
  6. trust_ladder.approvals_count >= MIN_APPROVALS_TO_GRADUATE
     (default 5).

The fourth tier ``AUTO_EXECUTE_LOW_RISK_LOCAL`` is reserved in the
enum but UNREACHABLE in Sprint-18; future sprints unlock it.

Daena CANNOT raise her own tier:

  ``set_max_auto_tier`` requires ``is_founder=True`` and a
  confirmation phrase string that matches an expected template.
  This is checked at the function call site -- the API endpoint
  layered on top is responsible for verifying JWT + adding
  ``is_founder``. Tool dispatches NEVER call this function.

Persistence: JSON file at ``backend/.trust_policy.json`` (gitignored)
mirroring the trust_ladder pattern. Multi-tenant cloud will move
to DB; founder-install single-process is fine on JSON.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from app.core.logging import get_logger
from app.services import trust_ladder

logger = get_logger(__name__)

_POLICY_FILE = Path(__file__).resolve().parents[2] / ".trust_policy.json"


# ────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────


class TrustTier(str, Enum):
    """Four-tier ladder. Sprint-18 unlocks tiers 0..2 only."""

    NONE = "none"
    SUGGEST_ONLY = "suggest_only"
    AUTO_APPROVE_LOW_RISK = "auto_approve_low_risk"
    # Reserved. UNREACHABLE in Sprint-18. Future sprint will allow
    # local-only execute for tools whose handler has zero remote
    # side effects (file_change_proposal create-only artifact).
    AUTO_EXECUTE_LOW_RISK_LOCAL = "auto_execute_low_risk_local"


class DispatchInitiator(str, Enum):
    """Who started the dispatch. Trust graduation is initiator-aware."""

    OPERATOR = "operator"
    SCHEDULER = "scheduler"
    SELF_HEALING = "self_healing"
    DELEGATED = "delegated"


# ────────────────────────────────────────────────────────────────────
# Tool eligibility sets (LOCKED Sprint-18)
# ────────────────────────────────────────────────────────────────────

# Eligible to graduate: low-risk, reversible, draft-class.
TRUST_ELIGIBLE_TOOLS: frozenset[str] = frozenset({
    "gmail.create_draft",
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
})

# Forbidden FOREVER: anything that sends to humans, executes a
# patch on disk, or rewrites repo history.
TRUST_FORBIDDEN_TOOLS: frozenset[str] = frozenset({
    "gmail.send_existing_draft",
    "local.file_change_proposal.apply",
    "local.git_commit_approved_patch",
})

# Default minimum approvals to graduate.
MIN_APPROVALS_TO_GRADUATE: int = 5


# ────────────────────────────────────────────────────────────────────
# Template class hashing
# ────────────────────────────────────────────────────────────────────


_SUBJECT_WORD_RE = re.compile(r"[a-z]+")


def compute_template_class(tool_id: str, payload: dict) -> str:
    """Stable identifier for "this kind of action".

    Trust graduates per-(tool_id, template_class), NOT per-tool. So
    "5 approvals of cold-outreach drafts to gmail.com" graduates
    only that class -- a draft to a different domain still asks.

    Falls back to ``{tool_id}:default`` for unknown tools.
    """
    if not isinstance(payload, dict):
        return f"{tool_id}:default"

    if tool_id == "gmail.create_draft":
        # Domain class + subject-stem class
        to_field = payload.get("to") or []
        if isinstance(to_field, str):
            to_field = [to_field]
        if not isinstance(to_field, list):
            to_field = []
        domains = sorted({
            str(addr).split("@")[-1].lower()
            for addr in to_field
            if isinstance(addr, str) and "@" in addr
        })
        domain_key = ",".join(domains) or "no_domain"
        subject = str(payload.get("subject") or "").strip().lower()
        words = _SUBJECT_WORD_RE.findall(subject)[:4]
        subject_key = "_".join(words) or "no_subject"
        return f"gmail.create_draft:{domain_key}:{subject_key}"

    if tool_id == "calendar.create_tentative_event_without_invites":
        cal_id = str(payload.get("calendar_id") or "primary").lower()
        duration_raw = payload.get("duration_minutes") or 30
        try:
            duration = int(duration_raw)
        except (TypeError, ValueError):
            duration = 30
        if duration <= 30:
            bucket = "short"
        elif duration <= 60:
            bucket = "medium"
        else:
            bucket = "long"
        return f"calendar.create_tentative:{cal_id}:{bucket}"

    if tool_id == "local.file_change_proposal":
        path = str(payload.get("target_path_repo_relative") or "")
        top = path.split("/")[0] if "/" in path else (path or "root")
        change = str(payload.get("change_type") or "modify").lower()
        return f"local.file_change_proposal:{top}:{change}"

    return f"{tool_id}:default"


# ────────────────────────────────────────────────────────────────────
# Policy storage
# ────────────────────────────────────────────────────────────────────


@dataclass
class TrustPolicyEntry:
    """Per (tool_id, template_class) policy row.

    ``max_auto_tier`` is the founder-set ceiling; auto-approval
    only fires when this is AUTO_APPROVE_LOW_RISK and ladder
    counters meet the threshold.
    """

    tool_id: str
    template_class: str
    max_auto_tier: TrustTier = TrustTier.NONE
    locked_reason: str | None = None
    last_updated_by_user_id: str | None = None
    updated_at: str | None = None

    @property
    def key(self) -> str:
        return f"{self.tool_id}::{self.template_class}"


def _read_all_policies() -> dict[str, TrustPolicyEntry]:
    if not _POLICY_FILE.exists():
        return {}
    try:
        raw = json.loads(_POLICY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("trust_policy.read_failed", error=str(exc))
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, TrustPolicyEntry] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        try:
            tier_raw = str(val.get("max_auto_tier", TrustTier.NONE.value))
            try:
                tier = TrustTier(tier_raw)
            except ValueError:
                tier = TrustTier.NONE
            entry = TrustPolicyEntry(
                tool_id=str(val.get("tool_id", "")),
                template_class=str(val.get("template_class", "")),
                max_auto_tier=tier,
                locked_reason=val.get("locked_reason"),
                last_updated_by_user_id=val.get("last_updated_by_user_id"),
                updated_at=val.get("updated_at"),
            )
            out[entry.key] = entry
        except (TypeError, ValueError) as exc:
            logger.warning("trust_policy.entry_skip", key=key, error=str(exc))
    return out


def _write_all_policies(entries: dict[str, TrustPolicyEntry]) -> None:
    payload = {}
    for k, v in entries.items():
        d = asdict(v)
        d["max_auto_tier"] = v.max_auto_tier.value
        payload[k] = d
    try:
        _POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _POLICY_FILE.write_text(
            json.dumps(payload, indent=2), encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("trust_policy.write_failed", error=str(exc))


def get_policy(
    *, tool_id: str, template_class: str,
) -> TrustPolicyEntry:
    """Return existing policy or a default NONE-tier policy.

    Never returns None -- callers can assume an entry shape. The
    default entry is NOT persisted; only set_max_auto_tier writes.
    """
    entries = _read_all_policies()
    key = f"{tool_id}::{template_class}"
    found = entries.get(key)
    if found is not None:
        return found
    locked_reason: str | None = None
    if tool_id in TRUST_FORBIDDEN_TOOLS:
        locked_reason = "tool_forbidden_from_graduation"
    elif tool_id not in TRUST_ELIGIBLE_TOOLS:
        locked_reason = "tool_not_in_eligible_set"
    return TrustPolicyEntry(
        tool_id=tool_id,
        template_class=template_class,
        max_auto_tier=TrustTier.NONE,
        locked_reason=locked_reason,
    )


def list_policies() -> list[TrustPolicyEntry]:
    return list(_read_all_policies().values())


# ────────────────────────────────────────────────────────────────────
# Founder-only mutation
# ────────────────────────────────────────────────────────────────────


def expected_confirmation_phrase(tool_id: str, tier: TrustTier) -> str:
    """The exact phrase the founder must type to raise a tier.

    Locking the phrase here means the API endpoint can show it to
    the founder and the trust_policy module verifies it -- prompt
    injection cannot bypass this because the phrase is a static
    template, not an LLM output.
    """
    return f"I authorize trust tier {tier.value} for {tool_id}"


def set_max_auto_tier(
    *,
    tool_id: str,
    template_class: str,
    tier: TrustTier,
    requested_by_user_id: str,
    is_founder: bool,
    confirmation_phrase: str,
) -> TrustPolicyEntry:
    """Founder-only tier mutation.

    Raises:
        PermissionError: caller is not founder.
        ValueError: confirmation_phrase mismatch, tool forbidden,
            tier reserved, or rejections force NONE.
    """
    if not is_founder:
        raise PermissionError("trust_tier_raise_founder_only")

    if tier == TrustTier.AUTO_EXECUTE_LOW_RISK_LOCAL:
        # Reserved tier; not unlocked in Sprint-18.
        raise ValueError("tier_reserved_unreachable_in_sprint18")

    if tool_id in TRUST_FORBIDDEN_TOOLS:
        raise ValueError("tool_forbidden_from_graduation")

    if tool_id not in TRUST_ELIGIBLE_TOOLS:
        raise ValueError("tool_not_in_eligible_set")

    expected = expected_confirmation_phrase(tool_id, tier)
    if (confirmation_phrase or "").strip() != expected:
        raise ValueError("confirmation_phrase_mismatch")

    # Rejection wall: rejection_count > 0 forces NONE.
    ladder = trust_ladder.get_entry(
        tool_id=tool_id, template_id=template_class,
    )
    if (
        ladder is not None
        and ladder.rejection_count > 0
        and tier != TrustTier.NONE
    ):
        raise ValueError("rejections_force_tier_none")

    entries = _read_all_policies()
    key = f"{tool_id}::{template_class}"
    entry = entries.get(key) or TrustPolicyEntry(
        tool_id=tool_id, template_class=template_class,
    )
    entry.max_auto_tier = tier
    entry.last_updated_by_user_id = requested_by_user_id
    entry.updated_at = datetime.now(UTC).isoformat()
    if tool_id in TRUST_FORBIDDEN_TOOLS:
        entry.locked_reason = "tool_forbidden_from_graduation"
    elif tool_id not in TRUST_ELIGIBLE_TOOLS:
        entry.locked_reason = "tool_not_in_eligible_set"
    else:
        entry.locked_reason = None
    entries[key] = entry
    _write_all_policies(entries)

    logger.info(
        "trust_policy.tier_set",
        tool_id=tool_id,
        template_class=template_class,
        tier=tier.value,
        by=requested_by_user_id,
    )
    return entry


# ────────────────────────────────────────────────────────────────────
# Auto-approval decision
# ────────────────────────────────────────────────────────────────────


@dataclass
class AutoApprovalDecision:
    """Result of evaluating one incoming request against trust policy.

    ``auto_approve`` is the boolean answer; ``reason`` is the stable
    code the audit log records and the UI surfaces ('Why did you
    not auto-approve?'). NEVER an LLM string.
    """

    auto_approve: bool
    reason: str
    template_class: str | None = None
    approvals_count: int = 0
    rejection_count: int = 0
    max_auto_tier: TrustTier = TrustTier.NONE


def should_auto_approve(
    *,
    tool_id: str,
    payload: dict,
    initiator: DispatchInitiator,
    min_approvals: int = MIN_APPROVALS_TO_GRADUATE,
) -> AutoApprovalDecision:
    """Pure decision function. NEVER raises. NEVER mutates state.

    Walls evaluated in order; first refusal wins. The reason code
    is stable so tests + audit + UI can match without parsing.
    """

    # Wall 1: forbidden tools NEVER graduate.
    if tool_id in TRUST_FORBIDDEN_TOOLS:
        return AutoApprovalDecision(
            auto_approve=False,
            reason="tool_forbidden_from_graduation",
            template_class=None,
        )

    # Wall 2: only operator-initiated dispatches graduate.
    if initiator != DispatchInitiator.OPERATOR:
        return AutoApprovalDecision(
            auto_approve=False,
            reason="non_operator_initiator_never_graduates",
            template_class=None,
        )

    # Wall 3: only eligible tools.
    if tool_id not in TRUST_ELIGIBLE_TOOLS:
        return AutoApprovalDecision(
            auto_approve=False,
            reason="tool_not_in_eligible_set",
            template_class=None,
        )

    # Compute template_class.
    template_class = compute_template_class(tool_id, payload)
    policy = get_policy(tool_id=tool_id, template_class=template_class)
    ladder = trust_ladder.get_entry(
        tool_id=tool_id, template_id=template_class,
    )
    approvals = ladder.approvals_count if ladder else 0
    rejections = ladder.rejection_count if ladder else 0

    # Wall 4: max_auto_tier must be exactly AUTO_APPROVE_LOW_RISK.
    if policy.max_auto_tier != TrustTier.AUTO_APPROVE_LOW_RISK:
        return AutoApprovalDecision(
            auto_approve=False,
            reason=f"max_auto_tier_is_{policy.max_auto_tier.value}",
            template_class=template_class,
            approvals_count=approvals,
            rejection_count=rejections,
            max_auto_tier=policy.max_auto_tier,
        )

    # Wall 5: zero rejections.
    if rejections > 0:
        return AutoApprovalDecision(
            auto_approve=False,
            reason="rejections_reset_trust_to_none",
            template_class=template_class,
            approvals_count=approvals,
            rejection_count=rejections,
            max_auto_tier=policy.max_auto_tier,
        )

    # Wall 6: minimum approvals.
    if approvals < min_approvals:
        return AutoApprovalDecision(
            auto_approve=False,
            reason=(
                f"approvals_count_{approvals}_below_threshold_"
                f"{min_approvals}"
            ),
            template_class=template_class,
            approvals_count=approvals,
            rejection_count=rejections,
            max_auto_tier=policy.max_auto_tier,
        )

    # All walls passed.
    return AutoApprovalDecision(
        auto_approve=True,
        reason="trust_graduated",
        template_class=template_class,
        approvals_count=approvals,
        rejection_count=rejections,
        max_auto_tier=policy.max_auto_tier,
    )


# ────────────────────────────────────────────────────────────────────
# Test helpers
# ────────────────────────────────────────────────────────────────────


def _reset_for_tests() -> None:
    if _POLICY_FILE.exists():
        try:
            _POLICY_FILE.unlink()
        except OSError:
            pass
