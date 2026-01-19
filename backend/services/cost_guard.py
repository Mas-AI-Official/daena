"""
Cost Guard - Safety and Cost Controls
Prevents unnecessary LLM calls and enforces cost limits.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CostGuardDecision(str, Enum):
    """Cost guard decisions"""
    ALLOW = "allow"
    BLOCK = "block"
    OVERRIDE = "override"


class CostGuard:
    """
    Guards against unnecessary LLM calls and enforces cost limits.
    """
    
    def __init__(
        self,
        cloud_disabled: bool = True,
        founder_override: bool = False
    ):
        self.cloud_disabled = cloud_disabled
        self.founder_override = founder_override
    
    def check(
        self,
        user_input: str,
        complexity_tier: str,
        provider: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if LLM call should be allowed.
        
        Returns:
            {
                decision: CostGuardDecision,
                reason: str,
                metadata: dict
            }
        """
        # Founder override
        if self.founder_override and context and context.get("role") == "founder":
            return {
                "decision": CostGuardDecision.OVERRIDE.value,
                "reason": "Founder override enabled",
                "metadata": {}
            }
        
        # Block cloud if disabled
        if self.cloud_disabled and provider.startswith("cloud/"):
            return {
                "decision": CostGuardDecision.BLOCK.value,
                "reason": f"Cloud LLM disabled, but provider '{provider}' requested",
                "metadata": {
                    "suggested_action": "Enable cloud with ENABLE_CLOUD_LLM=true or use local Ollama"
                }
            }
        
        # Block trivial tasks from using LLM (should be handled by deterministic gate)
        if complexity_tier == "no_llm":
            return {
                "decision": CostGuardDecision.BLOCK.value,
                "reason": "Task is trivial and should be handled by deterministic gate",
                "metadata": {
                    "suggested_action": "Use deterministic_gate.try_handle() first"
                }
            }
        
        # Allow all other cases
        return {
            "decision": CostGuardDecision.ALLOW.value,
            "reason": "No restrictions",
            "metadata": {}
        }
    
    def estimate_cost(
        self,
        prompt: str,
        provider: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estimate token cost for a request.
        
        Returns:
            {
                prompt_tokens_estimate: int,
                provider: str,
                model: str,
                cost_estimate_usd: float (if available)
            }
        """
        # Rough token estimation (1 token ≈ 4 characters)
        prompt_tokens = len(prompt) // 4
        
        # Cost estimates (per 1K tokens, approximate)
        cost_per_1k = {
            "local/ollama": 0.0,
            "cloud/openai": 0.03,  # gpt-4o-mini
            "cloud/gemini": 0.0005,
            "cloud/anthropic": 0.015,  # claude-3-haiku
        }
        
        cost_estimate = 0.0
        provider_key = provider.lower()
        for key, cost in cost_per_1k.items():
            if key in provider_key:
                cost_estimate = (prompt_tokens / 1000) * cost
                break
        
        return {
            "prompt_tokens_estimate": prompt_tokens,
            "provider": provider,
            "model": model or "default",
            "cost_estimate_usd": cost_estimate
        }


# Global instance
_cost_guard_instance: Optional[CostGuard] = None

def get_cost_guard() -> CostGuard:
    """Get singleton instance"""
    global _cost_guard_instance
    if _cost_guard_instance is None:
        from backend.config.settings import settings
        _cost_guard_instance = CostGuard(
            cloud_disabled=not getattr(settings, 'enable_cloud_llm', False),
            founder_override=getattr(settings, 'daena_founder_override', False)
        )
    return _cost_guard_instance




