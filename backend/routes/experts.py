
from fastapi import APIRouter, Depends, HTTPException
from ..services.expert_training.trainer import ExpertTrainer

router = APIRouter()
trainer = ExpertTrainer()

@router.post("/experts/{expert_id}/train")
async def train_expert(expert_id: str, domain: str):
    """Trigger training for an expert persona"""
    try:
        result = await trainer.train_expert(expert_id, domain)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/experts/{expert_id}")
async def get_expert(expert_id: str):
    """Get expert status"""
    return await trainer.get_expert_status(expert_id)
