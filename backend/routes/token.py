from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from ..services.blockchain_service import blockchain_service

router = APIRouter(prefix="/api/v1/token", tags=["blockchain"])

@router.get("/balance/{address}")
async def get_balance(address: str) -> Dict[str, Any]:
    """Get $DAENA balance for a given wallet address."""
    return blockchain_service.get_token_balance(address)

@router.get("/supply")
async def get_supply() -> Dict[str, Any]:
    """Get total $DAENA supply stats."""
    status = blockchain_service.get_treasury_status()
    return {
        "total_supply": status.get("total_supply"),
        "symbol": "DAENA",
        "circulating": "150,000"
    }
