import time
import asyncio
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        import os
        self.requests: Dict[str, list] = {}
        # Chat rate limit configurable via env (default: 60 req/min)
        chat_limit = int(os.getenv("CHAT_RATE_LIMIT_PER_MIN", "60"))
        self.limits = {
            "default": {"requests": 500, "window": 60},  # 500 requests per minute (increased for frontend)
            "auth": {"requests": 10, "window": 60},      # 10 auth attempts per minute
            "council": {"requests": 50, "window": 60},   # 50 council requests per minute
            "founder": {"requests": 200, "window": 60},  # 200 founder requests per minute
            "chat": {"requests": chat_limit, "window": 60},  # Chat endpoint (configurable)
        }
    
    def get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Use X-Forwarded-For if available (for proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"
    
    def get_limit_key(self, request: Request) -> str:
        """Determine rate limit key based on endpoint"""
        path = request.url.path
        
        if path.startswith("/api/v1/auth"):
            return "auth"
        elif path.startswith("/api/v1/council"):
            return "council"
        elif path.startswith("/api/v1/founder") or "founder" in path:
            return "founder"
        elif path.startswith("/api/v1/daena/chat") or path == "/api/v1/daena/chat":
            return "chat"
        else:
            return "default"
    
    def is_rate_limited(self, client_id: str, limit_key: str) -> bool:
        """Check if client is rate limited"""
        now = time.time()
        limit_config = self.limits.get(limit_key, self.limits["default"])
        
        # Initialize client requests if not exists
        if client_id not in self.requests:
            self.requests[client_id] = {}
        
        if limit_key not in self.requests[client_id]:
            self.requests[client_id][limit_key] = []
        
        # Clean old requests outside the window
        window_start = now - limit_config["window"]
        self.requests[client_id][limit_key] = [
            req_time for req_time in self.requests[client_id][limit_key]
            if req_time > window_start
        ]
        
        # Check if limit exceeded
        if len(self.requests[client_id][limit_key]) >= limit_config["requests"]:
            return True
        
        # Add current request
        self.requests[client_id][limit_key].append(now)
        return False
    
    def get_remaining_requests(self, client_id: str, limit_key: str) -> int:
        """Get remaining requests for client"""
        limit_config = self.limits.get(limit_key, self.limits["default"])
        current_requests = len(self.requests.get(client_id, {}).get(limit_key, []))
        return max(0, limit_config["requests"] - current_requests)

# Global rate limiter instance
rate_limiter = RateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    client_id = rate_limiter.get_client_id(request)
    limit_key = rate_limiter.get_limit_key(request)
    
    # Skip rate limiting for health checks, static files, and dashboard routes
    skip_paths = [
        "/health", "/docs", "/openapi.json", "/redoc",
        "/", "/dashboard", "/enhanced-dashboard", "/daena-office",
        "/command-center", "/council-dashboard", "/analytics"
    ]
    
    if request.url.path in skip_paths or request.url.path.startswith("/static") or request.url.path.startswith("/templates"):
        return await call_next(request)
    
    # Skip rate limiting for local/dev/test clients
    import os
    client_host = request.client.host if request.client else ""
    env = os.getenv("ENVIRONMENT", "development")
    if env in {"development", "test"} and client_host in ["127.0.0.1", "localhost", "::1", "testclient"]:
        return await call_next(request)
    
    # Check rate limit
    if rate_limiter.is_rate_limited(client_id, limit_key):
        logger.warning(f"Rate limit exceeded for {client_id} on {limit_key}")
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "limit_key": limit_key,
                "retry_after": rate_limiter.limits[limit_key]["window"]
            },
            headers={
                "Retry-After": str(rate_limiter.limits[limit_key]["window"]),
                "X-RateLimit-Limit": str(rate_limiter.limits[limit_key]["requests"]),
                "X-RateLimit-Remaining": str(rate_limiter.get_remaining_requests(client_id, limit_key))
            }
        )
    
    # Add rate limit headers to response
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.limits[limit_key]["requests"])
    response.headers["X-RateLimit-Remaining"] = str(rate_limiter.get_remaining_requests(client_id, limit_key))
    
    return response 