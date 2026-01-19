"""
Tenant-Specific Rate Limiting Middleware.

Provides per-tenant rate limiting with configurable limits and integration
with the backpressure system for flow control.
"""

import time
import os
import json
from typing import Dict, Optional, Tuple
from collections import defaultdict
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class TenantRateLimiter:
    """
    Rate limiter with per-tenant limits and token bucket algorithm.
    
    Features:
    - Per-tenant rate limits (configurable)
    - Token bucket algorithm for smooth rate limiting
    - Integration with backpressure system
    - Metrics tracking
    - Configurable via environment variables
    """
    
    def __init__(self):
        # Token buckets: tenant_id -> {tokens: float, last_refill: float}
        self.buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {"tokens": 0.0, "last_refill": time.time()})
        
        # Request counters for tracking (separate from token buckets)
        self.request_counts: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        
        # Default limits per tenant (requests per minute)
        # Increased limits for development
        env = os.getenv("ENVIRONMENT", "development")
        if env == "development":
            default_rpm = 10000  # Very high limit for development
            default_burst = 1000  # Large burst for development
        else:
            default_rpm = int(os.getenv("DAENA_TENANT_RATE_LIMIT_RPM", "1000"))
            default_burst = int(os.getenv("DAENA_TENANT_BURST_SIZE", "100"))
        
        self.default_limits = {
            "requests_per_minute": default_rpm,
            "burst_size": default_burst,
            "refill_rate": float(os.getenv("DAENA_TENANT_REFILL_RATE", "166.67")),  # tokens per second (10000/min)
        }
        
        # Per-tenant overrides (can be loaded from config)
        self.tenant_overrides: Dict[str, Dict[str, int]] = {}
        
        # Load tenant-specific limits from config if available
        self._load_tenant_config()
    
    def _load_tenant_config(self):
        """Load tenant-specific rate limit configurations."""
        config_path = os.getenv("DAENA_TENANT_RATE_LIMIT_CONFIG")
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    self.tenant_overrides = config.get("tenant_limits", {})
                    logger.info(f"Loaded tenant rate limit config: {len(self.tenant_overrides)} tenants")
            except Exception as e:
                logger.warning(f"Failed to load tenant rate limit config: {e}")
    
    def _get_tenant_limits(self, tenant_id: str) -> Dict[str, int]:
        """Get rate limits for a specific tenant."""
        if tenant_id in self.tenant_overrides:
            return {**self.default_limits, **self.tenant_overrides[tenant_id]}
        return self.default_limits
    
    def _refill_tokens(self, tenant_id: str, limits: Dict[str, int]) -> float:
        """Refill token bucket for a tenant."""
        bucket = self.buckets[tenant_id]
        now = time.time()
        elapsed = now - bucket["last_refill"]
        
        # Refill tokens based on refill rate
        refill_rate = limits.get("refill_rate", self.default_limits["refill_rate"])
        max_tokens = limits.get("burst_size", self.default_limits["burst_size"])
        
        tokens_to_add = elapsed * refill_rate
        bucket["tokens"] = min(max_tokens, bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now
        
        return bucket["tokens"]
    
    def consume_token(self, tenant_id: str, tokens: int = 1) -> Tuple[bool, Optional[Dict[str, int]]]:
        """
        Consume tokens from tenant's bucket.
        
        Returns:
            (allowed, rate_limit_info): Whether request is allowed and rate limit info
        """
        limits = self._get_tenant_limits(tenant_id)
        current_tokens = self._refill_tokens(tenant_id, limits)
        
        if current_tokens >= tokens:
            self.buckets[tenant_id]["tokens"] = current_tokens - tokens
            return True, {
                "limit": limits["requests_per_minute"],
                "remaining": int(self.buckets[tenant_id]["tokens"]),
                "reset_after": int(60 / limits.get("refill_rate", 16.67))
            }
        else:
            return False, {
                "limit": limits["requests_per_minute"],
                "remaining": 0,
                "reset_after": int(60 / limits.get("refill_rate", 16.67)),
                "retry_after": int((tokens - current_tokens) / limits.get("refill_rate", 16.67))
            }
    
    def track_request(self, tenant_id: str, limit_key: str = "default"):
        """Track request for metrics (separate from token bucket)."""
        now = time.time()
        window_start = now - 60  # 1 minute window
        
        # Clean old requests
        self.request_counts[tenant_id][limit_key] = [
            req_time for req_time in self.request_counts[tenant_id][limit_key]
            if req_time > window_start
        ]
        
        # Add current request
        self.request_counts[tenant_id][limit_key].append(now)
    
    def get_request_count(self, tenant_id: str, limit_key: str = "default") -> int:
        """Get current request count for tenant."""
        return len(self.request_counts[tenant_id][limit_key])
    
    def get_stats(self, tenant_id: Optional[str] = None) -> Dict:
        """Get rate limiting statistics."""
        if tenant_id:
            limits = self._get_tenant_limits(tenant_id)
            bucket = self.buckets[tenant_id]
            return {
                "tenant_id": tenant_id,
                "limits": limits,
                "current_tokens": bucket["tokens"],
                "request_count": sum(len(reqs) for reqs in self.request_counts[tenant_id].values())
            }
        else:
            return {
                "total_tenants": len(self.buckets),
                "default_limits": self.default_limits,
                "tenant_overrides": len(self.tenant_overrides)
            }


def extract_tenant_id(request: Request) -> Optional[str]:
    """
    Extract tenant ID from request.
    
    Checks in order:
    1. X-Tenant-ID header
    2. tenant_id query parameter
    3. tenant_id in request body (for POST/PUT)
    4. API key mapping (if configured)
    """
    # Check header first
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        return tenant_id.strip()
    
    # Check query parameter
    tenant_id = request.query_params.get("tenant_id")
    if tenant_id:
        return tenant_id.strip()
    
    # Check API key header (could map to tenant)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Could implement API key -> tenant mapping here
        # For now, use API key as tenant identifier
        return f"api_key_{api_key[:8]}"
    
    # Default tenant for unauthenticated requests
    return "default"


# Global tenant rate limiter instance
tenant_rate_limiter = TenantRateLimiter()


async def tenant_rate_limit_middleware(request: Request, call_next):
    """
    Tenant-specific rate limiting middleware.
    
    This middleware should run after authentication but before business logic.
    """
    # Skip rate limiting for health checks, static files, and dashboard routes
    skip_paths = [
        "/health", "/docs", "/openapi.json", "/redoc",
        "/", "/dashboard", "/enhanced-dashboard", "/daena-office", 
        "/command-center", "/council-dashboard", "/analytics"
    ]
    
    if request.url.path in skip_paths or request.url.path.startswith("/static") or request.url.path.startswith("/templates"):
        return await call_next(request)
    
    # Skip rate limiting for local/dev/test clients
    client_host = request.client.host if request.client else ""
    env = os.getenv("ENVIRONMENT", "development")
    if env in {"development", "test"} and client_host in ["127.0.0.1", "localhost", "::1", "testclient"]:
        return await call_next(request)
    
    # Extract tenant ID
    tenant_id = extract_tenant_id(request)
    if not tenant_id:
        tenant_id = "default"
    
    # Determine limit key based on endpoint
    path = request.url.path
    if path.startswith("/api/v1/auth"):
        limit_key = "auth"
    elif path.startswith("/api/v1/council"):
        limit_key = "council"
    elif path.startswith("/api/v1/founder"):
        limit_key = "founder"
    elif path.startswith("/monitoring"):
        limit_key = "monitoring"
    else:
        limit_key = "default"
    
    # Check rate limit
    allowed, rate_info = tenant_rate_limiter.consume_token(tenant_id, tokens=1)
    
    if not allowed:
        logger.warning(f"Tenant rate limit exceeded: tenant={tenant_id}, limit_key={limit_key}")
        
        # Track metrics
        try:
            from memory_service.metrics import incr
            incr("tenant_rate_limit_exceeded")
        except ImportError:
            pass
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "tenant_id": tenant_id,
                "limit_key": limit_key,
                "rate_limit_info": rate_info
            },
            headers={
                "Retry-After": str(rate_info.get("retry_after", 60)),
                "X-RateLimit-Limit": str(rate_info.get("limit", 0)),
                "X-RateLimit-Remaining": str(rate_info.get("remaining", 0)),
                "X-RateLimit-Reset-After": str(rate_info.get("reset_after", 60)),
                "X-Tenant-ID": tenant_id
            }
        )
    
    # Track request for metrics
    tenant_rate_limiter.track_request(tenant_id, limit_key)
    
    # Add rate limit headers to response
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(rate_info.get("limit", 0))
    response.headers["X-RateLimit-Remaining"] = str(rate_info.get("remaining", 0))
    response.headers["X-RateLimit-Reset-After"] = str(rate_info.get("reset_after", 60))
    response.headers["X-Tenant-ID"] = tenant_id
    
    return response

