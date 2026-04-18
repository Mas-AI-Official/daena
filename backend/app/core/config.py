"""Application configuration via environment variables.

Single source of truth for all settings. Uses pydantic-settings
to validate and parse environment variables at startup.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import PrivateAttr, field_validator
from pydantic_settings import BaseSettings, DotEnvSettingsSource, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ENV_FILE = _BACKEND_ROOT / ".env"
_LOCAL_ENV_NAMES = frozenset({"development", "dev", "local", "test"})
_PLACEHOLDER_SECRET_VALUES = frozenset({
    "CHANGE-ME-in-production-use-64-char-random",
    "CHANGE-ME-32-byte-key-for-aes256",
})
_LOCAL_ORIGIN_MARKERS = ("localhost", "127.0.0.1")
_ENV_PRECEDENCE_ENV_VAR = "DAENA_ENV_PRECEDENCE"
_ENV_PRECEDENCE_VALUES = frozenset({"env_file_first", "process_env_first"})


def _env_file_path(env_file: Any) -> Path | None:
    """Resolve the configured env file relative to the backend root."""
    if not env_file:
        return None

    if isinstance(env_file, (list, tuple)):
        for candidate in env_file:
            resolved = _env_file_path(candidate)
            if resolved is not None:
                return resolved
        return None

    path = Path(env_file)
    if not path.is_absolute():
        path = _BACKEND_ROOT / path
    return path


def _env_file_values(env_file: Any) -> dict[str, str]:
    """Best-effort key/value discovery for the configured env file."""
    path = _env_file_path(env_file)
    if path is None or not path.exists():
        return {}

    values: dict[str, str] = {}
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _value = line.split("=", 1)
            key = key.strip()
            if key:
                values[key.upper()] = _value.strip().strip('"').strip("'")
    except OSError:
        return {}

    return values


def _default_env_precedence(env_file: Any) -> str:
    """Infer a safe default precedence mode from the configured env file."""
    values = _env_file_values(env_file)
    env_file_app_env = values.get("APP_ENV", "").strip().lower()
    if env_file_app_env in _LOCAL_ENV_NAMES:
        return "env_file_first"
    return "process_env_first"


def _env_precedence_mode(env_file: Any) -> str:
    """Return the active precedence mode, allowing explicit override."""
    explicit = os.environ.get(_ENV_PRECEDENCE_ENV_VAR, "").strip().lower()
    if explicit in _ENV_PRECEDENCE_VALUES:
        return explicit
    return _default_env_precedence(env_file)


class Settings(BaseSettings):
    """Daena application settings.

    All values are read from environment variables or .env file.
    Validation happens at startup — fail fast on misconfiguration.
    """

    model_config = SettingsConfigDict(
        env_file=str(_DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    _effective_env_file: Path | None = PrivateAttr(default=None)
    _effective_env_precedence: str = PrivateAttr(default="process_env_first")

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    auto_port: bool = True  # find next free port if default is busy

    # --- Application ---
    app_name: str = "Daena"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # --- Feature flags ---
    # Session B (2026-04-17): Daena VP Stage 2.8 plans cross-department
    # routing for chat requests. The plan stage is fail-safe (VP never
    # blocks chat) and integration tests confirmed no regression on the
    # hot path. Flipped ON 2026-04-17: multi-department chat requests
    # now emit `daena_vp_plan` SSE events showing involved_departments
    # and required_approvers so the Company Dashboard + chat view can
    # render the routing. Execution wiring of subtask.required_approvers
    # to ask_department calls still lives in SwarmExecutor (next session).
    # Set DAENA_VP_ENABLED=false in .env to roll back.
    daena_vp_enabled: bool = True

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./daena_dev2.db"
    database_echo: bool = False

    # --- Server ---
    host: str = "127.0.0.1"  # Bind to loopback ONLY. Never 0.0.0.0 in dev.
    port: int = 8000

    # --- Redis ---
    redis_url: str = "redis://127.0.0.1:6379/0"

    # --- Auth ---
    jwt_secret_key: str = "CHANGE-ME-in-production-use-64-char-random"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24hr for dev; tighten to 30min for production
    jwt_refresh_token_expire_days: int = 7

    # --- Founder seed (auto-creates on startup if all three set) ---
    # The founder authored the terms so terms_accepted_at is set on
    # seed; no T&C interstitial is shown to these accounts. Other
    # Gmail OAuth users still have to accept T&C before profile is
    # marked complete.
    founder_email: str = ""
    founder_personal_email: str = ""
    founder_default_password: str = ""
    founder_tenant_name: str = "MAS-AI Technologies"

    # --- OAuth (multi-provider) ---
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    figma_client_id: str = ""
    figma_client_secret: str = ""
    slack_client_id: str = ""
    slack_client_secret: str = ""
    canva_client_id: str = ""
    canva_client_secret: str = ""
    oauth_redirect_base_url: str = "http://127.0.0.1:5173"

    # --- CORS ---
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://127.0.0.1:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Accept comma-separated string or JSON array."""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    # --- LLM Providers ---
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_default_model: str = "llama3.1:8b"
    perplexity_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    together_api_key: str = ""
    groq_api_key: str = ""
    vllm_base_url: str = "http://localhost:8100/v1"
    vllm_default_model: str = ""  # empty = auto-detect first available

    # --- Feature Flags ---
    enable_web3: bool = False
    enable_daenabot: bool = True
    disable_auth: bool = False

    # --- Governance Mode ---
    # UNLEASHED = No governance pipeline. Shield only. Raw power.
    # BALANCED  = Light governance (SecurityGate + auto-proceed most actions)
    # GOVERNED  = Full 10-stage pipeline (enterprise mode, default)
    governance_mode: str = "GOVERNED"

    # --- DaenaBot ---
    daenabot_allowed_paths: list[str] = []          # Sandbox dirs for FileAgent
    daenabot_terminal_timeout: int = 30             # Default command timeout (seconds)
    daenabot_terminal_max_timeout: int = 300        # Maximum allowed timeout

    # Developer Mode: when False (default), all deletes go to .archive/ for safety.
    # When True, actual file deletion is allowed. Only destructive toggle in Daena.
    developer_mode: bool = False

    # --- Vault ---
    vault_encryption_key: str = "CHANGE-ME-32-byte-key-for-aes256"

    # --- Celery ---
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"

    def __init__(self, **values: Any) -> None:
        env_file = values.get("_env_file", self.model_config.get("env_file"))
        super().__init__(**values)
        self._effective_env_file = _env_file_path(env_file)
        self._effective_env_precedence = _env_precedence_mode(env_file)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Use one explicit precedence contract instead of hidden defaults."""
        raw_env = getattr(dotenv_settings, "env_file", cls.model_config.get("env_file"))
        env_file = _env_file_path(raw_env)
        configured_dotenv = DotEnvSettingsSource(
            settings_cls,
            env_file=env_file,
            env_file_encoding=cls.model_config.get("env_file_encoding"),
            case_sensitive=cls.model_config.get("case_sensitive"),
            env_prefix=cls.model_config.get("env_prefix"),
            env_nested_delimiter=cls.model_config.get("env_nested_delimiter"),
            env_nested_max_split=cls.model_config.get("env_nested_max_split"),
            env_ignore_empty=cls.model_config.get("env_ignore_empty"),
            env_parse_none_str=cls.model_config.get("env_parse_none_str"),
            env_parse_enums=cls.model_config.get("env_parse_enums"),
        )

        precedence = _env_precedence_mode(env_file)
        if precedence == "env_file_first":
            return init_settings, configured_dotenv, env_settings, file_secret_settings
        return init_settings, env_settings, configured_dotenv, file_secret_settings

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env.lower() == "production"

    @property
    def normalized_app_env(self) -> str:
        """Normalized application environment name."""
        return self.app_env.strip().lower()

    @property
    def allows_unsafe_dev_features(self) -> bool:
        """Whether unsafe development shortcuts are allowed in this environment."""
        return self.normalized_app_env in _LOCAL_ENV_NAMES

    @property
    def env_file_path(self) -> Path | None:
        """Resolved env file path, if configured."""
        return self._effective_env_file

    @property
    def env_precedence(self) -> str:
        """Active environment precedence contract."""
        return self._effective_env_precedence

    @property
    def provider_key_status(self) -> dict[str, dict[str, str | bool]]:
        """Provider configuration truth without exposing secret values."""
        return {
            "ollama": {
                "configured": True,
                "source": self._field_source("ollama_base_url"),
            },
            "openai": {
                "configured": bool(self.openai_api_key),
                "source": self._field_source("openai_api_key"),
            },
            "anthropic": {
                "configured": bool(self.anthropic_api_key),
                "source": self._field_source("anthropic_api_key"),
            },
            "gemini": {
                "configured": bool(self.gemini_api_key),
                "source": self._field_source("gemini_api_key"),
            },
            "groq": {
                "configured": bool(self.groq_api_key),
                "source": self._field_source("groq_api_key"),
            },
            "openrouter": {
                "configured": bool(self.openrouter_api_key),
                "source": self._field_source("openrouter_api_key"),
            },
            "together": {
                "configured": bool(self.together_api_key),
                "source": self._field_source("together_api_key"),
            },
            "perplexity": {
                "configured": bool(self.perplexity_api_key),
                "source": self._field_source("perplexity_api_key"),
            },
            "vllm": {
                "configured": True,
                "source": self._field_source("vllm_base_url"),
            },
        }

    def runtime_guardrail_issues(self) -> list[str]:
        """Return launch-relevant guardrail failures for the current settings."""
        issues: list[str] = []

        if self.disable_auth and not self.allows_unsafe_dev_features:
            issues.append(
                "DISABLE_AUTH is only allowed in local development/test environments"
            )

        if self.is_production:
            if self.debug:
                issues.append("DEBUG must be false in production")
            if self._is_placeholder_secret(self.jwt_secret_key):
                issues.append("JWT_SECRET_KEY still uses the placeholder default")
            if self._is_placeholder_secret(self.vault_encryption_key):
                issues.append("VAULT_ENCRYPTION_KEY still uses the placeholder default")
            if self._cors_is_localhost_only():
                issues.append("CORS_ORIGINS still points only to localhost addresses")

        explicit_precedence = os.environ.get(_ENV_PRECEDENCE_ENV_VAR, "").strip().lower()
        if explicit_precedence and explicit_precedence not in _ENV_PRECEDENCE_VALUES:
            issues.append(
                "DAENA_ENV_PRECEDENCE must be one of: env_file_first, process_env_first"
            )

        return issues

    def runtime_diagnostics(self) -> dict[str, Any]:
        """Return redacted runtime-truth diagnostics for startup and health surfaces."""
        return {
            "app_env": self.app_env,
            "is_production": self.is_production,
            "allows_unsafe_dev_features": self.allows_unsafe_dev_features,
            "env_precedence": self.env_precedence,
            "debug": {
                "value": self.debug,
                "source": self._field_source("debug"),
            },
            "disable_auth": {
                "value": self.disable_auth,
                "source": self._field_source("disable_auth"),
            },
            "jwt_secret_key": {
                "source": self._field_source("jwt_secret_key"),
                "placeholder": self._is_placeholder_secret(self.jwt_secret_key),
            },
            "vault_encryption_key": {
                "source": self._field_source("vault_encryption_key"),
                "placeholder": self._is_placeholder_secret(self.vault_encryption_key),
            },
            "cors_origins": {
                "source": self._field_source("cors_origins"),
                "count": len(self.cors_origins),
                "localhost_only": self._cors_is_localhost_only(),
            },
            "ollama_default_model": {
                "value": self.ollama_default_model,
                "source": self._field_source("ollama_default_model"),
            },
            "provider_keys": self.provider_key_status,
            "rate_limit_fail_open": True,  # Always fail-open to avoid blocking users
            "env_file": str(self.env_file_path) if self.env_file_path else None,
            "env_file_present": bool(self.env_file_path and self.env_file_path.exists()),
            "guardrail_issues": self.runtime_guardrail_issues(),
        }

    @staticmethod
    def _is_placeholder_secret(value: str) -> bool:
        """Whether a secret still matches a known placeholder."""
        return value in _PLACEHOLDER_SECRET_VALUES

    def _field_source(self, field_name: str) -> str:
        """Best-effort source detection honoring the active precedence contract."""
        env_key = field_name.upper()
        env_names = {key.upper() for key in os.environ}
        env_file_keys = set(_env_file_values(self.env_file_path))

        if self.env_precedence == "env_file_first":
            if env_key in env_file_keys:
                path = self.env_file_path
                return f"env_file:{path}" if path else "env_file"
            if env_key in env_names:
                return "process_env"
        else:
            if env_key in env_names:
                return "process_env"
            if env_key in env_file_keys:
                path = self.env_file_path
                return f"env_file:{path}" if path else "env_file"

        return "default"

    def _cors_is_localhost_only(self) -> bool:
        """Whether every configured CORS origin is a localhost-style address."""
        if not self.cors_origins:
            return True
        return all(
            any(marker in origin for marker in _LOCAL_ORIGIN_MARKERS)
            for origin in self.cors_origins
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Call this everywhere."""
    return Settings()
