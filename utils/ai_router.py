"""
AI Router - Connects departments and agents to the brain
Routes chat requests to the appropriate LLM service
Uses local_brain directory for trained models
"""
import logging
import os
import httpx
from typing import Dict, Optional, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to local brain models
LOCAL_BRAIN_PATH = Path(__file__).parent.parent / "local_brain"

class AIRouter:
    """Routes AI requests to the brain/LLM service"""
    
    def __init__(self):
        self.llm_service = None
        self.ollama_url = "http://localhost:11434"
        self.available_models: List[str] = []
        self.default_model = "qwen2.5:7b-instruct"
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize connection to LLM service"""
        try:
            # Check for local brain models
            if LOCAL_BRAIN_PATH.exists():
                manifests_path = LOCAL_BRAIN_PATH / "manifests"
                if manifests_path.exists():
                    logger.info(f"✅ Found local_brain at {LOCAL_BRAIN_PATH}")
                    # List available manifests
                    for registry_dir in manifests_path.iterdir():
                        if registry_dir.is_dir():
                            for model_dir in registry_dir.iterdir():
                                if model_dir.is_dir():
                                    logger.info(f"  📦 Found model: {registry_dir.name}/{model_dir.name}")
            
            # Try LLM service
            try:
                from backend.services.llm_service import llm_service
                self.llm_service = llm_service
                logger.info("✅ AI Router connected to LLM service")
            except ImportError as e:
                logger.warning(f"⚠️ LLM service not available: {e}")
                
        except Exception as e:
            logger.warning(f"⚠️ AI Router init warning: {e}")
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from Ollama"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])
        except Exception as e:
            logger.warning(f"Could not get Ollama models: {e}")
        return []
    
    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None, 
                   system_prompt: Optional[str] = None, model: Optional[str] = None) -> str:
        """
        Send a chat message to the brain and get a response
        """
        model = model or self.default_model
        
        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": message})
            
            # Try Ollama directly first
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("message", {}).get("content", "I processed your request.")
            
            # Fallback to LLM service
            if self.llm_service:
                response = await self.llm_service.generate(
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500
                )
                return response
            
            return f"Brain is offline. Please start Ollama with: ollama serve"
            
        except Exception as e:
            logger.error(f"❌ AI Router error: {e}")
            return f"Brain connection error: {str(e)[:100]}. Please ensure Ollama is running."
    
    async def generate(self, messages: list, temperature: float = 0.7, 
                       max_tokens: int = 500, model: Optional[str] = None) -> str:
        """Generate response using Ollama"""
        model = model or self.default_model
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens
                        }
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("message", {}).get("content", "")
                    
        except Exception as e:
            logger.error(f"AI Router generate error: {e}")
            
        return "Brain offline - please start Ollama"
    
    async def check_status(self) -> Dict[str, Any]:
        """Check the status of the AI brain connection"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                ollama_ok = response.status_code == 200
                models = []
                if ollama_ok:
                    models = response.json().get("models", [])
                
                return {
                    "status": "online" if ollama_ok else "offline",
                    "ollama_available": ollama_ok,
                    "models": [m.get("name") for m in models],
                    "llm_service_connected": self.llm_service is not None,
                    "local_brain_path": str(LOCAL_BRAIN_PATH),
                    "local_brain_exists": LOCAL_BRAIN_PATH.exists()
                }
        except Exception as e:
            logger.error(f"Status check error: {e}")
            return {
                "status": "offline",
                "error": str(e),
                "ollama_available": False
            }

# Global singleton
ai_router = AIRouter()
