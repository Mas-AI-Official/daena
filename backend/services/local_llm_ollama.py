"""
Local LLM Service using Ollama
Provides local inference when cloud APIs are unavailable.
"""

import os
import httpx
import logging
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

# Ollama models path (defaults to local_brain directory)
OLLAMA_MODELS_PATH = settings.ollama_models_path
if OLLAMA_MODELS_PATH:
    # Ensure path exists
    os.makedirs(OLLAMA_MODELS_PATH, exist_ok=True)
    # Set OLLAMA_MODELS environment variable for Ollama CLI
    os.environ["OLLAMA_MODELS"] = OLLAMA_MODELS_PATH
    logger.info(f"Ollama models path configured: {OLLAMA_MODELS_PATH}")
else:
    # Default to local_brain if not set
    default_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "local_brain")
    if os.path.exists(default_path):
        OLLAMA_MODELS_PATH = default_path
        os.environ["OLLAMA_MODELS"] = OLLAMA_MODELS_PATH
        logger.info(f"Using default Ollama models path: {OLLAMA_MODELS_PATH}")


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


async def check_ollama_available() -> bool:
    """Check if Ollama service is running."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
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
    """Send chat messages to Ollama and return response."""

    # Choose model
    mdl = model
    if not mdl:
        mdl = DEFAULT_LOCAL_MODEL
        # Prefer trained model if it exists
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    available_models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                    # Match trained model (allow partial match for tag variations like :latest)
                    for available in available_models:
                        if available and (available == TRAINED_MODEL or available.startswith(f"{TRAINED_MODEL}:")):
                            mdl = available
                            logger.debug(f"✅ Using trained Daena brain: {mdl}")
                            break
        except Exception:
            pass

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
            response = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=request_data)
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
    # Choose model
    mdl = model
    if not mdl:
        mdl = DEFAULT_LOCAL_MODEL  # Default to 7B for speed
        # Check available models
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    available_models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                    # Match trained model (allow partial match for tag variations like :latest)
                    for available in available_models:
                        if available and (available == TRAINED_MODEL or available.startswith(f"{TRAINED_MODEL}:")):
                            # Check if it's the large 14B model - skip it for speed
                            if "14b" in available.lower() or available.startswith("daena-brain"):
                                logger.debug(f"Skipping large model {available} for streaming (GPU limited)")
                                continue
                            mdl = available
                            logger.debug(f"✅ Using model for streaming: {mdl}")
                            break
        except Exception:
            pass

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
            async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=request_data) as response:
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








