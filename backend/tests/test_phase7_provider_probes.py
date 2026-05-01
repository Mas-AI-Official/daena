"""Phase 7-A tests: real provider probes.

Founder-mandated coverage:
  1. Each of 9 providers has a probe spec
  2. Probe never prints API keys (canary regex test + redact unit test)
  3. Configured + 2xx response -> callable=True
  4. 401/403 -> failure_dim='authenticated'
  5. ConnectError/Timeout -> failure_dim='reachable'
  6. Empty key -> failure_dim='authenticated' (no HTTP call needed)
  7. Local providers (Ollama, vLLM) use base_url instead of API key
  8. install_provider_probe replaces NoopProbe in registry
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from app.models.connection_v2 import (
    AuthMethod as V2AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.services.connection_v2.probe import PROBE_REGISTRY, run_probe
from app.services.connection_v2.probes import install_all_probes
from app.services.connection_v2.probes.provider_probe import (
    PROVIDER_SPECS,
    ProviderProbe,
    _build_request,
    _redact,
    _spec_for,
    install_provider_probe,
)


# ──────────────────────────────────────────────────────────────────
# Spec catalog coverage
# ──────────────────────────────────────────────────────────────────


REQUIRED_PROVIDERS = {
    "OPENAI", "ANTHROPIC", "GEMINI", "PERPLEXITY", "GROQ",
    "OPENROUTER", "TOGETHER", "OLLAMA", "VLLM",
}


class TestSpecCatalog:
    def test_all_required_providers_have_specs(self):
        present = {s.provider_enum for s in PROVIDER_SPECS}
        assert present == REQUIRED_PROVIDERS

    def test_each_spec_has_settings_attr_and_url(self):
        for s in PROVIDER_SPECS:
            assert s.settings_attr
            assert s.url
            assert s.auth_header in {"bearer", "x_api_key", "query_key", "none"}

    def test_local_providers_have_none_auth(self):
        for s in PROVIDER_SPECS:
            if s.provider_enum in {"OLLAMA", "VLLM"}:
                assert s.auth_header == "none"

    def test_query_key_provider_is_gemini(self):
        gemini = _spec_for("GEMINI")
        assert gemini is not None
        assert gemini.auth_header == "query_key"


# ──────────────────────────────────────────────────────────────────
# Redaction (no-key-leakage canary)
# ──────────────────────────────────────────────────────────────────


class TestRedaction:
    def test_redact_replaces_api_key_shaped_strings(self):
        canary = "sk-ABCDEFGHIJKLMNOPQRSTUVWX1234"  # >=20 chars
        text = f"401 Unauthorized: invalid key {canary}, please retry"
        out = _redact(text)
        assert canary not in out
        assert "[REDACTED]" in out

    def test_redact_handles_anthropic_token_shape(self):
        canary = "sk-ant-api03-1234567890abcdefghij"
        out = _redact(f"x-api-key invalid: {canary}")
        assert canary not in out
        assert "[REDACTED]" in out

    def test_redact_truncates_long_text(self):
        out = _redact("x" * 1000)
        assert len(out) <= 160

    def test_redact_short_string_unchanged(self):
        # Words shorter than 20 chars stay readable.
        assert _redact("HTTP 401") == "HTTP 401"


# ──────────────────────────────────────────────────────────────────
# Request builder
# ──────────────────────────────────────────────────────────────────


class TestRequestBuilder:
    def test_bearer_provider_sets_authorization_header(self):
        spec = _spec_for("OPENAI")
        url, headers = _build_request(spec, "sk-key")
        assert headers["Authorization"] == "Bearer sk-key"
        assert url == spec.url

    def test_x_api_key_provider_sets_x_api_key_header(self):
        spec = _spec_for("ANTHROPIC")
        url, headers = _build_request(spec, "sk-ant-key")
        assert headers["x-api-key"] == "sk-ant-key"
        assert headers.get("anthropic-version") == "2023-06-01"

    def test_query_key_provider_appends_to_url(self):
        spec = _spec_for("GEMINI")
        url, headers = _build_request(spec, "AIzaSyTest")
        assert "key=AIzaSyTest" in url
        assert "Authorization" not in headers

    def test_local_provider_uses_base_url_template(self):
        spec = _spec_for("OLLAMA")
        url, headers = _build_request(spec, "http://localhost:11434/")
        # Trailing slash stripped + /api/tags appended.
        assert url == "http://localhost:11434/api/tags"
        assert headers == {}


# ──────────────────────────────────────────────────────────────────
# Probe behavior with mocked HTTP
# ──────────────────────────────────────────────────────────────────


def _v2_row(provider_enum: str) -> ConnectionV2:
    """Build a stand-alone (unsaved) ConnectionV2 row for probe testing."""
    now = datetime.now(timezone.utc)
    return ConnectionV2(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        kind=ConnectionKind.PROVIDER.value,
        slug=provider_enum.lower(),
        display_name=provider_enum.title(),
        canonical_key=f"k-{uuid.uuid4().hex[:16]}",
        auth_method=V2AuthMethod.API_TOKEN.value,
        trust_tier="official",
        config={"_provider_enum": provider_enum},
        detected=True, detected_at=now,
        configured=True, configured_at=now,
        imported=True, imported_at=now,
    )


class _FakeAsyncClient:
    """Drop-in for httpx.AsyncClient with deterministic responses."""

    def __init__(self, response: httpx.Response | Exception):
        self._response = response

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def request(self, method, url, headers=None):
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _patch_httpx(monkeypatch, response_or_exc):
    """Patch httpx.AsyncClient with a single-response stub."""
    from app.services.connection_v2.probes import provider_probe as pp

    def factory(*a, **k):
        return _FakeAsyncClient(response_or_exc)

    monkeypatch.setattr(pp.httpx, "AsyncClient", factory)


def _resp(status: int, body: dict | str | None = None) -> httpx.Response:
    """Build an httpx.Response with optional JSON body."""
    if body is None:
        content = b""
    elif isinstance(body, str):
        content = body.encode("utf-8")
    else:
        content = json.dumps(body).encode("utf-8")
    return httpx.Response(
        status_code=status,
        content=content,
        request=httpx.Request("GET", "http://test"),
    )


class TestProbeBehavior:
    @pytest.mark.asyncio
    async def test_empty_key_marks_authenticated_failure_no_http_call(
        self, monkeypatch,
    ):
        from app.core.config import get_settings
        s = get_settings()
        for spec in PROVIDER_SPECS:
            monkeypatch.setattr(s, spec.settings_attr, "", raising=False)

        # Even if HTTP would error, we should never reach it.
        _patch_httpx(monkeypatch, RuntimeError("should not be called"))

        probe = ProviderProbe()
        result = await probe.run(_v2_row("OPENAI"))
        assert result.success is False
        assert result.failure_dim == "authenticated"
        assert "openai_api_key" in result.failure_reason

    @pytest.mark.asyncio
    async def test_401_response_marks_authenticated_failure(self, monkeypatch):
        from app.core.config import get_settings
        s = get_settings()
        canary = "sk-CANARY-LEAK-1234567890abcdef"
        monkeypatch.setattr(s, "openai_api_key", canary, raising=False)

        _patch_httpx(monkeypatch, _resp(401, {"error": {"message": "bad key"}}))

        result = await ProviderProbe().run(_v2_row("OPENAI"))
        assert result.success is False
        assert result.failure_dim == "authenticated"
        # The canary key must NOT appear in failure_reason.
        assert canary not in (result.failure_reason or "")

    @pytest.mark.asyncio
    async def test_connection_error_marks_reachable_failure(self, monkeypatch):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)

        _patch_httpx(
            monkeypatch,
            httpx.ConnectError("getaddrinfo failed", request=httpx.Request("GET", "http://x")),
        )

        result = await ProviderProbe().run(_v2_row("OPENAI"))
        assert result.success is False
        assert result.failure_dim == "reachable"
        assert "transport error" in (result.failure_reason or "")

    @pytest.mark.asyncio
    async def test_timeout_marks_reachable_failure(self, monkeypatch):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)

        _patch_httpx(
            monkeypatch,
            httpx.ReadTimeout("timed out", request=httpx.Request("GET", "http://x")),
        )

        result = await ProviderProbe().run(_v2_row("OPENAI"))
        assert result.success is False
        assert result.failure_dim == "reachable"

    @pytest.mark.asyncio
    async def test_200_with_expected_field_marks_callable(self, monkeypatch):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)

        _patch_httpx(monkeypatch, _resp(200, {"data": [{"id": "gpt-4"}]}))

        result = await ProviderProbe().run(_v2_row("OPENAI"))
        assert result.success is True
        assert result.failure_dim is None

    @pytest.mark.asyncio
    async def test_200_missing_expected_field_marks_callable_failure(
        self, monkeypatch,
    ):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)

        _patch_httpx(monkeypatch, _resp(200, {"unexpected": "shape"}))

        result = await ProviderProbe().run(_v2_row("OPENAI"))
        assert result.success is False
        assert result.failure_dim == "callable"
        assert "data" in (result.failure_reason or "")

    @pytest.mark.asyncio
    async def test_500_marks_callable_failure_not_auth(self, monkeypatch):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)

        _patch_httpx(monkeypatch, _resp(503, "service unavailable"))

        result = await ProviderProbe().run(_v2_row("OPENAI"))
        assert result.success is False
        assert result.failure_dim == "callable"
        assert "503" in (result.failure_reason or "")

    @pytest.mark.asyncio
    async def test_local_ollama_uses_base_url(self, monkeypatch):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "ollama_base_url", "http://localhost:11434", raising=False)

        _patch_httpx(monkeypatch, _resp(200, {"models": [{"name": "llama3"}]}))

        result = await ProviderProbe().run(_v2_row("OLLAMA"))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_local_ollama_unreachable_marks_reachable_failure(
        self, monkeypatch,
    ):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "ollama_base_url", "http://localhost:11434", raising=False)

        _patch_httpx(
            monkeypatch,
            httpx.ConnectError("conn refused", request=httpx.Request("GET", "http://x")),
        )

        result = await ProviderProbe().run(_v2_row("OLLAMA"))
        assert result.success is False
        assert result.failure_dim == "reachable"

    @pytest.mark.asyncio
    async def test_perplexity_405_on_head_is_callable(self, monkeypatch):
        """Perplexity returns 405 on HEAD chat/completions -- still callable."""
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "perplexity_api_key", "pplx-test", raising=False)

        _patch_httpx(monkeypatch, _resp(405, ""))

        result = await ProviderProbe().run(_v2_row("PERPLEXITY"))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_unknown_provider_enum_marks_configured_failure(
        self, monkeypatch,
    ):
        row = _v2_row("OPENAI")
        row.config = {"_provider_enum": "TOTALLY_FAKE_PROVIDER"}
        result = await ProviderProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "configured"

    @pytest.mark.asyncio
    async def test_missing_provider_enum_in_config(self, monkeypatch):
        row = _v2_row("OPENAI")
        row.config = {}
        result = await ProviderProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "configured"


# ──────────────────────────────────────────────────────────────────
# Registry installation
# ──────────────────────────────────────────────────────────────────


class TestRegistryInstall:
    def test_install_provider_probe_replaces_noop(self):
        # Reset to ensure deterministic state.
        from app.services.connection_v2.probe import (
            NoopProbe, register_probe,
        )
        # Force NoopProbe back in.
        register_probe(NoopProbe(ConnectionKind.PROVIDER))
        assert isinstance(
            PROBE_REGISTRY[ConnectionKind.PROVIDER.value], NoopProbe,
        )
        # Install real one.
        install_provider_probe()
        assert isinstance(
            PROBE_REGISTRY[ConnectionKind.PROVIDER.value], ProviderProbe,
        )

    def test_install_all_probes_idempotent(self):
        install_all_probes()
        first = PROBE_REGISTRY[ConnectionKind.PROVIDER.value]
        install_all_probes()
        second = PROBE_REGISTRY[ConnectionKind.PROVIDER.value]
        # New instance per call (last-write-wins) but same class.
        assert type(first) is type(second) is ProviderProbe

    @pytest.mark.asyncio
    async def test_run_probe_dispatches_to_provider_probe(self, monkeypatch):
        install_provider_probe()
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)
        _patch_httpx(monkeypatch, _resp(200, {"data": []}))

        result = await run_probe(_v2_row("OPENAI"))
        assert result.success is True


# ──────────────────────────────────────────────────────────────────
# Canary: probe NEVER persists or returns the API key
# ──────────────────────────────────────────────────────────────────


class TestKeyLeakageCanary:
    @pytest.mark.asyncio
    async def test_full_failure_path_never_includes_api_key(self, monkeypatch):
        """Run every failure path and assert the key never appears in the
        ProbeResult's failure_reason."""
        from app.core.config import get_settings
        s = get_settings()
        canary = "sk-DAENA-FULLPATH-CANARY-1234567890"
        monkeypatch.setattr(s, "openai_api_key", canary, raising=False)

        # Try multiple bad responses.
        cases: list[httpx.Response | Exception] = [
            _resp(401, {"error": canary}),  # 401 with key echoed back
            _resp(403, f"forbidden, key={canary}"),
            _resp(500, f"error: {canary}"),
            _resp(429, f"rate limited for key {canary}"),
            httpx.ConnectError(
                f"failed for {canary}",
                request=httpx.Request("GET", "http://x"),
            ),
        ]
        for case in cases:
            _patch_httpx(monkeypatch, case)
            result = await ProviderProbe().run(_v2_row("OPENAI"))
            dumped = json.dumps({
                "success": result.success,
                "failure_dim": result.failure_dim,
                "failure_reason": result.failure_reason,
            })
            assert canary not in dumped, (
                f"API key leaked in ProbeResult for response {case!r}: {dumped}"
            )
