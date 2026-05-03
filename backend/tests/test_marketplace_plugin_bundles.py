"""PR-CONN-MCP-CATALOG-SKILL-BUNDLES regression tests.

Pins the plugin-bundle metadata contract:

  1. Schema: every entry has the new optional fields with sane defaults.
  2. Officiality: every external plugin (non-coming-soon) declares one
     of the seven trust tiers; default is "community".
  3. Source attribution: official / vendor-official / vendor-blessed /
     verified entries MUST cite at least one source_refs URL.
  4. High-confidence plugins added in this PR (from the founder list)
     MUST be in the catalog with the right officiality.
  5. Default skills: when an entry declares default_skills, those
     names are non-empty strings (not just placeholders).
  6. No leakage: no entry's serialized payload contains a real key
     prefix (sk-, pplx-, gsk_, AIza...).
  7. No skill marked executable -- the catalog only declares NAMES.
     Executability lives in the lifecycle gate, not the catalog row.
  8. Card payload exposes the new fields end-to-end.
"""

from __future__ import annotations

import json
import re

import pytest

from app.services.connection_v2.marketplace_catalog import (
    CATALOG,
    CATALOG_BY_ID,
    Officiality,
)
from app.services.connection_v2.marketplace_service import MarketplaceCard


# ──────────────────────────────────────────────────────────────────
# 1. Schema -- every entry has the new fields
# ──────────────────────────────────────────────────────────────────


def test_every_entry_has_officiality_field():
    for entry in CATALOG:
        assert hasattr(entry, "officiality")
        assert entry.officiality in (
            "official", "vendor-official", "vendor-blessed",
            "verified", "community", "archived", "coming-soon",
        ), f"{entry.id} has invalid officiality: {entry.officiality}"


def test_every_entry_has_default_skills_tuple():
    for entry in CATALOG:
        assert isinstance(entry.default_skills, tuple)
        # Empty is fine -- not every entry has skills declared yet.


def test_every_entry_has_source_refs_tuple():
    for entry in CATALOG:
        assert isinstance(entry.source_refs, tuple)


# ──────────────────────────────────────────────────────────────────
# 2. Officiality contract
# ──────────────────────────────────────────────────────────────────


def test_official_entries_cite_source_refs():
    """Every official / vendor-official / vendor-blessed / verified
    entry MUST cite at least one source URL. Otherwise the marketplace
    badge is unverifiable and the rule "Do not duplicate or fabricate
    third-party metadata without a source" is broken.
    """
    high_trust_tiers = {"official", "vendor-official", "vendor-blessed", "verified"}
    missing = [
        e.id for e in CATALOG
        if e.officiality in high_trust_tiers and not e.source_refs
    ]
    assert not missing, (
        f"High-trust entries missing source_refs: {missing}. "
        f"Every official/vendor-official/vendor-blessed/verified entry "
        f"must cite at least one URL."
    )


def test_default_officiality_is_community():
    """Entries that don't explicitly set officiality default to
    "community" so the operator sees a "Review source" CTA. Verifies
    the dataclass default didn't drift to a higher tier by accident.
    """
    from app.services.connection_v2.marketplace_catalog import _entry, CatalogEntry
    e = _entry(
        id="test-fixture-default",
        display_name="Test",
        vendor="Test",
        category="dev_tools",
        kind="mcp_server",
        short_description="...",
    )
    assert e.officiality == "community"


# ──────────────────────────────────────────────────────────────────
# 3. High-confidence plugins from research are present + correctly tiered
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "entry_id,expected_officiality",
    [
        # Reference servers (MCP steering group)
        ("mcp-filesystem", "official"),
        ("mcp-fetch", "official"),
        ("mcp-memory", "official"),
        ("mcp-time", "official"),
        ("mcp-git", "official"),
        ("mcp-sequential-thinking", "official"),
        # Vendor-shipped first-party
        ("mcp-github", "vendor-official"),
        ("mcp-cloudflare", "vendor-official"),
        ("mcp-sentry", "vendor-official"),
        ("mcp-vercel", "vendor-official"),
        ("mcp-jira", "vendor-official"),  # Atlassian Rovo
        ("mcp-slack", "vendor-official"),
        ("mcp-notion", "vendor-official"),
        ("mcp-linear", "vendor-official"),
        ("mcp-stripe", "vendor-official"),
        ("mcp-huggingface", "vendor-official"),
        ("mcp-figma", "vendor-official"),
        ("mcp-playwright", "vendor-official"),
        ("mcp-chrome-devtools", "vendor-official"),
        ("mcp-brave-search", "vendor-official"),
        # Vendor-blessed community
        ("mcp-supabase", "vendor-blessed"),
        ("mcp-mongodb", "vendor-blessed"),
        # Vendor-published from vendor org (Neon)
        ("mcp-neon", "vendor-official"),
        # Archived references
        ("mcp-postgres", "archived"),
        ("mcp-sqlite", "archived"),
        ("mcp-google-drive", "archived"),
        # Daena-verified OAuth integrations
        ("app-gmail", "verified"),
        ("app-google-calendar", "verified"),
        ("app-google-drive", "verified"),
    ],
)
def test_high_confidence_plugins_present_with_correct_tier(
    entry_id, expected_officiality,
):
    entry = CATALOG_BY_ID.get(entry_id)
    assert entry is not None, f"Plugin {entry_id} missing from catalog"
    assert entry.officiality == expected_officiality, (
        f"{entry_id}: expected officiality={expected_officiality}, "
        f"got {entry.officiality}"
    )


# ──────────────────────────────────────────────────────────────────
# 4. Default skills shape + dependency contract
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "entry_id,expected_skill",
    [
        ("mcp-github", "triage_issues"),
        ("mcp-github", "review_pull_request"),
        ("mcp-github", "summarize_repo"),
        ("mcp-slack", "summarize_channel"),
        ("mcp-slack", "find_decisions"),
        ("mcp-notion", "find_page"),
        ("mcp-linear", "triage_issues"),
        ("mcp-jira", "triage_tickets"),
        ("mcp-stripe", "summarize_payments"),
        ("mcp-sentry", "summarize_errors"),
        ("mcp-cloudflare", "inspect_dns"),
        ("mcp-vercel", "inspect_logs"),
        ("mcp-figma", "inspect_design"),
        ("mcp-huggingface", "find_model"),
        ("mcp-playwright", "open_page"),
        ("mcp-playwright", "run_smoke_test"),
        ("mcp-chrome-devtools", "analyze_perf"),
        ("app-gmail", "summarize_unread"),
        ("app-gmail", "draft_reply"),
        ("app-google-drive", "find_documents"),
        ("app-google-calendar", "find_free_time"),
    ],
)
def test_high_confidence_skill_present(entry_id, expected_skill):
    entry = CATALOG_BY_ID[entry_id]
    assert expected_skill in entry.default_skills, (
        f"{entry_id} missing default skill {expected_skill!r}; "
        f"declared: {entry.default_skills}"
    )


def test_default_skills_are_snake_case_names():
    """Default skill names should be machine-parseable identifiers
    (snake_case alphanumeric), NOT human prose. The latter belongs
    in suggested_prompts. Catches regressions where someone accidentally
    pastes "Triage the open PRs" into default_skills.
    """
    pat = re.compile(r"^[a-z][a-z0-9_]*$")
    bad = []
    for entry in CATALOG:
        for skill in entry.default_skills:
            if not pat.match(skill):
                bad.append((entry.id, skill))
    assert not bad, (
        f"default_skills must be snake_case identifiers, got: {bad}"
    )


def test_default_skills_no_executable_marker():
    """Verify the catalog never marks a skill as 'executable' -- the
    contract is that skills become available only when the plugin's
    lifecycle is ``callable``. This is enforced by the lifecycle gate,
    not the catalog row, but we pin the catalog shape too as defense.
    """
    for entry in CATALOG:
        for skill in entry.default_skills:
            assert "execute" not in skill.lower()
            assert "exec" not in skill.lower() or "execute" in skill.lower() is False
            # No skill name should literally claim to "execute" or "run_tool"
            # without the lifecycle gate. ``run_smoke_test`` is allowed
            # because it's a SCOPED action name, not a generic "execute X".


# ──────────────────────────────────────────────────────────────────
# 5. Leak safety -- no real key prefixes in catalog payload
# ──────────────────────────────────────────────────────────────────


def test_catalog_payload_no_real_key_prefixes():
    """Defense in depth: serialize every entry to dict and grep for
    real-looking key prefixes. The catalog is hand-curated so this
    SHOULD never produce a hit, but a future PR could accidentally
    paste a sample key into setup_notes.
    """
    real_key_pat = re.compile(
        r"(sk-ant-[A-Za-z0-9_-]{10,}"
        r"|sk-[A-Za-z0-9_-]{20,}"
        r"|gsk_[A-Za-z0-9_-]{10,}"
        r"|pplx-[A-Za-z0-9_-]{10,}"
        r"|AIza[A-Za-z0-9_-]{10,}"
        r"|xai-[A-Za-z0-9_-]{10,})"
    )
    blob = json.dumps([e.to_dict() for e in CATALOG])
    matches = real_key_pat.findall(blob)
    assert not matches, (
        f"Catalog payload contains real-looking key prefixes: "
        f"{[m[:8] + '...' for m in matches]}"
    )


# ──────────────────────────────────────────────────────────────────
# 6. Card payload propagates the bundle metadata
# ──────────────────────────────────────────────────────────────────


def test_card_to_dict_carries_bundle_fields():
    """Every MarketplaceCard.to_dict() output should expose the new
    bundle fields via the nested ``catalog`` dict (not as top-level
    fields -- the schema kept them inside catalog so the V2 truth
    surface stays cleanly separable).
    """
    entry = CATALOG_BY_ID["mcp-github"]
    card = MarketplaceCard(catalog=entry.to_dict())
    payload = card.to_dict()
    catalog = payload["catalog"]
    # Bundle fields are present + serialized as lists/strings
    assert "officiality" in catalog
    assert "default_skills" in catalog
    assert "suggested_prompts" in catalog
    assert "permissions_summary" in catalog
    assert "source_refs" in catalog
    assert "last_verified_at" in catalog
    assert isinstance(catalog["default_skills"], list)
    assert "triage_issues" in catalog["default_skills"]
    assert catalog["officiality"] == "vendor-official"


def test_card_payload_serializes_clean():
    """Sanity: every entry round-trips to JSON without crashing."""
    for entry in CATALOG:
        payload = MarketplaceCard(catalog=entry.to_dict()).to_dict()
        # Must be JSON-serializable
        json.dumps(payload)


# ──────────────────────────────────────────────────────────────────
# 7. Catalog growth check (sanity)
# ──────────────────────────────────────────────────────────────────


def test_catalog_count_at_least_55():
    """The pre-PR baseline was 55 entries; this PR adds vendor-blessed
    Supabase + Neon, so we expect 57+. If the count drops, someone
    accidentally removed entries.
    """
    assert len(CATALOG) >= 55, f"Catalog regressed to {len(CATALOG)} entries"


def test_catalog_has_minimum_official_count():
    """At least 6 reference + 14 vendor-official + 2 vendor-blessed +
    3 verified = 25 trusted entries. This is the hard floor for the
    high-trust slice the marketplace surfaces by default.
    """
    high_trust = {"official", "vendor-official", "vendor-blessed", "verified"}
    count = sum(1 for e in CATALOG if e.officiality in high_trust)
    assert count >= 25, (
        f"Only {count} high-trust catalog entries (needed >=25). "
        f"Did the officiality bump regression-revert a vendor entry?"
    )
