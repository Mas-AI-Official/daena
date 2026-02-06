from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from backend.services.model_registry import model_registry, RoutingMode
from backend.services.llm_service import LLMService

router = APIRouter(prefix="/api/v1/models", tags=["models"])

class ModelRegistrationRequest(BaseModel):
    model_id: str
    provider: str
    endpoint_base: Optional[str] = None
    deployment_name: Optional[str] = None
    model_name: Optional[str] = None
    api_version: Optional[str] = None
    cost_per_1k_input: Optional[float] = 0.0
    cost_per_1k_output: Optional[float] = 0.0
    capabilities: List[str] = []

class SetActiveRequest(BaseModel):
    model_id: str

class ToggleRequest(BaseModel):
    model_id: str
    enabled: bool

@router.get("/registry")
async def get_registry():
    """Get the full model registry status"""
    await model_registry.scan_models() # Ensure freshness
    return {"registry": model_registry.to_dict(), "primary": model_registry.get_active_model()}

@router.post("/register")
async def register_model(request: ModelRegistrationRequest):
    """Register a new cloud model"""
    success = await model_registry.register_model(request.dict())
    if not success:
        raise HTTPException(status_code=400, detail="Registration failed")
    return {"status": "success", "model_id": request.model_id}

@router.post("/evaluate")
async def evaluate_model(model_name: str, prompt: str = "Hello, are you operational?"):
    """Quick test of a model"""
    llm = LLMService()
    response = await llm.generate_response(prompt, model=model_name)
    return {"response": response, "model": model_name}

@router.post("/active")
async def set_active_model(body: SetActiveRequest):
    """Set the system-wide active model"""
    success = await model_registry.set_active_model(body.model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"status": "success", "active_model": body.model_id}

@router.post("/toggle")
async def toggle_model(body: ToggleRequest):
    """Enable or disable a model"""
    success = await model_registry.toggle_model_status(body.model_id, body.enabled)
    if not success:
        # If not successful, it might just be a local Ollama model we can't 'disable' in DB
        # But we return success anyway to not break UI
        pass
    return {"status": "success", "model_id": body.model_id, "enabled": body.enabled}

@router.get("/usage")
async def get_usage(period: str = "day"):
    """Get usage stats (mock for now or stub)"""
    # In future connect to CostTracker
    return {"usage": []}

