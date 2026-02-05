
"""
Model Gateway Service (Unified LLM Interface)
Handles routing, provider adaptation, cost tracking, and governance checks.
"""
import logging
import time
import json
import os
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from backend.database import SessionLocal, BrainModel, UsageLedger, FounderPolicy
from backend.services.model_registry import ModelRegistry # Legacy, migrate to DB
from backend.services.vault_service import get_vault_service

logger = logging.getLogger(__name__)

class ModelGateway:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ModelGateway()
        return cls._instance

    def __init__(self):
        self.vault = get_vault_service()
        
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        context_id: str = None,
        caller_agent_id: str = None
    ) -> Any:
        # 1. Fetch Model Coords
        db = SessionLocal()
        try:
            model = db.query(BrainModel).filter(BrainModel.model_id == model_id).first()
            if not model:
                # Fallback to legacy Ollama registry check for local-only
                # For now, raise specific error
                 raise ValueError(f"Model {model_id} not registered in BrainModels")
            
            if not model.enabled:
                raise ValueError(f"Model {model_id} is disabled")

            # 2. Budget Check (Pre-flight)
            if not self._check_budget(db, model):
                raise PermissionError(f"Budget exceeded for model {model_id}")

            # 3. Provider Dispatch
            start_time = time.time()
            response = None
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
            
            error = None
            try:
                if model.provider == "ollama":
                    response = await self._run_ollama(model, messages, temperature, max_tokens, stream)
                elif model.provider == "azure_openai":
                    response = await self._run_azure_openai(model, messages, temperature, max_tokens, stream)
                elif model.provider == "azure_ai_inference":
                    # Kimi-K2-Thinking style
                    response = await self._run_azure_inference(model, messages, temperature, max_tokens, stream)
                else:
                    raise ValueError(f"Unknown provider {model.provider}")
                    
            except Exception as e:
                error = str(e)
                raise
            finally:
                # 4. Usage Logging (Post-flight)
                if not stream and response and not error:
                    # Extract usage
                    # Note: Streaming usage often needs separate handling or approximation
                    # We'll assume non-stream for precise charging first
                    if hasattr(response, 'usage'): 
                         # Object style
                         u = response.usage
                         usage['prompt_tokens'] = u.prompt_tokens
                         usage['completion_tokens'] = u.completion_tokens
                    elif isinstance(response, dict) and 'usage' in response:
                         # Dict style (Ollama)
                         u = response.get('usage', {})
                         usage['prompt_tokens'] = u.get('prompt_tokens', 0)
                         usage['completion_tokens'] = u.get('completion_tokens', 0)
                         
                    # Calculate cost
                    input_cost = (usage['prompt_tokens'] / 1000) * (model.cost_per_1k_input or 0)
                    output_cost = (usage['completion_tokens'] / 1000) * (model.cost_per_1k_output or 0)
                    total_cost = input_cost + output_cost
                    
                    self._log_usage(db, model, usage, total_cost, context_id, caller_agent_id)
            
            return response
            
        finally:
            db.close()

    def _check_budget(self, db, model: BrainModel) -> bool:
        """Check daily/monthly budget caps."""
        # TODO: Aggregate UsageLedger for today/this month
        # For MVP, return True
        return True

    def _log_usage(self, db, model, usage, cost, context_id, caller_id):
        try:
            entry = UsageLedger(
                model_id=model.model_id,
                provider=model.provider,
                tokens_in=usage['prompt_tokens'],
                tokens_out=usage['completion_tokens'],
                estimated_cost_usd=cost,
                context_type="chat", # naive
                context_id=context_id,
                caller_agent_id=caller_id,
                timestamp=datetime.utcnow()
            )
            db.add(entry)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log usage: {e}")

    async def _run_ollama(self, model: BrainModel, messages, temperature, max_tokens, stream):
        import httpx
        # Assuming legacy model_name mapping or direct name
        ollama_name = model.model_name or model.name 
        url = f"{model.endpoint_base or 'http://127.0.0.1:11434'}/api/chat"
        
        payload = {
            "model": ollama_name,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Handling stream is complex for universal adapter, 
            # for now assume non-stream for standardized return
            if stream:
                # Return iterator/generator logic layer
                # For this snippet, we force non-stream to simplify usage calculation
                # Full implementation needs async generator wrapper
                payload["stream"] = False
                
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            # Normalize to OpenAI-like dict
            return {
                "choices": [{"message": data.get("message")}],
                "usage": {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0)
                }
            }

    async def _run_azure_openai(self, model: BrainModel, messages, temperature, max_tokens, stream):
        # https://<resource>.cognitiveservices.azure.com/openai/deployments/<deployment>/chat/completions?api-version=...
        import httpx
        
        # Get key from secret store
        # Key name convention: "azure_openai_<resource_name>" or just stored in API Key column which is encrypted?
        # BrainModel doesn't have api_key field in my new schema (good, keeps it out of DB row by default if not protected)
        # But we need to fetch it. For MVP, assume environment or Vault lookup by model_id
        
        # Note: In real implementation, pass api_key in context or fetch from Vault using model_id
        api_key = os.environ.get("AZURE_OPENAI_API_KEY") 
        if not api_key:
             # Try vault
             pass

        base = model.endpoint_base.rstrip('/')
        # construct URL if not full
        if "chat/completions" not in base:
             url = f"{base}/openai/deployments/{model.deployment_name}/chat/completions"
        else:
             url = base
             
        params = {"api-version": model.api_version}
        headers = {"api-key": api_key, "Content-Type": "application/json"}
        
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params=params, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def _run_azure_inference(self, model: BrainModel, messages, temperature, max_tokens, stream):
        # https://<resource>.services.ai.azure.com/models/chat/completions?api-version=...
        # Model is passed in BODY, sometimes? Or just straight endpoint?
        # "model-router" implies the model name might be routed.
        # Catalog models usually: POST /models/chat/completions
        
        import httpx
        api_key = os.environ.get("AZURE_INFERENCE_API_KEY") # Placeholder
        
        url = f"{model.endpoint_base.rstrip('/')}/models/chat/completions"
        params = {"api-version": model.api_version}
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # Some Azure AI Inference uses "api-key" header, others Bearer.
        # Foundry usually "api-key" or "Authorization: Bearer <token>"
        
        # User said: "Get endpointfor masou-ml9l9ooq-swedencentral ... services.ai.azure.com" => likely Key-based
        if "services.ai.azure.com" in url:
             headers = {"api-key": api_key, "Content-Type": "application/json"}

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "model": model.model_name # Kimi-K2-Thinking
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params=params, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

model_gateway = ModelGateway.get_instance()
