from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from ..services.blockchain_service import blockchain_service

router = APIRouter(prefix="/api/v1/nft", tags=["blockchain"])

@router.get("/slots")
async def get_slots() -> List[Dict[str, Any]]:
    """Get list of Agent NFT slots and their occupancy status."""
    return blockchain_service.get_nft_slots()

@router.post("/mint")
async def mint_agent(agent_data: Dict[str, str]) -> Dict[str, Any]:
    """Mint a new Agent NFT for a licensed slot."""
    name = agent_data.get("name")
    dept = agent_data.get("department")
    if not name or not dept:
        raise HTTPException(status_code=400, detail="Name and department required")
    
    tx_hash = blockchain_service.mint_agent_nft(name, dept)
    return {
        "success": True,
        "tx_hash": tx_hash,
        "message": f"Minting request for {name} submitted."
    }
