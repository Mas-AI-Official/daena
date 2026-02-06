"""
Local LLM Service using Ollama
Provides local inference when cloud APIs are unavailable.
"""

import os
import httpx
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Configuration (env-driven)
from backend.config.settings import settings

OLLAMA_BASE_URL = settings.ollama_base_url
# Priority: trained model > default > fallback
TRAINED_MODEL = settings.trained_daena_model
DEFAULT_LOCAL_MODEL = settings.default_local_model
# Use qwen2.5:14b-instruct as fallback (exists in local_brain)
FALLBACK_MODEL = os.getenv("FALLBACK_LOCAL_MODEL", "qwen2.5:14b-instruct")
TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# Ollama models path: prefer existing env (set from Brain setting at startup), else settings
OLLAMA_MODELS_PATH = os.environ.get("OLLAMA_MODELS")
if not OLLAMA_MODELS_PATH:
    OLLAMA_MODELS_PATH = settings.ollama_models_path
if OLLAMA_MODELS_PATH:
    os.makedirs(OLLAMA_MODELS_PATH, exist_ok=True)
    if "OLLAMA_MODELS" not in os.environ:
        os.environ["OLLAMA_MODELS"] = OLLAMA_MODELS_PATH
    logger.info(f"Ollama models path configured: {OLLAMA_MODELS_PATH}")
else:
    default_path = str(Path(settings.models_root) / "ollama")
    if os.path.exists(default_path):
        OLLAMA_MODELS_PATH = default_path
        if "OLLAMA_MODELS" not in os.environ:
            os.environ["OLLAMA_MODELS"] = OLLAMA_MODELS_PATH
        logger.info(f"Using models_root Ollama path: {OLLAMA_MODELS_PATH}")
    else:
        legacy = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "local_brain")
        if os.path.exists(legacy):
            OLLAMA_MODELS_PATH = legacy
            if "OLLAMA_MODELS" not in os.environ:
                os.environ["OLLAMA_MODELS"] = OLLAMA_MODELS_PATH
            logger.info(f"Using legacy local_brain path: {OLLAMA_MODELS_PATH}")


def log_ollama_config():
    """Log Ollama configuration for debugging"""
    logger.info("="*70)
    logger.info("OLLAMA CONFIGURATION")
    logger.info(f"  Base URL: {OLLAMA_BASE_URL}")
    logger.info(f"  Trained Model: {TRAINED_MODEL}")
    logger.info(f"  Default Model: {DEFAULT_LOCAL_MODEL}")
    logger.info(f"  Fallback Model: {FALLBACK_MODEL}")
    logger.info(f"  Timeout: {TIMEOUT}s")
    logger.info(f"  Models Path: {OLLAMA_MODELS_PATH or 'Not set'}")
    logger.info("="*70)


# Log configuration on module load
log_ollama_config()


async def get_ollama_base_url() -> str:
    """Primary Ollama if up; otherwise start/local fallback (daena brain) and return its URL."""
    try:
        from backend.services.local_brain_manager import try_primary_then_fallback
        return await try_primary_then_fallback()
    except Exception as e:
        logger.debug(f"Fallback resolution failed, using primary: {e}")
        return OLLAMA_BASE_URL


async def check_ollama_available() -> bool:
    """Check if Ollama service is running (primary or local brain fallback)."""
    try:
        base = await get_ollama_base_url()
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base.rstrip('/')}/api/tags")
            return response.status_code == 200
    except Exception as e:
        logger.debug(f"Ollama not available: {e}")
        return False


# Cache for available models to avoid constant hitting /api/tags
_available_models_cache = None
_last_cache_time = 0

async def get_available_models() -> List[str]:
    """Get list of available Ollama models with simple caching (1 min)."""
    global _available_models_cache, _last_cache_time
    import time
    
    if _available_models_cache and (time.time() - _last_cache_time < 60):
        return _available_models_cache
        
    try:
        base = await get_ollama_base_url()
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{base.rstrip('/')}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name") for m in data.get("models", [])]
                _available_models_cache = models
                _last_cache_time = time.time()
                return models
    except Exception:
        pass
    
    return _available_models_cache or []

async def resolve_model(requested_model: Optional[str]) -> str:
    """Resolve the best available model, falling back if necessary."""
    available = await get_available_models()
    
    # 1. If no specific request, try Trained > Default > Fallback
    if not requested_model:
        if TRAINED_MODEL and TRAINED_MODEL in available:
            return TRAINED_MODEL
        if DEFAULT_LOCAL_MODEL and DEFAULT_LOCAL_MODEL in available:
            return DEFAULT_LOCAL_MODEL
        if FALLBACK_MODEL and FALLBACK_MODEL in available:
            return FALLBACK_MODEL
        if available:
            return available[0] # Takes whatever is there (e.g. qwen2.5:7b)
        return DEFAULT_LOCAL_MODEL # Hope for the best
        
    # 2. If requested model exists, use it
    if requested_model in available:
        return requested_model
        
    # 3. Check for tag mismatch (e.g. user asks "qwen2.5", we have "qwen2.5:latest")
    for m in available:
        if requested_model in m or m in requested_model:
            return m
            
    # 4. Fallback if requested not found
    logger.warning(f"Requested model {requested_model} not found. Available: {available}. Using fallback.")
    if available:
        return available[0]
        
    return requested_model # Try anyway, maybe the cache is stale

async def chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """Send chat messages to Ollama and return response (uses primary or local brain fallback)."""

    base = await get_ollama_base_url()
    
    # Resolve valid model
    mdl = await resolve_model(model)
    logger.debug(f"Chat using model: {mdl}")

    request_data = {
        "model": mdl,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if max_tokens:
        request_data["options"]["num_predict"] = max_tokens

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"{base.rstrip('/')}/api/chat", json=request_data)
            
            # Handle 500/404 explicitly
            if response.status_code != 200:
                error_txt = response.text
                logger.error(f"Ollama Error ({response.status_code}): {error_txt}")
                
                # If 500/404 and we haven't tried fallback yet
                if response.status_code in [500, 404, 400] and mdl != FALLBACK_MODEL:
                    logger.warning(f"Model {mdl} failed. retrying with {FALLBACK_MODEL}")
                    return await chat(messages, model=FALLBACK_MODEL, temperature=temperature, max_tokens=max_tokens)
                    
                response.raise_for_status()
                
            data = response.json()

        msg = data.get("message") if isinstance(data, dict) else None
        if isinstance(msg, dict) and "content" in msg:
            content = str(msg["content"])
            
            # Record usage for cost tracking (optimistic)
            try:
                from backend.services.cost_tracker import get_cost_tracker
                tracker = get_cost_tracker()
                prompt_text = "".join([m.get("content", "") for m in messages])
                tracker.record_usage(mdl, len(prompt_text)//4, len(content)//4)
            except:
                pass
                
            return content
        logger.error(f"Unexpected Ollama response format: {data}")
        return "Error: Unexpected response format from local LLM"

    except httpx.TimeoutException:
        logger.error(f"Ollama request timed out after {TIMEOUT}s")
        return "Error: Local LLM request timed out. Try a smaller model."
    except Exception as e:
        logger.error(f"Ollama error: {e}", exc_info=True)
        return f"Error: Failed to communicate with local LLM: {str(e)}"


async def generate_stream(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
):
    """Generate streaming text from a prompt using Ollama."""
    base = await get_ollama_base_url()

    # Resolve valid model
    mdl = await resolve_model(model)
    logger.debug(f"Stream generating using model: {mdl}")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Legacy check for System: prefix (keep for compatibility)
    if prompt.startswith("System:"):
        parts = prompt.split("\n\n", 1)
        if len(parts) == 2:
            system_content = parts[0].replace("System:", "").strip()
            user_content = parts[1].strip()
            messages.append({"role": "system", "content": system_content})
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": prompt})
    else:
        messages.append({"role": "user", "content": prompt})

    request_data = {
        "model": mdl,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature},
    }
    if max_tokens:
        request_data["options"]["num_predict"] = max_tokens

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream("POST", f"{base.rstrip('/')}/api/chat", json=request_data) as response:
                
                # Handle initial connection errors
                if response.status_code != 200:
                    logger.error(f"Ollama Stream Error: {response.status_code}")
                    if response.status_code in [404, 500] and mdl != FALLBACK_MODEL:
                         async for chunk in generate_stream(prompt, system_prompt, model=FALLBACK_MODEL, temperature=temperature, max_tokens=max_tokens):
                             yield chunk
                         return
                    else:
                        yield f"Error: Ollama returned {response.status_code}"
                        return

                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json
                            chunk_data = json.loads(line)
                            if isinstance(chunk_data, dict):
                                msg = chunk_data.get("message")
                                if isinstance(msg, dict) and "content" in msg:
                                    content = msg.get("content", "")
                                    if content:
                                        yield content
                                if chunk_data.get("done", False):
                                    break
                        except Exception:
                            continue

    except Exception as e:
        logger.error(f"Ollama streaming error: {e}", exc_info=True)
        yield f"Error: Failed to communicate with local LLM: {str(e)}"








