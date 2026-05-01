"""Phase 6: Provider V2 row seeder.

Hosted-API providers (OpenAI, Anthropic, Gemini, Perplexity, Groq,
OpenRouter, Together) are not represented as CLI adapters in
RuntimeRegistry — they live in ``app.core.config.Settings`` as API
key strings. Phase 5 left their callable status as "lie if key is
configured." Phase 6 closes that lie by:

1. Creating ``ConnectionV2(kind=provider, slug=<lowercase>)`` rows for
   every provider whose API key is configured in settings.
2. Letting the existing probe endpoint flip ``callable`` based on a
   real ping.
3. Letting the Main Brain gate (Phase 6 refactor) consult those rows.

The seeder is idempotent: re-running it on each startup is safe.
Existing rows are NOT touched -- only missing rows are inserted.
This means re-running the seeder won't reset a probe's
``callable_at`` or any failure metadata.

Dev-only by default. The Main Brain gate honors V2 truth only when
``USE_CONNECTION_REGISTRY_V2`` is on, so the seeder writes V2 rows
even in legacy mode -- they're just informational until the flag
flips.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.constants import ModelProvider
from app.core.logging import get_logger
from app.core.vault_boot import load_kek_from_env
from app.models.connection_v2 import (
    AuthMethod as V2AuthMethod,
    ConnectionKind,
)
from app.models.identity import Tenant
from app.services.connection_v2.registry import ConnectionRegistryV2

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProviderSpec:
    """One provider entry in the seeder catalog."""

    enum: ModelProvider
    settings_attr: str
    display_name: str
    auth_method: V2AuthMethod = V2AuthMethod.API_TOKEN
    # When True, the provider is callable without a paid key (Ollama
    # local, vLLM local). The seeder still requires a base URL to be
    # set, but doesn't require an API key.
    local: bool = False
    base_url_attr: str | None = None


# Catalog of provider rows the seeder will materialize. Order is
# intentional: free/local providers first so a fresh dev tenant lands
# with at least one V2 row even when no paid keys are configured.
PROVIDER_CATALOG: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        enum=ModelProvider.OLLAMA,
        settings_attr="ollama_base_url",
        display_name="Ollama",
        auth_method=V2AuthMethod.NONE,
        local=True,
        base_url_attr="ollama_base_url",
    ),
    ProviderSpec(
        enum=ModelProvider.VLLM,
        settings_attr="vllm_base_url",
        display_name="vLLM",
        auth_method=V2AuthMethod.NONE,
        local=True,
        base_url_attr="vllm_base_url",
    ),
    ProviderSpec(
        enum=ModelProvider.OPENAI,
        settings_attr="openai_api_key",
        display_name="OpenAI",
    ),
    ProviderSpec(
        enum=ModelProvider.ANTHROPIC,
        settings_attr="anthropic_api_key",
        display_name="Anthropic",
    ),
    ProviderSpec(
        enum=ModelProvider.GEMINI,
        settings_attr="gemini_api_key",
        display_name="Google Gemini",
    ),
    ProviderSpec(
        enum=ModelProvider.PERPLEXITY,
        settings_attr="perplexity_api_key",
        display_name="Perplexity",
    ),
    ProviderSpec(
        enum=ModelProvider.GROQ,
        settings_attr="groq_api_key",
        display_name="Groq",
    ),
    ProviderSpec(
        enum=ModelProvider.OPENROUTER,
        settings_attr="openrouter_api_key",
        display_name="OpenRouter",
    ),
    ProviderSpec(
        enum=ModelProvider.TOGETHER,
        settings_attr="together_api_key",
        display_name="Together",
    ),
)


def _is_provider_configured(spec: ProviderSpec, settings: Settings) -> bool:
    """A provider is 'configured' iff its key (or base URL for local) is non-empty."""
    value = getattr(settings, spec.settings_attr, "") or ""
    return bool(value.strip())


def _provider_slug(spec: ProviderSpec) -> str:
    return spec.enum.value.lower()


@dataclass
class SeedReport:
    """Outcome of one seeder run."""

    tenant_id: str
    created: list[str]
    skipped_existing: list[str]
    skipped_unconfigured: list[str]

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "created": list(self.created),
            "skipped_existing": list(self.skipped_existing),
            "skipped_unconfigured": list(self.skipped_unconfigured),
        }


async def seed_providers_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    settings: Settings | None = None,
) -> SeedReport:
    """Materialize provider V2 rows for one tenant. Idempotent.

    Returns a SeedReport summarizing what happened. Never decrypts or
    prints API keys; only checks for non-empty configuration.

    Caller is responsible for the surrounding transaction (commit /
    rollback). The seeder calls ``registry.import_connection`` which
    flushes but does not commit.
    """
    settings = settings or get_settings()
    kek = load_kek_from_env(is_production=settings.is_production)
    registry = ConnectionRegistryV2(db, kek_seed=kek)

    created: list[str] = []
    skipped_existing: list[str] = []
    skipped_unconfigured: list[str] = []

    for spec in PROVIDER_CATALOG:
        slug = _provider_slug(spec)
        if not _is_provider_configured(spec, settings):
            skipped_unconfigured.append(slug)
            continue

        result = await registry.import_connection(
            tenant_id=tenant_id,
            kind=ConnectionKind.PROVIDER,
            slug=slug,
            display_name=spec.display_name,
            auth_method=spec.auth_method,
            config={
                "_provider_enum": spec.enum.value,
                "_seeded_by": "provider_seeder",
                "_local": spec.local,
                **(
                    {"base_url_attr": spec.base_url_attr}
                    if spec.base_url_attr else {}
                ),
            },
        )
        if result.created:
            created.append(slug)
        else:
            skipped_existing.append(slug)

    logger.info(
        "provider_seeder.tenant_seeded",
        tenant_id=str(tenant_id),
        created_count=len(created),
        skipped_existing_count=len(skipped_existing),
        skipped_unconfigured_count=len(skipped_unconfigured),
    )

    return SeedReport(
        tenant_id=str(tenant_id),
        created=created,
        skipped_existing=skipped_existing,
        skipped_unconfigured=skipped_unconfigured,
    )


async def seed_providers_all_tenants(
    db: AsyncSession,
    *,
    settings: Settings | None = None,
) -> list[SeedReport]:
    """Seed provider rows for every tenant in the DB.

    Used at lifespan startup so tenants don't have to wait for the
    first connections_v2 query before their provider rows exist.
    """
    from sqlalchemy import select
    rows = (await db.execute(select(Tenant.id))).scalars().all()
    reports: list[SeedReport] = []
    for tid in rows:
        reports.append(
            await seed_providers_for_tenant(db, tenant_id=tid, settings=settings)
        )
    return reports


__all__ = [
    "PROVIDER_CATALOG",
    "ProviderSpec",
    "SeedReport",
    "seed_providers_for_tenant",
    "seed_providers_all_tenants",
]
