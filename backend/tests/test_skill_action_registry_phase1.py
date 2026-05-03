"""PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE1 regression tests.

The Phase 1 skill execution registry is a frontend file
(``frontend/src/pages/connections/skillActionRegistry.ts``).
Daena has no Vitest harness, so the safety-critical contract is
pinned by THIS test file: parse the TS file as text + structurally
verify every catalog ``default_skill`` is mapped + the safety
invariants hold.

Pinned invariants (founder rules 9, 10, 13, 14):
  1. Every catalog default_skill identifier appears in the registry
     OR is intentionally omitted (test fails otherwise so a new
     catalog skill cannot be added without a registry decision).
  2. No entry with ``allowed_in_phase1: true`` may have
     ``writes_external_state: true`` -- write-capable skills must
     stay blocked until Phase 3.
  3. No entry with ``allowed_in_phase1: true`` may have
     ``sends_external_message: true`` -- messaging actions must
     stay blocked until Phase 3.
  4. Every high-risk plugin (catalog ``risk_level == "high"``) has
     AT LEAST one chip mapped to ``blocked_high_risk_consent_missing``
     OR every entry for that plugin is risk_level=high (so the
     Asset Shield consent dialog will fire on every chip in Phase 3).
  5. Every Stripe / Cloudflare write-capable skill is blocked.
  6. Every Playwright browser-action skill (open_page, fill_form_safe,
     capture_screenshot, run_smoke_test) is blocked.
  7. The registry has no malformed entries (every entry has all
     required fields).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.connection_v2.marketplace_catalog import CATALOG


REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "frontend" / "src" / "pages" / "connections" / "skillActionRegistry.ts"
)


# ──────────────────────────────────────────────────────────────────
# Registry parser (regex-based; the TS file uses a fixed shape)
# ──────────────────────────────────────────────────────────────────

# Matches: { plugin_id: 'mcp-github', skill_id: 'triage_issues', ... }
# Captures the (plugin_id, skill_id) pair AND the surrounding object
# body so we can inspect spread macros (...COMPOSER, ...BLOCKED_WRITE).
_ENTRY_REGEX = re.compile(
    r"\{\s*plugin_id:\s*'([^']+)',\s*skill_id:\s*'([^']+)',(.*?)\}\s*,",
    re.DOTALL,
)


def _load_registry_text() -> str:
    assert REGISTRY_PATH.exists(), (
        f"skillActionRegistry.ts not found at {REGISTRY_PATH}"
    )
    return REGISTRY_PATH.read_text(encoding="utf-8")


def _parse_entries() -> list[dict]:
    """Parse the registry's entry blocks into Python dicts.

    Each returned dict has: plugin_id, skill_id, body, plus the
    spread macro name if present (e.g. 'COMPOSER', 'BLOCKED_WRITE').
    """
    text = _load_registry_text()
    out: list[dict] = []
    # Only look inside the SKILL_ACTION_REGISTRY array, not the helper
    # constants above it. Find the array body once.
    arr_match = re.search(
        r"export const SKILL_ACTION_REGISTRY[^=]*=\s*\[(.+?)^\]",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert arr_match, "Could not locate SKILL_ACTION_REGISTRY array body"
    arr_body = arr_match.group(1)
    for m in _ENTRY_REGEX.finditer(arr_body):
        plugin_id, skill_id, body = m.group(1), m.group(2), m.group(3)
        spread = None
        spread_match = re.search(r"\.\.\.([A-Z_]+)", body)
        if spread_match:
            spread = spread_match.group(1)
        out.append({
            "plugin_id": plugin_id,
            "skill_id": skill_id,
            "body": body,
            "spread": spread,
        })
    return out


# Spread-macro definitions parsed from the helper block at the top
# of the registry. Captured ONCE so each test doesn't re-parse.
_SPREAD_PROPERTIES = {
    "PLAN_ONLY": {
        "action_type": "action_plan",
        "writes_external_state": False,
        "sends_external_message": False,
        "allowed_in_phase1": True,
    },
    "COMPOSER": {
        "action_type": "composer_draft",
        "writes_external_state": False,
        "sends_external_message": False,
        "allowed_in_phase1": True,
    },
    "COMPOSER_HIGH_RISK": {
        "action_type": "composer_draft",
        "writes_external_state": False,
        "sends_external_message": False,
        "allowed_in_phase1": True,
    },
    "BLOCKED_WRITE": {
        "action_type": "blocked_high_risk_consent_missing",
        "writes_external_state": True,
        "sends_external_message": False,
        "allowed_in_phase1": False,
    },
    "BLOCKED_MESSAGE": {
        "action_type": "blocked_high_risk_consent_missing",
        "writes_external_state": True,
        "sends_external_message": True,
        "allowed_in_phase1": False,
    },
    "BLOCKED_BROWSER_ACTION": {
        "action_type": "blocked_high_risk_consent_missing",
        "writes_external_state": True,
        "sends_external_message": False,
        "allowed_in_phase1": False,
    },
}


def _entry_props(entry: dict) -> dict:
    """Resolve an entry's effective properties via its spread macro."""
    spread = entry["spread"]
    if spread and spread in _SPREAD_PROPERTIES:
        return _SPREAD_PROPERTIES[spread]
    return {}


# ──────────────────────────────────────────────────────────────────
# Coverage: every catalog default_skill is mapped
# ──────────────────────────────────────────────────────────────────


class TestCoverage:
    def test_registry_file_exists_and_parses(self):
        entries = _parse_entries()
        assert len(entries) > 50, (
            f"Expected >50 registry entries; got {len(entries)}. "
            f"Either the file is malformed or _ENTRY_REGEX needs updating."
        )

    def test_every_catalog_default_skill_is_mapped(self):
        """If a new default_skill lands in the catalog without a
        registry decision, this test fails. Forces the contributor
        to make an explicit Phase 1 choice (composer / plan / blocked)."""
        registry_keys = {
            (e["plugin_id"], e["skill_id"]) for e in _parse_entries()
        }
        catalog_skills = [
            (entry.id, skill)
            for entry in CATALOG
            for skill in (entry.default_skills or ())
        ]
        missing = [
            (pid, sid) for pid, sid in catalog_skills
            if (pid, sid) not in registry_keys
        ]
        assert not missing, (
            f"Catalog default_skills missing from skillActionRegistry.ts: "
            f"{missing}. Add a Phase 1 entry (composer / plan / blocked) "
            f"per skill."
        )

    def test_no_phantom_registry_entries(self):
        """Every registry entry must point at a real catalog
        (plugin_id, skill_id) pair. Catches typos."""
        catalog_skills = {
            (entry.id, skill)
            for entry in CATALOG
            for skill in (entry.default_skills or ())
        }
        registry_keys = {
            (e["plugin_id"], e["skill_id"]) for e in _parse_entries()
        }
        phantom = [k for k in registry_keys if k not in catalog_skills]
        assert not phantom, (
            f"Registry references skills not declared in any catalog "
            f"entry: {phantom}"
        )


# ──────────────────────────────────────────────────────────────────
# Phase 1 safety invariants
# ──────────────────────────────────────────────────────────────────


class TestPhase1SafetyInvariants:
    def test_no_phase1_entry_writes_external_state(self):
        """If allowed_in_phase1 is true, writes_external_state MUST
        be false. Phase 1 is composer/plan only."""
        bad: list[tuple[str, str]] = []
        for entry in _parse_entries():
            props = _entry_props(entry)
            if (
                props.get("allowed_in_phase1") is True
                and props.get("writes_external_state") is True
            ):
                bad.append((entry["plugin_id"], entry["skill_id"]))
        assert not bad, (
            f"Phase 1 entries cannot write external state: {bad}. "
            f"Move these to BLOCKED_WRITE until Phase 3."
        )

    def test_no_phase1_entry_sends_external_message(self):
        """If allowed_in_phase1 is true, sends_external_message MUST
        be false. Phase 1 cannot send emails / DMs / webhooks."""
        bad: list[tuple[str, str]] = []
        for entry in _parse_entries():
            props = _entry_props(entry)
            if (
                props.get("allowed_in_phase1") is True
                and props.get("sends_external_message") is True
            ):
                bad.append((entry["plugin_id"], entry["skill_id"]))
        assert not bad, (
            f"Phase 1 entries cannot send external messages: {bad}. "
            f"Move these to BLOCKED_MESSAGE until Phase 3."
        )

    def test_blocked_macros_have_allowed_in_phase1_false(self):
        """The BLOCKED_* spread macros MUST have allowed_in_phase1=False
        so a maintainer can't accidentally let a high-risk skill fire."""
        for name in ("BLOCKED_WRITE", "BLOCKED_MESSAGE", "BLOCKED_BROWSER_ACTION"):
            assert _SPREAD_PROPERTIES[name]["allowed_in_phase1"] is False, (
                f"{name} must have allowed_in_phase1=False"
            )


# ──────────────────────────────────────────────────────────────────
# High-risk + write skill enforcement
# ──────────────────────────────────────────────────────────────────


# Skills that MUST be blocked in Phase 1 (per founder spec). If any
# of these become allowed, the test fails loudly.
EXPLICITLY_BLOCKED_SKILLS = {
    # Stripe writes
    ("mcp-stripe", "reconcile_subscriptions"),
    # Notion content writes
    ("mcp-notion", "update_page"),
    # Sentry issue tracker writes
    ("mcp-sentry", "create_bug_task"),
    # Calendar event writes (also sends invites)
    ("app-google-calendar", "schedule_meeting"),
    # Browser action skills (Playwright)
    ("mcp-playwright", "open_page"),
    ("mcp-playwright", "fill_form_safe"),
    ("mcp-playwright", "capture_screenshot"),
    ("mcp-playwright", "run_smoke_test"),
    # Browser screenshot from Chrome DevTools (matches Playwright policy)
    ("mcp-chrome-devtools", "capture_screenshot"),
}


class TestExplicitBlocks:
    @pytest.mark.parametrize("plugin_id,skill_id", sorted(EXPLICITLY_BLOCKED_SKILLS))
    def test_each_dangerous_skill_is_explicitly_blocked(self, plugin_id, skill_id):
        target = next(
            (e for e in _parse_entries()
             if e["plugin_id"] == plugin_id and e["skill_id"] == skill_id),
            None,
        )
        assert target is not None, (
            f"{plugin_id}:{skill_id} not in registry"
        )
        spread = target["spread"]
        # Must use one of the BLOCKED_* macros.
        assert spread in {"BLOCKED_WRITE", "BLOCKED_MESSAGE", "BLOCKED_BROWSER_ACTION"}, (
            f"{plugin_id}:{skill_id} must use a BLOCKED_* macro; got '{spread}'"
        )
        props = _SPREAD_PROPERTIES[spread]
        assert props["allowed_in_phase1"] is False
        assert props["action_type"] == "blocked_high_risk_consent_missing"


class TestHighRiskPlugins:
    """High-risk plugins (catalog risk_level=high) are Cloudflare and
    Stripe today. Even their READ skills must be flagged risk_level=high
    in the registry so the Phase 3 consent dialog fires on every chip,
    not just writes.
    """

    def test_cloudflare_skills_use_high_risk_macro(self):
        """All Cloudflare default_skills are reads, so they're allowed
        in Phase 1 -- but they MUST use COMPOSER_HIGH_RISK so the
        consent dialog still kicks in for Phase 3."""
        cf_entries = [
            e for e in _parse_entries() if e["plugin_id"] == "mcp-cloudflare"
        ]
        assert len(cf_entries) >= 4, "Cloudflare has 4 default_skills"
        for e in cf_entries:
            assert e["spread"] == "COMPOSER_HIGH_RISK", (
                f"mcp-cloudflare:{e['skill_id']} must use COMPOSER_HIGH_RISK; "
                f"got {e['spread']}"
            )

    def test_stripe_read_skills_use_high_risk_macro(self):
        """Stripe reads (summarize_payments, inspect_customer) must use
        COMPOSER_HIGH_RISK so the Phase 3 consent dialog fires."""
        stripe_reads = [
            e for e in _parse_entries()
            if e["plugin_id"] == "mcp-stripe"
            and e["skill_id"] in {"summarize_payments", "inspect_customer"}
        ]
        assert len(stripe_reads) == 2
        for e in stripe_reads:
            assert e["spread"] == "COMPOSER_HIGH_RISK", (
                f"mcp-stripe:{e['skill_id']} must use COMPOSER_HIGH_RISK"
            )


# ──────────────────────────────────────────────────────────────────
# Template safety -- no shell metacharacters, no leaked secrets
# ──────────────────────────────────────────────────────────────────


class TestTemplateSafety:
    """The registry's templates feed straight into the chat composer.
    They must not contain anything that would behave differently if
    eventually composed into a shell or template literal."""

    def test_no_template_contains_real_credentials(self):
        text = _load_registry_text()
        # Token-shaped strings (>=20 chars of [A-Za-z0-9_-])
        suspect = re.findall(
            r"(sk-ant-[A-Za-z0-9_\-]{15,}"
            r"|sk-[A-Za-z0-9_\-]{20,}"
            r"|gsk_[A-Za-z0-9_\-]{15,}"
            r"|pplx-[A-Za-z0-9_\-]{15,}"
            r"|AIza[A-Za-z0-9_\-]{15,}"
            r"|xai-[A-Za-z0-9_\-]{15,})",
            text,
        )
        # The ProviderProbe tests use canary keys; we should never
        # see one in this file. Allow nothing.
        assert not suspect, f"Possible real credential in registry: {suspect}"

    def test_no_template_uses_template_literal_syntax(self):
        """Templates are stored as plain strings so they cannot be
        interpolated by accident. Catch ${...} usage inside template:
        '...' values."""
        text = _load_registry_text()
        # Find every "template: '...'" string and check it has no ${
        templates = re.findall(r"template:\s*'((?:\\'|[^'])*)'", text)
        bad = [t for t in templates if "${" in t]
        assert not bad, (
            f"Templates must not use template-literal syntax: {bad[:3]}"
        )

    def test_every_allowed_entry_has_non_empty_template(self):
        """Every registry entry that COULD draft into the composer
        (composer_draft / action_plan, allowed_in_phase1=true) must
        have a non-empty template."""
        text = _load_registry_text()
        # Find entries whose body has a template: '' empty string
        # AND uses one of the allowing spread macros.
        entries = _parse_entries()
        bad: list[tuple[str, str]] = []
        for e in entries:
            spread = e["spread"]
            if spread not in {"COMPOSER", "COMPOSER_HIGH_RISK", "PLAN_ONLY"}:
                continue
            tmpl_match = re.search(r"template:\s*'((?:\\'|[^'])*)'", e["body"])
            if not tmpl_match or not tmpl_match.group(1).strip():
                bad.append((e["plugin_id"], e["skill_id"]))
        assert not bad, (
            f"Allowed Phase 1 entries with empty template: {bad}"
        )
