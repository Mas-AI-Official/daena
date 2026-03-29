"""Tests for runtime config diagnostics and guardrails."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings


def test_runtime_diagnostics_prefers_env_file_for_local_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local backend .env should beat inherited shell env by default."""
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=development\nDEBUG=true\n", encoding="utf-8")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.delenv("DAENA_ENV_PRECEDENCE", raising=False)

    settings = Settings(_env_file=str(env_file))
    diagnostics = settings.runtime_diagnostics()

    assert diagnostics["env_precedence"] == "env_file_first"
    assert diagnostics["debug"]["value"] is True
    assert diagnostics["debug"]["source"] == f"env_file:{env_file}"


def test_runtime_diagnostics_can_opt_into_process_env_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit process-env-first mode should still be available."""
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=development\nDEBUG=true\n", encoding="utf-8")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("DAENA_ENV_PRECEDENCE", "process_env_first")

    settings = Settings(_env_file=str(env_file))
    diagnostics = settings.runtime_diagnostics()

    assert diagnostics["env_precedence"] == "process_env_first"
    assert diagnostics["debug"]["value"] is False
    assert diagnostics["debug"]["source"] == "process_env"


def test_production_guardrails_flag_placeholder_secrets() -> None:
    """Production config should reject placeholder secrets."""
    settings = Settings(
        _env_file=None,
        app_env="production",
        debug=False,
        cors_origins=["https://app.daena.test"],
    )

    issues = settings.runtime_guardrail_issues()

    assert "JWT_SECRET_KEY still uses the placeholder default" in issues
    assert "VAULT_ENCRYPTION_KEY still uses the placeholder default" in issues


def test_disable_auth_not_allowed_outside_local_envs() -> None:
    """Unsafe auth bypass should be rejected outside local/test-style envs."""
    settings = Settings(
        _env_file=None,
        app_env="staging",
        disable_auth=True,
        jwt_secret_key="real-secret",
        vault_encryption_key="real-vault-secret",
    )

    issues = settings.runtime_guardrail_issues()

    assert issues == [
        "DISABLE_AUTH is only allowed in local development/test environments"
    ]


def test_invalid_env_precedence_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid precedence override should fail guardrail checks visibly."""
    monkeypatch.setenv("DAENA_ENV_PRECEDENCE", "mystery_mode")

    settings = Settings(_env_file=None)
    issues = settings.runtime_guardrail_issues()

    assert issues == [
        "DAENA_ENV_PRECEDENCE must be one of: env_file_first, process_env_first"
    ]
