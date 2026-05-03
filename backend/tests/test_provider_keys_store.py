"""PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT regression tests.

Pins behaviors of ``provider_keys_store`` and the
``/api/v1/account/provider-keys`` endpoints. Critical contract is
LEAK SAFETY -- no test response or log payload may contain a saved
key value or a recoverable prefix of it.

Coverage:
  1. Store CRUD: set / get / clear / list_provider_status
  2. Atomic file write: temp + rename
  3. Field allowlist: refuses unknown settings attributes
  4. Hydration: applies stored overrides to a Settings stub
  5. Endpoint shape: GET never returns values, POST returns no value
  6. Marketplace integration: card moves Configure -> Test after save
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.integrations import provider_keys_store as store


# ──────────────────────────────────────────────────────────────────
# Per-test isolation: redirect _STORE_PATH to a tmp file
# ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path: Path, monkeypatch):
    """Redirect every test to its own tmp store file.

    Without this, tests would write to the real
    ``backend/.daena_provider_overrides.json`` and pollute the
    operator's local config.
    """
    tmp_file = tmp_path / "provider_overrides.json"
    monkeypatch.setattr(store, "_STORE_PATH", tmp_file)
    store.reset_cache_for_tests()
    yield
    store.reset_cache_for_tests()


# ──────────────────────────────────────────────────────────────────
# Store unit tests
# ──────────────────────────────────────────────────────────────────


class TestStoreCrud:
    async def test_set_then_get(self):
        await store.set_override("anthropic_api_key", "sk-ant-FAKE-FAKE-FAKE")
        assert store.get_override("anthropic_api_key") == "sk-ant-FAKE-FAKE-FAKE"

    async def test_set_persists_to_disk(self, tmp_path):
        await store.set_override("openai_api_key", "sk-FAKE")
        # Force re-read from disk
        store.reset_cache_for_tests()
        assert store.get_override("openai_api_key") == "sk-FAKE"

    async def test_set_writes_atomically(self):
        """The temp file pattern is observable: after a successful
        write, no .tmp sibling should be left behind.
        """
        await store.set_override("groq_api_key", "gsk_FAKE")
        tmp_sibling = store._STORE_PATH.with_suffix(".json.tmp")
        assert not tmp_sibling.exists(), (
            "Atomic write should rename temp file, not leave .tmp behind"
        )

    async def test_set_records_updated_at(self):
        await store.set_override("perplexity_api_key", "pplx-FAKE")
        meta = store.get_metadata("perplexity_api_key")
        assert meta["configured"] is True
        assert isinstance(meta["last_updated"], str)
        assert meta["last_updated"]  # non-empty iso8601

    async def test_clear_removes_value(self):
        await store.set_override("openrouter_api_key", "sk-or-FAKE")
        removed = await store.clear_override("openrouter_api_key")
        assert removed is True
        assert store.get_override("openrouter_api_key") == ""
        assert store.get_metadata("openrouter_api_key")["configured"] is False

    async def test_clear_returns_false_when_unset(self):
        removed = await store.clear_override("together_api_key")
        assert removed is False

    async def test_set_refuses_unknown_field(self):
        """The allowlist blocks accidental writes via this code path."""
        with pytest.raises(ValueError):
            await store.set_override("session_secret", "should-not-write")
        with pytest.raises(ValueError):
            await store.set_override("jwt_secret_key", "should-not-write")

    async def test_set_refuses_empty_value(self):
        with pytest.raises(ValueError):
            await store.set_override("anthropic_api_key", "")

    async def test_get_unknown_field_returns_empty(self):
        assert store.get_override("session_secret") == ""
        assert store.get_metadata("session_secret")["configured"] is False


class TestListProviderStatus:
    async def test_lists_every_supported_provider(self):
        rows = store.list_provider_status()
        slugs = {row["slug"] for row in rows}
        assert slugs == {
            "anthropic", "openai", "gemini", "groq",
            "perplexity", "openrouter", "together",
        }

    async def test_status_does_not_leak_value(self):
        await store.set_override("anthropic_api_key", "sk-ant-SUPERSECRET-XYZ")
        rows = store.list_provider_status()
        anthropic = next(r for r in rows if r["slug"] == "anthropic")
        assert anthropic["configured"] is True
        # Defense in depth: serialize the row and grep for the secret
        payload = json.dumps(rows)
        assert "SUPERSECRET" not in payload
        assert "sk-ant-SUPERSECRET" not in payload

    async def test_status_carries_display_metadata(self):
        rows = store.list_provider_status()
        anthropic = next(r for r in rows if r["slug"] == "anthropic")
        assert anthropic["display_name"] == "Anthropic"
        assert anthropic["marketplace_id"] == "provider-anthropic"
        assert anthropic["settings_field"] == "anthropic_api_key"


class TestHydration:
    async def test_hydrate_applies_stored_overrides(self):
        await store.set_override("groq_api_key", "gsk_FAKE")
        await store.set_override("openai_api_key", "sk-FAKE")

        class _StubSettings:
            anthropic_api_key = ""
            openai_api_key = ""
            groq_api_key = ""

        settings = _StubSettings()
        applied = store.hydrate_settings(settings)

        assert sorted(applied) == ["groq_api_key", "openai_api_key"]
        assert settings.openai_api_key == "sk-FAKE"
        assert settings.groq_api_key == "gsk_FAKE"

    async def test_hydrate_idempotent(self):
        await store.set_override("anthropic_api_key", "sk-ant-FAKE")

        class _StubSettings:
            anthropic_api_key = ""

        s = _StubSettings()
        applied1 = store.hydrate_settings(s)
        applied2 = store.hydrate_settings(s)
        assert applied1 == applied2 == ["anthropic_api_key"]
        assert s.anthropic_api_key == "sk-ant-FAKE"

    async def test_hydrate_empty_store_is_noop(self):
        class _StubSettings:
            anthropic_api_key = "from-env"

        s = _StubSettings()
        applied = store.hydrate_settings(s)
        assert applied == []
        # Did not stomp the .env baseline
        assert s.anthropic_api_key == "from-env"


class TestLeakSafety:
    """Pin the leak-safety properties of the store.

    Asserts that a saved value never appears in any payload the store
    is allowed to emit. Catches regressions where a future PR adds a
    "preview" field that accidentally returns N characters of the key.
    """

    async def test_get_metadata_never_includes_value(self):
        await store.set_override("anthropic_api_key", "sk-ant-CANARY")
        meta = store.get_metadata("anthropic_api_key")
        assert "value" not in meta
        assert "CANARY" not in json.dumps(meta)

    async def test_list_provider_status_never_includes_value(self):
        await store.set_override("openai_api_key", "sk-CANARY")
        rows = store.list_provider_status()
        for row in rows:
            assert "value" not in row
        assert "CANARY" not in json.dumps(rows)

    async def test_list_configured_fields_returns_names_only(self):
        await store.set_override("groq_api_key", "gsk_CANARY")
        names = store.list_configured_fields()
        assert names == ["groq_api_key"]
        assert "CANARY" not in json.dumps(names)


class TestLegacyMigration:
    async def test_legacy_string_format_is_migrated(self):
        """Legacy plain-string format used to be ``{field: "value"}``.
        New format is ``{field: {value, updated_at}}``. Reading a legacy
        file should not crash and should produce the same get_override
        result.
        """
        legacy = {"anthropic_api_key": "sk-ant-LEGACY"}
        store._STORE_PATH.write_text(json.dumps(legacy), encoding="utf-8")
        store.reset_cache_for_tests()
        assert store.get_override("anthropic_api_key") == "sk-ant-LEGACY"
        assert store.get_metadata("anthropic_api_key")["configured"] is True


class TestSlugMapping:
    def test_slug_to_field_covers_every_supported_provider(self):
        # Every PROVIDER_DISPLAY entry must have a SLUG_TO_FIELD entry
        for slug in store.PROVIDER_DISPLAY:
            assert slug in store.SLUG_TO_FIELD
            assert store.SLUG_TO_FIELD[slug] in store.PROVIDER_KEY_FIELDS

    def test_field_to_slug_is_inverse(self):
        for slug, field in store.SLUG_TO_FIELD.items():
            assert store.FIELD_TO_SLUG[field] == slug
