"""
Brain Status API
Provides status and control endpoints for the AI brain/LLM connection

IMPORTANT: This is the SINGLE SOURCE OF TRUTH for brain status.
UI and chat must query these endpoints, never hardcode model names.
"""
from fastapi import APIRouter, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum
import httpx
import logging
from pathlib import Path

router = APIRouter(prefix="/api/v1/brain", tags=["brain"])
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434"
LOCAL_BRAIN_PATH = Path(__file__).parent.parent.parent / "local_brain"


class RoutingMode(str, Enum):
    """Brain routing mode"""
    LOCAL_ONLY = "local_only"
    API_ONLY = "api_only"
    HYBRID = "hybrid"


# In-memory routing mode (survives restart via DB)
_current_routing_mode = RoutingMode.LOCAL_ONLY


@router.get("/status")
async def get_brain_status() -> Dict[str, Any]:
    """Get comprehensive brain/LLM status - supports multiple active models"""
    from backend.database import SessionLocal, SystemConfig
    import json
    
    # Get active models from DB (supports multiple)
    db = SessionLocal()
    active_models = []
    active_model = None
    try:
        # Try to get multiple active models first
        config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_models").first()
        if config:
            try:
                active_models = json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                if not isinstance(active_models, list):
                    active_models = []
            except:
                active_models = []
        
        # Fallback to single active model for backward compatibility
        if not active_models:
            single_config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_model").first()
            if single_config:
                active_model = single_config.config_value
                if active_model:
                    active_models = [active_model]
    finally:
        db.close()
    
    status = {
        "connected": False,
        "ollama_available": False,
        "llm_available": False,
        "provider": "ollama",
        "models": [],
        "active_model": active_models[0] if active_models else None,  # Primary for backward compatibility
        "active_models": active_models,  # All active models
        "routing_mode": _current_routing_mode.value,
        "local_brain_path": str(LOCAL_BRAIN_PATH),
        "local_brain_exists": LOCAL_BRAIN_PATH.exists()
    }
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                status["connected"] = True
                status["ollama_available"] = True
                status["llm_available"] = len(models) > 0
                model_list = [
                    {
                        "name": m.get("name"),
                        "size": m.get("size", 0),
                        "modified_at": m.get("modified_at"),
                        "active": m.get("name") in active_models
                    }
                    for m in models
                ]
                status["models"] = model_list
                
                # If no active models set, default to first model
                if not active_models and models:
                    status["active_model"] = models[0].get("name")
                    status["active_models"] = [models[0].get("name")]
    except Exception as e:
        logger.warning(f"Ollama not available: {e}")
        status["error"] = str(e)
    
    return status

@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """List all available LLM models"""
    models = {
        "local": [],
        "trained": [],
        "cloud": []
    }
    
    # Get Ollama models
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                for m in data.get("models", []):
                    models["local"].append({
                        "name": m.get("name"),
                        "size_gb": round(m.get("size", 0) / (1024**3), 2),
                        "modified": m.get("modified_at")
                    })
    except Exception as e:
        logger.warning(f"Could not list Ollama models: {e}")
    
    # Check local_brain trained models
    if LOCAL_BRAIN_PATH.exists():
        manifests = LOCAL_BRAIN_PATH / "manifests"
        if manifests.exists():
            for registry in manifests.iterdir():
                if registry.is_dir():
                    for model in registry.iterdir():
                        if model.is_dir():
                            models["trained"].append({
                                "name": f"{registry.name}/{model.name}",
                                "path": str(model)
                            })
    
    # Cloud APIs (status only)
    models["cloud"] = [
        {"name": "openai/gpt-4", "status": "not_configured"},
        {"name": "google/gemini-pro", "status": "not_configured"},
        {"name": "anthropic/claude-3", "status": "not_configured"},
        {"name": "xai/grok", "status": "not_configured"}
    ]
    
    return models

@router.get("/list-models")
async def list_all_models() -> Dict[str, Any]:
    """List ALL available local models from Ollama"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                
                return {
                    "success": True,
                    "count": len(models),
                    "models": [{"name": m.get("name"), "size": m.get("size", 0)} for m in models]
                }
            else:
                return {"success": False, "error": "Ollama not responding", "models": []}
    except Exception as e:
        return {"success": False, "error": str(e), "models": []}

@router.get("/recommended")
async def list_recommended_models() -> List[Dict[str, Any]]:
    """List recommended models for installation"""
    from backend.services.model_registry import get_model_registry
    registry = get_model_registry()
    # Ensure we have latest status
    await registry.get_status()
    return registry.get_recommended_models()

@router.post("/routing_mode")
async def set_routing_mode(mode: str = Body(..., embed=True)) -> Dict[str, Any]:
    """Set the brain routing mode (local_only, api_only, hybrid)"""
    global _current_routing_mode
    try:
        _current_routing_mode = RoutingMode(mode)
        return {
            "success": True,
            "routing_mode": _current_routing_mode.value
        }
    except ValueError:
        return {
            "success": False,
            "error": f"Invalid mode. Must be one of: {[m.value for m in RoutingMode]}"
        }

@router.post("/scan")
async def scan_models() -> Dict[str, Any]:
    """Force scan of available models"""
    try:
        from backend.services.model_registry import get_model_registry
        registry = get_model_registry()
        models = await registry.scan_models()
        return {
            "success": True,
            "count": len(models),
            "models": [m.name for m in models]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/test")
async def test_brain_connection() -> Dict[str, Any]:
    """Test the brain connection with a simple prompt using the ACTIVE model"""
    # Get active model from DB
    from backend.database import SessionLocal, SystemConfig
    import json
    
    db = SessionLocal()
    active_model = "qwen2.5:7b-instruct" # Default fallback
    try:
        config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_model").first()
        if config and config.config_value:
            active_model = config.config_value
    finally:
        db.close()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": active_model,
                    "prompt": "Say 'Hello, I am Daena's brain and I am working!' in one sentence.",
                    "stream": False
                }
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "model": active_model
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": f"Model '{active_model}' not found. Please pull it or select a different model.",
                    "model": active_model
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "hint": "Make sure Ollama is running: ollama serve"
        }
    
    return {"success": False, "error": "Unknown error"}

class PullModelRequest(BaseModel):
    model_name: str = "qwen2.5:7b-instruct"

@router.post("/pull")
async def pull_model(request: PullModelRequest = Body(...)) -> Dict[str, Any]:
    """Pull/download a model from Ollama"""
    model_name = request.model_name
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": model_name}
            )
            return {
                "success": response.status_code == 200,
                "model": model_name,
                "message": f"Started pulling {model_name}"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/models/{model_name}/select")
async def select_model(model_name: str, enabled: bool = True) -> Dict[str, Any]:
    """Select/set active model(s) for the system - supports multiple active models"""
    from backend.database import SessionLocal, SystemConfig
    from datetime import datetime
    import json
    
    db = SessionLocal()
    try:
        # Get or create active models config (JSON array)
        config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_models").first()
        
        if config:
            try:
                active_models = json.loads(config.config_value) if isinstance(config.config_value, str) else config.config_value
                if not isinstance(active_models, list):
                    active_models = []
            except:
                active_models = []
        else:
            active_models = []
            config = SystemConfig(
                config_key="active_brain_models",
                config_value=json.dumps([]),
                config_type="json",
                description="List of active brain models (supports multiple)"
            )
            db.add(config)
        
        # Add or remove model from active list
        if enabled:
            if model_name not in active_models:
                active_models.append(model_name)
        else:
            if model_name in active_models:
                active_models.remove(model_name)
                # Ensure at least one model is active
                if not active_models:
                    return {
                        "success": False,
                        "error": "Cannot disable all models. At least one model must be active."
                    }
        
        # Update config
        config.config_value = json.dumps(active_models)
        config.updated_at = datetime.utcnow()
        
        # Also update single active_brain_model for backward compatibility
        single_config = db.query(SystemConfig).filter(SystemConfig.config_key == "active_brain_model").first()
        if single_config:
            single_config.config_value = active_models[0] if active_models else ""
            single_config.updated_at = datetime.utcnow()
        elif active_models:
            single_config = SystemConfig(
                config_key="active_brain_model",
                config_value=active_models[0],
                config_type="string",
                description="Primary active brain model (for backward compatibility)"
            )
            db.add(single_config)
        
        db.commit()
        
        # Verify model exists in Ollama
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{OLLAMA_URL}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    if model_name not in models:
                        return {
                            "success": False,
                            "error": f"Model {model_name} not found in Ollama. Available: {', '.join(models)}"
                        }
        except Exception as e:
            logger.warning(f"Could not verify model in Ollama: {e}")
        
        return {
            "success": True,
            "model": model_name,
            "enabled": enabled,
            "active_models": active_models,
            "message": f"Model {model_name} {'enabled' if enabled else 'disabled'}. Active models: {', '.join(active_models)}"
        }
    finally:
        db.close()

@router.delete("/models/{model_name}")
async def delete_model(model_name: str) -> Dict[str, Any]:
    """Delete a model from Ollama"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{OLLAMA_URL}/api/delete",
                json={"name": model_name}
            )
            return {
                "success": response.status_code == 200,
                "model": model_name,
                "message": f"Deleted {model_name}" if response.status_code == 200 else "Failed to delete"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/models/usage")
async def get_model_usage() -> Dict[str, Any]:
    """Get usage statistics for models from database"""
    from backend.database import SessionLocal, ChatMessage
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        # Get usage stats for last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Count messages by model
        usage_stats = db.query(
            ChatMessage.model,
            func.count(ChatMessage.id).label('call_count'),
            func.sum(ChatMessage.tokens).label('total_tokens')
        ).filter(
            ChatMessage.created_at >= thirty_days_ago,
            ChatMessage.model.isnot(None)
        ).group_by(ChatMessage.model).all()
        
        stats = {}
        for model, calls, tokens in usage_stats:
            stats[model or "unknown"] = {
                "calls": calls or 0,
                "tokens": tokens or 0
            }
        
        return {
            "success": True,
            "period": "30_days",
            "stats": stats
        }
    finally:
        db.close()
