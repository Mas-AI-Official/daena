"""
LLM Status API endpoint (Phase B).

Provides honest status of local and cloud LLM providers.
"""

from fastapi import APIRouter
from typing import Dict, Any
import asyncio

from backend.services.llm_service import llm_service
from backend.services.local_llm_ollama import check_ollama_available, OLLAMA_BASE_URL, DEFAULT_LOCAL_MODEL, TRAINED_MODEL

router = APIRouter(prefix="/api/v1/llm", tags=["LLM Status"])


@router.get("/providers")
async def get_providers() -> Dict[str, Any]:
    """
    Get list of available LLM providers for CMP/Explorer.
    
    Returns:
    {
        providers: [
            {
                name: str,
                type: "local" | "cloud",
                available: bool,
                models: [...],
                test_status: "ok" | "error" | "not_tested"
            }
        ]
    }
    """
    providers = []
    
    # Local Ollama provider
    try:
        from backend.services.local_llm_ollama import check_ollama_available, OLLAMA_BASE_URL, DEFAULT_LOCAL_MODEL, TRAINED_MODEL
        ollama_ok = await check_ollama_available()
        models = []
        if ollama_ok:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
            except Exception:
                pass
        
        providers.append({
            "name": "ollama",
            "type": "local",
            "available": ollama_ok,
            "models": models,
            "base_url": OLLAMA_BASE_URL,
            "default_model": DEFAULT_LOCAL_MODEL,
            "trained_model": TRAINED_MODEL,
            "test_status": "ok" if ollama_ok else "error"
        })
    except Exception as e:
        providers.append({
            "name": "ollama",
            "type": "local",
            "available": False,
            "models": [],
            "test_status": "error",
            "error": str(e)
        })
    
    # Cloud providers
    if llm_service and llm_service.providers:
        for provider_name, provider_config in llm_service.providers.items():
            providers.append({
                "name": str(provider_name),
                "type": "cloud",
                "available": bool(provider_config.get("api_key")),
                "models": ["default"],  # Could be expanded
                "test_status": "ok" if provider_config.get("api_key") else "not_tested"
            })
    
    return {
        "providers": providers,
        "total": len(providers),
        "local_count": len([p for p in providers if p["type"] == "local"]),
        "cloud_count": len([p for p in providers if p["type"] == "cloud"])
    }


@router.post("/providers/test")
async def test_provider(provider_name: str) -> Dict[str, Any]:
    """
    Test connectivity to a specific provider.
    
    Returns:
    {
        provider: str,
        success: bool,
        latency_ms: int,
        error: str (if any)
    }
    """
    import time
    start_time = time.time()
    
    try:
        if provider_name == "ollama":
            from backend.services.local_llm_ollama import check_ollama_available
            available = await check_ollama_available()
            if available:
                return {
                    "provider": "ollama",
                    "success": True,
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "message": "Ollama is reachable"
                }
            else:
                return {
                    "provider": "ollama",
                    "success": False,
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "error": "Ollama not reachable"
                }
        else:
            # Test cloud provider (simplified - just check if configured)
            if llm_service and llm_service.providers:
                if provider_name in llm_service.providers:
                    return {
                        "provider": provider_name,
                        "success": True,
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "message": f"Provider {provider_name} is configured"
                    }
            
            return {
                "provider": provider_name,
                "success": False,
                "latency_ms": int((time.time() - start_time) * 1000),
                "error": f"Provider {provider_name} not configured"
            }
    except Exception as e:
        return {
            "provider": provider_name,
            "success": False,
            "latency_ms": int((time.time() - start_time) * 1000),
            "error": str(e)
        }


@router.get("/status")
async def get_llm_status() -> Dict[str, Any]:
    """
    Get honest LLM provider status.
    
    Returns:
    {
        local_provider: {type, base_url, model, ok, error},
        cloud_providers: [...],
        active_provider: {type, model}
    }
    """
    # Check local Ollama
    local_status = {
        "type": "ollama",
        "base_url": OLLAMA_BASE_URL,
        "model": TRAINED_MODEL or DEFAULT_LOCAL_MODEL,
        "ok": False,
        "error": None
    }
    
    try:
        ollama_available = await check_ollama_available()
        if ollama_available:
            local_status["ok"] = True
            # Try to get available models
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        available_models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                        local_status["available_models"] = available_models
                        if TRAINED_MODEL in available_models:
                            local_status["model"] = TRAINED_MODEL
                        elif DEFAULT_LOCAL_MODEL in available_models:
                            local_status["model"] = DEFAULT_LOCAL_MODEL
            except Exception as e:
                local_status["error"] = f"Could not list models: {e}"
        else:
            local_status["error"] = "Ollama not reachable. Start Ollama and ensure it's running on the configured base_url."
    except Exception as e:
        local_status["error"] = str(e)
    
    # Get cloud providers
    cloud_providers = []
    if llm_service and llm_service.providers:
        for provider_name, provider_config in llm_service.providers.items():
            cloud_providers.append({
                "type": str(provider_name),
                "configured": True,
                "has_api_key": bool(provider_config.get("api_key"))
            })
    
    # Determine active provider
    active_provider = None
    if local_status["ok"]:
        active_provider = {
            "type": "local",
            "provider": "ollama",
            "model": local_status["model"],
            "base_url": local_status["base_url"]
        }
    elif cloud_providers:
        # Use first available cloud provider
        active_provider = {
            "type": "cloud",
            "provider": cloud_providers[0]["type"],
            "model": "default"
        }
    else:
        active_provider = {
            "type": "none",
            "error": "No LLM providers available. Start Ollama or configure a cloud provider."
        }
    
    return {
        "local_provider": local_status,
        "cloud_providers": cloud_providers,
        "active_provider": active_provider,
        "local_first_mode": True  # Always local-first
    }


@router.get("/active")
async def get_active_provider() -> Dict[str, Any]:
    """
    Get the currently active LLM provider and why it was selected.
    
    Returns:
    {
        provider: str,
        model: str,
        type: "local" | "cloud" | "fallback",
        reason: str,
        available: bool
    }
    """
    import time
    start_time = time.time()
    
    try:
        from backend.services.local_llm_ollama import check_ollama_available, TRAINED_MODEL, DEFAULT_LOCAL_MODEL
        
        # Check Ollama first (local-first priority)
        ollama_ok = await check_ollama_available()
        
        if ollama_ok:
            # Determine which model will be used
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        available_models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                        model_to_use = DEFAULT_LOCAL_MODEL
                        if TRAINED_MODEL in available_models:
                            model_to_use = TRAINED_MODEL
                            reason = f"Trained model '{TRAINED_MODEL}' is available"
                        elif DEFAULT_LOCAL_MODEL in available_models:
                            model_to_use = DEFAULT_LOCAL_MODEL
                            reason = f"Default model '{DEFAULT_LOCAL_MODEL}' is available"
                        elif available_models:
                            model_to_use = available_models[0]
                            reason = f"Using fallback model '{model_to_use}'"
                        else:
                            reason = "No models available in Ollama"
                        
                        return {
                            "provider": "ollama",
                            "model": model_to_use,
                            "type": "local",
                            "reason": reason,
                            "available": True,
                            "base_url": OLLAMA_BASE_URL,
                            "latency_ms": int((time.time() - start_time) * 1000)
                        }
            except Exception as e:
                return {
                    "provider": "ollama",
                    "model": DEFAULT_LOCAL_MODEL,
                    "type": "local",
                    "reason": f"Ollama available but model check failed: {e}",
                    "available": True,
                    "latency_ms": int((time.time() - start_time) * 1000)
                }
        
        # Check cloud providers
        if llm_service and llm_service.providers:
            first_provider = list(llm_service.providers.keys())[0]
            return {
                "provider": str(first_provider),
                "model": "default",
                "type": "cloud",
                "reason": f"Ollama not available, using cloud provider '{first_provider}'",
                "available": True,
                "latency_ms": int((time.time() - start_time) * 1000)
            }
        
        # Fallback
        return {
            "provider": "fallback",
            "model": "none",
            "type": "fallback",
            "reason": "No LLM providers available. Ollama not running and no cloud keys configured.",
            "available": False,
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
    except Exception as e:
        return {
            "provider": "error",
            "model": "none",
            "type": "error",
            "reason": f"Error checking provider: {str(e)}",
            "available": False,
            "latency_ms": int((time.time() - start_time) * 1000)
        }


@router.post("/test")
async def test_llm(prompt: str = "Hello, Daena!") -> Dict[str, Any]:
    """
    Test LLM connectivity and Prompt Intelligence.
    
    Returns:
    {
        success: bool,
        response: str,
        prompt_intelligence: {...},
        provider_used: str,
        error: str (if any)
    }
    """
    result = {
        "success": False,
        "response": "",
        "prompt_intelligence": {},
        "provider_used": None,
        "error": None
    }
    
    try:
        # Check Prompt Intelligence status
        try:
            from backend.services.prompt_intelligence import get_prompt_intelligence
            prompt_intel = get_prompt_intelligence()
            result["prompt_intelligence"] = {
                "enabled": prompt_intel.enabled,
                "mode": prompt_intel.mode.value,
                "complexity_threshold": prompt_intel.complexity_threshold
            }
        except Exception as e:
            result["prompt_intelligence"] = {"error": str(e)}
        
        # Test LLM generation
        response = await llm_service.generate_response(
            prompt=prompt,
            max_tokens=100,
            temperature=0.7
        )
        
        result["success"] = True
        result["response"] = response
        
        # Determine provider used
        try:
            from backend.services.local_llm_ollama import check_ollama_available
            if await check_ollama_available():
                result["provider_used"] = "local/ollama"
            elif llm_service.providers:
                result["provider_used"] = f"cloud/{list(llm_service.providers.keys())[0]}"
            else:
                result["provider_used"] = "fallback"
        except Exception:
            result["provider_used"] = "unknown"
        
    except Exception as e:
        result["error"] = str(e)
        import traceback
        result["traceback"] = traceback.format_exc()
    
    return result