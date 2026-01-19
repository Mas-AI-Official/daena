"""
Prompt Intelligence Brain
Central prompt optimizer for all agents and Daena.

Provides:
- Normalized Intent Spec (model-agnostic)
- Provider Wrapper (model-specific)
- Rule-based optimization (cheap mode)
- Optional LLM-based rewrite (expensive mode)
- Governance hooks (versioning, allow/deny lists)
"""

import logging
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Version for governance tracking
PROMPT_BRAIN_VERSION = "1.0.0"


class PromptMode(str, Enum):
    """Prompt optimization modes"""
    RULES = "rules"  # Cheap: rule-based only
    HYBRID = "hybrid"  # Rules + selective LLM rewrite
    LLM_REWRITE = "llm_rewrite"  # Expensive: LLM-based rewrite


@dataclass
class OptimizedPrompt:
    """Output of prompt intelligence optimization"""
    optimized_prompt: str
    output_contract: Dict[str, Any] = field(default_factory=lambda: {
        "format": "text",
        "tone": "professional",
        "verbosity": "normal",
        "constraints": []
    })
    safety_notes: List[str] = field(default_factory=list)
    model_hints: Dict[str, Any] = field(default_factory=lambda: {
        "provider": None,
        "model": None,
        "temperature": 0.7,
        "max_tokens": 1000
    })
    cache_key: str = ""
    original_prompt: str = ""
    transformations_applied: List[str] = field(default_factory=list)


class PromptIntelligence:
    """
    Central prompt optimizer used by all agents and Daena.
    """
    
    def __init__(
        self,
        enabled: bool = True,
        mode: PromptMode = PromptMode.RULES,
        complexity_threshold: int = 50,
        allow_llm_rewrite: bool = False
    ):
        self.enabled = enabled
        self.mode = mode
        self.complexity_threshold = complexity_threshold  # Skip optimization for short prompts
        self.allow_llm_rewrite = allow_llm_rewrite
        
        # Provider-specific templates (NOT separate brains, just formatting)
        self.provider_templates = {
            "gpt/azure-openai": self._wrap_openai,
            "openai": self._wrap_openai,
            "gemini": self._wrap_gemini,
            "anthropic/claude": self._wrap_anthropic,
            "claude": self._wrap_anthropic,
            "grok": self._wrap_grok,
            "mistral": self._wrap_mistral,
            "deepseek": self._wrap_deepseek,
            "local/ollama": self._wrap_ollama,
            "ollama": self._wrap_ollama,
        }
    
    def optimize(
        self,
        raw_prompt: str,
        context: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        role: Optional[str] = None,
        department: Optional[str] = None
    ) -> OptimizedPrompt:
        """
        Optimize a prompt using the configured mode.
        
        Returns:
            OptimizedPrompt with optimized_prompt, output_contract, model_hints, etc.
        """
        if not self.enabled:
            return OptimizedPrompt(
                optimized_prompt=raw_prompt,
                original_prompt=raw_prompt,
                cache_key=self._generate_cache_key(raw_prompt)
            )
        
        # Skip optimization for very simple queries (cheap mode)
        if len(raw_prompt.strip()) < self.complexity_threshold:
            logger.debug(f"Skipping optimization for short prompt: {raw_prompt[:30]}...")
            return OptimizedPrompt(
                optimized_prompt=raw_prompt,
                original_prompt=raw_prompt,
                cache_key=self._generate_cache_key(raw_prompt)
            )
        
        # Step 1: Normalize intent (model-agnostic)
        normalized = self._normalize_intent(raw_prompt, context, role, department)
        
        # Step 2: Apply rule-based optimizations
        optimized = self._apply_rules(normalized, context, role, department)
        
        # Step 3: Apply provider-specific wrapper (if provider known)
        if provider and provider in self.provider_templates:
            optimized = self.provider_templates[provider](optimized, context, role)
        
        # Step 4: Optional LLM-based rewrite (expensive, only if enabled)
        if self.mode == PromptMode.LLM_REWRITE and self.allow_llm_rewrite:
            optimized = self._llm_rewrite(optimized, context)
        elif self.mode == PromptMode.HYBRID:
            # Hybrid: only rewrite complex prompts
            if self._is_complex(optimized):
                optimized = self._llm_rewrite(optimized, context)
        
        # Build output contract
        output_contract = self._build_output_contract(raw_prompt, context, role, department)
        
        # Build model hints
        model_hints = self._build_model_hints(provider, context)
        
        # Generate cache key
        cache_key = self._generate_cache_key(optimized)
        
        return OptimizedPrompt(
            optimized_prompt=optimized,
            original_prompt=raw_prompt,
            output_contract=output_contract,
            model_hints=model_hints,
            cache_key=cache_key,
            transformations_applied=self._get_transformations()
        )
    
    def _normalize_intent(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]],
        role: Optional[str],
        department: Optional[str]
    ) -> str:
        """Normalize user intent into structured format (model-agnostic)"""
        # Extract key components
        intent_parts = []
        
        # Add role context if available
        if role:
            intent_parts.append(f"[Role: {role}]")
        
        # Add department context if available
        if department:
            intent_parts.append(f"[Department: {department}]")
        
        # Add system context if available
        if context:
            if context.get("task_type"):
                intent_parts.append(f"[Task: {context['task_type']}]")
            if context.get("urgency"):
                intent_parts.append(f"[Urgency: {context['urgency']}]")
        
        # Combine with original prompt
        if intent_parts:
            normalized = " ".join(intent_parts) + "\n\n" + prompt
        else:
            normalized = prompt
        
        return normalized
    
    def _apply_rules(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]],
        role: Optional[str],
        department: Optional[str]
    ) -> str:
        """Apply rule-based optimizations (cheap, deterministic)"""
        optimized = prompt
        
        # Rule 1: Ensure clear instruction structure
        if not any(keyword in optimized.lower() for keyword in ["please", "can you", "help", "analyze", "explain", "create", "generate"]):
            # Add implicit instruction if missing
            if len(optimized.split()) < 10:
                optimized = f"Please: {optimized}"
        
        # Rule 2: Add constraints for safety
        safety_constraints = []
        if "delete" in optimized.lower() or "remove" in optimized.lower():
            safety_constraints.append("Ensure no data loss.")
        if "password" in optimized.lower() or "secret" in optimized.lower():
            safety_constraints.append("Do not expose sensitive information.")
        
        if safety_constraints:
            optimized = optimized + "\n\nConstraints: " + " ".join(safety_constraints)
        
        # Rule 3: Add output format hints if missing
        if "format" not in optimized.lower() and "json" not in optimized.lower():
            # For structured tasks, suggest format
            if any(keyword in optimized.lower() for keyword in ["list", "table", "summary", "report"]):
                optimized = optimized + "\n\nOutput format: Clear, structured response."
        
        # Rule 4: Minimize verbosity for simple queries
        if len(optimized.split()) < 20:
            optimized = optimized + "\n\nBe concise."
        
        return optimized
    
    def _wrap_openai(self, prompt: str, context: Optional[Dict[str, Any]], role: Optional[str]) -> str:
        """Wrap prompt for OpenAI/Azure OpenAI"""
        system_prompt = "You are a helpful AI assistant."
        if role:
            system_prompt = f"You are {role}."
        
        return f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:"
    
    def _wrap_gemini(self, prompt: str, context: Optional[Dict[str, Any]], role: Optional[str]) -> str:
        """Wrap prompt for Google Gemini"""
        # Gemini prefers direct prompts
        if role:
            return f"As {role}, {prompt}"
        return prompt
    
    def _wrap_anthropic(self, prompt: str, context: Optional[Dict[str, Any]], role: Optional[str]) -> str:
        """Wrap prompt for Anthropic Claude"""
        # Claude prefers structured prompts
        if role:
            return f"<role>{role}</role>\n\n<task>{prompt}</task>"
        return f"<task>{prompt}</task>"
    
    def _wrap_grok(self, prompt: str, context: Optional[Dict[str, Any]], role: Optional[str]) -> str:
        """Wrap prompt for Grok"""
        return prompt  # Grok prefers direct prompts
    
    def _wrap_mistral(self, prompt: str, context: Optional[Dict[str, Any]], role: Optional[str]) -> str:
        """Wrap prompt for Mistral"""
        return prompt  # Mistral prefers direct prompts
    
    def _wrap_deepseek(self, prompt: str, context: Optional[Dict[str, Any]], role: Optional[str]) -> str:
        """Wrap prompt for DeepSeek"""
        return prompt  # DeepSeek prefers direct prompts
    
    def _wrap_ollama(self, prompt: str, context: Optional[Dict[str, Any]], role: Optional[str]) -> str:
        """Wrap prompt for local Ollama"""
        # Ollama works well with direct prompts, but can benefit from system context
        if role:
            return f"System: You are {role}.\n\nUser: {prompt}\n\nAssistant:"
        return prompt
    
    def _llm_rewrite(self, prompt: str, context: Optional[Dict[str, Any]]) -> str:
        """
        Optional LLM-based rewrite (expensive).
        Only called if mode is LLM_REWRITE or HYBRID with complex prompts.
        """
        # For now, return as-is (can be enhanced later with actual LLM call)
        # This is a placeholder for future enhancement
        logger.debug("LLM rewrite requested but not implemented yet (placeholder)")
        return prompt
    
    def _is_complex(self, prompt: str) -> bool:
        """Determine if prompt is complex enough for LLM rewrite"""
        # Simple heuristic: length + keyword complexity
        word_count = len(prompt.split())
        complex_keywords = ["analyze", "synthesize", "compare", "evaluate", "design", "architect"]
        has_complex_keywords = any(kw in prompt.lower() for kw in complex_keywords)
        return word_count > 100 or has_complex_keywords
    
    def _build_output_contract(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]],
        role: Optional[str],
        department: Optional[str]
    ) -> Dict[str, Any]:
        """Build output contract (format, tone, verbosity, constraints)"""
        contract = {
            "format": "text",
            "tone": "professional",
            "verbosity": "normal",
            "constraints": []
        }
        
        # Detect format requirements
        if "json" in prompt.lower():
            contract["format"] = "json"
        elif "list" in prompt.lower() or "table" in prompt.lower():
            contract["format"] = "structured"
        
        # Detect tone
        if "casual" in prompt.lower() or "friendly" in prompt.lower():
            contract["tone"] = "casual"
        elif "formal" in prompt.lower() or "professional" in prompt.lower():
            contract["tone"] = "formal"
        
        # Detect verbosity
        if "brief" in prompt.lower() or "short" in prompt.lower() or "concise" in prompt.lower():
            contract["verbosity"] = "brief"
        elif "detailed" in prompt.lower() or "comprehensive" in prompt.lower():
            contract["verbosity"] = "detailed"
        
        return contract
    
    def _build_model_hints(
        self,
        provider: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build model hints (provider, model, temperature, max_tokens)"""
        hints = {
            "provider": provider,
            "model": None,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        if context:
            if "temperature" in context:
                hints["temperature"] = context["temperature"]
            if "max_tokens" in context:
                hints["max_tokens"] = context["max_tokens"]
            if "model" in context:
                hints["model"] = context["model"]
        
        return hints
    
    def _generate_cache_key(self, prompt: str) -> str:
        """Generate cache key for prompt (for deduplication)"""
        return hashlib.md5(prompt.encode()).hexdigest()[:16]
    
    def _get_transformations(self) -> List[str]:
        """Get list of transformations applied (for audit)"""
        return ["normalize_intent", "apply_rules", "provider_wrapper"]


# Global instance (singleton)
_prompt_intelligence: Optional[PromptIntelligence] = None


def get_prompt_intelligence() -> PromptIntelligence:
    """Get global Prompt Intelligence instance"""
    global _prompt_intelligence
    if _prompt_intelligence is None:
        from backend.config.settings import settings
        
        enabled = getattr(settings, "prompt_brain_enabled", True)
        mode_str = getattr(settings, "prompt_brain_mode", "rules")
        mode = PromptMode(mode_str) if mode_str in [m.value for m in PromptMode] else PromptMode.RULES
        complexity_threshold = getattr(settings, "prompt_brain_complexity_threshold", 50)
        allow_llm_rewrite = getattr(settings, "prompt_brain_allow_llm_rewrite", False)
        
        _prompt_intelligence = PromptIntelligence(
            enabled=enabled,
            mode=mode,
            complexity_threshold=complexity_threshold,
            allow_llm_rewrite=allow_llm_rewrite
        )
    
    return _prompt_intelligence




