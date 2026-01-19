"""
Production-ready configuration settings for Daena AI System
"""

import os
import json
from pathlib import Path
from typing import List, Optional
from pydantic import Field, ConfigDict, field_validator
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
    debug: bool = Field(default=True, env="DEBUG")
    
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
    host: str = Field(default="0.0.0.0", env="BACKEND_HOST")
    port: int = Field(default=8000, env="BACKEND_PORT")
    backend_base_url: str = Field(default="http://localhost:8000", env="BACKEND_BASE_URL")
    frontend_origin: str = Field(default="http://localhost:8000", env="FRONTEND_ORIGIN")
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000", "http://127.0.0.1:8000"],
        env="CORS_ORIGINS"
    )
    
    # API Keys (env-based only; no credentials stored in repo)
    # NOTE: In local no-auth mode (DISABLE_AUTH=1) these are bypassed.
    api_key: Optional[str] = Field(None, env="DAENA_API_KEY")
    secret_key: Optional[str] = Field(None, env="DAENA_SECRET_KEY")
    test_api_key: Optional[str] = Field(None, env="DAENA_TEST_API_KEY")
    
    # AI Provider API Keys
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY") 
    gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY")
    deepseek_api_key: Optional[str] = Field(None, env="DEEPSEEK_API_KEY")
    grok_api_key: Optional[str] = Field(None, env="GROK_API_KEY")
    mistral_api_key: Optional[str] = Field(None, env="MISTRAL_API_KEY")
    
    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = Field(None, env="AZURE_OPENAI_API_KEY")
    azure_openai_api_version: str = Field("2025-01-01-preview", env="AZURE_OPENAI_API_VERSION")
    azure_openai_api_base: Optional[str] = Field(None, env="AZURE_OPENAI_API_BASE")
    azure_openai_deployment_id: Optional[str] = Field(None, env="AZURE_OPENAI_DEPLOYMENT_ID")

    # Cloud providers are opt-in (local-first by default)
    enable_cloud_llm: bool = Field(default=False, env="ENABLE_CLOUD_LLM")
    
    # Ollama Configuration
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_models_path: Optional[str] = Field(
        default_factory=lambda: str(project_root / "local_brain"),
        env="OLLAMA_MODELS"
    )
    trained_daena_model: str = Field(default="daena-brain", env="TRAINED_DAENA_MODEL")
    default_local_model: str = Field(default="qwen2.5:7b-instruct", env="DEFAULT_LOCAL_MODEL")
    
    # Prompt Intelligence Brain
    prompt_brain_enabled: bool = Field(default=True, env="PROMPT_BRAIN_ENABLED")
    prompt_brain_mode: str = Field(default="rules", env="PROMPT_BRAIN_MODE")  # rules|hybrid|llm_rewrite
    prompt_brain_complexity_threshold: int = Field(default=50, env="PROMPT_BRAIN_COMPLEXITY_THRESHOLD")
    prompt_brain_allow_llm_rewrite: bool = Field(default=False, env="PROMPT_BRAIN_ALLOW_LLM_REWRITE")
    
    # Complexity Scorer Thresholds
    daena_complexity_no_llm_max: int = Field(default=2, env="DAENA_COMPLEXITY_NO_LLM_MAX")
    daena_complexity_cheap_max: int = Field(default=5, env="DAENA_COMPLEXITY_CHEAP_MAX")
    daena_complexity_strong_max: int = Field(default=8, env="DAENA_COMPLEXITY_STRONG_MAX")
    
    # Cost Guard
    daena_founder_override: bool = Field(default=False, env="DAENA_FOUNDER_OVERRIDE")
    daena_deterministic_gate_enabled: bool = Field(default=True, env="DAENA_DETERMINISTIC_GATE_ENABLED")
    
    # Explorer Mode: Human-in-the-loop consultation (NO APIs, NO automation)
    enable_explorer_mode: bool = Field(default=True, env="ENABLE_EXPLORER_MODE")
    
    # Human Relay Explorer: Manual copy/paste bridge (NO automation, NO scraping)
    enable_human_relay_explorer: bool = Field(default=True, env="ENABLE_HUMAN_RELAY_EXPLORER")

    # ------------------------------------------------------------------
    # Training Configuration (Kill-switch)
    # ------------------------------------------------------------------
    training_enabled: bool = Field(default=False, env="DAENA_TRAINING_ENABLED")
    wandb_disabled: bool = Field(default=True, env="WANDB_DISABLED")
    hf_hub_disable_telemetry: bool = Field(default=True, env="HF_HUB_DISABLE_TELEMETRY")
    do_not_track: bool = Field(default=True, env="DO_NOT_TRACK")

    # ------------------------------------------------------------------
    # Operator / Automation (local-first, safe by default)
    # ------------------------------------------------------------------
    automation_safe_mode: bool = Field(default=True, env="AUTOMATION_SAFE_MODE")
    automation_allowed_domains: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "example.com", "httpbin.org"],
        env="AUTOMATION_ALLOWED_DOMAINS",
    )
    automation_enable_browser: bool = Field(default=False, env="AUTOMATION_ENABLE_BROWSER")
    automation_enable_desktop: bool = Field(default=False, env="AUTOMATION_ENABLE_DESKTOP")
    automation_request_timeout_sec: float = Field(default=15.0, env="AUTOMATION_REQUEST_TIMEOUT_SEC")
    automation_action_timeout_sec: float = Field(default=20.0, env="AUTOMATION_ACTION_TIMEOUT_SEC")
    automation_rate_limit_per_min: int = Field(default=30, env="AUTOMATION_RATE_LIMIT_PER_MIN")
    automation_max_processes: int = Field(default=50, env="AUTOMATION_MAX_PROCESSES")
    
    # Voice Services
    elevenlabs_api_key: Optional[str] = Field(None, env="ELEVENLABS_API_KEY")
    did_api_key: Optional[str] = Field(None, env="DID_API_KEY")
    google_tts_api_key: Optional[str] = Field(None, env="GOOGLE_TTS_API_KEY")
    
    # Authentication & Roles
    auth_enabled: bool = True
    # LOCAL DEV ONLY: bypass all auth when True (default True for no-auth baseline)
    disable_auth: bool = Field(default=True, env="DISABLE_AUTH")
    dev_founder_name: str = Field(default="Masoud", env="DEV_FOUNDER_NAME")
    founder_role: str = "founder"
    agent_role: str = "agent"
    guest_role: str = "guest"
    session_expiry: int = 3600

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
    gcp_project_id: Optional[str] = Field(None, env="GCP_PROJECT_ID")
    gcp_zone: str = "us-central1-a"
    gcp_instance_name: str = "daena-gpu-instance"
    gcp_machine_type: str = "n1-standard-4"
    gcp_gpu_type: str = "nvidia-tesla-t4"
    gcp_gpu_count: int = 1
    
    # Compute Device Configuration (CPU/GPU/TPU)
    compute_prefer: str = Field("auto", env="COMPUTE_PREFER")  # auto, cpu, gpu, tpu
    compute_allow_tpu: bool = Field(True, env="COMPUTE_ALLOW_TPU")
    compute_tpu_batch_factor: int = Field(128, env="COMPUTE_TPU_BATCH_FACTOR")
    
    # OCR Comparison Configuration
    ocr_comparison_enabled: bool = Field(False, env="OCR_COMPARISON_ENABLED")
    ocr_confidence_threshold: float = Field(0.7, env="OCR_CONFIDENCE_THRESHOLD")
    ocr_hybrid_mode: bool = Field(True, env="OCR_HYBRID_MODE")

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
    stripe_publishable_key: Optional[str] = Field(None, env="STRIPE_PUBLISHABLE_KEY")
    stripe_secret_key: Optional[str] = Field(None, env="STRIPE_SECRET_KEY")
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
    
    # Prompt Intelligence Brain Configuration
    prompt_brain_enabled: bool = Field(default=True, env="PROMPT_BRAIN_ENABLED")
    prompt_brain_mode: str = Field(default="rules", env="PROMPT_BRAIN_MODE")  # rules|hybrid|llm_rewrite
    prompt_brain_complexity_threshold: int = Field(default=50, env="PROMPT_BRAIN_COMPLEXITY_THRESHOLD")
    prompt_brain_allow_llm_rewrite: bool = Field(default=False, env="PROMPT_BRAIN_ALLOW_LLM_REWRITE")

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


def get_settings() -> Settings:
    """Expose application settings for dependency injection/tests."""
    return settings