"""Per-plugin governance presets.

PR-CONN-PER-PLUGIN-GOV-PRESETS (Sprint-4 PR-5, 2026-05-03):
ships a STATIC METADATA table mapping (plugin_id, skill_class) ->
default governance tier. The table is consumed by the future
approval-queue UI to render the right "ask / allow / deny" badge,
and by the operator's policy editor to start from a sensible
preset rather than a blank slate.

Per the founder's brief, this PR ships METADATA ONLY. The presets
do NOT enforce anything beyond what the existing safety layers
already do:

  * Phase 2 read_only defense -- still the hard wall on writes.
  * Asset Shield consent gate (Sprint-4 PR-4) -- already requires
    operator approval for any write skill.
  * OAuth account-profile gate (Sprint-4 PR-3) -- already disambiguates
    Google accounts.

The presets layer adds RECOMMENDED defaults the operator can install
in one click via a future "use preset" button. The current safety
floor is unchanged: no preset can MAKE a write skill executable; it
can only TIGHTEN the rules (e.g. "Filesystem reads ASK every time"
instead of allow).

Why static, not DB-backed for the foundation
--------------------------------------------

The presets are vendor opinions ("Daena recommends Stripe payments
require explicit operator approval"). They are not per-tenant
configuration -- those live in the operator's edited policy. A
static module-level table is the right shape for vendor opinion;
DB-backed presets would invite drift between tenants over a fact
that should be the same for everyone.

A future PR (`PR-CONN-PER-TENANT-POLICY-OVERRIDES`) will let an
operator override these per-plugin via the policy editor; that PR
will store the OVERRIDE in DB, but read the BASELINE from this
module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from app.services.connection_v2.skill_consent import SkillConsentCategory

if TYPE_CHECKING:
    from app.services.connection_v2.skill_executor import SkillToolMapping


# ──────────────────────────────────────────────────────────────────
# Tiers
# ──────────────────────────────────────────────────────────────────


class GovernanceTier(str, Enum):
    """Governance disposition for a (plugin, skill class) pair.

    * ``ALLOW``  -- run without asking; audit-logged.
    * ``ASK``    -- explicit per-call operator confirmation
                    (Asset Shield consent gate or approval queue).
    * ``DENY``   -- never run; even with consent the skill is blocked
                    (operator must override the preset to switch to ASK).
    """

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


# ──────────────────────────────────────────────────────────────────
# Skill classes
# ──────────────────────────────────────────────────────────────────
# Coarse-grained classes used by the preset table. A preset entry
# pins ONE tier per (plugin, skill_class). The categorization
# function from skill_consent.SkillConsentCategory is the source of
# truth for which class a given skill falls into.


class SkillClass(str, Enum):
    """Per-plugin skill-class buckets the operator cares about.

    Order roughly matches blast-radius from low to high.
    """

    READ = "read"                       # any read_only=True skill
    READ_SENSITIVE = "read_sensitive"   # private inboxes / vault / etc.
    WRITE_EXTERNAL = "write_external"   # mutate files / records
    SEND_MESSAGE = "send_message"       # email / Slack / DMs
    PAYMENT = "payment"                 # Stripe / Plaid
    BROWSER_ACTION = "browser_action"   # Playwright / Chrome DevTools
    SECURITY_SCAN = "security_scan"     # offensive ops


# Map SkillConsentCategory -> SkillClass for cross-module lookup.
_CONSENT_TO_CLASS: dict[SkillConsentCategory, SkillClass] = {
    SkillConsentCategory.READ_SENSITIVE: SkillClass.READ_SENSITIVE,
    SkillConsentCategory.WRITE_EXTERNAL: SkillClass.WRITE_EXTERNAL,
    SkillConsentCategory.SEND_MESSAGE: SkillClass.SEND_MESSAGE,
    SkillConsentCategory.PAYMENT: SkillClass.PAYMENT,
    SkillConsentCategory.BROWSER_ACTION: SkillClass.BROWSER_ACTION,
    SkillConsentCategory.SECURITY_SCAN: SkillClass.SECURITY_SCAN,
}


# ──────────────────────────────────────────────────────────────────
# Preset table
# ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PluginGovernancePreset:
    """Vendor-recommended governance tiers for one plugin."""

    plugin_id: str
    rationale: str
    tiers: dict[SkillClass, GovernanceTier] = field(default_factory=dict)

    def tier_for(self, klass: SkillClass) -> GovernanceTier:
        """Return the preset tier for a class, defaulting to ASK
        (conservative -- never silently allows; never denies without
        explicit pinning)."""
        return self.tiers.get(klass, GovernanceTier.ASK)


# Mirrors the founder brief's example list. Plugins not in this table
# fall back to ``DEFAULT_PRESET`` (read=ALLOW, anything else=ASK).
PLUGIN_PRESETS: tuple[PluginGovernancePreset, ...] = (
    PluginGovernancePreset(
        plugin_id="mcp-filesystem",
        rationale=(
            "Sandboxed filesystem reads are low-risk; broad recursive "
            "reads can leak structure outside the operator's intent. "
            "Writes are high-risk on a developer machine."
        ),
        tiers={
            SkillClass.READ: GovernanceTier.ASK,
            SkillClass.WRITE_EXTERNAL: GovernanceTier.DENY,
        },
    ),
    PluginGovernancePreset(
        plugin_id="mcp-github",
        rationale=(
            "GitHub reads (repo metadata, issues, PRs, CI logs) are "
            "low-risk. Comments / issues / PRs touch public state and "
            "need explicit approval."
        ),
        tiers={
            SkillClass.READ: GovernanceTier.ALLOW,
            SkillClass.WRITE_EXTERNAL: GovernanceTier.ASK,
        },
    ),
    PluginGovernancePreset(
        plugin_id="app-gmail",
        rationale=(
            "Reading message ids / summaries is low-risk. Sending email "
            "is irreversible + reaches the world; never auto-allow."
        ),
        tiers={
            SkillClass.READ: GovernanceTier.ALLOW,
            SkillClass.READ_SENSITIVE: GovernanceTier.ASK,
            SkillClass.SEND_MESSAGE: GovernanceTier.DENY,
        },
    ),
    PluginGovernancePreset(
        plugin_id="app-google-drive",
        rationale=(
            "Drive search + metadata reads are low-risk. Reading file "
            "BODIES touches the operator's documents; gate it. Writes "
            "(rename / share / delete) need explicit approval."
        ),
        tiers={
            SkillClass.READ: GovernanceTier.ALLOW,
            SkillClass.READ_SENSITIVE: GovernanceTier.ASK,
            SkillClass.WRITE_EXTERNAL: GovernanceTier.ASK,
        },
    ),
    PluginGovernancePreset(
        plugin_id="mcp-slack",
        rationale=(
            "Reading channel history is low-risk for channels the "
            "Daena bot is in. Sending messages or reactions reaches "
            "real humans -- always ask, never auto-send."
        ),
        tiers={
            SkillClass.READ: GovernanceTier.ALLOW,
            SkillClass.SEND_MESSAGE: GovernanceTier.ASK,
        },
    ),
    PluginGovernancePreset(
        plugin_id="mcp-stripe",
        rationale=(
            "Reading payments / subscriptions is high-impact info. "
            "Processing payments / refunds is the highest-blast-radius "
            "Phase 3 skill; never ALLOW without explicit per-call "
            "consent AND audit. Default DENY until operator opts in."
        ),
        tiers={
            SkillClass.READ_SENSITIVE: GovernanceTier.ASK,
            SkillClass.PAYMENT: GovernanceTier.DENY,
        },
    ),
    PluginGovernancePreset(
        plugin_id="mcp-playwright",
        rationale=(
            "Local-page browser actions are useful for dev workflows. "
            "External browsing automation can leak operator IP, leave "
            "footprints, or take destructive actions on third-party "
            "sites. Always ASK; DENY external until consent + scope."
        ),
        tiers={
            SkillClass.BROWSER_ACTION: GovernanceTier.ASK,
        },
    ),
    PluginGovernancePreset(
        plugin_id="mcp-chrome-devtools",
        rationale=(
            "Same risk profile as mcp-playwright -- DevTools can "
            "snapshot, intercept network, modify storage."
        ),
        tiers={
            SkillClass.BROWSER_ACTION: GovernanceTier.ASK,
        },
    ),
)


_PRESETS_BY_ID: dict[str, PluginGovernancePreset] = {
    p.plugin_id: p for p in PLUGIN_PRESETS
}


# Default preset for plugins not in the table: reads allow, everything
# else asks. Conservative -- never silently allows a write surface
# the vendor table didn't pre-approve.
DEFAULT_PRESET = PluginGovernancePreset(
    plugin_id="__default__",
    rationale=(
        "Vendor table has no pinned preset. Default: read=ALLOW, "
        "everything else=ASK. Operator can install a custom preset "
        "via the policy editor."
    ),
    tiers={
        SkillClass.READ: GovernanceTier.ALLOW,
    },
)


def get_preset(plugin_id: str) -> PluginGovernancePreset:
    """Return the preset for a plugin, falling back to DEFAULT_PRESET."""
    return _PRESETS_BY_ID.get(plugin_id, DEFAULT_PRESET)


def classify_skill(entry: "SkillToolMapping") -> SkillClass:
    """Map a SkillToolMapping to its SkillClass for preset lookup.

    Mirrors ``skill_consent.categorize_skill`` but returns READ for
    read_only entries (vs None) so the presets table can pin a
    READ tier per plugin.
    """
    from app.services.connection_v2.skill_consent import categorize_skill

    if entry.read_only:
        return SkillClass.READ
    consent_category = categorize_skill(entry)
    if consent_category is None:
        # Defensive: a non-read-only entry should always have a category.
        return SkillClass.WRITE_EXTERNAL
    return _CONSENT_TO_CLASS.get(consent_category, SkillClass.WRITE_EXTERNAL)


def recommended_tier(entry: "SkillToolMapping") -> GovernanceTier:
    """Top-level helper: given an allowlist entry, what tier does the
    vendor preset table recommend? The answer is METADATA only --
    actual enforcement still lives in the consent gate + read_only
    defense layers."""
    preset = get_preset(entry.plugin_id)
    klass = classify_skill(entry)
    return preset.tier_for(klass)


# ──────────────────────────────────────────────────────────────────
# JSON serialization for the future API
# ──────────────────────────────────────────────────────────────────


def list_presets_for_api() -> list[dict]:
    """Render every preset as a JSON-serializable dict for a future
    GET /v2/governance/plugin-presets endpoint. Pure metadata -- safe
    to call without auth."""
    out: list[dict] = []
    for p in PLUGIN_PRESETS:
        out.append({
            "plugin_id": p.plugin_id,
            "rationale": p.rationale,
            "tiers": {k.value: v.value for k, v in p.tiers.items()},
        })
    out.append({
        "plugin_id": DEFAULT_PRESET.plugin_id,
        "rationale": DEFAULT_PRESET.rationale,
        "tiers": {k.value: v.value for k, v in DEFAULT_PRESET.tiers.items()},
        "_is_fallback": True,
    })
    return out


__all__ = [
    "DEFAULT_PRESET",
    "GovernanceTier",
    "PLUGIN_PRESETS",
    "PluginGovernancePreset",
    "SkillClass",
    "classify_skill",
    "get_preset",
    "list_presets_for_api",
    "recommended_tier",
]
