"""
Production-ready configuration settings for Daena AI System
"""

import os
import json
from pathlib import Path
from typing import List, Optional
from pydantic import Field, ConfigDict, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent.parent.parent
env_file = project_root / ".env"
env_azure_openai = project_root / ".env_azure_openai"

if env_file.exists():
    load_dotenv(env_file)
if env_azure_openai.exists():
    load_dotenv(env_azure_openai)


def env_first(*keys: str, default: Optional[str] = None) -> Optional[str]:
    """Return the first env var that is set and non-empty. Backward-compat for renames (e.g. OPENCLAW_* -> DAENABOT_HANDS_*)."""
    for k in keys:
        v = os.getenv(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="allow", 
        protected_namespaces=(),
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False
    )
    
    # API Configuration
    app_name: str = "Mas-AI Company - Daena AI VP System"
    app_version: str = "2.0.0"
    debug: bool = Field(default=True, validation_alias="DEBUG")
    
    @field_validator('debug', mode='before')
    @classmethod
    def parse_debug(cls, v):
        """Parse debug value from various formats"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ('true', '1', 'yes', 'on'):
                return True
            if v_lower in ('false', '0', 'no', 'off', 'warn'):
                return False
        return bool(v)
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", validation_alias="BACKEND_HOST")
    port: int = Field(default=8000, validation_alias="BACKEND_PORT")
    backend_base_url: str = Field(default="http://localhost:8000", validation_alias="BACKEND_BASE_URL")
    frontend_origin: str = Field(default="http://localhost:8000", validation_alias="FRONTEND_ORIGIN")
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"],
        validation_alias="CORS_ORIGINS"
    )
    
    # API Keys (env-based only; no credentials stored in repo)
    # NOTE: In local no-auth mode (DISABLE_AUTH=1) these are bypassed.
    api_key: Optional[str] = Field(None, validation_alias="DAENA_API_KEY")
    secret_key: Optional[str] = Field(None, validation_alias="DAENA_SECRET_KEY")
    test_api_key: Optional[str] = Field(None, validation_alias="DAENA_TEST_API_KEY")
    
    # AI Provider API Keys
    openai_api_key: Optional[str] = Field(None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, validation_alias="ANTHROPIC_API_KEY") 
    gemini_api_key: Optional[str] = Field(None, validation_alias="GEMINI_API_KEY")
    deepseek_api_key: Optional[str] = Field(None, validation_alias="DEEPSEEK_API_KEY")
    grok_api_key: Optional[str] = Field(None, validation_alias="GROK_API_KEY")
    mistral_api_key: Optional[str] = Field(None, validation_alias="MISTRAL_API_KEY")
    
    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = Field(None, validation_alias="AZURE_OPENAI_API_KEY")
    azure_openai_api_version: str = Field("2025-01-01-preview", validation_alias="AZURE_OPENAI_API_VERSION")
    azure_openai_api_base: Optional[str] = Field(None, validation_alias="AZURE_OPENAI_API_BASE")
    azure_openai_deployment_id: Optional[str] = Field(None, validation_alias="AZURE_OPENAI_DEPLOYMENT_ID")

    # Cloud providers are opt-in (local-first by default)
    enable_cloud_llm: bool = Field(default=False, validation_alias="ENABLE_CLOUD_LLM")
    
    # Model weights + caches (Ollama, XTTS, Whisper, reasoning models). Set per project via env.
    models_root: str = Field(default="D:/Ideas/MODELS_ROOT", validation_alias="MODELS_ROOT")
    # Learned memory, chat history, embeddings, governance logs. Default: project/local_brain or DAENA_BRAIN_ROOT.
    brain_root: Optional[str] = Field(default=None, validation_alias="BRAIN_ROOT")
    # Ollama Configuration (ollama models live under MODELS_ROOT/ollama; OLLAMA_MODELS overrides)
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_models_path: Optional[str] = Field(
        default=None,
        validation_alias="OLLAMA_MODELS"
    )
    # Local brain fallback: when primary Ollama fails, use Daena-managed Ollama on this port (same binary, MODELS_ROOT)
    ollama_fallback_port: int = Field(default=11435, validation_alias="OLLAMA_FALLBACK_PORT")
    ollama_use_local_brain_fallback: bool = Field(default=True, validation_alias="OLLAMA_USE_LOCAL_BRAIN_FALLBACK")
    trained_daena_model: str = Field(default="daena-brain", validation_alias="TRAINED_DAENA_MODEL")
    default_local_model: str = Field(default="qwen2.5:7b-instruct", validation_alias="DEFAULT_LOCAL_MODEL")

    @model_validator(mode="after")
    def set_ollama_models_path_from_root(self):
        """Derive ollama_models_path and xtts_model_path from models_root when not set."""
        if self.ollama_models_path is None or (isinstance(self.ollama_models_path, str) and self.ollama_models_path.strip() == ""):
            object.__setattr__(self, "ollama_models_path", str(Path(self.models_root).resolve() / "ollama"))
        if getattr(self, "xtts_model_path", None) is None or (isinstance(self.xtts_model_path, str) and self.xtts_model_path.strip() == ""):
            object.__setattr__(self, "xtts_model_path", str(Path(self.models_root).resolve() / "xtts"))
        return self
    
    # Prompt Intelligence Brain
    prompt_brain_enabled: bool = Field(default=True, validation_alias="PROMPT_BRAIN_ENABLED")
    prompt_brain_mode: str = Field(default="rules", validation_alias="PROMPT_BRAIN_MODE")  # rules|hybrid|llm_rewrite
    prompt_brain_complexity_threshold: int = Field(default=50, validation_alias="PROMPT_BRAIN_COMPLEXITY_THRESHOLD")
    prompt_brain_allow_llm_rewrite: bool = Field(default=False, validation_alias="PROMPT_BRAIN_ALLOW_LLM_REWRITE")
    
    # Complexity Scorer Thresholds
    daena_complexity_no_llm_max: int = Field(default=2, validation_alias="DAENA_COMPLEXITY_NO_LLM_MAX")
    daena_complexity_cheap_max: int = Field(default=5, validation_alias="DAENA_COMPLEXITY_CHEAP_MAX")
    daena_complexity_strong_max: int = Field(default=8, validation_alias="DAENA_COMPLEXITY_STRONG_MAX")
    
    # Cost Guard
    daena_founder_override: bool = Field(default=False, validation_alias="DAENA_FOUNDER_OVERRIDE")
    daena_deterministic_gate_enabled: bool = Field(default=True, validation_alias="DAENA_DETERMINISTIC_GATE_ENABLED")
    
    # Explorer Mode: Human-in-the-loop consultation (NO APIs, NO automation)
    enable_explorer_mode: bool = Field(default=True, validation_alias="ENABLE_EXPLORER_MODE")
    
    # Human Relay Explorer: Manual copy/paste bridge (NO automation, NO scraping)
    enable_human_relay_explorer: bool = Field(default=True, validation_alias="ENABLE_HUMAN_RELAY_EXPLORER")

    # ------------------------------------------------------------------
    # Training Configuration (Kill-switch)
    # ------------------------------------------------------------------
    training_enabled: bool = Field(default=False, validation_alias="DAENA_TRAINING_ENABLED")
    wandb_disabled: bool = Field(default=True, validation_alias="WANDB_DISABLED")
    hf_hub_disable_telemetry: bool = Field(default=True, validation_alias="HF_HUB_DISABLE_TELEMETRY")
    do_not_track: bool = Field(default=True, validation_alias="DO_NOT_TRACK")

    # ------------------------------------------------------------------
    # Operator / Automation (local-first, safe by default)
    # ------------------------------------------------------------------
    enable_execution_layer: bool = Field(default=True, validation_alias="ENABLE_EXECUTION_LAYER")
    automation_safe_mode: bool = Field(default=True, validation_alias="AUTOMATION_SAFE_MODE")
    automation_allowed_domains: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "example.com", "httpbin.org"],
        validation_alias="AUTOMATION_ALLOWED_DOMAINS",
    )
    automation_enable_browser: bool = Field(default=False, validation_alias="AUTOMATION_ENABLE_BROWSER")
    automation_enable_desktop: bool = Field(default=False, validation_alias="AUTOMATION_ENABLE_DESKTOP")
    automation_request_timeout_sec: float = Field(default=15.0, validation_alias="AUTOMATION_REQUEST_TIMEOUT_SEC")
    automation_action_timeout_sec: float = Field(default=20.0, validation_alias="AUTOMATION_ACTION_TIMEOUT_SEC")
    automation_rate_limit_per_min: int = Field(default=30, validation_alias="AUTOMATION_RATE_LIMIT_PER_MIN")
    automation_max_processes: int = Field(default=50, validation_alias="AUTOMATION_MAX_PROCESSES")
    # Execution Layer: require X-Execution-Token when set; ALWAYS require token unless dev override
    execution_token: Optional[str] = Field(None, validation_alias="EXECUTION_TOKEN")
    allow_insecure_execution_local: bool = Field(default=False, validation_alias="ALLOW_INSECURE_EXECUTION_LOCAL")
    execution_bind: str = Field(default="127.0.0.1", validation_alias="EXECUTION_BIND")
    allow_remote_execution: bool = Field(default=False, validation_alias="ALLOW_REMOTE_EXECUTION")
    # Moltbot-style providers: credentials from env only; default all disabled
    discord_bot_token: Optional[str] = Field(None, validation_alias="DISCORD_BOT_TOKEN")
    telegram_bot_token: Optional[str] = Field(None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret_token: Optional[str] = Field(None, validation_alias="TELEGRAM_WEBHOOK_SECRET_TOKEN")
    # Workspace root for filesystem_read/write (allowlist); default project root
    execution_workspace_root: Optional[str] = Field(None, validation_alias="EXECUTION_WORKSPACE_ROOT")
    # Daena Windows Node (Moltbot-style hands): URL and token from env only
    windows_node_url: Optional[str] = Field(None, validation_alias="WINDOWS_NODE_URL")  # default http://127.0.0.1:18888
    # Shell allowlist: only these commands (or prefixes) allowed for shell_exec
    shell_allowlist: List[str] = Field(
        default_factory=lambda: ["git ", "python -m ", "pip list", "pip show", "pip --version"],
        validation_alias="SHELL_ALLOWLIST",
    )
    # DaenaBot "hands" = OpenClaw Gateway (bind 127.0.0.1 only; do not expose to LAN)
    daenabot_display_name: str = Field(default="DaenaBot", validation_alias="DAENABOT_DISPLAY_NAME")
    daenabot_hands_url: str = Field(default="ws://127.0.0.1:18789/ws", validation_alias="DAENABOT_HANDS_URL")
    daenabot_hands_token: Optional[str] = Field(None, validation_alias="DAENABOT_HANDS_TOKEN")
    daena_tool_automation: str = Field(default="low_only", validation_alias="DAENA_TOOL_AUTOMATION")  # off | low_only | on
    daena_emergency_stop: bool = Field(default=False, validation_alias="DAENA_EMERGENCY_STOP")
    # XTTS / TTS (use MODELS_ROOT/xtts)
    xtts_enabled: bool = Field(default=True, validation_alias="XTTS_ENABLED")
    xtts_server_url: str = Field(default="http://localhost:8020", validation_alias="XTTS_SERVER_URL")
    xtts_model_path: Optional[str] = Field(None, validation_alias="XTTS_MODEL_PATH")
    xtts_speaker_wav: Optional[str] = Field(None, validation_alias="XTTS_SPEAKER_WAV")
    xtts_language: str = Field(default="en", validation_alias="XTTS_LANGUAGE")
    # Reasoning / heavy models (Ollama model names under MODELS_ROOT/ollama)
    ollama_reasoning_model: str = Field(default="deepseek-r1:7b", validation_alias="OLLAMA_REASONING_MODEL")
    ollama_reasoning_fallback: str = Field(default="qwen2.5:14b-instruct", validation_alias="OLLAMA_REASONING_FALLBACK")
    
    # Voice Services
    elevenlabs_api_key: Optional[str] = Field(None, validation_alias="ELEVENLABS_API_KEY")
    did_api_key: Optional[str] = Field(None, validation_alias="DID_API_KEY")
    google_tts_api_key: Optional[str] = Field(None, validation_alias="GOOGLE_TTS_API_KEY")
    
    # Authentication & Roles
    auth_enabled: bool = True
    # LOCAL DEV ONLY: bypass all auth when True. Default False (auth ON); set DISABLE_AUTH=1 for local dev.
    disable_auth: bool = Field(default=False, validation_alias="DISABLE_AUTH")
    dev_founder_name: str = Field(default="Masoud", validation_alias="DEV_FOUNDER_NAME")
    founder_role: str = "founder"
    agent_role: str = "agent"
    guest_role: str = "guest"
    session_expiry: int = 3600

    # Security Guardian / Incident response: system-wide lockdown (env + runtime)
    security_lockdown_mode: bool = Field(default=False, validation_alias="SECURITY_LOCKDOWN_MODE")

    # Global HTTP rate limiting (middleware): enable in production to reduce abuse
    rate_limit_enabled: bool = Field(default=False, validation_alias="RATE_LIMIT_ENABLED")

    @model_validator(mode="after")
    def inject_daenabot_hands_fallback(self):
        """Prefer DAENABOT_HANDS_*; fallback to OPENCLAW_GATEWAY_* so old env still works."""
        url = env_first("DAENABOT_HANDS_URL", "OPENCLAW_GATEWAY_URL", default="ws://127.0.0.1:18789/ws")
        if url:
            object.__setattr__(self, "daenabot_hands_url", url)
        token = env_first("DAENABOT_HANDS_TOKEN", "OPENCLAW_GATEWAY_TOKEN", default=None)
        object.__setattr__(self, "daenabot_hands_token", token)
        return self

    @field_validator("rate_limit_enabled", "security_lockdown_mode", mode="before")
    @classmethod
    def parse_bool_env(cls, v):
        """Parse bool from env (1/true/yes -> True, 0/false/no -> False)."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ("true", "1", "yes", "on"):
                return True
            if v_lower in ("false", "0", "no", "off"):
                return False
        return bool(v)

    @field_validator("disable_auth", mode="before")
    @classmethod
    def parse_disable_auth(cls, v):
        """Parse DISABLE_AUTH from various formats."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ("true", "1", "yes", "on"):
                return True
            if v_lower in ("false", "0", "no", "off"):
                return False
        return bool(v)
    
    # Voice Configuration
    voice_enabled: bool = True
    raw_voice_activation_phrases: Optional[str] = None  # Raw string from env
    voice_response_enabled: bool = True
    voice_recognition_enabled: bool = True
    voice_env_path: str = "./daena_tts/Scripts/Activate.ps1"
    
    # Hybrid GPU/Cloud Configuration
    gpu_enabled: bool = True
    gcp_fallback_enabled: bool = True
    gcp_project_id: Optional[str] = Field(None, validation_alias="GCP_PROJECT_ID")
    gcp_zone: str = "us-central1-a"
    gcp_instance_name: str = "daena-gpu-instance"
    gcp_machine_type: str = "n1-standard-4"
    gcp_gpu_type: str = "nvidia-tesla-t4"
    gcp_gpu_count: int = 1
    
    # Compute Device Configuration (CPU/GPU/TPU)
    compute_prefer: str = Field("auto", validation_alias="COMPUTE_PREFER")  # auto, cpu, gpu, tpu
    compute_allow_tpu: bool = Field(True, validation_alias="COMPUTE_ALLOW_TPU")
    compute_tpu_batch_factor: int = Field(128, validation_alias="COMPUTE_TPU_BATCH_FACTOR")
    
    # OCR Comparison Configuration
    ocr_comparison_enabled: bool = Field(False, validation_alias="OCR_COMPARISON_ENABLED")
    ocr_confidence_threshold: float = Field(0.7, validation_alias="OCR_CONFIDENCE_THRESHOLD")
    ocr_hybrid_mode: bool = Field(True, validation_alias="OCR_HYBRID_MODE")

    @property
    def voice_activation_phrases(self) -> List[str]:
        """
        Robust accessor for voice activation phrases:
        - Supports JSON list format: '["Hey Daena", "Jarvis"]'
        - Supports comma-separated: 'Hey Daena,Jarvis'
        - Supports blank or unset values (returns default)
        """
        raw = self.raw_voice_activation_phrases
        if not raw:
            return ["Hey Daena", "Computer", "Assistant"]
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                return parsed
        except Exception:
            pass
        return [p.strip() for p in raw.split(",") if p.strip()]

    @property
    def voice_activation_phrases_list(self) -> list[str]:
        """Alias for backward compatibility"""
        return self.voice_activation_phrases

    @field_validator("cors_origins", mode='before')
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @field_validator("shell_allowlist", mode="before")
    @classmethod
    def parse_shell_allowlist(cls, v):
        if v is None:
            return ["git ", "python -m ", "pip list", "pip show", "pip --version"]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return ["git ", "python -m ", "pip list", "pip show", "pip --version"]
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass
            return [p.strip() for p in s.split(",") if p.strip()]
        return ["git ", "python -m ", "pip list", "pip show", "pip --version"]

    @field_validator("automation_allowed_domains", mode="before")
    @classmethod
    def parse_automation_allowed_domains(cls, v):
        if v is None:
            return ["localhost", "127.0.0.1", "example.com", "httpbin.org"]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            # Supports JSON list or comma-separated list
            s = v.strip()
            if not s:
                return []
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:
                pass
            return [p.strip() for p in s.split(",") if p.strip()]
        return [str(v).strip()] if str(v).strip() else []
    
    # Monetization
    stripe_publishable_key: Optional[str] = Field(None, validation_alias="STRIPE_PUBLISHABLE_KEY")
    stripe_secret_key: Optional[str] = Field(None, validation_alias="STRIPE_SECRET_KEY")
    enable_payments: bool = False
    marketplace_enabled: bool = True
    commission_rate: float = 0.15
    
    # Database Configuration
    database_url: str = "sqlite:///./daena.db"
    postgres_server: str = "localhost"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "daena"
    
    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    
    # Logging Configuration
    log_level: str = "info"

    # Monitoring
    prometheus_enabled: bool = True
    metrics_port: int = 9090
    


settings = Settings()

def validate_llm_providers():
    """Validate that at least one LLM provider is configured"""
    provider_keys = [
        settings.openai_api_key,
        settings.gemini_api_key,
        settings.anthropic_api_key,
        settings.deepseek_api_key,
        settings.grok_api_key,
        settings.mistral_api_key,
    ]
    if not any(provider_keys):
        print("⚠️ WARNING: No LLM providers are configured. AI responses will be disabled.")
    else:
        print("✅ LLM providers configured.")

def get_database_url() -> str:
    """Construct database URL from settings"""
    if settings.database_url and settings.database_url.startswith("postgresql"):
        return settings.database_url
    
    # Fallback to constructing from individual components
    return f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_server}/{settings.postgres_db}"

def get_cors_origins():
    """Get CORS origins for FastAPI - supports environment variable"""
    # Allow comma-separated list from env var
    if isinstance(settings.cors_origins, str):
        return [origin.strip() for origin in settings.cors_origins.split(",")]
    return settings.cors_origins


def get_brain_root() -> Path:
    """Brain root for learned memory, chat history, governance (brain_store, user_context, chat_history). Prefer BRAIN_ROOT, else MODELS_ROOT/daena_brain, else project local_brain."""
    if settings.brain_root and str(settings.brain_root).strip():
        return Path(settings.brain_root).resolve()
    if settings.models_root:
        return Path(settings.models_root).resolve() / "daena_brain"
    return project_root / "local_brain"


def get_settings() -> Settings:
    """Expose application settings for dependency injection/tests."""
    return settings