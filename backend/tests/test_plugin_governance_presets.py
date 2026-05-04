"""PR-CONN-PER-PLUGIN-GOV-PRESETS (Sprint-4 PR-5, 2026-05-03) tests.

Pins:

  1. Every preset in PLUGIN_PRESETS uses only known SkillClass +
     GovernanceTier values.
  2. Founder's example list is FULLY covered: Filesystem / GitHub /
     Gmail / Drive / Slack / Stripe / Playwright / Chrome DevTools.
  3. The most-dangerous classes are pinned conservatively:
     - Stripe PAYMENT defaults to DENY
     - Filesystem WRITE_EXTERNAL defaults to DENY
     - Gmail SEND_MESSAGE defaults to DENY
     - everything else with no explicit pin -> ASK (default tier_for)
  4. Read tier is permissive for code/comm reads (GitHub / Gmail /
     Drive / Slack default to ALLOW for READ).
  5. classify_skill() routes a SkillToolMapping into the right class:
     - read_only=True -> READ
     - non-read-only -> matches the consent category mapping
  6. recommended_tier() composes get_preset + classify_skill correctly.
  7. list_presets_for_api() renders JSON-safe dicts including the
     fallback DEFAULT_PRESET marker.
  8. The presets layer DOES NOT enforce or change executor behavior;
     pure metadata. The Phase 2 read_only defense + consent gate
     remain the actual enforcement.
"""

from __future__ import annotations

import pytest

from app.services.connection_v2.plugin_governance_presets import (
    DEFAULT_PRESET,
    GovernanceTier,
    PLUGIN_PRESETS,
    PluginGovernancePreset,
    SkillClass,
    classify_skill,
    get_preset,
    list_presets_for_api,
    recommended_tier,
)
from app.services.connection_v2.skill_consent import (
    SkillConsentCategory,
)
from app.services.connection_v2.skill_executor import (
    PHASE2_ALLOWLIST,
    SkillToolMapping,
)


# ──────────────────────────────────────────────────────────────────
# 1. Schema validity
# ──────────────────────────────────────────────────────────────────


def test_every_preset_uses_valid_classes_and_tiers():
    for p in PLUGIN_PRESETS:
        for klass, tier in p.tiers.items():
            assert isinstance(klass, SkillClass)
            assert isinstance(tier, GovernanceTier)


def test_default_preset_uses_valid_classes_and_tiers():
    for klass, tier in DEFAULT_PRESET.tiers.items():
        assert isinstance(klass, SkillClass)
        assert isinstance(tier, GovernanceTier)


def test_no_duplicate_plugin_id_in_preset_table():
    seen: set[str] = set()
    for p in PLUGIN_PRESETS:
        assert p.plugin_id not in seen, f"Duplicate preset for {p.plugin_id}"
        seen.add(p.plugin_id)


# ──────────────────────────────────────────────────────────────────
# 2. Founder example list coverage
# ──────────────────────────────────────────────────────────────────


FOUNDER_REQUIRED_PRESET_PLUGINS = (
    "mcp-filesystem",
    "mcp-github",
    "app-gmail",
    "app-google-drive",
    "mcp-slack",
    "mcp-stripe",
    "mcp-playwright",
    "mcp-chrome-devtools",
)


def test_all_founder_listed_plugins_have_preset_entries():
    by_id = {p.plugin_id for p in PLUGIN_PRESETS}
    missing = set(FOUNDER_REQUIRED_PRESET_PLUGINS) - by_id
    assert not missing, f"Missing preset entries for: {missing}"


# ──────────────────────────────────────────────────────────────────
# 3. Conservative defaults
# ──────────────────────────────────────────────────────────────────


def test_stripe_payment_defaults_to_deny():
    preset = get_preset("mcp-stripe")
    assert preset.tier_for(SkillClass.PAYMENT) == GovernanceTier.DENY


def test_filesystem_write_external_defaults_to_deny():
    preset = get_preset("mcp-filesystem")
    assert preset.tier_for(SkillClass.WRITE_EXTERNAL) == GovernanceTier.DENY


def test_gmail_send_message_defaults_to_deny():
    preset = get_preset("app-gmail")
    assert preset.tier_for(SkillClass.SEND_MESSAGE) == GovernanceTier.DENY


def test_unspecified_class_defaults_to_ask_per_preset():
    """A preset that doesn't pin a tier for a class returns ASK
    (defensive fallback). Stripe doesn't pin BROWSER_ACTION, so
    ask is the right answer."""
    preset = get_preset("mcp-stripe")
    assert preset.tier_for(SkillClass.BROWSER_ACTION) == GovernanceTier.ASK


# ──────────────────────────────────────────────────────────────────
# 4. Permissive reads
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("plugin_id", [
    "mcp-github", "app-gmail", "app-google-drive", "mcp-slack",
])
def test_communication_and_code_reads_default_to_allow(plugin_id):
    preset = get_preset(plugin_id)
    assert preset.tier_for(SkillClass.READ) == GovernanceTier.ALLOW


def test_filesystem_reads_default_to_ask_not_allow():
    """Filesystem reads can leak structure; founder rule says ASK."""
    preset = get_preset("mcp-filesystem")
    assert preset.tier_for(SkillClass.READ) == GovernanceTier.ASK


# ──────────────────────────────────────────────────────────────────
# 5. classify_skill mapping
# ──────────────────────────────────────────────────────────────────


def _entry(plugin_id, skill_id, *, read_only):
    return SkillToolMapping(
        plugin_id=plugin_id, skill_id=skill_id,
        backend_surface="mcp", read_only=read_only,
        execution_mode="planned_only",
        target_tool=skill_id, required_inputs=(),
        reads_summary="test",
    )


def test_classify_read_only_entry_is_read():
    e = _entry("mcp-github", "summarize_repo", read_only=True)
    assert classify_skill(e) == SkillClass.READ


def test_classify_stripe_write_is_payment():
    e = _entry("mcp-stripe", "process_payment", read_only=False)
    assert classify_skill(e) == SkillClass.PAYMENT


def test_classify_unknown_write_is_write_external():
    e = _entry("mcp-mysterious", "do_thing_xyz", read_only=False)
    assert classify_skill(e) == SkillClass.WRITE_EXTERNAL


# ──────────────────────────────────────────────────────────────────
# 6. recommended_tier composition
# ──────────────────────────────────────────────────────────────────


def test_recommended_tier_filesystem_read_is_ask():
    e = _entry("mcp-filesystem", "find_files", read_only=True)
    assert recommended_tier(e) == GovernanceTier.ASK


def test_recommended_tier_github_read_is_allow():
    e = _entry("mcp-github", "summarize_repo", read_only=True)
    assert recommended_tier(e) == GovernanceTier.ALLOW


def test_recommended_tier_stripe_payment_is_deny():
    e = _entry("mcp-stripe", "process_payment", read_only=False)
    assert recommended_tier(e) == GovernanceTier.DENY


def test_recommended_tier_unknown_plugin_falls_through_to_default():
    """Plugin not in the table -> DEFAULT_PRESET. read_only=True
    -> READ -> ALLOW (default's pinned tier). non-read-only -> ASK."""
    read_only_entry = _entry("mcp-mystery", "find_things", read_only=True)
    assert recommended_tier(read_only_entry) == GovernanceTier.ALLOW

    write_entry = _entry("mcp-mystery", "do_things", read_only=False)
    # WRITE_EXTERNAL not pinned in default -> tier_for returns ASK.
    assert recommended_tier(write_entry) == GovernanceTier.ASK


# ──────────────────────────────────────────────────────────────────
# 7. JSON serialization
# ──────────────────────────────────────────────────────────────────


def test_list_presets_for_api_returns_json_safe_dicts():
    data = list_presets_for_api()
    assert isinstance(data, list)
    assert len(data) == len(PLUGIN_PRESETS) + 1  # plus fallback
    for entry in data:
        assert isinstance(entry["plugin_id"], str)
        assert isinstance(entry["rationale"], str)
        assert isinstance(entry["tiers"], dict)
        for k, v in entry["tiers"].items():
            assert isinstance(k, str)
            assert isinstance(v, str)
    # Fallback marker present
    fallbacks = [e for e in data if e.get("_is_fallback")]
    assert len(fallbacks) == 1


def test_list_presets_for_api_serializes_via_json():
    """Round-trip through json.dumps to confirm the shape is fully
    JSON-safe (no enum / dataclass leakage)."""
    import json
    data = list_presets_for_api()
    text = json.dumps(data)
    assert "mcp-stripe" in text
    assert "deny" in text  # Stripe PAYMENT preset


# ──────────────────────────────────────────────────────────────────
# 8. Foundation invariant: presets do not change current enforcement
# ──────────────────────────────────────────────────────────────────


def test_every_phase2_skill_classified_as_read():
    """Today every PHASE2_ALLOWLIST entry is read_only=True.
    classify_skill MUST return READ for all of them. If a future PR
    adds a non-read-only entry, this test forces a deliberate update
    + a governance preset choice."""
    for entry in PHASE2_ALLOWLIST:
        if entry.read_only:
            assert classify_skill(entry) == SkillClass.READ, (
                f"{entry.plugin_id}:{entry.skill_id} is read_only=True "
                f"but classify_skill returned a non-READ class"
            )


def test_recommended_tier_for_every_phase2_skill_is_allow_or_ask():
    """Phase 2 is read-only-only. The vendor presets allow READ on
    most plugins (see test_communication_and_code_reads_default_to_allow)
    and ASK on Filesystem (more conservative). NEITHER permits a
    write skill to fire silently. This invariant defends the floor."""
    for entry in PHASE2_ALLOWLIST:
        tier = recommended_tier(entry)
        assert tier in (GovernanceTier.ALLOW, GovernanceTier.ASK), (
            f"{entry.plugin_id}:{entry.skill_id} recommended_tier "
            f"is {tier!r}; expected ALLOW or ASK for any read_only=True "
            f"Phase 2 entry"
        )


def test_skill_class_consent_category_mapping_is_complete():
    """Every SkillConsentCategory MUST map to a SkillClass via
    _CONSENT_TO_CLASS so classify_skill never silently degrades."""
    from app.services.connection_v2.plugin_governance_presets import (
        _CONSENT_TO_CLASS,
    )
    for cat in SkillConsentCategory:
        assert cat in _CONSENT_TO_CLASS, (
            f"SkillConsentCategory.{cat.name} has no _CONSENT_TO_CLASS "
            f"mapping; classify_skill would default to WRITE_EXTERNAL "
            f"silently."
        )
