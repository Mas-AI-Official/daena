"""
Router Agent - Model-Aware Task Dispatcher
Selects optimal LLM/GLM per task, adapts prompts, and merges outputs safely.

LAW 6 — ROUTER AWARENESS:
Every agent must adapt prompts to the target model's expected structure and limitations
(tool use, context, formatting).
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel
import logging
import asyncio
import httpx

logger = logging.getLogger(__name__)


class ModelCapability(str, Enum):
    """Model capability categories"""
    REASONING = "reasoning"
    CODE = "code"
    CREATIVE = "creative"
    FACTUAL = "factual"
    CONVERSATIONAL = "conversational"
    STRUCTURED = "structured"


class ModelProfile(BaseModel):
    """Profile for a specific model"""
    name: str
    provider: str  # ollama, openai, anthropic, etc.
    endpoint: str
    capabilities: List[ModelCapability]
    context_limit: int
    prefers_structured: bool  # Prefers numbered constraints
    has_tool_use: bool
    hallucination_tendency: str  # low, medium, high
    speed: str  # fast, medium, slow
    cost_per_1k: float = 0.0


class TaskType(str, Enum):
    """Task categories for routing"""
    DEEP_REASONING = "deep_reasoning"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    FACTUAL_QUERY = "factual_query"
    CREATIVE_WRITING = "creative_writing"
    CONVERSATION = "conversation"
    STRUCTURED_OUTPUT = "structured_output"
    CONFLICT_RESOLUTION = "conflict_resolution"


class RouterAgent:
    """
    Router Agent - Intelligent model dispatcher
    
    Routes tasks to optimal models based on:
    - Task type and requirements
    - Model capabilities and constraints
    - Time/cost requirements
    - Risk level
    """
    
    def __init__(self):
        """Initialize router with model profiles"""
        self.models = self._initialize_models()
        logger.info(f"✅ Router Agent initialized with {len(self.models)} models")
    
    def _initialize_models(self) -> Dict[str, ModelProfile]:
        """Load available model profiles"""
        return {
            # Ollama local models
            "qwen2.5-coder:32b": ModelProfile(
                name="qwen2.5-coder:32b",
                provider="ollama",
                endpoint="http://127.0.0.1:11434",
                capabilities=[ModelCapability.CODE, ModelCapability.REASONING],
                context_limit=32768,
                prefers_structured=True,
                has_tool_use=False,
                hallucination_tendency="low",
                speed="medium",
                cost_per_1k=0.0
            ),
            "deepseek-r1:8b": ModelProfile(
                name="deepseek-r1:8b",
                provider="ollama",
                endpoint="http://127.0.0.1:11434",
                capabilities=[ModelCapability.REASONING, ModelCapability.CODE],
                context_limit=32768,
                prefers_structured=True,
                has_tool_use=False,
                hallucination_tendency="low",
                speed="fast",
                cost_per_1k=0.0
            ),
            "llama3.2:3b": ModelProfile(
                name="llama3.2:3b",
                provider="ollama",
                endpoint="http://127.0.0.1:11434",
                capabilities=[ModelCapability.CONVERSATIONAL, ModelCapability.CREATIVE],
                context_limit=8192,
                prefers_structured=False,
                has_tool_use=False,
                hallucination_tendency="medium",
                speed="fast",
                cost_per_1k=0.0
            ),
        }
    
    async def get_available_models(self) -> List[str]:
        """Fetch currently available models from Ollama"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get("http://127.0.0.1:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [m.get("name") for m in data.get("models", [])]
                return []
        except Exception as e:
            logger.warning(f"Could not fetch available models: {e}")
            return []
    
    def select_model(
        self,
        task_type: TaskType,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelProfile]:
        """
        Select optimal model for task
        
        Args:
            task_type: Type of task to perform
            constraints: Additional constraints (time, cost, accuracy)
        
        Returns:
            Selected ModelProfile or None
        """
        constraints = constraints or {}
        risk_level = constraints.get("risk_level", "medium")  # low, medium, high
        max_time = constraints.get("max_time_seconds", 30)
        require_accuracy = constraints.get("require_accuracy", False)
        
        # Task routing rules
        routing_rules = {
            TaskType.DEEP_REASONING: [
                ModelCapability.REASONING,
            ],
            TaskType.CODE_GENERATION: [
                ModelCapability.CODE,
            ],
            TaskType.CODE_REVIEW: [
                ModelCapability.CODE,
                ModelCapability.REASONING,
            ],
            TaskType.FACTUAL_QUERY: [
                ModelCapability.FACTUAL,
            ],
            TaskType.CREATIVE_WRITING: [
                ModelCapability.CREATIVE,
            ],
            TaskType.CONVERSATION: [
                ModelCapability.CONVERSATIONAL,
            ],
            TaskType.STRUCTURED_OUTPUT: [
                ModelCapability.STRUCTURED,
            ],
            TaskType.CONFLICT_RESOLUTION: [
                ModelCapability.REASONING,
            ],
        }
        
        required_caps = routing_rules.get(task_type, [])
        
        # Filter models by capabilities
        candidates = []
        for model in self.models.values():
            if any(cap in model.capabilities for cap in required_caps):
                candidates.append(model)
        
        if not candidates:
            logger.warning(f"No models found for task type: {task_type}")
            return None
        
        # Score candidates
        scored = []
        for model in candidates:
            score = 0
            
            # Capability match
            matching_caps = sum(1 for cap in required_caps if cap in model.capabilities)
            score += matching_caps * 10
            
            # Risk level preference
            if risk_level == "high" and model.hallucination_tendency == "low":
                score += 20
            elif risk_level == "medium" and model.hallucination_tendency in ["low", "medium"]:
                score += 10
            
            # Speed preference
            if model.speed == "fast":
                score += 5
            
            # Accuracy preference
            if require_accuracy and model.hallucination_tendency == "low":
                score += 15
            
            scored.append((score, model))
        
        # Sort by score (descending)
        scored.sort(key=lambda x: x[0], reverse=True)
        
        selected = scored[0][1]
        logger.info(f"✅ Selected model: {selected.name} for {task_type} (score: {scored[0][0]})")
        
        return selected
    
    def adapt_prompt(
        self,
        prompt: str,
        model: ModelProfile,
        add_evidence_request: bool = False
    ) -> str:
        """
        Adapt prompt to model's preferred format
        
        Args:
            prompt: Original prompt
            model: Target model profile
            add_evidence_request: Add "evidence first" for hallucination-prone models
        
        Returns:
            Adapted prompt
        """
        adapted = prompt
        
        # For structured-preferring models, add explicit formatting
        if model.prefers_structured:
            if not any(marker in prompt for marker in ["1.", "- ", "* "]):
                adapted = f"Please provide a structured response to the following:\n\n{prompt}"
        
        # For hallucination-prone models, request evidence
        if add_evidence_request or model.hallucination_tendency in ["medium", "high"]:
            if "evidence" not in prompt.lower():
                adapted += "\n\nPlease provide evidence and cite sources for factual claims."
        
        # For models without tool use, be explicit about output format
        if not model.has_tool_use and "json" in prompt.lower():
            adapted += "\n\nProvide the JSON response in a code block."
        
        logger.debug(f"Adapted prompt for {model.name}")
        return adapted
    
    async def route_and_execute(
        self,
        task_type: TaskType,
        prompt: str,
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route task to best model and execute
        
        Args:
            task_type: Type of task
            prompt: Task prompt
            constraints: Additional constraints
        
        Returns:
            Result dict with response, model used, metadata
        """
        # Select model
        model = self.select_model(task_type, constraints)
        if not model:
            return {
                "success": False,
                "error": f"No suitable model found for {task_type}",
                "model": None
            }
        
        # Adapt prompt
        adapted_prompt = self.adapt_prompt(
            prompt,
            model,
            add_evidence_request=constraints.get("require_accuracy", False) if constraints else False
        )
        
        # Execute (depending on provider)
        try:
            if model.provider == "ollama":
                result = await self._execute_ollama(model, adapted_prompt)
            else:
                result = {"success": False, "error": f"Provider {model.provider} not implemented"}
            
            return {
                **result,
                "model_used": model.name,
                "task_type": task_type.value,
                "prompt_adapted": adapted_prompt != prompt
            }
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "model_used": model.name
            }
    
    async def _execute_ollama(self, model: ModelProfile, prompt: str) -> Dict[str, Any]:
        """Execute on Ollama"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{model.endpoint}/api/generate",
                    json={
                        "model": model.name,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "response": data.get("response", ""),
                        "context": data.get("context", [])
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def merge_multi_model_outputs(
        self,
        outputs: List[Tuple[ModelProfile, str]]
    ) -> str:
        """
        Merge outputs from multiple models
        Reconcile contradictions and choose best evidence
        
        Args:
            outputs: List of (model, response) tuples
        
        Returns:
            Merged response
        """
        if len(outputs) == 1:
            return outputs[0][1]
        
        # Simple merging strategy for now
        # In production, this would use a separate consensus model
        merged = "# Multi-Model Consensus\n\n"
        
        for i, (model, response) in enumerate(outputs, 1):
            merged += f"## Model {i}: {model.name}\n{response}\n\n"
        
        merged += "---\n*Note: Multiple models consulted for high-risk decision*"
        
        logger.info(f"Merged outputs from {len(outputs)} models")
        return merged


# Global instance
router_agent = RouterAgent()
