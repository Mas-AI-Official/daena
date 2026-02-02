"""
Crypto monitoring API — dashboard data for /ui/crypto-monitor.
Synced with DeFi module; price/summary for monitoring page.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/crypto", tags=["crypto"])


@router.get("/dashboard")
async def get_crypto_dashboard() -> Dict[str, Any]:
    """
    Dashboard data for Crypto Monitor page: summary, price placeholders, DeFi status, tools.
    Wire to /ui/crypto-monitor; sync with backend.
    """
    try:
        from backend.routes.defi import defi_status, list_scans
        defi = await defi_status()
        scans = await list_scans()
    except Exception as e:
        logger.debug("DeFi not available: %s", e)
        defi = {"status": "unknown", "module": "defi", "scans_count": 0, "active_scans": 0}
        scans = []

    # Price/summary placeholders (can be replaced with real feed later)
    prices: List[Dict[str, Any]] = []
    symbol = (os.environ.get("CRYPTO_SYMBOL") or "DAENA").strip().upper()
    price_raw = os.environ.get("CRYPTO_PRICE_USD")
    try:
        price_usd = float(price_raw) if price_raw else None
    except (TypeError, ValueError):
        price_usd = None
    if symbol:
        prices.append({
            "symbol": symbol,
            "price_usd": price_usd,
            "label": "Token" if symbol == "DAENA" else symbol,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        })

    return {
        "success": True,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "prices": prices,
            "defi_status": defi.get("status", "unknown"),
            "scans_count": defi.get("scans_count", 0),
            "active_scans": defi.get("active_scans", 0),
        },
        "defi": defi,
        "scans": scans[:20],
        "tools": [
            {"id": "defi_scan", "name": "DeFi contract scan", "endpoint": "/api/v1/defi/scan", "status": defi.get("status")},
            {"id": "defi_health", "name": "DeFi health", "endpoint": "/api/v1/defi/health", "status": "ok"},
        ],
    }
