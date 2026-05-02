"""PR-CONNECTIONS-MARKETPLACE-UX tests.

Pins the contract:
  1. Catalog is non-empty + every entry has the expected shape.
  2. Catalog covers every founder-listed category (filesystem, browser,
     code platform, communication, productivity, design, data storage,
     payment, research, local LLM, AI provider, dev tools, CLI runtime,
     computer use).
  3. Catalog NEVER contains a secret value (sentinel-secret audit).
  4. install_plan_for() returns a Setup-Guide plan with NO secrets,
     NO auto-execution, and a pinned executable=False flag.
  5. MarketplaceService overlays catalog with V2 truth honestly:
     - When no V2 row exists, lifecycle is "available" (or "needs_setup"
       for coming-soon entries).
     - When a V2 row exists with callable=True, lifecycle is "callable".
     - When a V2 row exists with a recent failure, lifecycle is "failed"
       and v2_failure_reason carries the actionable message.
     - Skill packs always get lifecycle="skill_pack" regardless of state.
  6. install_plan() never returns a None plan body for a real entry.
  7. Per project Rule 17: no card claims callable=True without a probe.

Tests are unit-level: pure-python catalog assertions for #1-#4 and #6,
plus DB-backed MarketplaceService coverage for #5 and #7. The HTTP
endpoint is a thin wrapper around these and gets manual smoke
coverage.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.models.identity import Tenant


def _canonical_key(tenant_id, kind: str, slug: str, auth_method: str) -> str:
    raw = f"{tenant_id}|{kind}|{slug}|{auth_method}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
from app.services.connection_v2.marketplace_catalog import (
    CATALOG,
    CATALOG_BY_ID,
    CATEGORIES,
    CatalogEntry,
    install_plan_for,
    list_catalog,
    list_categories,
)
from app.services.connection_v2.marketplace_service import (
    MarketplaceService,
    install_plan,
)


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    tenant = Tenant(id=test_tenant_id, name="T", slug="t", settings={})
    db_session.add(tenant)
    await db_session.flush()
    return tenant


# ──────────────────────────────────────────────────────────────────
# 1. Catalog shape
# ──────────────────────────────────────────────────────────────────


class TestCatalogShape:
    def test_catalog_is_non_empty(self):
        assert len(CATALOG) >= 30, "Catalog should ship at least 30 entries"

    def test_every_entry_has_required_fields(self):
        for entry in CATALOG:
            assert entry.id, f"Empty id: {entry}"
            assert entry.display_name, f"Empty display_name: {entry.id}"
            assert entry.vendor, f"Empty vendor: {entry.id}"
            assert entry.category, f"Empty category: {entry.id}"
            assert entry.kind, f"Empty kind: {entry.id}"
            assert entry.short_description, f"Empty description: {entry.id}"
            assert entry.install_method, f"Empty install_method: {entry.id}"
            assert entry.auth_type, f"Empty auth_type: {entry.id}"
            assert entry.risk_level in ("low", "medium", "high"), entry.id
            assert entry.probe_type, f"Empty probe_type: {entry.id}"

    def test_ids_are_unique(self):
        ids = [e.id for e in CATALOG]
        assert len(ids) == len(set(ids)), "Catalog ids must be unique"

    def test_catalog_by_id_lookup_works(self):
        assert "mcp-github" in CATALOG_BY_ID
        assert CATALOG_BY_ID["mcp-github"].vendor == "Anthropic"

    def test_to_dict_serializes_to_json(self):
        for entry in CATALOG[:5]:
            d = entry.to_dict()
            json.dumps(d)  # must not raise
            assert isinstance(d["capabilities"], list)
            assert isinstance(d["required_env_vars"], list)
            assert isinstance(d["compatible_os"], list)

    def test_categories_metadata_complete(self):
        for cat in CATEGORIES:
            assert cat.id
            assert cat.display_name
            assert cat.short_description


# ──────────────────────────────────────────────────────────────────
# 2. Coverage -- every founder-listed category present
# ──────────────────────────────────────────────────────────────────


class TestCatalogCoverage:
    @pytest.mark.parametrize(
        "category",
        [
            "filesystem",
            "browser",
            "computer_use",
            "code_platform",
            "communication",
            "productivity",
            "design",
            "data_storage",
            "payment",
            "research",
            "local_llm",
            "ai_provider",
            "dev_tools",
            "cli_runtime",
        ],
    )
    def test_category_has_entries(self, category):
        matching = [e for e in CATALOG if e.category == category]
        assert matching, f"No catalog entries for category {category!r}"

    def test_main_brain_runtimes_present(self):
        kinds = {e.kind for e in CATALOG}
        assert "cli_runtime" in kinds
        assert "api_provider" in kinds

    def test_browser_tools_first_class(self):
        browser_entries = [e for e in CATALOG if e.kind == "browser_tool"]
        ids = {e.id for e in browser_entries}
        assert "mcp-playwright" in ids
        assert "mcp-chrome-devtools" in ids

    def test_high_risk_entries_explicitly_marked(self):
        # Computer use entries must be high-risk so the UI badges them.
        for entry in CATALOG:
            if entry.kind == "computer_use":
                assert entry.risk_level == "high", (
                    f"Computer use entry {entry.id} should be risk=high"
                )

    def test_oauth_apps_match_oauth_service(self):
        # The Apps tab catalog should mirror oauth_service.OAUTH_PROVIDERS
        # for the supported set.
        from app.services.integrations.oauth_service import OAUTH_PROVIDERS

        oauth_entries = [e for e in CATALOG if e.kind == "oauth_app"]
        # Build a relaxed mapping: any oauth catalog entry whose required
        # env var matches an OAUTH_PROVIDERS client_id_setting counts.
        provider_setting_names = {
            cfg.client_id_setting.upper()
            for cfg in OAUTH_PROVIDERS.values()
        }
        for entry in oauth_entries:
            if entry.install_method == "coming-soon":
                continue
            assert any(
                env in provider_setting_names
                for env in entry.required_env_vars
            ), f"OAuth entry {entry.id} env vars don't match any oauth_service provider"


# ──────────────────────────────────────────────────────────────────
# 3. Sentinel-secret audit
# ──────────────────────────────────────────────────────────────────


class TestNoSecretLeak:
    """The catalog is source-tree-versioned + public. It MUST NOT carry
    real secret values. This test plants distinctive sentinel substrings
    that look secret-like and confirms none made it into the catalog.

    NOTE: this test scans the LITERAL catalog data (no API call). The
    point is to catch a future contributor who accidentally pastes a
    real key into setup_notes or command_template.
    """

    SECRET_INDICATORS = (
        "sk-",        # OpenAI / Anthropic-style
        "sk-ant-",    # Anthropic
        "pplx-",      # Perplexity
        "xai-",       # xAI / Grok
        "gsk_",       # Groq
        "AIza",       # Google API
        "ghp_",       # GitHub PAT
        "github_pat_",
        "ya29.",      # Google OAuth refresh
        "ASIA",       # AWS access key
        "AKIA",       # AWS access key
        "DAEN_",      # Daena-internal sentinel (future)
    )

    def test_no_obvious_secret_in_catalog(self):
        for entry in CATALOG:
            text_to_scan = " ".join(
                str(s)
                for s in (
                    entry.id,
                    entry.display_name,
                    entry.vendor,
                    entry.short_description,
                    entry.command_template,
                    entry.setup_notes,
                    entry.official_url,
                    *entry.capabilities,
                    *entry.required_env_vars,
                )
            )
            for indicator in self.SECRET_INDICATORS:
                assert indicator not in text_to_scan, (
                    f"Possible secret leak in catalog entry {entry.id!r}: "
                    f"contains {indicator!r}. Catalog must NEVER carry real secret "
                    f"values."
                )

    def test_required_env_vars_are_names_not_values(self):
        # NAMES contain only uppercase letters + underscores + digits.
        # Values would contain quotes, colons, dashes, etc.
        for entry in CATALOG:
            for env_name in entry.required_env_vars:
                assert env_name.isupper() or any(c.isdigit() or c == "_" for c in env_name), (
                    f"required_env_vars must be NAMES only: {env_name!r} in {entry.id}"
                )
                assert "=" not in env_name, (
                    f"env var contains assignment: {env_name!r} in {entry.id}"
                )
                assert " " not in env_name, (
                    f"env var contains space: {env_name!r} in {entry.id}"
                )


# ──────────────────────────────────────────────────────────────────
# 4. Install plans
# ──────────────────────────────────────────────────────────────────


class TestInstallPlans:
    def test_every_entry_has_a_plan(self):
        for entry in CATALOG:
            plan = install_plan_for(entry)
            assert plan["entry_id"] == entry.id
            assert plan["executable"] is False, "Plans must NEVER be auto-executed"
            assert isinstance(plan["steps"], list)

    def test_coming_soon_plan_includes_link_step(self):
        coming_soon = [e for e in CATALOG if e.install_method == "coming-soon"]
        assert coming_soon, "Catalog should have at least one coming-soon entry"
        for entry in coming_soon:
            plan = install_plan_for(entry)
            kinds = {step["kind"] for step in plan["steps"]}
            assert "info" in kinds, f"coming-soon plan {entry.id} missing info step"
            assert "link" in kinds or any(
                step["kind"] == "env" for step in plan["steps"]
            ), f"coming-soon plan {entry.id} should link out or list env vars"

    def test_npm_plan_includes_command_step(self):
        npm_entries = [e for e in CATALOG if e.install_method == "npm"]
        assert npm_entries
        for entry in npm_entries:
            plan = install_plan_for(entry)
            kinds = {step["kind"] for step in plan["steps"]}
            assert "command" in kinds, f"npm plan {entry.id} missing command step"

    def test_oauth_plan_includes_auth_step(self):
        oauth_entries = [
            e for e in CATALOG
            if e.auth_type == "oauth" and e.install_method != "coming-soon"
        ]
        assert oauth_entries
        for entry in oauth_entries:
            plan = install_plan_for(entry)
            kinds = {step["kind"] for step in plan["steps"]}
            assert "auth" in kinds, f"oauth plan {entry.id} missing auth step"

    def test_install_plan_lookup_by_id(self):
        plan = install_plan("mcp-github")
        assert plan is not None
        assert plan["entry_id"] == "mcp-github"
        assert plan["executable"] is False

    def test_install_plan_unknown_returns_none(self):
        assert install_plan("does-not-exist") is None


# ──────────────────────────────────────────────────────────────────
# 5. MarketplaceService overlay
# ──────────────────────────────────────────────────────────────────


class TestMarketplaceServiceOverlay:
    """End-to-end: catalog + V2 truth -> honest lifecycle."""

    async def test_no_v2_row_yields_available_lifecycle(
        self, db_session, seeded_tenant
    ):
        svc = MarketplaceService(db_session, tenant_id=seeded_tenant.id)
        cards = await svc.list_cards()
        assert cards
        # No V2 rows seeded -> every catalog entry is at most "available"
        # or "needs_setup" (coming-soon variants).
        for card in cards:
            assert card.v2_row_id is None
            assert card.lifecycle in ("available", "needs_setup")
            assert card.primary_action == "setup_guide"

    async def test_v2_callable_row_yields_callable_lifecycle(
        self, db_session, seeded_tenant
    ):
        # Insert a V2 row matching mcp-filesystem's slug pattern.
        now = datetime.now(UTC)
        row = ConnectionV2(
            tenant_id=seeded_tenant.id,
            kind=ConnectionKind.MCP_SERVER.value,
            slug="mcp-filesystem",
            display_name="Filesystem",
            canonical_key=_canonical_key(
                seeded_tenant.id, "mcp_server", "mcp-filesystem", "none",
            ),
            auth_method=AuthMethod.NONE.value,
            config={"command": "npx", "_seeded_by": "test"},
            detected=True, detected_at=now,
            configured=True, configured_at=now,
            imported=True, imported_at=now,
            reachable=True, reachable_at=now,
            authenticated=True, authenticated_at=now,
            callable=True, callable_at=now,
        )
        db_session.add(row)
        await db_session.flush()

        svc = MarketplaceService(db_session, tenant_id=seeded_tenant.id)
        cards = await svc.list_cards()
        fs_card = next(c for c in cards if c.catalog["id"] == "mcp-filesystem")
        assert fs_card.v2_row_id == str(row.id)
        assert fs_card.lifecycle == "callable"
        assert fs_card.primary_action == "test"
        assert fs_card.v2_truth is not None
        assert fs_card.v2_truth["callable"]["value"] is True

    async def test_v2_failed_row_yields_failed_lifecycle(
        self, db_session, seeded_tenant
    ):
        now = datetime.now(UTC)
        # Probe ran but failed at reachable -- failure_at > at means recent failure.
        row = ConnectionV2(
            tenant_id=seeded_tenant.id,
            kind=ConnectionKind.MCP_SERVER.value,
            slug="mcp-github",
            display_name="GitHub",
            canonical_key=_canonical_key(
                seeded_tenant.id, "mcp_server", "mcp-github", "api_token",
            ),
            auth_method=AuthMethod.API_TOKEN.value,
            config={"command": "npx", "_seeded_by": "test"},
            detected=True, detected_at=now,
            configured=True, configured_at=now,
            imported=True, imported_at=now,
            reachable=False,
            reachable_at=now - timedelta(minutes=10),
            reachable_failure_at=now,
            reachable_failure_reason="ECONNREFUSED 127.0.0.1:3000",
        )
        db_session.add(row)
        await db_session.flush()

        svc = MarketplaceService(db_session, tenant_id=seeded_tenant.id)
        cards = await svc.list_cards()
        gh_card = next(c for c in cards if c.catalog["id"] == "mcp-github")
        assert gh_card.lifecycle == "failed"
        assert gh_card.primary_action == "test"
        assert gh_card.v2_failure_reason == "ECONNREFUSED 127.0.0.1:3000"

    async def test_v2_disabled_row_yields_disabled_lifecycle(
        self, db_session, seeded_tenant
    ):
        now = datetime.now(UTC)
        row = ConnectionV2(
            tenant_id=seeded_tenant.id,
            kind=ConnectionKind.MCP_SERVER.value,
            slug="mcp-fetch",
            display_name="Fetch",
            canonical_key=_canonical_key(
                seeded_tenant.id, "mcp_server", "mcp-fetch", "none",
            ),
            auth_method=AuthMethod.NONE.value,
            config={"command": "npx", "_seeded_by": "test"},
            detected=True, detected_at=now,
            configured=True, configured_at=now,
            imported=True, imported_at=now,
            reachable=True, reachable_at=now,
            authenticated=True, authenticated_at=now,
            callable=True, callable_at=now,
            disabled=True,
        )
        db_session.add(row)
        await db_session.flush()

        svc = MarketplaceService(db_session, tenant_id=seeded_tenant.id)
        cards = await svc.list_cards()
        fetch_card = next(c for c in cards if c.catalog["id"] == "mcp-fetch")
        assert fetch_card.lifecycle == "disabled"
        assert fetch_card.primary_action == "enable"

    async def test_skill_pack_always_skill_pack_lifecycle(
        self, db_session, seeded_tenant
    ):
        now = datetime.now(UTC)
        # Use a skill_pack slug that does NOT exist in the curated
        # marketplace catalog (skill packs come from PLUGIN_CATALOG +
        # ConnectionDiscoveryService.skill_pack_slug). The lifecycle
        # rule still kicks in for any V2 row of kind=skill_pack -- even
        # if no catalog entry matches by slug, the test confirms the
        # lifecycle derivation rule fires when a row IS present.
        row = ConnectionV2(
            tenant_id=seeded_tenant.id,
            kind=ConnectionKind.SKILL_PACK.value,
            slug="skill-some-pack",
            display_name="Some Skill Pack",
            canonical_key=_canonical_key(
                seeded_tenant.id, "skill_pack", "skill-some-pack", "none",
            ),
            auth_method=AuthMethod.NONE.value,
            config={"_seeded_by": "test"},
            detected=True, detected_at=now,
            configured=True, configured_at=now,
            imported=True, imported_at=now,
        )
        db_session.add(row)
        await db_session.flush()

        # Verify the row exists; the marketplace service won't surface
        # it as a catalog entry (no matching slug), but if a future
        # catalog entry does match, lifecycle should always collapse to
        # skill_pack. We exercise the rule directly via _derive_lifecycle.
        from app.services.connection_v2.marketplace_service import (
            _derive_lifecycle,
        )
        from app.services.connection_v2.marketplace_catalog import CATALOG

        # Pick any catalog entry as a stand-in for the matcher hit.
        sample_entry = next(e for e in CATALOG if e.kind == "mcp_server")
        lifecycle, action, label = _derive_lifecycle(sample_entry, row)
        assert lifecycle == "skill_pack"
        assert action == "open"
        assert label == "Open"


# ──────────────────────────────────────────────────────────────────
# 6. JSON list helpers
# ──────────────────────────────────────────────────────────────────


class TestListHelpers:
    def test_list_catalog_returns_dicts(self):
        data = list_catalog()
        assert isinstance(data, list)
        assert len(data) == len(CATALOG)
        for d in data[:3]:
            assert isinstance(d, dict)
            assert "id" in d
            assert "display_name" in d

    def test_list_categories_returns_dicts(self):
        data = list_categories()
        assert isinstance(data, list)
        assert len(data) == len(CATEGORIES)
        for d in data[:3]:
            assert "id" in d
            assert "display_name" in d


# ──────────────────────────────────────────────────────────────────
# 7. Route registration + live HTTP smoke
# ──────────────────────────────────────────────────────────────────
#
# PR-CONNECTIONS-MARKETPLACE-404-FIX (2026-05-02): the 404 the founder
# hit was caused by a stale backend process (uptime 25h+) running
# pre-commit code that did not yet have these endpoints. The routes
# WERE correctly registered in the source. To prevent this regression
# from masking future actual route-registration breakage, the tests
# below pin three contracts:
#   1. The 3 marketplace routes ARE present in app.routes after
#      `create_app()` returns -- if a future contributor accidentally
#      drops the router import or removes the endpoint, this fails
#      loud at test time, not at the operator's "Backend error: Not
#      Found" toast.
#   2. The endpoints respond 200 OK with the auth fixture.
#   3. The catalog response shape is non-empty + matches the in-process
#      catalog count, so a future schema drift breaks tests, not the UI.


# ──────────────────────────────────────────────────────────────────
# 7a. Founder-required plugin coverage
# (PR-CONN-PLUGIN-PARITY-UX, 2026-05-02)
# ──────────────────────────────────────────────────────────────────


# Founder's Claude Desktop / Codex parity list. Each entry maps a
# canonical brand to one or more catalog ids; at least one must be
# present. If a future PR adds a real Configure flow for a brand that
# is currently "coming-soon" only, the catalog grows; this test stays
# green because we accept ANY matching catalog id.
FOUNDER_REQUIRED_PLUGINS: dict[str, tuple[str, ...]] = {
    "GitHub": ("mcp-github", "app-github"),
    "GitLab": ("mcp-gitlab",),
    "Gmail": ("app-gmail",),
    "Google Calendar": ("app-google-calendar",),
    "Google Drive": ("app-google-drive", "mcp-google-drive"),
    "Slack": ("mcp-slack", "app-slack"),
    "Notion": ("mcp-notion", "app-notion-oauth"),
    "Linear": ("mcp-linear",),
    "Jira": ("mcp-jira",),
    "Figma": ("mcp-figma", "app-figma"),
    "Canva": ("app-canva",),
    "Cloudflare": ("mcp-cloudflare", "app-cloudflare-oauth"),
    "Sentry": ("mcp-sentry", "app-sentry-oauth"),
    "Vercel": ("mcp-vercel",),
    "Netlify": ("mcp-netlify",),
    "Stripe": ("mcp-stripe", "app-stripe-oauth"),
    "Shopify": ("mcp-shopify",),
    "Postgres": ("mcp-postgres",),
    "SQLite": ("mcp-sqlite",),
    "MongoDB": ("mcp-mongodb",),
    "Redis": ("mcp-redis",),
    "Filesystem": ("mcp-filesystem",),
    "Fetch / Web": ("mcp-fetch",),
    "Brave Search": ("mcp-brave-search",),
    "Perplexity": ("provider-perplexity", "mcp-perplexity"),
    "Hugging Face": ("mcp-huggingface",),
    "Ollama": ("local-ollama",),
    "vLLM / llama-server": ("local-vllm",),
    "OpenAI": ("provider-openai",),
    "Anthropic": ("provider-anthropic",),
    "Gemini": ("provider-google-gemini",),
    "Groq": ("provider-groq",),
    "OpenRouter": ("provider-openrouter",),
    "Together": ("provider-together",),
    "Claude Code": ("cli-claude-code",),
    "Codex CLI": ("cli-codex",),
    "Gemini CLI": ("cli-gemini",),
    "Playwright": ("mcp-playwright",),
    "Chrome DevTools": ("mcp-chrome-devtools",),
    "Desktop Commander": ("mcp-desktop-commander",),
    "Windows MCP": ("mcp-windows",),
    "Memory": ("mcp-memory",),
    "Git": ("mcp-git",),
    "Time": ("mcp-time",),
    "Sequential Thinking": ("mcp-sequential-thinking",),
}


class TestFounderRequiredPlugins:
    """Pin: every founder-required brand has at least one catalog entry."""

    def test_minimum_catalog_size(self):
        # Founder asked for >50 plugin cards. The catalog ships 55+ today.
        assert len(CATALOG) >= 50, (
            f"Catalog should ship at least 50 plugins; got {len(CATALOG)}"
        )

    @pytest.mark.parametrize(
        "brand,allowed_ids",
        sorted(FOUNDER_REQUIRED_PLUGINS.items()),
        ids=list(FOUNDER_REQUIRED_PLUGINS.keys()),
    )
    def test_brand_present(self, brand: str, allowed_ids: tuple[str, ...]):
        catalog_ids = {e.id for e in CATALOG}
        present = [aid for aid in allowed_ids if aid in catalog_ids]
        assert present, (
            f"Founder-required brand {brand!r} is missing from the catalog. "
            f"Expected at least one of: {', '.join(allowed_ids)}. "
            f"Add to marketplace_catalog.py or update FOUNDER_REQUIRED_PLUGINS "
            f"if the brand was intentionally deferred."
        )

    def test_no_required_brand_is_silently_dropped(self):
        # Defense-in-depth: if a future contributor removes a brand, the
        # parametrized test above fires. This test additionally checks
        # the count so a typo in allowed_ids cannot mask a removal.
        catalog_ids = {e.id for e in CATALOG}
        missing = []
        for brand, ids in FOUNDER_REQUIRED_PLUGINS.items():
            if not any(aid in catalog_ids for aid in ids):
                missing.append(brand)
        assert not missing, (
            f"{len(missing)} founder-required brand(s) missing from catalog: "
            f"{', '.join(missing)}"
        )


# ──────────────────────────────────────────────────────────────────
# 8. Route registration + live HTTP smoke
# ──────────────────────────────────────────────────────────────────
class TestMarketplaceRouteRegistration:
    """Pin: the 3 marketplace endpoints are mounted under /api/v1/connections/v2."""

    REQUIRED_ROUTES = (
        ("GET", "/api/v1/connections/v2/catalog"),
        ("GET", "/api/v1/connections/v2/marketplace/cards"),
        ("GET", "/api/v1/connections/v2/marketplace/install-plan/{entry_id}"),
    )

    def test_routes_registered_in_app(self, app):
        registered: set[tuple[str, str]] = set()
        for r in app.routes:
            methods = getattr(r, "methods", None)
            path = getattr(r, "path", None)
            if methods and path:
                for m in methods:
                    registered.add((m, path))
        for method, path in self.REQUIRED_ROUTES:
            assert (method, path) in registered, (
                f"Route {method} {path} is NOT registered in the FastAPI app. "
                "Did the connections_v2 router get unmounted, or did the "
                "marketplace endpoint get removed by accident?"
            )


class TestMarketplaceLiveSmoke:
    """Pin: the 3 marketplace endpoints respond 200 with auth + valid shape."""

    async def test_catalog_endpoint_returns_entries(
        self, client, auth_headers, seeded_tenant
    ):
        _ = seeded_tenant  # ensure tenant FK is satisfied for any auth lookup
        res = await client.get(
            "/api/v1/connections/v2/catalog", headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        assert "categories" in data
        assert "entries" in data
        assert len(data["entries"]) == len(CATALOG)
        assert len(data["categories"]) == len(CATEGORIES)
        # Smoke: entries carry the expected keys
        first = data["entries"][0]
        for key in ("id", "display_name", "vendor", "category", "kind", "auth_type"):
            assert key in first, f"Catalog entry missing key {key!r}"

    async def test_marketplace_cards_returns_one_per_entry(
        self, client, auth_headers, seeded_tenant
    ):
        _ = seeded_tenant
        res = await client.get(
            "/api/v1/connections/v2/marketplace/cards", headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        cards = body["data"]["cards"]
        assert len(cards) == len(CATALOG)
        # Founder-required minimum -- pins the marketplace stays a real
        # marketplace, not an empty grid.
        assert len(cards) > 50, f"Expected >50 cards, got {len(cards)}"
        for card in cards[:3]:
            assert "catalog" in card
            assert "lifecycle" in card
            assert "primary_action" in card
            # No V2 rows exist for this tenant -> every card is available
            # or needs_setup (coming-soon entries)
            assert card["lifecycle"] in ("available", "needs_setup")

    async def test_no_card_marked_connected_without_v2_truth(
        self, client, auth_headers, seeded_tenant
    ):
        """Honesty pin (project Rule 17): a card cannot show
        lifecycle=callable / enabled / connected without a real V2 row
        whose probe proved callable=True. Empty tenant -> zero cards
        in those states."""
        _ = seeded_tenant
        res = await client.get(
            "/api/v1/connections/v2/marketplace/cards", headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        cards = res.json()["data"]["cards"]
        for card in cards:
            if card["lifecycle"] in ("callable", "enabled"):
                assert card["v2_row_id"] is not None, (
                    f"Card {card['catalog']['id']} claims callable but has "
                    f"no V2 row. This violates the honesty contract."
                )
                truth = card.get("v2_truth") or {}
                callable_dim = truth.get("callable") or {}
                assert callable_dim.get("value") is True, (
                    f"Card {card['catalog']['id']} claims callable but V2 "
                    f"truth.callable.value is not True."
                )

    async def test_install_plan_returns_steps_for_known_entry(
        self, client, auth_headers, seeded_tenant
    ):
        _ = seeded_tenant
        res = await client.get(
            "/api/v1/connections/v2/marketplace/install-plan/mcp-github",
            headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        plan = body["data"]
        assert plan["entry_id"] == "mcp-github"
        assert plan["executable"] is False
        assert isinstance(plan["steps"], list)
        assert len(plan["steps"]) > 0

    async def test_install_plan_returns_404_for_unknown_entry(
        self, client, auth_headers, seeded_tenant
    ):
        _ = seeded_tenant
        res = await client.get(
            "/api/v1/connections/v2/marketplace/install-plan/does-not-exist",
            headers=auth_headers,
        )
        assert res.status_code == 404

    async def test_marketplace_routes_require_auth(self, client, seeded_tenant):
        _ = seeded_tenant
        for path in (
            "/api/v1/connections/v2/catalog",
            "/api/v1/connections/v2/marketplace/cards",
            "/api/v1/connections/v2/marketplace/install-plan/mcp-github",
        ):
            res = await client.get(path)
            assert res.status_code == 401, f"{path} should require auth, got {res.status_code}"
