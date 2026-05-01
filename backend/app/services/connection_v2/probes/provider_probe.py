"""Phase 7-A: Real provider probes.

Replaces NoopProbe for ``kind=provider`` rows. Each supported
provider has a harmless HTTP "list models" call that proves the
API key is valid AND the endpoint is reachable WITHOUT incurring
inference cost or side effects.

Truth ladder for a provider:
  1. detected   = API key (or base URL for local) is configured
  2. configured = same as detected for providers
  3. reachable  = TCP connect + TLS handshake + HTTP response received
  4. authenticated = HTTP < 400 (no 401/403)
  5. callable   = response parses as expected JSON shape

Safety:
  * The API key is NEVER printed in failure_reason. Failure messages
    use status code + response.text[:160] with a regex sanitizer that
    redacts any 20+ char token-shaped string.
  * Probes use HEAD or smallest-cost GET (e.g. /models endpoint).
  * 8s timeout per call.

Per-provider catalog lives in ``provider_probe_specs.py`` so it can
be tested independently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.services.connection_v2.probe import Probe, ProbeResult

logger = get_logger(__name__)

PROBE_HTTP_TIMEOUT = 8.0
RESPONSE_BODY_PREVIEW = 160

# Anything 20+ chars long that looks like an API token (alphanumeric
# with -, _, .). Used to scrub failure_reason before it reaches the
# DB or the operator UI.
_TOKEN_REGEX = re.compile(r"[A-Za-z0-9_\-\.]{20,}")


def _redact(text: str) -> str:
    """Replace anything that looks like a secret with [REDACTED]."""
    if not text:
        return text
    return _TOKEN_REGEX.sub("[REDACTED]", text)[:RESPONSE_BODY_PREVIEW]


@dataclass(frozen=True)
class ProviderProbeSpec:
    """How to probe one provider over HTTP.

    Auth shapes:
      - bearer: Authorization: Bearer <key>
      - x_api_key: x-api-key: <key>
      - query_key: <url>?key=<key>
      - none: no auth header (local providers)
    """

    provider_enum: str   # ModelProvider.value (e.g. "OPENAI")
    url: str             # full URL (or template with {base_url} for local)
    auth_header: str     # 'bearer' | 'x_api_key' | 'query_key' | 'none'
    settings_attr: str   # which Settings attribute holds the key/URL
    extra_headers: dict[str, str] | None = None
    # Optional: callable that takes the parsed JSON and returns True
    # if the response shape proves callability. Default: any 2xx is
    # callable.
    expected_json_field: str | None = None


# Spec catalog. Order doesn't matter -- lookup is by provider_enum.
PROVIDER_SPECS: tuple[ProviderProbeSpec, ...] = (
    ProviderProbeSpec(
        provider_enum="OPENAI",
        url="https://api.openai.com/v1/models",
        auth_header="bearer",
        settings_attr="openai_api_key",
        expected_json_field="data",
    ),
    ProviderProbeSpec(
        provider_enum="ANTHROPIC",
        url="https://api.anthropic.com/v1/models",
        auth_header="x_api_key",
        settings_attr="anthropic_api_key",
        extra_headers={"anthropic-version": "2023-06-01"},
        expected_json_field="data",
    ),
    ProviderProbeSpec(
        provider_enum="GEMINI",
        url="https://generativelanguage.googleapis.com/v1beta/models",
        auth_header="query_key",
        settings_attr="gemini_api_key",
        expected_json_field="models",
    ),
    ProviderProbeSpec(
        provider_enum="PERPLEXITY",
        # Perplexity doesn't expose a /models list publicly. Use the
        # chat completions endpoint with HEAD -- it returns 200/405
        # for valid auth and 401 for invalid auth, neither costs
        # tokens.
        url="https://api.perplexity.ai/chat/completions",
        auth_header="bearer",
        settings_attr="perplexity_api_key",
    ),
    ProviderProbeSpec(
        provider_enum="GROQ",
        url="https://api.groq.com/openai/v1/models",
        auth_header="bearer",
        settings_attr="groq_api_key",
        expected_json_field="data",
    ),
    ProviderProbeSpec(
        provider_enum="OPENROUTER",
        url="https://openrouter.ai/api/v1/models",
        auth_header="bearer",
        settings_attr="openrouter_api_key",
        expected_json_field="data",
    ),
    ProviderProbeSpec(
        provider_enum="TOGETHER",
        url="https://api.together.xyz/v1/models",
        auth_header="bearer",
        settings_attr="together_api_key",
        expected_json_field="data",
    ),
    ProviderProbeSpec(
        provider_enum="OLLAMA",
        # Local: no auth, base URL from config.
        url="{base_url}/api/tags",
        auth_header="none",
        settings_attr="ollama_base_url",
        expected_json_field="models",
    ),
    ProviderProbeSpec(
        provider_enum="VLLM",
        url="{base_url}/v1/models",
        auth_header="none",
        settings_attr="vllm_base_url",
        expected_json_field="data",
    ),
)


def _spec_for(provider_enum: str) -> ProviderProbeSpec | None:
    for s in PROVIDER_SPECS:
        if s.provider_enum == provider_enum:
            return s
    return None


def _build_request(
    spec: ProviderProbeSpec, key_value: str,
) -> tuple[str, dict[str, str]]:
    """Compute the final URL + headers for the probe.

    Never returns the key in a logged form -- caller passes the URL
    and headers to httpx directly.
    """
    headers: dict[str, str] = {}
    url = spec.url

    if spec.auth_header == "bearer":
        headers["Authorization"] = f"Bearer {key_value}"
    elif spec.auth_header == "x_api_key":
        headers["x-api-key"] = key_value
    elif spec.auth_header == "query_key":
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}key={key_value}"
    elif spec.auth_header == "none":
        # Local providers -- key_value is the base URL.
        url = url.format(base_url=key_value.rstrip("/"))

    if spec.extra_headers:
        headers.update(spec.extra_headers)

    return url, headers


class ProviderProbe(Probe):
    """Real HTTP probe for ``kind=provider`` rows.

    Resolves the provider enum from ``row.config['_provider_enum']``,
    looks up the spec + settings key, performs a harmless GET, and
    returns a structured ProbeResult. NEVER raises -- contract is
    "structured failure in ProbeResult.failure_dim".
    """

    kind = ConnectionKind.PROVIDER

    async def run(self, row: ConnectionV2) -> ProbeResult:
        config = row.config or {}
        provider_enum = config.get("_provider_enum")
        if not provider_enum:
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason="row.config missing '_provider_enum' key",
            )

        spec = _spec_for(str(provider_enum))
        if spec is None:
            return ProbeResult(
                success=False,
                failure_dim="configured",
                failure_reason=f"no probe spec for provider '{provider_enum}'",
            )

        settings = get_settings()
        key_value = (getattr(settings, spec.settings_attr, "") or "").strip()
        if not key_value:
            return ProbeResult(
                success=False,
                failure_dim="authenticated",
                failure_reason=(
                    f"settings.{spec.settings_attr} is empty -- configure it "
                    f"and re-probe"
                ),
            )

        url, headers = _build_request(spec, key_value)
        method = "HEAD" if spec.provider_enum == "PERPLEXITY" else "GET"

        try:
            async with httpx.AsyncClient(timeout=PROBE_HTTP_TIMEOUT) as client:
                resp = await client.request(method, url, headers=headers)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=(
                    f"transport error ({type(exc).__name__}); provider "
                    f"unreachable"
                ),
            )
        except httpx.HTTPError as exc:
            return ProbeResult(
                success=False,
                failure_dim="reachable",
                failure_reason=f"HTTP error: {type(exc).__name__}",
            )

        # Auth failures map to 'authenticated' dim explicitly.
        if resp.status_code in (401, 403):
            return ProbeResult(
                success=False,
                failure_dim="authenticated",
                failure_reason=(
                    f"HTTP {resp.status_code} -- API key rejected: "
                    f"{_redact(resp.text)}"
                ),
            )
        # Server errors are reachability proof but not callability.
        if resp.status_code >= 500:
            return ProbeResult(
                success=False,
                failure_dim="callable",
                failure_reason=(
                    f"HTTP {resp.status_code} -- provider 5xx: "
                    f"{_redact(resp.text)}"
                ),
            )
        # 4xx other than auth: depends on the provider. For HEAD-based
        # probes (Perplexity), 405 is acceptable (server reachable +
        # method not allowed for HEAD).
        if resp.status_code >= 400 and resp.status_code not in (405,):
            return ProbeResult(
                success=False,
                failure_dim="callable",
                failure_reason=(
                    f"HTTP {resp.status_code}: {_redact(resp.text)}"
                ),
            )

        # 2xx (or 405 for HEAD) -- check JSON shape if expected.
        if spec.expected_json_field and resp.status_code < 300:
            try:
                payload = resp.json()
            except Exception:
                return ProbeResult(
                    success=False,
                    failure_dim="callable",
                    failure_reason=(
                        f"HTTP {resp.status_code} OK but body is not JSON"
                    ),
                )
            if spec.expected_json_field not in payload:
                return ProbeResult(
                    success=False,
                    failure_dim="callable",
                    failure_reason=(
                        f"response missing expected '{spec.expected_json_field}' "
                        f"field"
                    ),
                )

        # Success.
        return ProbeResult(success=True)


def install_provider_probe() -> None:
    """Replace the NoopProbe for ``kind=provider`` with the real one.

    Safe to call multiple times -- last write wins via register_probe.
    """
    from app.services.connection_v2.probe import register_probe
    register_probe(ProviderProbe())


__all__ = [
    "PROVIDER_SPECS",
    "ProviderProbe",
    "ProviderProbeSpec",
    "_redact",
    "_spec_for",
    "install_provider_probe",
]
