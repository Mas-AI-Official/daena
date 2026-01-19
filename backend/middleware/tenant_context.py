"""
Tenant Context Middleware - Extracts and validates tenant_id from requests.
Ensures tenant_id is available in request state for all downstream operations.
"""
import logging
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


def extract_tenant_id(request: Request) -> Optional[str]:
    """
    Extract tenant ID from request.
    
    Priority:
    1. X-Tenant-ID header
    2. tenant_id query parameter
    3. tenant_id in request body (for POST/PUT)
    4. API key mapping (if implemented)
    5. Default tenant for unauthenticated requests
    
    Returns:
        tenant_id or None
    """
    # 1. Check header
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        return tenant_id.strip()
    
    # 2. Check query parameter
    tenant_id = request.query_params.get("tenant_id")
    if tenant_id:
        return tenant_id.strip()
    
    # 3. Check API key header (could map to tenant)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # In production, implement API key -> tenant mapping
        # For now, use API key as tenant identifier if no explicit tenant
        pass
    
    # 4. Default tenant for unauthenticated requests
    # In production, this should require authentication
    return "default"


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract tenant_id and add it to request state.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Extract tenant_id
        tenant_id = extract_tenant_id(request)
        
        # Add to request state
        request.state.tenant_id = tenant_id
        
        # Add to response headers for debugging
        response = await call_next(request)
        response.headers["X-Tenant-ID"] = tenant_id or "default"
        
        return response


def get_tenant_id(request: Request) -> str:
    """
    Get tenant_id from request state.
    
    Returns:
        tenant_id (defaults to "default" if not set)
    """
    return getattr(request.state, "tenant_id", "default")


def require_tenant(request: Request) -> str:
    """
    Require tenant_id from request, raise exception if not found.
    
    Returns:
        tenant_id
        
    Raises:
        HTTPException if tenant_id is missing or invalid
    """
    tenant_id = get_tenant_id(request)
    if not tenant_id or tenant_id == "default":
        raise HTTPException(
            status_code=400,
            detail="Tenant ID required. Provide X-Tenant-ID header or tenant_id query parameter."
        )
    return tenant_id

