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


def test_production_guardrails_flag_placeholder_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production config should reject placeholder secrets.

    Pydantic Settings reads from os.environ even when ``_env_file=None``,
    so a developer who has a real JWT_SECRET_KEY exported locally would
    see the placeholder guard pass and the test fail. Strip the
    relevant env vars so the Settings instance genuinely defaults to
    the placeholder values.
    """
    for name in (
        "JWT_SECRET_KEY",
        "VAULT_ENCRYPTION_KEY",
        "DAENA_JWT_SECRET_KEY",
        "DAENA_VAULT_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(
        _env_file=None,
        app_env="production",
        debug=False,
        cors_origins=["https://app.daena.test"],
    )

    issues = settings.runtime_guardrail_issues()

    assert "JWT_SECRET_KEY still uses the placeholder default" in issues
    assert "VAULT_ENCRYPTION_KEY still uses the placeholder default" in issues


def test_staging_guardrails_flag_placeholder_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staging is a deployed env, so placeholder secrets must fail there too.

    is_production is True only for app_env=="production", but a placeholder
    JWT/vault key is just as forge-able in staging. The guard is gated on
    ``not allows_unsafe_dev_features`` so any non-local env is covered.
    """
    for name in (
        "JWT_SECRET_KEY",
        "VAULT_ENCRYPTION_KEY",
        "DAENA_JWT_SECRET_KEY",
        "DAENA_VAULT_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(
        _env_file=None,
        app_env="staging",
        debug=False,
        cors_origins=["https://staging.daena.test"],
    )

    issues = settings.runtime_guardrail_issues()

    assert "JWT_SECRET_KEY still uses the placeholder default" in issues
    assert "VAULT_ENCRYPTION_KEY still uses the placeholder default" in issues


def test_local_envs_keep_placeholder_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local/dev/test must NOT be forced to set real secrets (zero-config)."""
    for name in (
        "JWT_SECRET_KEY",
        "VAULT_ENCRYPTION_KEY",
        "DAENA_JWT_SECRET_KEY",
        "DAENA_VAULT_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None, app_env="development")

    issues = settings.runtime_guardrail_issues()

    assert "JWT_SECRET_KEY still uses the placeholder default" not in issues
    assert "VAULT_ENCRYPTION_KEY still uses the placeholder default" not in issues


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


def _load_env_template(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE .env template into a dict (ignores comments/blanks)."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def test_production_env_template_trips_the_boot_guardrail() -> None:
    """The shipped prod env template, used verbatim, MUST trip the guardrail.

    Regression guard for the template-to-guardrail contract. The guardrail
    detects placeholder secrets by EXACT membership in a frozenset, so a
    template whose JWT/Vault sentinels are NOT in that set would let a
    copy-and-forget operator boot production on a world-known signing key
    (full auth-bypass via token forgery) without the fail-closed boot-abort
    ever firing. No prior test loaded the actual template values, which is
    exactly how that drift went unnoticed. This pins the contract: if anyone
    edits .env.production.example back to an unrecognized sentinel, this fails.

    Init kwargs take highest priority in pydantic-settings, so the template
    values below cannot be overridden by an exported JWT_SECRET_KEY in the
    developer's shell.
    """
    template = Path(__file__).resolve().parents[2] / ".env.production.example"
    assert template.exists(), f"production env template missing: {template}"

    values = _load_env_template(template)
    assert "JWT_SECRET_KEY" in values, "template lost its JWT_SECRET_KEY entry"
    assert "VAULT_ENCRYPTION_KEY" in values, (
        "template lost its VAULT_ENCRYPTION_KEY entry"
    )
    assert values.get("APP_ENV") == "production", (
        "this template must declare APP_ENV=production so the guardrail is fail-closed"
    )

    settings = Settings(
        _env_file=None,
        app_env="production",
        debug=False,
        cors_origins=["https://app.daena.test"],
        jwt_secret_key=values["JWT_SECRET_KEY"],
        vault_encryption_key=values["VAULT_ENCRYPTION_KEY"],
    )

    issues = settings.runtime_guardrail_issues()

    assert "JWT_SECRET_KEY still uses the placeholder default" in issues
    assert "VAULT_ENCRYPTION_KEY still uses the placeholder default" in issues
