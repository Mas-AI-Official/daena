"""
Model Registry API endpoints (Phase D).

Provides:
- List all models
- Get model details
- Evaluate model
- Promote model (manual)
- Rollback model
- Set offline mode
- Auto-upgrade check
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

from backend.services.model_registry import model_registry

router = APIRouter(prefix="/api/v1/models", tags=["Model Registry"])


class PromoteRequest(BaseModel):
    model_id: str
    actor: str = "manual"


class RollbackRequest(BaseModel):
    model_id: str
    actor: str = "manual"


@router.get("/")
async def list_models(include_retired: bool = False) -> Dict[str, Any]:
    """List all registered models"""
    models = model_registry.list_all(include_retired=include_retired)
    return {
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "provider": m.provider,
                "type": m.model_type,
                "status": m.status,
                "health": m.health_status,
                "score": m.score,
                "retired": m.retired,
                "capability_tags": m.capability_tags,
                "cost_estimate": m.cost_estimate,
                "latency_estimate": m.latency_estimate,
            }
            for m in models
        ],
        "primary_model_id": model_registry.primary_model_id,
        "default_model_id": model_registry.default_model_id,
        "offline_mode": model_registry.offline_mode,
    }


@router.get("/{model_id}")
async def get_model(model_id: str) -> Dict[str, Any]:
    """Get model details"""
    model = model_registry.models.get(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {
        "id": model.id,
        "name": model.name,
        "provider": model.provider,
        "type": model.model_type,
        "status": model.status,
        "health": model.health_status,
        "score": model.score,
        "retired": model.retired,
        "capability_tags": model.capability_tags,
        "cost_estimate": model.cost_estimate,
        "latency_estimate": model.latency_estimate,
        "local_path": model.local_path,
        "endpoint": model.endpoint,
    }


@router.post("/{model_id}/evaluate")
async def evaluate_model(model_id: str) -> Dict[str, Any]:
    """Evaluate a model and update its score"""
    result = model_registry.evaluate_model(model_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/promote")
async def promote_model(request: PromoteRequest) -> Dict[str, Any]:
    """Manually promote a model to primary"""
    result = model_registry.promote_model(request.model_id, request.actor)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/rollback")
async def rollback_model(request: RollbackRequest) -> Dict[str, Any]:
    """Rollback to a previous model"""
    result = model_registry.rollback_model(request.model_id, request.actor)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/auto-upgrade/check")
async def check_auto_upgrade() -> Dict[str, Any]:
    """Check if a better model should become primary"""
    new_primary = model_registry.auto_upgrade_check()
    if new_primary:
        return {
            "should_upgrade": True,
            "new_primary": new_primary,
            "current_primary": model_registry.primary_model_id,
        }
    return {
        "should_upgrade": False,
        "current_primary": model_registry.primary_model_id,
    }


@router.post("/auto-upgrade/execute")
async def execute_auto_upgrade() -> Dict[str, Any]:
    """Execute auto-upgrade if a better model is available"""
    new_primary = model_registry.auto_upgrade_check()
    if new_primary:
        result = model_registry.promote_model(new_primary, "auto_upgrade")
        return {
            "upgraded": True,
            **result
        }
    return {
        "upgraded": False,
        "message": "No better model found"
    }


@router.post("/offline-mode")
async def set_offline_mode(enabled: bool) -> Dict[str, Any]:
    """Enable/disable offline mode"""
    model_registry.set_offline_mode(enabled)
    return {
        "offline_mode": model_registry.offline_mode,
        "message": "Offline mode enabled" if enabled else "Offline mode disabled"
    }


@router.get("/offline-mode/status")
async def get_offline_mode() -> Dict[str, Any]:
    """Get offline mode status"""
    return {
        "offline_mode": model_registry.offline_mode,
        "current_primary": model_registry.primary_model_id,
        "available_local_models": [
            m.id for m in model_registry.list_available()
            if m.provider in ["ollama", "local"]
        ]
    }





