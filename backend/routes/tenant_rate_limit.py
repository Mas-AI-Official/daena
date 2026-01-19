"""
API endpoints for tenant rate limiting management.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
import logging

from backend.middleware.tenant_rate_limit import tenant_rate_limiter, extract_tenant_id
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/tenant-rate-limit/stats")
async def get_tenant_rate_limit_stats(
    tenant_id: Optional[str] = None,
    _: bool = Depends(verify_monitoring_auth)
):
    """Get rate limiting statistics for a tenant or all tenants."""
    if tenant_id:
        stats = tenant_rate_limiter.get_stats(tenant_id)
        if not stats:
            raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
        return stats
    else:
        return tenant_rate_limiter.get_stats()


@router.get("/tenant-rate-limit/{tenant_id}/status")
async def get_tenant_status(
    tenant_id: str,
    _: bool = Depends(verify_monitoring_auth)
):
    """Get current rate limit status for a specific tenant."""
    limits = tenant_rate_limiter._get_tenant_limits(tenant_id)
    bucket = tenant_rate_limiter.buckets.get(tenant_id, {"tokens": 0.0, "last_refill": 0.0})
    
    # Refill to get current tokens
    current_tokens = tenant_rate_limiter._refill_tokens(tenant_id, limits)
    
    return {
        "tenant_id": tenant_id,
        "limits": limits,
        "current_tokens": round(current_tokens, 2),
        "request_count": tenant_rate_limiter.get_request_count(tenant_id),
        "utilization_percent": round((1 - current_tokens / limits.get("burst_size", 100)) * 100, 2)
    }

