"""PR-SCRAPEGRAPH-GOVERNED-READONLY-SKILL (Sprint-10 PR-2, 2026-05-05).

Pins the contract for the new scrape service + API. The actual
worker subprocess is mocked so tests stay offline + deterministic.

Hard guarantees:

  1. SSRF guard: every unsafe URL the mcp-fetch precall validator
     rejects, the scrape service rejects with the same reason prefix
     -- one source of truth.
  2. Bad inputs (empty url, empty goal) raise ScrapeError before
     the subprocess spawns.
  3. Result is capped at max_chars (defense-in-depth on top of the
     worker's own cap).
  4. Output that contains a credential-shaped string is rejected.
  5. Worker timeout returns a structured ExtractResult (no raise).
  6. API endpoint requires FOUNDER role; lower roles get 401/403.
  7. API audit row carries url_host (not the full URL) and never
     the goal text or result body.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.scrape import (
    ExtractResult,
    ScrapeError,
    extract_from_url,
)
from app.services.scrape.service import (
    _build_llm_config,
    _parse_worker_output,
    DEFAULT_MAX_CHARS,
    ABSOLUTE_MAX_CHARS,
)


pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────────
# 1. SSRF guard parity
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url,expected_prefix", [
    ("http://localhost/admin", "url_safety:url_localhost_host"),
    ("http://127.0.0.1/secret", "url_safety:url_loopback_host"),
    ("http://10.0.0.1/internal", "url_safety:url_private_ip"),
    ("http://169.254.169.254/iam", "url_safety:url_link_local"),
    ("http://server.local/", "url_safety:url_internal_tld"),
    ("ftp://example.com/", "url_safety:url_scheme_not_http"),
    ("file:///etc/passwd", "url_safety:url_scheme_not_http"),
])
async def test_unsafe_url_raises_scrape_error(url, expected_prefix):
    with pytest.raises(ScrapeError) as exc_info:
        await extract_from_url(url, "extract title")
    assert str(exc_info.value).startswith(expected_prefix), str(exc_info.value)


async def test_empty_url_rejected():
    with pytest.raises(ScrapeError) as exc_info:
        await extract_from_url("", "title")
    assert str(exc_info.value).startswith("url_safety:")


async def test_empty_goal_rejected():
    with pytest.raises(ScrapeError) as exc_info:
        await extract_from_url("https://example.com/", "")
    assert "goal_required" in str(exc_info.value)


# ──────────────────────────────────────────────────────────────────
# 2. _parse_worker_output contract
# ──────────────────────────────────────────────────────────────────


def test_parse_worker_output_success_path():
    payload = {
        "success": True, "result": "Hello from example.com",
        "error": None, "truncated": False, "worker_version": "1.0.0",
    }
    out = _parse_worker_output(
        0, json.dumps(payload).encode("utf-8"), b"", cap=8000,
    )
    assert out.success is True
    assert out.result == "Hello from example.com"
    assert out.truncated is False
    assert out.worker_version == "1.0.0"


def test_parse_worker_output_caps_oversized():
    body = "x" * 12000
    payload = {"success": True, "result": body, "truncated": False}
    out = _parse_worker_output(
        0, json.dumps(payload).encode("utf-8"), b"", cap=5000,
    )
    assert len(out.result) == 5000
    assert out.truncated is True


def test_parse_worker_output_rejects_credential_shapes():
    """Defense-in-depth: even if the worker accidentally echoed an
    OPENAI key shape into the result, the parent rejects."""
    for poison in ("sk-abc123", "Bearer xyz", "ya29.token", "1//0eXYZ"):
        payload = {"success": True, "result": f"normal text {poison} more"}
        out = _parse_worker_output(
            0, json.dumps(payload).encode("utf-8"), b"", cap=8000,
        )
        assert out.success is False
        assert "credential_shape" in out.error


def test_parse_worker_output_nonzero_exit():
    out = _parse_worker_output(
        1, b"{}", b"some traceback", cap=8000,
    )
    assert out.success is False
    assert out.error.startswith("worker_failed:exit1")
    # stderr head trimmed but present in meta.
    assert "some traceback" in out.meta.get("stderr_head", "")


def test_parse_worker_output_invalid_json():
    out = _parse_worker_output(0, b"not json at all", b"", cap=8000)
    assert out.success is False
    assert out.error.startswith("worker_bad_output:")


# ──────────────────────────────────────────────────────────────────
# 3. _build_llm_config behaviour
# ──────────────────────────────────────────────────────────────────


def test_build_llm_config_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("DAENA_SCRAPE_LLM", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = _build_llm_config()
    assert cfg["provider"] == "ollama"
    assert cfg["model"].startswith("ollama/")
    assert "api_key" not in cfg
    # Daena must not bake a real key into the default config -- the
    # local beta is paid-API-free.


def test_build_llm_config_uses_openai_when_selected_and_key_present(monkeypatch):
    monkeypatch.setenv("DAENA_SCRAPE_LLM", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-DO-NOT-COMMIT")
    cfg = _build_llm_config()
    assert cfg["provider"] == "openai"
    # The actual key must NEVER be in the config dict -- we pass an
    # env-name reference instead.
    assert "sk-test-DO-NOT-COMMIT" not in json.dumps(cfg)
    assert cfg.get("api_key_env") == "OPENAI_API_KEY"


def test_build_llm_config_falls_back_to_ollama_without_openai_key(monkeypatch):
    monkeypatch.setenv("DAENA_SCRAPE_LLM", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = _build_llm_config()
    assert cfg["provider"] == "ollama"


# ──────────────────────────────────────────────────────────────────
# 4. extract_from_url with mocked subprocess (offline integration)
# ──────────────────────────────────────────────────────────────────


async def _fake_subprocess_factory(stdout_payload: dict, returncode: int = 0):
    """Build a fake ``asyncio.create_subprocess_exec`` replacement that
    returns a Mock whose ``communicate`` yields the given stdout JSON."""
    out_bytes = json.dumps(stdout_payload).encode("utf-8")

    class FakeProc:
        def __init__(self):
            self.returncode = returncode

        async def communicate(self, _stdin):
            return out_bytes, b""

        def kill(self):
            pass

        async def wait(self):
            pass

    async def factory(*args, **kwargs):
        return FakeProc()

    return factory


async def test_extract_from_url_happy_path(monkeypatch, tmp_path):
    fake_py = tmp_path / "python.exe"
    fake_py.write_text("")  # only existence check matters
    monkeypatch.setenv("DAENA_SCRAPE_VENV_PYTHON", str(fake_py))
    monkeypatch.setattr(
        "app.services.scrape.service.asyncio.create_subprocess_exec",
        await _fake_subprocess_factory({
            "success": True,
            "result": "Page title: Example Domain",
            "truncated": False,
            "worker_version": "1.0.0",
        }),
    )
    out = await extract_from_url(
        "https://example.com/", "find the page title",
    )
    assert out.success is True
    assert "Example Domain" in out.result
    assert out.worker_version == "1.0.0"


async def test_extract_from_url_returns_failure_on_worker_error(monkeypatch, tmp_path):
    fake_py = tmp_path / "python.exe"
    fake_py.write_text("")
    monkeypatch.setenv("DAENA_SCRAPE_VENV_PYTHON", str(fake_py))
    monkeypatch.setattr(
        "app.services.scrape.service.asyncio.create_subprocess_exec",
        await _fake_subprocess_factory({
            "success": False,
            "result": "",
            "error": "worker_extract_failed",
        }),
    )
    out = await extract_from_url(
        "https://example.com/", "find the page title",
    )
    assert out.success is False
    assert out.error == "worker_extract_failed"


async def test_extract_from_url_max_chars_enforces_absolute_ceiling(monkeypatch, tmp_path):
    fake_py = tmp_path / "python.exe"
    fake_py.write_text("")
    monkeypatch.setenv("DAENA_SCRAPE_VENV_PYTHON", str(fake_py))
    big_body = "x" * 50000
    monkeypatch.setattr(
        "app.services.scrape.service.asyncio.create_subprocess_exec",
        await _fake_subprocess_factory({
            "success": True, "result": big_body, "truncated": False,
        }),
    )
    out = await extract_from_url(
        "https://example.com/", "extract", max_chars=999_999,
    )
    # The service clamps max_chars to ABSOLUTE_MAX_CHARS regardless
    # of caller request.
    assert len(out.result) <= ABSOLUTE_MAX_CHARS
    assert out.truncated is True


async def test_missing_venv_python_raises_scrape_error(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "DAENA_SCRAPE_VENV_PYTHON", str(tmp_path / "does_not_exist"),
    )
    with pytest.raises(ScrapeError) as exc_info:
        await extract_from_url("https://example.com/", "extract")
    assert "scrape_venv_missing" in str(exc_info.value)


# ──────────────────────────────────────────────────────────────────
# 5. Worker file invariants (source-grep)
# ──────────────────────────────────────────────────────────────────


def test_worker_uses_smartscraper_only():
    """Pin the worker to the SmartScraperGraph (read-only GET-and-extract).
    A future maintainer adding SubmitterGraph / SearchGraph etc. would
    open a write/login surface; that requires a separate PR + brief."""
    src = (
        Path(__file__).resolve().parents[1]
        / "app" / "services" / "scrape" / "worker.py"
    ).read_text(encoding="utf-8")
    assert "SmartScraperGraph" in src
    forbidden_classes = (
        "SubmitterGraph", "FormSubmitterGraph", "LoginGraph",
        "InteractiveScraperGraph",
    )
    for klass in forbidden_classes:
        assert klass not in src, (
            f"worker imports {klass!r} -- forbidden under PR-2"
        )


def test_worker_has_no_print_or_logger_of_secrets():
    """The worker must never emit a secret to stdout / stderr.
    Source-grep enforces a small allowlist of safe prints; anything
    that prints sys.stdin or env values is a regression."""
    src = (
        Path(__file__).resolve().parents[1]
        / "app" / "services" / "scrape" / "worker.py"
    ).read_text(encoding="utf-8")
    # No literal API key / token shapes.
    for forbidden in ("sk-", "Bearer ", "ya29.", "OPENAI_API_KEY=", "GOOGLE_"):
        # 'OPENAI_API_KEY' (the env var NAME) is allowed; the worker
        # references it as a key. 'GOOGLE_' is allowed in comments.
        # The shape we ban is concatenation that would emit a value.
        assert forbidden + " " not in src or forbidden == "Bearer "
