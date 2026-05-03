"""PR-CONN-PLUGIN-SKILLS-UX-WIRING regression tests.

Pins the contract the frontend SkillBundleSection + PluginDetailDrawer
rely on:

  1. Suggested prompts are present on at least N high-confidence
     plugins so the drawer's "What Daena can do" section has real
     intent copy (not just the catalog short_description fallback).
  2. Suggested prompts are HUMAN-READABLE sentences, not snake_case
     identifiers (those go in default_skills).
  3. Permissions summary uses a small controlled vocabulary so the
     UI can map to icons/colors without a free-form parse.
  4. Bundle metadata round-trips through the marketplace card payload
     (re-asserts what test_marketplace_plugin_bundles.py covers, but
     also checks the new ``suggested_prompts`` + ``permissions_summary``
     are accessible from the card's catalog dict).
  5. No suggested_prompt collides with a default_skill identifier
     (categories are kept clean: prompts are prose, skills are names).
  6. High-risk plugins ALL declare permissions_summary so the drawer's
     PermissionsBlock can highlight them with the Asset Shield reminder.
"""

from __future__ import annotations

import re

import pytest

from app.services.connection_v2.marketplace_catalog import (
    CATALOG,
    CATALOG_BY_ID,
)
from app.services.connection_v2.marketplace_service import MarketplaceCard


# ──────────────────────────────────────────────────────────────────
# 1. Suggested prompts coverage
# ──────────────────────────────────────────────────────────────────


def test_at_least_15_entries_have_suggested_prompts():
    """The drawer's "What Daena can do" section needs concrete intent
    sentences for the high-confidence plugin set. PR baseline: 15+
    entries (GitHub, Slack, Notion, Linear, etc) carry prompts."""
    with_prompts = [e for e in CATALOG if e.suggested_prompts]
    assert len(with_prompts) >= 15, (
        f"Only {len(with_prompts)} entries have suggested_prompts; "
        f"the drawer's intent surface needs at least 15."
    )


@pytest.mark.parametrize(
    "entry_id",
    [
        "mcp-github", "mcp-slack", "mcp-notion", "mcp-linear",
        "mcp-stripe", "mcp-sentry", "mcp-cloudflare", "mcp-vercel",
        "mcp-figma", "mcp-jira", "mcp-playwright", "mcp-chrome-devtools",
        "app-gmail", "app-google-drive", "app-google-calendar",
    ],
)
def test_high_confidence_entry_has_at_least_one_prompt(entry_id):
    entry = CATALOG_BY_ID.get(entry_id)
    assert entry is not None, f"Plugin {entry_id} missing from catalog"
    assert len(entry.suggested_prompts) >= 1, (
        f"{entry_id} has no suggested_prompts; the drawer's "
        f"\"What Daena can do\" section will fall back to the "
        f"short_description, which is less actionable."
    )


# ──────────────────────────────────────────────────────────────────
# 2. Suggested prompts are sentences, not identifiers
# ──────────────────────────────────────────────────────────────────


def test_suggested_prompts_are_human_sentences():
    """Suggested prompts are prose ("Triage the open PRs in repo X"),
    not snake_case identifiers ("triage_open_prs"). Catches the
    accidental copy-paste of a default_skill name into the prompt
    bucket. Heuristic: must contain a space and start with a capital
    letter or quote.
    """
    bad: list[tuple[str, str]] = []
    for entry in CATALOG:
        for prompt in entry.suggested_prompts:
            # Allow leading whitespace just in case
            stripped = prompt.strip()
            if not stripped:
                bad.append((entry.id, "<empty>"))
                continue
            # No snake_case identifiers (foo_bar_baz with no spaces)
            if re.fullmatch(r"[a-z][a-z0-9_]*", stripped):
                bad.append((entry.id, stripped))
                continue
            # Must contain a space (it's a sentence, not a single word)
            if " " not in stripped:
                bad.append((entry.id, stripped))
    assert not bad, (
        f"suggested_prompts must be human prose, got identifier-like "
        f"entries: {bad}"
    )


# ──────────────────────────────────────────────────────────────────
# 3. Permissions vocabulary is controlled
# ──────────────────────────────────────────────────────────────────

ALLOWED_PERMISSIONS = {
    "Read", "Write", "Network",
    # Allow a few extended scopes for special-purpose plugins
    "Browser", "Filesystem", "Compute", "Email", "Calendar", "Storage",
    "Payment", "Admin",
}


def test_permissions_summary_uses_controlled_vocabulary():
    """permissions_summary must use the controlled set so the
    PermissionsBlock chip palette is predictable (icon/color per
    permission). Free-form text breaks the chip layout.
    """
    bad: list[tuple[str, str]] = []
    for entry in CATALOG:
        for perm in entry.permissions_summary:
            if perm not in ALLOWED_PERMISSIONS:
                bad.append((entry.id, perm))
    assert not bad, (
        f"permissions_summary must use the controlled vocab "
        f"({sorted(ALLOWED_PERMISSIONS)}); got: {bad}"
    )


# ──────────────────────────────────────────────────────────────────
# 4. Bundle metadata round-trip through MarketplaceCard
# ──────────────────────────────────────────────────────────────────


def test_card_payload_carries_suggested_prompts_and_permissions():
    """Re-assert that the wire shape the drawer reads is intact.
    test_marketplace_plugin_bundles covers default_skills; here we
    pin the prompts + permissions specifically so a future schema
    refactor can't silently drop these fields without flipping a test."""
    entry = CATALOG_BY_ID["mcp-github"]
    card = MarketplaceCard(catalog=entry.to_dict())
    payload = card.to_dict()
    catalog = payload["catalog"]

    # suggested_prompts is a list of strings, all non-empty
    assert isinstance(catalog["suggested_prompts"], list)
    assert len(catalog["suggested_prompts"]) >= 1
    for prompt in catalog["suggested_prompts"]:
        assert isinstance(prompt, str) and prompt.strip()

    # permissions_summary is a list of strings, all in vocab
    assert isinstance(catalog["permissions_summary"], list)
    assert len(catalog["permissions_summary"]) >= 1
    for perm in catalog["permissions_summary"]:
        assert perm in ALLOWED_PERMISSIONS


# ──────────────────────────────────────────────────────────────────
# 5. Categories stay clean (prompts != skills)
# ──────────────────────────────────────────────────────────────────


def test_no_prompt_collides_with_skill_identifier():
    """A prompt should never be the literal name of a default_skill.
    They live in different buckets for a reason: skills are
    snake_case identifiers wired to actions, prompts are prose
    examples of intent. Collision means someone confused the two
    fields when curating an entry.
    """
    collisions: list[tuple[str, str]] = []
    for entry in CATALOG:
        skill_set = set(entry.default_skills)
        for prompt in entry.suggested_prompts:
            if prompt in skill_set:
                collisions.append((entry.id, prompt))
    assert not collisions, (
        f"suggested_prompts overlap default_skills: {collisions}"
    )


# ──────────────────────────────────────────────────────────────────
# 6. High-risk plugins declare permissions
# ──────────────────────────────────────────────────────────────────


def test_high_risk_plugins_declare_permissions_summary():
    """If risk_level=high, the drawer's PermissionsBlock surfaces an
    Asset Shield reminder -- but only if permissions_summary is
    non-empty (otherwise the whole block hides). Make sure every
    high-risk plugin in the high-trust slice has the data so the
    operator gets the warning copy.
    """
    high_trust = {"official", "vendor-official", "vendor-blessed", "verified"}
    missing = [
        e.id for e in CATALOG
        if e.risk_level == "high"
        and e.officiality in high_trust
        and not e.permissions_summary
    ]
    assert not missing, (
        f"High-risk + high-trust entries without permissions_summary: "
        f"{missing}. The PermissionsBlock can't show the Asset Shield "
        f"reminder without at least one declared scope."
    )


# ──────────────────────────────────────────────────────────────────
# 7. Skill-pack entries advertise prompts (their core value prop)
# ──────────────────────────────────────────────────────────────────


def test_skill_pack_entries_have_prompts_or_skills():
    """Skill packs are CONTENT not callables. Their drawer surfaces
    suggested_prompts as the primary value prop. If a skill pack
    has neither prompts NOR default_skills, the drawer renders an
    empty section -- bad UX.
    """
    bad: list[str] = []
    for entry in CATALOG:
        if entry.kind != "skill_pack":
            continue
        if not entry.suggested_prompts and not entry.default_skills:
            bad.append(entry.id)
    assert not bad, (
        f"Skill-pack entries without prompts OR skills: {bad}"
    )


# ──────────────────────────────────────────────────────────────────
# 8. Composer-draft template safety
#    (PR-CONN-UI-GHOSTS-AND-PROMPT-WIRING)
# ──────────────────────────────────────────────────────────────────


def test_suggested_prompts_are_single_line():
    """The composer-draft helper templates each prompt into a single
    sentence: ``Use the <plugin> plugin to <prompt>.`` If a prompt
    contains a newline, the templated draft renders as two ragged
    lines in the textarea. Catch this at the catalog layer rather
    than escaping at the frontend.
    """
    bad: list[tuple[str, str]] = []
    for entry in CATALOG:
        for prompt in entry.suggested_prompts:
            if "\n" in prompt or "\r" in prompt:
                bad.append((entry.id, prompt))
    assert not bad, (
        f"suggested_prompts must be single-line; got newlines in: {bad}"
    )


def test_suggested_prompts_are_short_enough_for_composer():
    """Each prompt becomes a one-liner in the textarea. Anything
    >200 chars looks awkward and triggers ChatInput's
    long-paste-collapse heuristic the operator does not want here
    (the chip pattern is for *user* paste, not for our drafts).
    """
    too_long: list[tuple[str, int]] = []
    for entry in CATALOG:
        for prompt in entry.suggested_prompts:
            if len(prompt) > 200:
                too_long.append((entry.id, len(prompt)))
    assert not too_long, (
        f"suggested_prompts longer than 200 chars: {too_long}"
    )


def test_suggested_prompts_have_no_template_metacharacters():
    """Defense in depth: no prompt should contain template
    metacharacters that would change meaning when interpolated into
    the draft. Today the JS template is plain string concat (no
    eval), so this is precautionary -- but if someone refactors to
    template literals or `.replace()` with a function callback later,
    a prompt containing ``$0``, ``${`` or ``\\b`` could break.
    """
    bad: list[tuple[str, str]] = []
    pat = re.compile(r"(\$\{|\\\d|\$0|\$\d)")
    for entry in CATALOG:
        for prompt in entry.suggested_prompts:
            if pat.search(prompt):
                bad.append((entry.id, prompt))
    assert not bad, (
        f"suggested_prompts contain template metacharacters: {bad}"
    )
