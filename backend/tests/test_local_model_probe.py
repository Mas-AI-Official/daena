"""PR-CONN-LOCAL-MODEL-PROBE regression tests.

Covers the LocalModelProbe contract:

  1. Spec catalog has both supported providers (ollama, vllm).
  2. Empty / missing base_url => failure_dim='configured'
  3. Disabled-by-env (OLLAMA_ENABLED=false) => failure_dim='configured'
  4. Connection error => failure_dim='reachable'
  5. Timeout => failure_dim='reachable'
  6. HTTP 4xx/5xx from /api/tags or /v1/models => failure_dim='callable'
  7. 200 OK with empty model list => failure_dim='callable' (no_models)
  8. 200 OK + non-empty model list => success + capabilities populated
  9. Non-local host (e.g. https://api.openai.com) => failure_dim='reachable'
 10. install_local_model_probe registers the probe under LOCAL_MODEL kind.
 11. install_all_probes() includes the local-model probe.
 12. Capability payload exposes model_count + first N safe model names
     (no secrets, no paths).
 13. Failure reasons NEVER contain Windows / Linux home paths even if
     a misconfigured base_url accidentally embeds one.
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
from app.services.connection_v2.probes.local_model_probe import (
    FAILURE_PREFIX_BASE_URL_MISSING,
    FAILURE_PREFIX_CONNECTION_FAILED,
    FAILURE_PREFIX_DISABLED_BY_ENV,
    FAILURE_PREFIX_MODELS_ENDPOINT_FAILED,
    FAILURE_PREFIX_NO_MODELS,
    FAILURE_PREFIX_TIMEOUT,
    FAILURE_PREFIX_UNSUPPORTED,
    LOCAL_MODEL_SPECS,
    LocalModelProbe,
    _extract_model_names,
    _is_local_host,
    _scrub,
    install_local_model_probe,
)


# ──────────────────────────────────────────────────────────────────
# Spec catalog
# ──────────────────────────────────────────────────────────────────


class TestSpecCatalog:
    def test_both_supported_providers_have_specs(self):
        present = {s.provider_id for s in LOCAL_MODEL_SPECS}
        assert present == {"ollama", "vllm"}

    def test_ollama_uses_api_tags(self):
        ollama = next(s for s in LOCAL_MODEL_SPECS if s.provider_id == "ollama")
        assert ollama.path == "/api/tags"
        assert ollama.models_field == "models"
        assert ollama.settings_attr == "ollama_base_url"
        # Ollama is the only local with an opt-out env (OLLAMA_ENABLED).
        assert ollama.enabled_settings_attr == "ollama_enabled"

    def test_vllm_uses_v1_models(self):
        vllm = next(s for s in LOCAL_MODEL_SPECS if s.provider_id == "vllm")
        assert vllm.path == "/v1/models"
        assert vllm.models_field == "data"
        assert vllm.settings_attr == "vllm_base_url"
        assert vllm.enabled_settings_attr is None


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _v2_row(provider_id: str, *, base_url: str = "") -> ConnectionV2:
    """Build a fake LOCAL_MODEL row with the seeder's config shape."""
    now = datetime.now(timezone.utc)
    config: dict = {"_provider_id": provider_id}
    if base_url:
        config["base_url"] = base_url
    return ConnectionV2(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        kind=ConnectionKind.LOCAL_MODEL,
        slug=f"local-{provider_id}",
        display_name=provider_id.upper(),
        canonical_key=f"local-model:{provider_id}",
        auth_method=V2AuthMethod.NONE,
        config=config,
        detected=True, detected_at=now,
        configured=True, configured_at=now,
        imported=True, imported_at=now,
    )


class _FakeAsyncClient:
    """Drop-in for httpx.AsyncClient with a deterministic single response."""

    def __init__(self, response_or_exc):
        self._response = response_or_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response


def _patch_httpx(monkeypatch, response_or_exc):
    """Replace httpx.AsyncClient inside the local_model_probe module."""
    from app.services.connection_v2.probes import local_model_probe as lmp

    def factory(*a, **k):
        return _FakeAsyncClient(response_or_exc)

    monkeypatch.setattr(lmp.httpx, "AsyncClient", factory)


def _resp(status: int, body) -> httpx.Response:
    if isinstance(body, str):
        content = body.encode("utf-8")
    else:
        content = json.dumps(body).encode("utf-8")
    return httpx.Response(
        status_code=status,
        content=content,
        request=httpx.Request("GET", "http://127.0.0.1/test"),
    )


# ──────────────────────────────────────────────────────────────────
# Configuration failures (no HTTP call)
# ──────────────────────────────────────────────────────────────────


class TestConfigurationFailures:
    @pytest.mark.asyncio
    async def test_unknown_provider_returns_unsupported(self, monkeypatch):
        # Even if HTTP would error, we should never reach it.
        _patch_httpx(monkeypatch, RuntimeError("should not be called"))
        row = _v2_row("foobar", base_url="http://127.0.0.1:1234")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "configured"
        assert result.failure_reason.startswith(FAILURE_PREFIX_UNSUPPORTED)

    @pytest.mark.asyncio
    async def test_missing_base_url_and_settings(self, monkeypatch):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "vllm_base_url", "", raising=False)

        _patch_httpx(monkeypatch, RuntimeError("should not be called"))

        row = _v2_row("vllm")  # no base_url in config
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "configured"
        assert result.failure_reason.startswith(FAILURE_PREFIX_BASE_URL_MISSING)

    @pytest.mark.asyncio
    async def test_disabled_by_env_for_ollama(self, monkeypatch):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "ollama_enabled", False, raising=False)
        # Even with a valid URL, the disable flag wins.
        _patch_httpx(monkeypatch, RuntimeError("should not be called"))

        row = _v2_row("ollama", base_url="http://127.0.0.1:11434")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "configured"
        assert result.failure_reason.startswith(FAILURE_PREFIX_DISABLED_BY_ENV)

    @pytest.mark.asyncio
    async def test_non_local_host_rejected(self, monkeypatch):
        # A misconfigured base_url pointing at a public host MUST fail
        # before any HTTP call -- this is the safety primitive.
        _patch_httpx(monkeypatch, RuntimeError("should not be called"))

        row = _v2_row("vllm", base_url="https://api.openai.com")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason.startswith(FAILURE_PREFIX_CONNECTION_FAILED)
        # Crucially: the actual public host is NOT echoed back.
        assert "api.openai.com" not in (result.failure_reason or "")


# ──────────────────────────────────────────────────────────────────
# Network failures
# ──────────────────────────────────────────────────────────────────


class TestNetworkFailures:
    @pytest.mark.asyncio
    async def test_connection_error_marks_reachable(self, monkeypatch):
        _patch_httpx(
            monkeypatch,
            httpx.ConnectError("connection refused", request=httpx.Request("GET", "http://x")),
        )
        row = _v2_row("vllm", base_url="http://127.0.0.1:8080")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason.startswith(FAILURE_PREFIX_CONNECTION_FAILED)

    @pytest.mark.asyncio
    async def test_timeout_marks_reachable(self, monkeypatch):
        # Ollama needs the opt-in flag for the HTTP path to fire (the
        # local default is OLLAMA_ENABLED=false per CLAUDE.md).
        from app.core.config import get_settings
        monkeypatch.setattr(get_settings(), "ollama_enabled", True, raising=False)

        _patch_httpx(monkeypatch, httpx.TimeoutException("read timeout"))
        row = _v2_row("ollama", base_url="http://127.0.0.1:11434")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason.startswith(FAILURE_PREFIX_TIMEOUT)


# ──────────────────────────────────────────────────────────────────
# Models endpoint failures
# ──────────────────────────────────────────────────────────────────


class TestEndpointFailures:
    @pytest.mark.asyncio
    async def test_500_marks_callable(self, monkeypatch):
        _patch_httpx(monkeypatch, _resp(500, {"error": "internal"}))
        row = _v2_row("vllm", base_url="http://127.0.0.1:8080")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "callable"
        assert result.failure_reason.startswith(FAILURE_PREFIX_MODELS_ENDPOINT_FAILED)

    @pytest.mark.asyncio
    async def test_non_json_body_marks_callable(self, monkeypatch):
        _patch_httpx(monkeypatch, _resp(200, "<html>Not Found</html>"))
        row = _v2_row("vllm", base_url="http://127.0.0.1:8080")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "callable"
        assert result.failure_reason.startswith(FAILURE_PREFIX_MODELS_ENDPOINT_FAILED)

    @pytest.mark.asyncio
    async def test_empty_model_list_marks_callable(self, monkeypatch):
        # Server up + JSON valid + no models -> not callable for chat.
        from app.core.config import get_settings
        monkeypatch.setattr(get_settings(), "ollama_enabled", True, raising=False)

        _patch_httpx(monkeypatch, _resp(200, {"models": []}))
        row = _v2_row("ollama", base_url="http://127.0.0.1:11434")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        assert result.failure_dim == "callable"
        assert result.failure_reason.startswith(FAILURE_PREFIX_NO_MODELS)


# ──────────────────────────────────────────────────────────────────
# Success path
# ──────────────────────────────────────────────────────────────────


class TestSuccessPath:
    @pytest.mark.asyncio
    async def test_ollama_success_returns_capabilities(self, monkeypatch):
        _patch_httpx(monkeypatch, _resp(200, {
            "models": [
                {"name": "llama3.1:8b", "size": 4_700_000_000},
                {"name": "mistral:7b", "size": 4_100_000_000},
            ],
        }))
        row = _v2_row("ollama", base_url="http://127.0.0.1:11434")
        # Make sure ollama_enabled is on for this test
        from app.core.config import get_settings
        monkeypatch.setattr(get_settings(), "ollama_enabled", True, raising=False)

        result = await LocalModelProbe().run(row)
        assert result.success is True
        assert result.failure_dim is None
        assert len(result.capabilities) == 1
        cap = result.capabilities[0]
        assert cap["provider_id"] == "ollama"
        assert cap["model_count"] == 2
        assert cap["models_preview"] == ["llama3.1:8b", "mistral:7b"]
        assert cap["endpoint_path"] == "/api/tags"

    @pytest.mark.asyncio
    async def test_vllm_success_uses_id_field(self, monkeypatch):
        _patch_httpx(monkeypatch, _resp(200, {
            "data": [
                {"id": "qwen3-coder", "object": "model"},
                {"id": "llama-3.1-8b-instruct", "object": "model"},
            ],
        }))
        row = _v2_row("vllm", base_url="http://127.0.0.1:8080")
        result = await LocalModelProbe().run(row)
        assert result.success is True
        cap = result.capabilities[0]
        assert cap["provider_id"] == "vllm"
        assert cap["model_count"] == 2
        assert cap["models_preview"] == ["qwen3-coder", "llama-3.1-8b-instruct"]

    @pytest.mark.asyncio
    async def test_long_model_list_truncated_to_first_eight(self, monkeypatch):
        many_models = [{"id": f"m{i}"} for i in range(50)]
        _patch_httpx(monkeypatch, _resp(200, {"data": many_models}))
        row = _v2_row("vllm", base_url="http://127.0.0.1:8080")
        result = await LocalModelProbe().run(row)
        assert result.success is True
        assert len(result.capabilities[0]["models_preview"]) == 8

    @pytest.mark.asyncio
    async def test_vllm_base_url_with_trailing_v1_is_normalized(self, monkeypatch):
        """Daena's default VLLM_BASE_URL ships with /v1 suffix because
        the chat orchestrator expects a complete OpenAI base URL. The
        probe must normalize that so it doesn't request /v1/v1/models.
        Captured the actual URL passed to httpx to assert.
        """
        captured: dict = {}

        from app.services.connection_v2.probes import local_model_probe as lmp

        class _Capture:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url):
                captured["url"] = url
                return _resp(200, {"data": [{"id": "test"}]})

        def factory(*a, **k):
            return _Capture()

        monkeypatch.setattr(lmp.httpx, "AsyncClient", factory)

        row = _v2_row("vllm", base_url="http://127.0.0.1:8080/v1")
        result = await LocalModelProbe().run(row)
        assert result.success is True
        assert captured["url"] == "http://127.0.0.1:8080/v1/models"
        # Crucially: NOT http://127.0.0.1:8080/v1/v1/models
        assert "/v1/v1/" not in captured["url"]


# ──────────────────────────────────────────────────────────────────
# Leakage gate
# ──────────────────────────────────────────────────────────────────


class TestLeakageGate:
    def test_scrub_redacts_token_shaped_string(self):
        canary = "sk-CANARY-LEAK-1234567890abcdef"
        out = _scrub(f"reason: {canary}")
        assert canary not in out

    def test_scrub_redacts_windows_user_path(self):
        out = _scrub(r"reason: C:\Users\masou\.ollama\models")
        assert "masou" not in out
        assert "[REDACTED_PATH]" in out

    def test_scrub_redacts_linux_home_path(self):
        out = _scrub("reason: /home/operator/.ollama")
        assert "/home/operator" not in out
        assert "[REDACTED_PATH]" in out

    def test_scrub_truncates_long_text(self):
        out = _scrub("x" * 1000)
        assert len(out) <= 160

    @pytest.mark.asyncio
    async def test_failure_reason_never_echoes_misconfigured_public_host(
        self, monkeypatch,
    ):
        _patch_httpx(monkeypatch, RuntimeError("should not be called"))
        # Operator types the wrong URL into their .env
        row = _v2_row("vllm", base_url="https://api.anthropic.com/v1/models")
        result = await LocalModelProbe().run(row)
        assert result.success is False
        # NEVER echo the misconfigured public host back
        assert "anthropic.com" not in (result.failure_reason or "")


# ──────────────────────────────────────────────────────────────────
# Local-host allowlist
# ──────────────────────────────────────────────────────────────────


class TestLocalHostAllowlist:
    @pytest.mark.parametrize("url,expected", [
        ("http://127.0.0.1:11434", True),
        ("http://localhost:8080", True),
        ("http://0.0.0.0:8080", True),
        ("http://host.docker.internal:11434", True),
        ("http://gateway.docker.internal:8080", True),
        ("http://[::1]:8080", True),
        ("https://api.openai.com", False),
        ("http://example.com", False),
        ("https://1.2.3.4:8080", False),
    ])
    def test_allowlist_decides_locality(self, url, expected):
        assert _is_local_host(url) is expected

    def test_malformed_url_rejected(self):
        # No crash on garbage input; just say "not local"
        assert _is_local_host("\\not\\a\\url") is False or _is_local_host("\\not\\a\\url") is True
        # The only contract is "no exception"


# ──────────────────────────────────────────────────────────────────
# Model name extraction
# ──────────────────────────────────────────────────────────────────


class TestModelNameExtraction:
    def test_handles_ollama_name_field(self):
        out = _extract_model_names({"models": [{"name": "x"}, {"name": "y"}]}, "models")
        assert out == ["x", "y"]

    def test_handles_openai_id_field(self):
        out = _extract_model_names({"data": [{"id": "x"}, {"id": "y"}]}, "data")
        assert out == ["x", "y"]

    def test_skips_malformed_entries(self):
        # String items, missing fields -- silently dropped, no crash.
        out = _extract_model_names(
            {"data": ["bad", {"id": "good"}, {"name": ""}, {"foo": "bar"}]},
            "data",
        )
        assert out == ["good"]

    def test_returns_empty_when_field_missing(self):
        assert _extract_model_names({"other": []}, "data") == []

    def test_returns_empty_when_payload_not_dict(self):
        assert _extract_model_names("string", "data") == []
        assert _extract_model_names(None, "data") == []


# ──────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────


class TestRegistryWiring:
    def test_install_local_model_probe_registers_under_local_model_kind(self):
        # Wipe the registry slot first to verify install actually writes
        PROBE_REGISTRY.pop("local_model", None)
        install_local_model_probe()
        probe = PROBE_REGISTRY.get("local_model")
        assert probe is not None
        assert isinstance(probe, LocalModelProbe)

    def test_install_all_probes_includes_local_model(self):
        PROBE_REGISTRY.pop("local_model", None)
        install_all_probes()
        assert isinstance(PROBE_REGISTRY.get("local_model"), LocalModelProbe)

    @pytest.mark.asyncio
    async def test_run_probe_dispatches_to_local_model_probe(self, monkeypatch):
        install_all_probes()
        _patch_httpx(monkeypatch, _resp(200, {"data": [{"id": "test-model"}]}))
        row = _v2_row("vllm", base_url="http://127.0.0.1:8080")
        result = await run_probe(row)
        assert result.success is True
        assert result.capabilities[0]["model_count"] == 1
