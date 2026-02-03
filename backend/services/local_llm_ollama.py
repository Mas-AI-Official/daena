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


async def chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """Send chat messages to Ollama and return response (uses primary or local brain fallback)."""

    base = await get_ollama_base_url()

    # Choose model
    mdl = model
    if not mdl:
        # User preference: Try DEFAULT_LOCAL_MODEL (Kimi/Cloud) first!
        # Even if not in local 'tags', cloud proxy might accept it.
        mdl = DEFAULT_LOCAL_MODEL
        
        # Note: We skip the preamble availability check to allow "blind" cloud calls.
        # If it fails with 404, the standard exception handler below will catch it 
        # and try FALLBACK_MODEL.

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
            response.raise_for_status()
            data = response.json()

        msg = data.get("message") if isinstance(data, dict) else None
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"])
        logger.error(f"Unexpected Ollama response format: {data}")
        return "Error: Unexpected response format from local LLM"

    except httpx.TimeoutException:
        logger.error(f"Ollama request timed out after {TIMEOUT}s")
        return "Error: Local LLM request timed out. Try a smaller model or increase timeout."
    except httpx.HTTPStatusError as e:
        if e.response is not None and e.response.status_code == 404:
            if mdl != FALLBACK_MODEL:
                logger.warning(f"Model {mdl} not found, trying fallback {FALLBACK_MODEL}")
                return await chat(messages, model=FALLBACK_MODEL, temperature=temperature, max_tokens=max_tokens)
            return f"Error: Model {mdl} not found. Please run: ollama pull {mdl}"
        logger.error(f"Ollama HTTP error: {e}")
        return f"Error: Local LLM request failed: {str(e)}"
    except Exception as e:
        logger.error(f"Ollama error: {e}", exc_info=True)
        return f"Error: Failed to communicate with local LLM: {str(e)}"


async def generate(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> str:
    """Generate text from a prompt (wrapper around chat)."""
    # Parse system prompt if present
    messages = []
    if prompt.startswith("System:"):
        # Split system prompt and user message
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

    return await chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)


async def generate_stream(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
):
    """Generate streaming text from a prompt using Ollama."""
    base = await get_ollama_base_url()

    # Choose model
    mdl = model
    if not mdl:
        # Trust DEFAULT_LOCAL_MODEL (Kimi/Cloud) blindly for speed
        mdl = DEFAULT_LOCAL_MODEL

    # Parse system prompt if present
    messages = []
    if prompt.startswith("System:"):
        # Split system prompt and user message
        parts = prompt.split("\n\n", 1)
        if len(parts) == 2:
            system_content = parts[0].replace("System:", "").strip()
            user_content = parts[1].strip()
            messages.append({"role": "system", "content": system_content})
            messages.append({"role": "user", "content": user_content})
        else:
            # Fallback if no double newline
            messages.append({"role": "user", "content": prompt})
    else:
        messages.append({"role": "user", "content": prompt})

    request_data = {
        "model": mdl,
        "messages": messages,
        "stream": True,  # Enable streaming
        "options": {"temperature": temperature},
    }
    if max_tokens:
        request_data["options"]["num_predict"] = max_tokens

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream("POST", f"{base.rstrip('/')}/api/chat", json=request_data) as response:
                response.raise_for_status()
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
                                # Check if done
                                if chunk_data.get("done", False):
                                    break
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.debug(f"Error parsing Ollama stream chunk: {e}")
                            continue

    except httpx.TimeoutException:
        logger.error(f"Ollama streaming request timed out after {TIMEOUT}s")
        yield "Error: Local LLM request timed out. Try a smaller model or increase timeout."
    except httpx.HTTPStatusError as e:
        if e.response is not None and e.response.status_code == 404:
            if mdl != FALLBACK_MODEL:
                logger.warning(f"Model {mdl} not found, trying fallback {FALLBACK_MODEL}")
                async for chunk in generate_stream(prompt, model=FALLBACK_MODEL, temperature=temperature, max_tokens=max_tokens):
                    yield chunk
                return
            yield f"Error: Model {mdl} not found. Please run: ollama pull {mdl}"
        else:
            logger.error(f"Ollama HTTP error: {e}")
            yield f"Error: Local LLM request failed: {str(e)}"
    except Exception as e:
        logger.error(f"Ollama streaming error: {e}", exc_info=True)
        yield f"Error: Failed to communicate with local LLM: {str(e)}"








