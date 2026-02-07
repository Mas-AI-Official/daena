"""
Brain API endpoints - Shared brain with governance-gated writes.
"""

from __future__ import annotations

import os

from typing import Any, Dict, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.core.brain.store import brain_store, GovernanceState
from backend.config.settings import get_settings
from backend.services.websocket_manager import get_websocket_manager

router = APIRouter(prefix="/api/v1/brain", tags=["Brain"])


class QueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None


class ProposeExperienceRequest(BaseModel):
    experience: Dict[str, Any]
    reason: str
    source_agent_id: str
    department: Optional[str] = None


class CommitRequest(BaseModel):
    approved_by: str
    notes: Optional[str] = None


from backend.routes.auth import get_current_user

def get_real_user_role(current_user: dict) -> str:
    """Extract role from authenticated user payload"""
    return current_user.get("role", "client")


@router.get("/status")
async def get_brain_status() -> Dict[str, Any]:
    """Get brain status (read-only, available to all)"""
    status = brain_store.get_status()
    
    # Check Ollama and model availability
    ollama_available = False
    available_models = []
    active_model = None
    model_error = None
    llm_available = False
    
    try:
        from backend.services.local_llm_ollama import check_ollama_available, OLLAMA_BASE_URL, TRAINED_MODEL, DEFAULT_LOCAL_MODEL
        from backend.config.settings import settings
        
        # Get model names from settings
        trained_model_name = settings.trained_daena_model or "daena-brain"
        default_model_name = settings.default_local_model or "qwen2.5:7b-instruct"
        
        ollama_available = await check_ollama_available()
        
        if ollama_available:
            # Get available models
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        available_models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                        
                        # Determine active model (priority: trained > default > first available)
                        # Check for daena-brain (with or without :latest tag)
                        trained_found = False
                        for model_name in available_models:
                            # Check exact match or starts with trained model name
                            if (model_name == trained_model_name or 
                                model_name.startswith(trained_model_name + ":") or
                                model_name == "daena-brain" or
                                model_name.startswith("daena-brain:")):
                                active_model = model_name
                                trained_found = True
                                break
                        
                        if not trained_found:
                            # Check for default model (qwen2.5:7b-instruct or qwen2.5:14b-instruct)
                            default_found = False
                            for model_name in available_models:
                                if (model_name == default_model_name or 
                                    model_name.startswith(default_model_name.split(":")[0] + ":") or
                                    "qwen2.5" in model_name.lower()):
                                    active_model = model_name
                                    default_found = True
                                    break
                            
                            if not default_found and available_models:
                                active_model = available_models[0]
                        
                        # If we have models, LLM is available
                        if available_models:
                            llm_available = True
            except Exception as e:
                model_error = f"Could not list models: {e}"
        else:
            model_error = "Ollama is not running. Start it with: scripts\\START_OLLAMA.bat"
    except Exception as e:
        model_error = f"Ollama check failed: {e}"
    
    # Check if brain can actually process messages
    brain_operational = status.get("status") == "operational"
    brain_connected = brain_operational and ollama_available and llm_available
    
    # Add connection and model info
    status["connected"] = brain_connected
    status["ollama_available"] = ollama_available
    status["llm_available"] = llm_available
    status["available_models"] = available_models
    status["active_model"] = active_model
    status["brain_operational"] = brain_operational
    if model_error:
        status["model_error"] = model_error
    else:
        status["model_error"] = None
    
    # Add connection details for debugging
    status["connection_details"] = {
        "brain_store": "operational" if brain_operational else "not_operational",
        "ollama_service": "running" if ollama_available else "not_running",
        "models_loaded": len(available_models),
        "can_process_messages": brain_connected
    }
    
    return status


@router.get("/list-models")
async def list_available_models() -> Dict[str, Any]:
    """
    List all available LLM models from Ollama.
    This endpoint is called by Daena's model_list tool.
    """
    try:
        from backend.services.local_llm_ollama import check_ollama_available, OLLAMA_BASE_URL
        
        ollama_available = await check_ollama_available()
        
        if not ollama_available:
            return {
                "success": False,
                "error": "Ollama is not running. Start it with: scripts\\START_OLLAMA.bat",
                "models": [],
                "active_model": None
            }
        
        # Get available models from Ollama
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = []
                for m in data.get("models", []):
                    if isinstance(m, dict):
                        models.append({
                            "name": m.get("name"),
                            "size": m.get("size"),
                            "modified": m.get("modified_at"),
                            "family": m.get("details", {}).get("family", "unknown")
                        })
                
                # Determine active model (priority: trained > default > first)
                active_model = None
                for model in models:
                    if "daena" in model["name"].lower():
                        active_model = model["name"]
                        break
                if not active_model and models:
                    active_model = models[0]["name"]
                
                return {
                    "success": True,
                    "models": models,
                    "count": len(models),
                    "active_model": active_model,
                    "ollama_url": OLLAMA_BASE_URL
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to fetch models: HTTP {response.status_code}",
                    "models": []
                }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "models": []
        }


@router.get("/ping-ollama")
async def ping_ollama() -> Dict[str, Any]:
    """
    Test Ollama connection and return timing info.
    Useful for diagnosing timeout issues.
    """
    import time
    from backend.services.local_llm_ollama import OLLAMA_BASE_URL
    from backend.config.settings import settings
    
    result = {
        "base_url": OLLAMA_BASE_URL,
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    # Test 1: List models (should be fast)
    start = time.time()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = r.json().get("models", [])
            result["tests"]["list_models"] = {
                "status": "success",
                "duration_ms": int((time.time() - start) * 1000),
                "models_count": len(models),
                "models": [m.get("name") for m in models]
            }
    except Exception as e:
        result["tests"]["list_models"] = {
            "status": "error",
            "duration_ms": int((time.time() - start) * 1000),
            "error": str(e)
        }
    
    # Test 2: Generate with tiny prompt (tests first-token latency)
    start = time.time()
    try:
        import httpx
        # Use first available model or qwen2.5:7b
        test_model = "qwen2.5:7b-instruct"
        if result["tests"]["list_models"]["status"] == "success":
            available = result["tests"]["list_models"]["models"]
            if available:
                test_model = available[0]
        
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": test_model,
                    "prompt": "Hi",
                    "stream": False
                }
            )
            response_data = r.json()
            result["tests"]["generate"] = {
                "status": "success",
                "duration_ms": int((time.time() - start) * 1000),
                "model_used": test_model,
                "response_length": len(response_data.get("response", "")),
                "load_duration_ms": int(response_data.get("load_duration", 0) / 1000000),
                "eval_count": response_data.get("eval_count", 0)
            }
    except Exception as e:
        result["tests"]["generate"] = {
            "status": "error",
            "duration_ms": int((time.time() - start) * 1000),
            "error": str(e)
        }
    
    # Overall health
    all_success = all(
        test.get("status") == "success" 
        for test in result["tests"].values()
    )
    result["overall_status"] = "healthy" if all_success else "degraded"
    
    return result


@router.post("/governance/writeback/attempt")
async def log_writeback_attempt(
    agent_id: str,
    attempt_type: str,
    details: Optional[Dict[str, Any]] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Log an attempt by an agent to write directly to the brain (DENIED).
    """
    # Log the denied attempt
    brain_store._log_audit(
        action="writeback_attempt_denied",
        proposal_id="N/A",
        actor=agent_id,
        details={
            "attempt_type": attempt_type,
            "reason": "DENIED: requires governance pipeline",
            "details": details or {}
        }
    )
    
    return {
        "success": False,
        "message": "DENIED: requires governance pipeline",
        "reason": "Agents cannot write directly to the brain. All writeback must go through: Agent → Council/Governance Gate → Daena VP Merge → Memory Forge → Brain Commit",
        "correct_path": "/api/v1/brain/propose_experience",
        "agent_id": agent_id,
        "attempt_type": attempt_type,
        "logged": True
    }


@router.post("/query")
async def query_brain(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Query shared brain (read-only, available to all agents).
    """
    return brain_store.query(request.query, request.context)


@router.post("/propose_experience")
async def propose_experience(
    request: ProposeExperienceRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Propose experience to be added to shared brain (agents only).
    """
    return brain_store.propose_experience(
        experience=request.experience,
        reason=request.reason,
        source_agent_id=request.source_agent_id,
        department=request.department
    )


@router.post("/propose_knowledge")
async def propose_knowledge(
    agent_id: str,
    content: str,
    evidence: Optional[Dict[str, Any]] = None,
    department: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Propose knowledge to be added to shared brain (agents only).
    """
    return brain_store.propose_knowledge(
        agent_id=agent_id,
        content=content,
        evidence=evidence,
        department=department
    )


@router.post("/review/{proposal_id}")
async def review_proposal(
    proposal_id: str,
    council_member: str,
    score: float,
    comments: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Review and score a proposal (Council members only).
    """
    user_role = get_real_user_role(current_user)
    if user_role not in ["council", "daena_vp", "founder"]:
        raise HTTPException(status_code=403, detail="Access denied. Only council members can review proposals.")
    
    if not (0.0 <= score <= 1.0):
        raise HTTPException(status_code=400, detail="Score must be between 0.0 and 1.0")
    
    return brain_store.review_and_score(
        proposal_id=proposal_id,
        council_member=council_member,
        score=score,
        comments=comments
    )


@router.get("/queue")
async def get_governance_queue(
    state: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get governance queue (pending proposals).
    """
    user_role = get_real_user_role(current_user)
    if user_role not in ["daena_vp", "founder", "council"]:
        raise HTTPException(status_code=403, detail="Access denied. Governance queue requires VP/council access.")
    
    if state:
        try:
            state_enum = GovernanceState(state.lower())
            queue = brain_store.get_queue(state_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid state: {state}")
    else:
        queue = brain_store.get_queue()
    
    return {
        "queue": queue,
        "count": len(queue)
    }


@router.post("/commit/{proposal_id}")
async def commit_experience(
    proposal_id: str,
    request: CommitRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Commit proposal to shared brain (Daena VP / Founder only).
    """
    user_role = get_real_user_role(current_user)
    if user_role not in ["daena_vp", "founder"]:
        raise HTTPException(status_code=403, detail="Access denied. Only Daena VP or Founder can commit experiences.")
    
    return brain_store.approve_and_commit(
        proposal_id=proposal_id,
        daena_vp=request.approved_by,
        notes=request.notes
    )


@router.post("/approve_and_commit/{proposal_id}")
async def approve_and_commit_proposal(
    proposal_id: str,
    request: CommitRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Approve and commit proposal to shared brain (Daena VP only).
    """
    user_role = get_real_user_role(current_user)
    if user_role not in ["daena_vp", "founder"]:
        raise HTTPException(status_code=403, detail="Access denied. Only Daena VP or Founder can approve and commit.")
    
    return brain_store.approve_and_commit(
        proposal_id=proposal_id,
        daena_vp=request.approved_by,
        notes=request.notes
    )


@router.post("/transition/{proposal_id}")
async def transition_proposal_state(
    proposal_id: str,
    new_state: str,
    actor: str,
    notes: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Transition proposal to new state (Daena VP / Council only).
    """
    user_role = get_real_user_role(current_user)
    if user_role not in ["daena_vp", "founder", "council"]:
        raise HTTPException(status_code=403, detail="Access denied. State transitions require VP/council access.")
    
    try:
        state_enum = GovernanceState(new_state.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid state: {new_state}")
    
    return brain_store.transition_state(
        proposal_id=proposal_id,
        new_state=state_enum,
        actor=actor,
        notes=notes
    )


@router.post("/models/{model_id}/test")
async def test_model(model_id: str, current_user: dict = Depends(get_current_user)):
    """Test if model is working"""
    try:
        from backend.services.local_llm_ollama import check_ollama_available, OLLAMA_BASE_URL
        import httpx
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model_id,
                    "prompt": "Hi",
                    "stream": False
                }
            )
            
            if resp.status_code != 200:
                return {"status": "error", "message": f"Ollama returned {resp.status_code}"}
                
            result = resp.json()
        
        return {
            "status": "success",
            "model_id": model_id,
            "response_time_ms": int(result.get("total_duration", 0) / 1000000),
            "tokens_generated": result.get("eval_count", 0)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/models/scan")
async def scan_ollama_models(current_user: dict = Depends(get_current_user)):
    """Scan Ollama for installed models"""
    from backend.services.ollama_scanner import get_ollama_scanner
    
    scanner = get_ollama_scanner()
    models = await scanner.scan_models()
    
    # Save to database if available
    try:
        from backend.database import SessionLocal, Model
        
        db = SessionLocal()
        try:
            for model in models:
                # Check if model exists
                existing = db.query(Model).filter(Model.id == model['id']).first()
                if existing:
                    existing.size_gb = model['size_gb']
                    existing.status = model['status']
                else:
                    new_model = Model(
                        id=model['id'],
                        name=model['name'],
                        size_gb=model['size_gb'],
                        provider=model['provider'],
                        enabled=False,
                        status=model['status']
                    )
                    db.add(new_model)
            
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[Brain] Database save warning: {e}")
    
    return {
        "models": models,
        "count": len(models),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/models/{model_id}/enable")
async def enable_model(model_id: str, current_user: dict = Depends(get_current_user)):
    """Enable a model"""
    try:
        from backend.database import SessionLocal, Model
        
        db = SessionLocal()
        try:
            model = db.query(Model).filter(Model.id == model_id).first()
            if not model:
                raise HTTPException(404, "Model not found")
            
            model.enabled = True
            db.commit()
            
            # Broadcast update
            manager = get_websocket_manager()
            await manager.broadcast_to_user(str(current_user.get('id')), {
                'event': 'model.enabled',
                'data': {'model_id': model_id}
            })
            
            return {"status": "enabled", "model_id": model_id}
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/models/{model_id}/disable")
async def disable_model(model_id: str, current_user: dict = Depends(get_current_user)):
    """Disable a model"""
    try:
        from backend.database import SessionLocal, Model
        
        db = SessionLocal()
        try:
            model = db.query(Model).filter(Model.id == model_id).first()
            if not model:
                raise HTTPException(404, "Model not found")
            
            model.enabled = False
            db.commit()
            
            # Broadcast update
            manager = get_websocket_manager()
            await manager.broadcast_to_user(str(current_user.get('id')), {
                'event': 'model.disabled',
                'data': {'model_id': model_id}
            })
            
            return {"status": "disabled", "model_id": model_id}
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

