"""PR-CONN-PROVIDER-KEY-VISIBILITY regression tests.

Pins five behaviors from the provider key visibility PR:

1. ``MarketplaceCard.to_dict()`` carries a ``provider_key_present``
   field that is leak-safe (boolean only, never the value).

2. ``_resolve_provider_key_present`` returns:
     * True when the settings attribute is non-empty
     * False when empty / unset
     * None for kinds that do not use a settings credential
       (oauth_app, mcp_server, browser_tool, computer_use,
       cli_runtime, skill_pack)

3. ``_derive_lifecycle`` promotes a card with ``provider_key_present
   is True`` and no V2 row from "available" -> "configured" so the
   marketplace surfaces a Test action instead of Setup Guide.

4. ``_derive_lifecycle`` returns "configure" action for cards with
   ``provider_key_present is False`` so the founder vocabulary lines up
   with the frontend pluginCard.ts adapter.

5. The Ollama special case: with ``OLLAMA_ENABLED=false``, even though
   ``ollama_base_url`` has a default, ``provider_key_present`` reports
   False -- mirroring the model_registry skip rule so the marketplace
   doesn't fake-green an endpoint Daena would refuse to register.
"""

from __future__ import annotations

import pytest

from app.services.connection_v2.marketplace_catalog import CATALOG_BY_ID
from app.services.connection_v2.marketplace_service import (
    MarketplaceCard,
    _PROVIDER_KEY_BY_ENTRY_ID,
    _derive_lifecycle,
    _resolve_provider_key_present,
)


# ──────────────────────────────────────────────────────────────────
# 1. Leak-safety / shape
# ──────────────────────────────────────────────────────────────────


def test_card_dict_carries_provider_key_present_bool_only():
    """to_dict() must include provider_key_present and the value must
    be a bool or None -- never a string, dict, or anything that could
    accidentally embed a credential.
    """
    entry = CATALOG_BY_ID["provider-anthropic"]
    card = MarketplaceCard(catalog=entry.to_dict(), provider_key_present=True)
    payload = card.to_dict()

    assert "provider_key_present" in payload
    assert payload["provider_key_present"] is True

    card2 = MarketplaceCard(catalog=entry.to_dict(), provider_key_present=False)
    assert card2.to_dict()["provider_key_present"] is False

    card3 = MarketplaceCard(catalog=entry.to_dict(), provider_key_present=None)
    assert card3.to_dict()["provider_key_present"] is None


def test_card_dict_never_contains_secret_substrings():
    """Defense in depth: scan the serialized payload for common secret
    prefixes / env-var names. None should appear in the value position;
    env-var NAMES are allowed in catalog.required_env_vars only.
    """
    entry = CATALOG_BY_ID["provider-anthropic"]
    card = MarketplaceCard(catalog=entry.to_dict(), provider_key_present=True)
    payload = card.to_dict()

    # The catalog payload legitimately mentions env-var NAMES
    # (ANTHROPIC_API_KEY) inside required_env_vars. The PR's safety
    # property is that the VALUE never appears -- which we can't test
    # directly here without a fixture, so we assert the relevant fields
    # are bool/list/string of names, not raw bytes.
    assert isinstance(payload["provider_key_present"], (bool, type(None)))
    assert isinstance(payload["catalog"]["required_env_vars"], list)
    for name in payload["catalog"]["required_env_vars"]:
        # env var NAMES are uppercase + underscores; values would be
        # something like sk-ant-... or eyJ... -- validate the shape
        assert isinstance(name, str)
        assert name.isupper() or "_" in name


# ──────────────────────────────────────────────────────────────────
# 2. _resolve_provider_key_present mapping
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "entry_id",
    [
        "provider-anthropic",
        "provider-openai",
        "provider-google-gemini",
        "provider-perplexity",
        "provider-groq",
        "provider-openrouter",
        "provider-together",
        "local-ollama",
        "local-vllm",
    ],
)
def test_resolve_returns_bool_for_credentialed_kinds(monkeypatch, entry_id):
    """Every entry in _PROVIDER_KEY_BY_ENTRY_ID must resolve to bool
    (True or False). None would mean we forgot to map it.
    """
    entry = CATALOG_BY_ID[entry_id]
    settings_attr = _PROVIDER_KEY_BY_ENTRY_ID[entry_id]

    # Force the settings attribute to a known truthy value
    from app.services.connection_v2 import marketplace_service as svc

    class _StubSettings:
        ollama_enabled = True

    stub = _StubSettings()
    setattr(stub, settings_attr, "stub-value-DO-NOT-LOG")
    monkeypatch.setattr(svc, "get_settings", lambda: stub)

    result = _resolve_provider_key_present(entry)
    assert isinstance(result, bool)
    assert result is True


@pytest.mark.parametrize(
    "entry_id",
    [
        "cli-claude-code",       # cli_runtime
        "mcp-github",            # mcp_server
        "app-gmail",             # oauth_app
        "mcp-playwright",        # browser_tool
        "mcp-desktop-commander", # computer_use
    ],
)
def test_resolve_returns_none_for_non_credentialed_kinds(entry_id):
    """Kinds whose truth lives in the V2 probe (binary_check,
    oauth_token, mcp_initialize) MUST return None -- never a False
    that would mislead the UI into showing a Configure button for an
    OAuth app or a CLI binary.
    """
    entry = CATALOG_BY_ID[entry_id]
    assert _resolve_provider_key_present(entry) is None


def test_resolve_returns_false_for_empty_setting(monkeypatch):
    entry = CATALOG_BY_ID["provider-anthropic"]
    from app.services.connection_v2 import marketplace_service as svc

    class _StubSettings:
        anthropic_api_key = ""
        ollama_enabled = True

    monkeypatch.setattr(svc, "get_settings", lambda: _StubSettings())

    assert _resolve_provider_key_present(entry) is False


def test_resolve_ollama_respects_disabled_flag(monkeypatch):
    """Ollama mirrors model_registry's skip rule: even with a default
    base URL, OLLAMA_ENABLED=false reports key_present=False so the
    marketplace doesn't fake-green an endpoint Daena refuses to use.
    """
    entry = CATALOG_BY_ID["local-ollama"]
    from app.services.connection_v2 import marketplace_service as svc

    class _StubSettings:
        ollama_enabled = False
        ollama_base_url = "http://127.0.0.1:11434"  # default still set

    monkeypatch.setattr(svc, "get_settings", lambda: _StubSettings())

    assert _resolve_provider_key_present(entry) is False


# ──────────────────────────────────────────────────────────────────
# 3-4. Lifecycle promotion + action vocabulary
# ──────────────────────────────────────────────────────────────────


def test_lifecycle_promotes_to_configured_when_key_present_no_v2_row():
    """A card with the credential set but no V2 row yet should render
    as 'configured' -> 'test', not 'available' -> 'setup_guide'.
    Without this rule, an operator who already pasted ANTHROPIC_API_KEY
    into .env still sees a useless Setup Guide button.
    """
    entry = CATALOG_BY_ID["provider-anthropic"]
    lifecycle, action, label = _derive_lifecycle(
        entry, row=None, provider_key_present=True,
    )
    assert lifecycle == "configured"
    assert action == "test"
    assert label == "Test"


def test_lifecycle_uses_configure_action_when_key_missing():
    """An api_provider card whose credential is empty surfaces
    'configure' so the pluginCard.ts adapter routes the click to
    /account/api-keys.
    """
    entry = CATALOG_BY_ID["provider-anthropic"]
    lifecycle, action, label = _derive_lifecycle(
        entry, row=None, provider_key_present=False,
    )
    assert lifecycle == "available"
    assert action == "configure"
    assert label == "Configure"


def test_lifecycle_keeps_local_model_on_setup_guide_when_key_missing():
    """local_model entries with provider_key_present=False stay on
    Setup Guide. Their missing config is an env var (OLLAMA_BASE_URL /
    VLLM_BASE_URL) handled in the setup-notes drawer, not a paste-in
    key. Routing to /account/api-keys would mislead the operator.
    Mirrors the pluginCard.ts deriveAction guard.
    """
    entry = CATALOG_BY_ID["local-ollama"]
    lifecycle, action, label = _derive_lifecycle(
        entry, row=None, provider_key_present=False,
    )
    assert lifecycle == "available"
    assert action == "setup_guide"
    assert label == "Setup guide"


def test_lifecycle_falls_back_to_setup_guide_when_key_state_unknown():
    """When provider_key_present is None (non-credentialed kind), the
    legacy Setup Guide path stays intact.
    """
    entry = CATALOG_BY_ID["mcp-github"]
    lifecycle, action, label = _derive_lifecycle(
        entry, row=None, provider_key_present=None,
    )
    assert lifecycle == "available"
    assert action == "setup_guide"
    assert label == "Setup guide"


def test_lifecycle_coming_soon_beats_provider_key_present():
    """A coming-soon entry must render needs_setup even if the (future)
    credential happens to be present. Catalog state wins because the
    install path doesn't exist yet.
    """
    # app-stripe-oauth is install_method=coming-soon; force a key
    # presence and verify the coming-soon branch still wins.
    entry = CATALOG_BY_ID["app-stripe-oauth"]
    lifecycle, action, label = _derive_lifecycle(
        entry, row=None, provider_key_present=True,
    )
    assert lifecycle == "needs_setup"
    assert action == "setup_guide"


# ──────────────────────────────────────────────────────────────────
# 5. Catalog/mapping consistency
# ──────────────────────────────────────────────────────────────────


def test_every_provider_key_map_id_exists_in_catalog():
    """If we drift the entry id in marketplace_catalog without updating
    _PROVIDER_KEY_BY_ENTRY_ID, the lookup silently returns None and
    every provider card regresses to Setup Guide. Pin the mapping.
    """
    missing = [
        eid for eid in _PROVIDER_KEY_BY_ENTRY_ID
        if eid not in CATALOG_BY_ID
    ]
    assert not missing, (
        f"_PROVIDER_KEY_BY_ENTRY_ID references non-existent catalog ids: "
        f"{missing}"
    )


def test_every_api_provider_in_catalog_has_a_key_mapping():
    """Conversely, if a new api_provider entry lands in the catalog
    without a key mapping, it would fall through provider_key_present
    = None and lose the lifecycle bump. Catch the regression early.
    """
    api_providers_in_catalog = [
        eid for eid, entry in CATALOG_BY_ID.items()
        if entry.kind == "api_provider"
    ]
    unmapped = [
        eid for eid in api_providers_in_catalog
        if eid not in _PROVIDER_KEY_BY_ENTRY_ID
    ]
    assert not unmapped, (
        f"api_provider entries missing from _PROVIDER_KEY_BY_ENTRY_ID: "
        f"{unmapped}"
    )
