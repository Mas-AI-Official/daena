"""
Compatibility shim for legacy imports.

Historically some modules imported `config.settings`.
The canonical settings live in `backend.config.settings`.
"""

from backend.config.settings import settings, Settings, validate_llm_providers, get_cors_origins, get_settings  # noqa: F401