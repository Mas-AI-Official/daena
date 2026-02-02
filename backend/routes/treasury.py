"""
Treasury API — $DAENA and treasury stats for Control Plane.
Placeholder until blockchain deployment; returns config/DB or defaults.
"""
from fastapi import APIRouter
from typing import Dict, Any, List
import logging

router = APIRouter(prefix="/api/v1/treasury", tags=["treasury"])
logger = logging.getLogger(__name__)


def _get_treasury_config() -> Dict[str, Any]:
    """Read treasury balances from DB or env (placeholder)."""
    try:
        from backend.database import SessionLocal, SystemConfig
        import json
        db = SessionLocal()
        try:
            row = db.query(SystemConfig).filter(SystemConfig.config_key == "treasury_status").first()
            if row and row.config_value:
                data = json.loads(row.config_value) if isinstance(row.config_value, str) else row.config_value
                if isinstance(data, dict):
                    return data
        finally:
            db.close()
    except Exception as e:
        logger.debug("treasury config read: %s", e)
    return {}


@router.get("/status")
async def get_treasury_status() -> Dict[str, Any]:
    """Get treasury stats for Control Plane Treasury tab."""
    cfg = _get_treasury_config()
    daena_balance = cfg.get("daena_balance", "0")
    nft_minted = cfg.get("nft_minted", 0)
    eth_held = cfg.get("eth_held", "0")
    monthly_spend = cfg.get("monthly_spend", "$0")
    transactions: List[Dict[str, Any]] = cfg.get("transactions") or []
    return {
        "success": True,
        "daena_balance": daena_balance,
        "nft_minted": nft_minted,
        "eth_held": eth_held,
        "monthly_spend": monthly_spend,
        "transactions": transactions,
    }
