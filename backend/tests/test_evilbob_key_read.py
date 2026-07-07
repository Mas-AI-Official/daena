"""Deterministic oracle for the EVILBOB_KEY read choke point (PR-9(c)).

EVILBOB_KEY is the master-key-class activation secret for /3vilbob mode. PR-9(c)
routes all reads of it through a single consume-only choke point,
`read_activation_key()`, with a provider seam (`set_activation_key_provider`)
so a real secret backend (e.g. GCP Secret Manager on Cloud Run) can be wired in
at deploy time WITHOUT editing any read site. The process environment stays the
local/test fallback, which is what keeps the existing env-based /3vilbob tests
green.

Contract under test (written before the implementation):
  1. No provider registered, EVILBOB_KEY set   -> returns the env value.
  2. No provider registered, EVILBOB_KEY unset  -> returns "".
  3. Provider yields a value                    -> provider wins over env.
  4. Provider yields None                        -> falls back to env.
  5. Provider yields ""                          -> falls back to env.
  6. Provider raises                             -> falls back to env, never crashes.
  7. Provider failure path never logs the key value.

Deleting or weakening any of these to go green is a BREACH, not a pass.
"""

from __future__ import annotations

import pytest

from app.services.security import evilbob_mode
from app.services.security.evilbob_mode import (
    read_activation_key,
    set_activation_key_provider,
)


@pytest.fixture(autouse=True)
def _reset_provider():
    """Guarantee provider state never leaks between tests (or into other suites).

    The provider is module-global; a leak would silently change what the
    env-based /3vilbob tests read. Reset before and after every test.
    """
    set_activation_key_provider(None)
    try:
        yield
    finally:
        set_activation_key_provider(None)


def test_reads_env_when_no_provider(monkeypatch):
    monkeypatch.setenv("EVILBOB_KEY", "env-secret-123")
    assert read_activation_key() == "env-secret-123"


def test_returns_empty_when_env_unset_and_no_provider(monkeypatch):
    monkeypatch.delenv("EVILBOB_KEY", raising=False)
    assert read_activation_key() == ""


def test_provider_wins_over_env(monkeypatch):
    monkeypatch.setenv("EVILBOB_KEY", "env-secret-123")
    set_activation_key_provider(lambda: "vault-secret-xyz")
    assert read_activation_key() == "vault-secret-xyz"


def test_falls_back_to_env_when_provider_returns_none(monkeypatch):
    monkeypatch.setenv("EVILBOB_KEY", "env-secret-123")
    set_activation_key_provider(lambda: None)
    assert read_activation_key() == "env-secret-123"


def test_falls_back_to_env_when_provider_returns_empty(monkeypatch):
    monkeypatch.setenv("EVILBOB_KEY", "env-secret-123")
    set_activation_key_provider(lambda: "")
    assert read_activation_key() == "env-secret-123"


def test_falls_back_to_env_when_provider_raises(monkeypatch):
    monkeypatch.setenv("EVILBOB_KEY", "env-secret-123")

    def _boom():
        raise RuntimeError("secret backend unreachable")

    set_activation_key_provider(_boom)
    # Must not propagate the provider exception into the activation path.
    assert read_activation_key() == "env-secret-123"


def test_provider_failure_never_logs_key_value(monkeypatch):
    """The failure path logs the exception TYPE only, never any key value."""
    monkeypatch.setenv("EVILBOB_KEY", "env-secret-123")

    calls: list[tuple[tuple, dict]] = []

    class _Recorder:
        def warning(self, *args, **kwargs):
            calls.append((args, kwargs))

        def __getattr__(self, _name):
            return lambda *a, **k: None

    monkeypatch.setattr(evilbob_mode, "logger", _Recorder())

    def _boom():
        raise RuntimeError("env-secret-123 leaked into the message")

    set_activation_key_provider(_boom)
    assert read_activation_key() == "env-secret-123"

    blob = repr(calls)
    assert "env-secret-123" not in blob
    # The exception type name is a safe thing to surface.
    assert "RuntimeError" in blob
