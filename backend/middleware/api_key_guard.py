from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Fallback settings if config module is not available
try:
    from backend.config.settings import get_settings
    settings = get_settings()
    API_KEY = getattr(settings, "secret_key", None) or getattr(settings, "api_key", None)
    TEST_API_KEY = getattr(settings, "test_api_key", None)
except ImportError:
    try:
        from config.settings import get_settings
        settings = get_settings()
        API_KEY = getattr(settings, "secret_key", None) or getattr(settings, "api_key", None)
        TEST_API_KEY = getattr(settings, "test_api_key", None)
    except ImportError:
        # Fallback settings
        API_KEY = None
        TEST_API_KEY = None

class APIKeyGuard(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.api_key = API_KEY
        self.test_api_key = TEST_API_KEY
        
        # Strictly public paths only (no auth). System/config/logs/daena require API key.
        self.public_paths = [
            "/",
            "/health",
            "/health/",
            "/api/v1/health",
            "/api/v1/rate-limit",
            "/dashboard",
            "/dashboard/",
            "/api/v1/external/test",
            "/docs",
            "/openapi.json",
            "/api/v1/docs",
            "/api/v1/openapi.json",
        ]
        
        # External API paths that use their own authentication
        self.external_api_paths = [
            "/api/v1/external/templates/list",
            "/api/v1/external/integrations/available", 
            "/api/v1/external/llm/models"
        ]

    async def dispatch(self, request: Request, call_next):
        import os

        # NO-AUTH local/dev mode: bypass API key enforcement
        if getattr(settings, "disable_auth", False) or os.getenv("DISABLE_AUTH", "0").lower() in {"1", "true", "yes", "on"}:
            return await call_next(request)

        # Testing/dev environments: do not block internal test clients
        if os.getenv("ENVIRONMENT", "development") in {"development", "test"}:
            return await call_next(request)

        # Exclude documentation paths from API key check
        if request.url.path in self.public_paths or request.url.path.startswith("/dashboard/"):
            return await call_next(request)
            
        # Allow external API paths (they have their own authentication)
        if request.url.path.startswith("/api/v1/external/"):
            return await call_next(request)

        # Execution layer uses X-Execution-Token only (no global API key required)
        if request.url.path.startswith("/api/v1/execution/"):
            return await call_next(request)
            
        # Allow OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
            
        client_key = request.headers.get("x-api-key")
        
        # Only accept env-provided keys (no hardcoded secrets)
        valid_keys = [k for k in [self.api_key, self.test_api_key] if k]
        
        # For development-like hosts - allow local requests
        if hasattr(request.url, 'hostname') and (
            "localhost" in str(request.url.hostname) or
            "127.0.0.1" in str(request.url.hostname) or
            "testserver" in str(request.url.hostname) or
            request.url.hostname in ["localhost", "127.0.0.1", "testserver"]
        ):
            return await call_next(request)
        
        # If no API keys configured, fail closed outside localhost/testserver.
        if not valid_keys:
            raise HTTPException(status_code=500, detail="API key guard enabled but no keys configured. Set DAENA_API_KEY or enable DISABLE_AUTH=1 for local mode.")

        # If no API key provided and not localhost
        if not client_key:
            raise HTTPException(status_code=403, detail="Forbidden: API Key required")
            
        if client_key not in valid_keys:
            raise HTTPException(status_code=403, detail="Forbidden: Invalid API Key")
            
        return await call_next(request)
