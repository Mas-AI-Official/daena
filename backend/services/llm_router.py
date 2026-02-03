"""
LLM Router Service 
===================
Handles multi-model routing, cost optimization, and consensus strategies.
Part of DAENA_FULL_POWER.md implementation.
"""

import os
import time
import logging
import asyncio
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class RoutingStrategy(Enum):
    LOCAL_FIRST = "local_first"    # Use Ollama, fallback to Cloud if offline/slow
    CLOUD_ONLY = "cloud_only"      # Always use high-performance cloud
    CONSENSUS = "consensus"        # Call 3 models (Ollama, Claude, GPT) and compare
    AUTO = "auto"                  # Smart routing based on task complexity

class LLMRouter:
    def __init__(self):
        self.local_model = os.getenv("DEFAULT_LOCAL_MODEL", "deepseek-r1:8b")
        self.cloud_reasoning = os.getenv("CLOUD_REASONING_MODEL", "claude-3-5-sonnet-latest")
        self.cloud_fast = os.getenv("CLOUD_FAST_MODEL", "gpt-4o-mini")
        
        self.enable_cloud = os.getenv("ENABLE_CLOUD_LLM", "false").lower() in ("true", "1", "on")
        # Ensure cloud is enabled if settings say so
        try:
            from backend.config.settings import settings
            if settings.enable_cloud_llm:
                self.enable_cloud = True
        except:
            pass
            
        self.strategy = RoutingStrategy(os.getenv("ROUTING_STRATEGY", "local_first"))
        
        # Stats & Performance tracking
        self.perf_metrics = {
            "local_calls": 0,
            "cloud_calls": 0,
            "fallbacks": 0,
            "avg_latency": 0.0
        }
        
    def _is_cloud_model(self, model_name: str) -> bool:
        """Check if model name implies cloud usage."""
        if not model_name: return False
        m = model_name.lower()
        return ":cloud" in m or "claude" in m or "gpt-" in m or "gemini" in m

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                       complexity: str = "medium", model: Optional[str] = None) -> Dict[str, Any]:
        """Route generation request to the best model based on strategy."""
        start_time = time.time()
        
        target_model = model or self.local_model
        
        if self.strategy == RoutingStrategy.CONSENSUS and not model:
            return await self._run_consensus(prompt, system_prompt)
            
        # Standard Local-First routing
        try:
            from backend.services.local_llm_ollama import generate_stream, check_ollama_available
            ollama_ok = await check_ollama_available()
            
            # If a cloud model is explicitly requested, or complexity is critical
            if (self._is_cloud_model(target_model) or complexity == "critical") and self.enable_cloud:
                 return await self._call_cloud(prompt, system_prompt, complexity, model=target_model)

            if ollama_ok:
                logger.info(f"Routing to Local LLM ({target_model})")
                full_text = ""
                async for token in generate_stream(prompt, system_prompt=system_prompt, model=target_model):
                    full_text += token
                
                self.perf_metrics["local_calls"] += 1
                return {
                    "text": full_text,
                    "model": target_model,
                    "provider": "ollama",
                    "latency": time.time() - start_time
                }
            
            # Fallback to cloud if local offline
            if self.enable_cloud:
                return await self._call_cloud(prompt, system_prompt, complexity)
            else:
                raise Exception("Local LLM offline and Cloud LLM disabled")
                
        except Exception as e:
            logger.error(f"Router error: {e}")
            self.perf_metrics["fallbacks"] += 1
            if self.enable_cloud:
                return await self._call_cloud(prompt, system_prompt, complexity)
            raise

    async def _call_cloud(self, prompt: str, system_prompt: Optional[str], complexity: str, model: str = None) -> Dict[str, Any]:
        """Integrated Cloud LLM call (stub)"""
        logger.info(f"Routing to Cloud LLM (complexity={complexity})")
        self.perf_metrics["cloud_calls"] += 1
        
        target_model = model or (self.cloud_reasoning if complexity in ("high", "critical") else self.cloud_fast)
        
        return {
            "text": f"[CLOULD SIMULATED RESPONSE via {target_model}]\nBased on your request: {prompt[:50]}...",
            "model": target_model,
            "provider": "cloud",
            "latency": 0.5
        }

    async def _run_consensus(self, prompt: str, system_prompt: Optional[str]) -> Dict[str, Any]:
        """Run multiple models and pick the best answer via consensus voting."""
        return await self.council_mode(prompt, system_prompt)

    async def council_mode(self, prompt: str, system_prompt: Optional[str] = None, models: List[str] = None) -> Dict[str, Any]:
        """
        The Council: Parallel consultation + synthesis pass.
        Prioritizes free/local models.
        """
        if not models:
            # Detect available models or use defaults
            models = ["daena-brain:latest", "qwen2.5-coder:7b", "llama3"]
            # Filter for what's actually in Ollama or just use what we have
            models = models[:3] # Use up to 3 for speed

        logger.info(f"Council Mode activated with {len(models)} advisors")
        
        tasks = [self.generate(prompt, system_prompt, model=m) for m in models]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.warning(f"Council advisor {models[i]} failed: {res}")
            else:
                valid_results.append(res)
        
        if not valid_results:
            raise Exception("Council dissolved: All advisors failed")
            
        # Synthesizer Pass
        synthesis_prompt = f"MERGE AND SYNTHESIZE these advisor responses into one FINAL authoritative answer.\n"
        for i, r in enumerate(valid_results):
            synthesis_prompt += f"\n--- Advisor {i+1} ({r['model']}) ---\n{r['text']}\n"
        
        # Synthesis should use a strong model
        final = await self.generate(synthesis_prompt, complexity="high")
        
        return {
            "text": final["text"],
            "model": "council_consensus",
            "advisors": valid_results,
            "provider": "multi"
        }

# Singleton
_router = None

def get_llm_router():
    global _router
    if not _router:
        _router = LLMRouter()
    return _router
