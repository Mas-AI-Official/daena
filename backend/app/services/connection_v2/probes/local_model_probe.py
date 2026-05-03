"""LocalModelProbe -- real V2 probe for ``kind=local_model`` rows.

PR-CONN-LOCAL-MODEL-PROBE (2026-05-03). Replaces the
``probe_unavailable`` default for the two local-LLM cards Daena
currently surfaces:

  * ``local-ollama``  -> GET ``{base_url}/api/tags``
  * ``local-vllm``    -> GET ``{base_url}/v1/models``  (OpenAI-compatible:
                          llama-server / vLLM / LM Studio / etc.)

Truth ladder for a local model row:

  1. ``configured``    = ``base_url`` is set in row.config OR the matching
                         settings attribute is non-empty
  2. ``reachable``     = TCP connect + HTTP response received before the
                         5s timeout
  3. ``authenticated`` = always True for local endpoints (no auth)
  4. ``callable``      = the ``models`` (or ``data``) list parses AND has
                         at least one entry. An empty list means the
                         server is up but has no model loaded -- not
                         callable for chat.

Safety contract:

  * NEVER calls a chat / completions endpoint -- truth-only.
  * NEVER follows redirects to external hosts. Local probes target
    127.0.0.1 / localhost / docker-internal hosts; httpx allows
    redirects by default but we explicitly disable them.
  * NEVER reads or transmits the raw ``base_url`` if it contains a
    user path or token-shaped query string; the redaction regex from
    ``provider_probe`` is reused for failure_reason scrubbing.
  * ``failure_reason`` uses a structured prefix vocabulary
    (``base_url_missing:``, ``disabled_by_env:``,
    ``connection_failed:``, ``timeout:``, ``models_endpoint_failed:``,
    ``no_models:``, ``unsupported_local_model:``) so the frontend can
    pattern-match and surface WSL / Docker localhost guidance for
    connection failures without parsing free-form English.
  * Capabilities returned: ``model_count`` (int) and the FIRST 8
    model identifiers as plain strings -- local model names are not
    sensitive (the operator chose to pull them) but capping the list
    keeps the V2 row's JSON column small.

Honesty (project rule 17):
  * No prompt inference. No external HTTP. No tool dispatch. The
    probe answers exactly one question: "is the local LLM endpoint
    serving a non-empty model list?"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.services.connection_v2.probe import Probe, ProbeResult
from app.services.connection_v2.probes.provider_probe import _redact

logger = get_logger(__name__)

PROBE_HTTP_TIMEOUT = 5.0
RESPONSE_BODY_PREVIEW = 160
MAX_MODEL_NAMES_RETURNED = 8

# Structured failure-prefix vocabulary. Frontend uses these prefixes
# to surface targeted guidance (e.g. WSL/Docker localhost copy when
# the prefix is "connection_failed:") without parsing free-form text.
FAILURE_PREFIX_BASE_URL_MISSING = "base_url_missing:"
FAILURE_PREFIX_DISABLED_BY_ENV = "disabled_by_env:"
FAILURE_PREFIX_CONNECTION_FAILED = "connection_failed:"
FAILURE_PREFIX_TIMEOUT = "timeout:"
FAILURE_PREFIX_MODELS_ENDPOINT_FAILED = "models_endpoint_failed:"
FAILURE_PREFIX_NO_MODELS = "no_models:"
FAILURE_PREFIX_UNSUPPORTED = "unsupported_local_model:"

# Local URL allowlist: any host outside this set is rejected before
# the HTTP call. Defense against a misconfigured base_url pointing at
# a public endpoint that would leak the operator's IP / model usage.
_LOCAL_HOST_ALLOWLIST = {
    "127.0.0.1", "localhost", "0.0.0.0", "::1",
    "host.docker.internal", "gateway.docker.internal",
}

# Match any value that LOOKS like an absolute path so the redactor
# catches accidentally-leaked usernames in failure_reason (defense in
# depth -- the URL itself is supposed to be local-only). Two shapes:
# Windows ``C:\Users\<name>\...`` and POSIX ``/home/<name>/...``.
_PATH_REGEX = re.compile(r"(?:[A-Z]:\\[^\s]+|/(?:home|Users|root)/[^\s]+)")


def _scrub(text: str) -> str:
    """Run BOTH the token-shaped regex (from provider_probe) and a
    path-shaped regex over text. Useful when failure_reason might
    accidentally pick up a Windows username (C:\\Users\\masou\\...) or
    a Linux home path."""
    if not text:
        return text
    return _PATH_REGEX.sub("[REDACTED_PATH]", _redact(text))[:RESPONSE_BODY_PREVIEW]


@dataclass(frozen=True)
class LocalModelSpec:
    """How to probe one local-LLM provider over HTTP.

    Mirrors the spec shape used by ProviderProbe but tuned for the
    LOCAL_MODEL kind: no auth header, no API key lookup -- just a
    base_url + a relative path + the JSON field that contains the
    model list.
    """

    provider_id: str             # "ollama" | "vllm"
    path: str                    # e.g. "/api/tags" or "/v1/models"
    models_field: str            # JSON field that holds the model list
    settings_attr: str           # fallback Settings attribute for base_url
    enabled_settings_attr: str | None  # opt-out env (Ollama only today)


LOCAL_MODEL_SPECS: tuple[LocalModelSpec, ...] = (
    LocalModelSpec(
        provider_id="ollama",
        path="/api/tags",
        models_field="models",
        settings_attr="ollama_base_url",
        enabled_settings_attr="ollama_enabled",
    ),
    LocalModelSpec(
        provider_id="vllm",
        path="/v1/models",
        models_field="data",
        settings_attr="vllm_base_url",
        enabled_settings_attr=None,
    ),
)


def _spec_for(provider_id: str) -> LocalModelSpec | None:
    for s in LOCAL_MODEL_SPECS:
        if s.provider_id == provider_id:
            return s
    return None


def _resolve_provider_id(row: ConnectionV2) -> str | None:
    """Pull the provider_id out of row.config (preferred) or derive
    from the slug suffix (fallback for rows seeded before the seeder
    started writing _provider_id).
    """
    config = row.config or {}
    provider_id = config.get("_provider_id")
    if isinstance(provider_id, str) and provider_id.strip():
        return provider_id.strip().lower()
    # Slug fallback: "local-ollama" -> "ollama"
    slug = (row.slug or "").lower()
    if slug.startswith("local-"):
        return slug[len("local-"):]
    return None


def _resolve_base_url(row: ConnectionV2, spec: LocalModelSpec) -> str:
    """Prefer the seeded row.config['base_url']; fall back to the live
    Settings attribute so the probe still works for rows imported
    before that key was written.

    Normalizes trailing OpenAI-style ``/v1`` segments so a base_url of
    ``http://127.0.0.1:8080/v1`` doesn't produce ``/v1/v1/models`` when
    the spec's path is appended. This matters in practice: Daena's
    default ``VLLM_BASE_URL`` ships with the ``/v1`` suffix because the
    chat orchestrator's vllm adapter expects a complete OpenAI base URL.
    """
    config = row.config or {}
    val = config.get("base_url")
    if not (isinstance(val, str) and val.strip()):
        settings = get_settings()
        val = getattr(settings, spec.settings_attr, "") or ""
    val = val.strip().rstrip("/")
    # Strip trailing /v1 so spec.path can append safely. This is
    # idempotent and only affects vLLM-style URLs.
    if val.endswith("/v1"):
        val = val[:-3]
    return val


def _is_local_host(url: str) -> bool:
    """Reject any base_url whose host is not in the local allowlist.

    Local LLM probes MUST stay local -- a misconfigured base_url
    pointing at a public endpoint would leak the operator's IP, model
    usage, and timing to a third party. We do not mark it as a
    failure_reason that includes the host (would echo it back to the
    UI / DB), just refuse with "connection_failed: non-local host".
    """
    try:
        parsed = httpx.URL(url)
    except Exception:
        return False
    host = (parsed.host or "").lower()
    return host in _LOCAL_HOST_ALLOWLIST


def _extract_model_names(payload: Any, models_field: str) -> list[str]:
    """Extract the first MAX_MODEL_NAMES_RETURNED model identifiers.

    Both Ollama and OpenAI-compatible servers expose an "id" or
    "name" field per entry. We accept either; anything else is
    silently dropped (defense against a malformed response polluting
    capabilities).
    """
    if not isinstance(payload, dict):
        return []
    items = payload.get(models_field)
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items[:MAX_MODEL_NAMES_RETURNED]:
        if not isinstance(item, dict):
            continue
        # Ollama: {"name": "llama3.1:8b", ...}; OpenAI: {"id": "...",
        # "object": "model", ...}
        name = item.get("name") or item.get("id")
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return out


class LocalModelProbe(Probe):
    """Real HTTP probe for ``kind=local_model`` rows.

    Resolves the local provider via row.config['_provider_id'] (or
    slug suffix), looks up the spec, performs the harmless models-list
    GET, and returns a structured ProbeResult.

    Contract: NEVER raises -- all failure paths return a structured
    ProbeResult with a prefixed failure_reason.
    """

    kind = ConnectionKind.LOCAL_MODEL

    async def run(self, row: ConnectionV2) -> ProbeResult:
        provider_id = _resolve_provider_id(row)
        if provider_id is None:
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason=(
                    f"{FAILURE_PREFIX_UNSUPPORTED} row.config missing "
                    f"'_provider_id' and slug does not start with 'local-'"
                ),
            )

        spec = _spec_for(provider_id)
        if spec is None:
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason=(
                    f"{FAILURE_PREFIX_UNSUPPORTED} no local-model spec for "
                    f"provider '{provider_id}' (supported: ollama, vllm)"
                ),
            )

        # Optional opt-out env (Ollama can be disabled without removing
        # the URL; respect it so the probe doesn't fight the operator's
        # explicit disable).
        if spec.enabled_settings_attr is not None:
            settings = get_settings()
            if not getattr(settings, spec.enabled_settings_attr, False):
                return ProbeResult(
                    success=False,
                    failure_dim="configured",
                    failure_reason=(
                        f"{FAILURE_PREFIX_DISABLED_BY_ENV} {spec.provider_id} "
                        f"is disabled via {spec.enabled_settings_attr.upper()}=false"
                    ),
                )

        base_url = _resolve_base_url(row, spec)
        if not base_url:
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason=(
                    f"{FAILURE_PREFIX_BASE_URL_MISSING} no base_url in row.config "
                    f"and settings.{spec.settings_attr} is empty -- set the env "
                    f"var and re-probe"
                ),
            )

        if not _is_local_host(base_url):
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=(
                    f"{FAILURE_PREFIX_CONNECTION_FAILED} non-local host -- "
                    f"local model probes only target 127.0.0.1 / localhost / "
                    f"docker-internal"
                ),
            )

        url = f"{base_url.rstrip('/')}{spec.path}"

        try:
            async with httpx.AsyncClient(
                timeout=PROBE_HTTP_TIMEOUT,
                follow_redirects=False,
            ) as client:
                resp = await client.get(url)
        except httpx.TimeoutException:
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=(
                    f"{FAILURE_PREFIX_TIMEOUT} no response in "
                    f"{PROBE_HTTP_TIMEOUT}s from {spec.provider_id} "
                    f"models endpoint -- is the server running?"
                ),
            )
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=(
                    f"{FAILURE_PREFIX_CONNECTION_FAILED} {type(exc).__name__} "
                    f"reaching {spec.provider_id} -- is the local server "
                    f"listening on the configured port?"
                ),
            )
        except httpx.HTTPError as exc:
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=(
                    f"{FAILURE_PREFIX_CONNECTION_FAILED} HTTP transport error "
                    f"({type(exc).__name__})"
                ),
            )

        if resp.status_code >= 400:
            return ProbeResult(
                success=False,
                failure_dim="callable",
                failure_reason=(
                    f"{FAILURE_PREFIX_MODELS_ENDPOINT_FAILED} HTTP "
                    f"{resp.status_code} from {spec.path}: {_scrub(resp.text)}"
                ),
            )

        try:
            payload = resp.json()
        except Exception:
            return ProbeResult(
                success=False,
                failure_dim="callable",
                failure_reason=(
                    f"{FAILURE_PREFIX_MODELS_ENDPOINT_FAILED} {spec.path} "
                    f"returned non-JSON body: {_scrub(resp.text)}"
                ),
            )

        model_names = _extract_model_names(payload, spec.models_field)
        if not model_names:
            return ProbeResult(
                success=False,
                failure_dim="callable",
                failure_reason=(
                    f"{FAILURE_PREFIX_NO_MODELS} {spec.provider_id} reachable "
                    f"but no models loaded -- pull or load a model and re-probe"
                ),
            )

        # Success: callable + model count + first N safe names.
        return ProbeResult(
            success=True,
            capabilities=[{
                "kind": "local_model",
                "provider_id": spec.provider_id,
                "model_count": len(model_names),
                "models_preview": model_names,
                "endpoint_path": spec.path,
            }],
        )


def install_local_model_probe() -> None:
    """Replace the probe_unavailable default for kind=local_model.

    Safe to call multiple times -- last write wins via register_probe.
    """
    from app.services.connection_v2.probe import register_probe
    register_probe(LocalModelProbe())


__all__ = [
    "FAILURE_PREFIX_BASE_URL_MISSING",
    "FAILURE_PREFIX_CONNECTION_FAILED",
    "FAILURE_PREFIX_DISABLED_BY_ENV",
    "FAILURE_PREFIX_MODELS_ENDPOINT_FAILED",
    "FAILURE_PREFIX_NO_MODELS",
    "FAILURE_PREFIX_TIMEOUT",
    "FAILURE_PREFIX_UNSUPPORTED",
    "LOCAL_MODEL_SPECS",
    "LocalModelProbe",
    "LocalModelSpec",
    "install_local_model_probe",
]
