"""
Intelligent LLM Router for Daena AI VP

Routes tasks to optimal LLM based on:
- Task type (reasoning, creative, chat, code)
- Model availability (local vs external)
- Performance requirements
- Cost optimization

Supports:
- DeepSeek-R1 for reasoning tasks (local)
- GPT-4/Claude for creative tasks (external)
- Qwen/Llama for general chat (local)
- Automatic fallback on failure
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks that require different LLM capabilities"""
    REASONING = "reasoning"      # Math, logic, step-by-step thinking
    CREATIVE = "creative"        # Writing, storytelling, brainstorming
    CODE = "code"               # Code generation, debugging
    CHAT = "chat"               # General conversation
    ANALYSIS = "analysis"       # Data analysis, summarization
    TOOL_SELECTION = "tool"     # Deciding which tool to use


class ModelTier(Enum):
    """Model tiers for routing decisions"""
    LOCAL_REASONING = "local_reasoning"   # DeepSeek-R1
    LOCAL_CHAT = "local_chat"             # Qwen, Llama
    EXTERNAL_PREMIUM = "external_premium" # GPT-4, Claude
    EXTERNAL_FAST = "external_fast"       # GPT-3.5, Gemini Flash
    FALLBACK = "fallback"                 # Offline responses


@dataclass
class RoutingDecision:
    """Result of routing decision"""
    model_tier: ModelTier
    model_name: str
    provider: str
    reason: str
    fallback_chain: List[str]


# Model configurations
MODEL_CONFIG = {
    ModelTier.LOCAL_REASONING: {
        "provider": "ollama",
        "models": ["deepseek-r1:8b", "deepseek-r1:14b", "qwq:latest"],
        "best_for": [TaskType.REASONING, TaskType.ANALYSIS, TaskType.TOOL_SELECTION],
        "priority": 1,
    },
    ModelTier.LOCAL_CHAT: {
        "provider": "ollama", 
        "models": ["qwen2.5:7b-instruct", "llama3.2:latest", "mistral:latest"],
        "best_for": [TaskType.CHAT, TaskType.CODE],
        "priority": 2,
    },
    ModelTier.EXTERNAL_PREMIUM: {
        "provider": "openai",
        "models": ["gpt-4", "gpt-4-turbo", "claude-3-opus"],
        "best_for": [TaskType.CREATIVE, TaskType.ANALYSIS],
        "priority": 3,
    },
    ModelTier.EXTERNAL_FAST: {
        "provider": "openai",
        "models": ["gpt-3.5-turbo", "gemini-pro"],
        "best_for": [TaskType.CHAT],
        "priority": 4,
    },
}

# Task type detection keywords
TASK_KEYWORDS = {
    TaskType.REASONING: [
        "calculate", "solve", "prove", "logic", "step by step",
        "reasoning", "why", "how does", "explain", "analyze",
        "what if", "deduce", "infer", "compare"
    ],
    TaskType.CREATIVE: [
        "write", "create", "story", "imagine", "design",
        "brainstorm", "poem", "creative", "novel", "ideas"
    ],
    TaskType.CODE: [
        "code", "function", "bug", "program", "script",
        "python", "javascript", "debug", "implement", "refactor"
    ],
    TaskType.TOOL_SELECTION: [
        "scan", "browse", "navigate", "search", "query",
        "execute", "run", "tool", "command", "database"
    ],
    TaskType.ANALYSIS: [
        "summarize", "analyze", "review", "breakdown",
        "statistics", "data", "report", "insights"
    ],
}


class IntelligentRouter:
    """
    Routes tasks to optimal LLM based on task type and availability.
    """
    
    def __init__(self):
        self.available_models: Dict[str, bool] = {}
        self.routing_history: List[Dict] = []
        self._ollama_url = "http://127.0.0.1:11434"
        
    async def check_model_availability(self) -> Dict[str, bool]:
        """Check which models are currently available"""
        import httpx
        
        availability = {}
        
        # Check Ollama models
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    ollama_models = [m["name"] for m in data.get("models", [])]
                    
                    for tier, config in MODEL_CONFIG.items():
                        if config["provider"] == "ollama":
                            for model in config["models"]:
                                # Check if model exists (with or without tag)
                                model_base = model.split(":")[0]
                                availability[model] = any(
                                    m.startswith(model_base) for m in ollama_models
                                )
        except Exception as e:
            logger.warning(f"Could not check Ollama models: {e}")
            
        # Check external providers (basic check)
        try:
            from backend.services.llm_service import llm_service
            for provider in ["openai", "gemini", "anthropic"]:
                availability[f"provider_{provider}"] = provider in llm_service.providers
        except Exception as e:
            logger.warning(f"Could not check external providers: {e}")
            
        self.available_models = availability
        return availability
    
    def detect_task_type(self, message: str) -> TaskType:
        """Detect the type of task from the message"""
        message_lower = message.lower()
        
        # Count keyword matches for each task type
        scores = {}
        for task_type, keywords in TASK_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            scores[task_type] = score
            
        # Return task type with highest score, default to CHAT
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return TaskType.CHAT
    
    async def route(self, message: str, context: Optional[Dict] = None) -> RoutingDecision:
        """
        Route a message to the optimal LLM.
        
        Args:
            message: The user message or task
            context: Optional context (agent info, priority, etc.)
            
        Returns:
            RoutingDecision with model selection and reasoning
        """
        # Detect task type
        task_type = self.detect_task_type(message)
        logger.info(f"Detected task type: {task_type.value} for message: {message[:50]}...")
        
        # Get available models
        await self.check_model_availability()
        
        # Find best tier for this task type
        best_tier = None
        best_model = None
        fallback_chain = []
        
        # Priority order based on task type
        tier_priority = self._get_tier_priority(task_type)
        
        for tier in tier_priority:
            config = MODEL_CONFIG[tier]
            
            # Check if any model in this tier is available
            for model in config["models"]:
                if self.available_models.get(model, False):
                    if best_tier is None:
                        best_tier = tier
                        best_model = model
                    else:
                        fallback_chain.append(model)
                    break
                    
            # Check external provider availability
            if config["provider"] != "ollama":
                provider_key = f"provider_{config['provider']}"
                if self.available_models.get(provider_key, False):
                    if best_tier is None:
                        best_tier = tier
                        best_model = config["models"][0]
                    else:
                        fallback_chain.append(config["models"][0])
        
        # Default to fallback if nothing available
        if best_tier is None:
            best_tier = ModelTier.FALLBACK
            best_model = "offline"
            
        decision = RoutingDecision(
            model_tier=best_tier,
            model_name=best_model,
            provider=MODEL_CONFIG.get(best_tier, {}).get("provider", "fallback"),
            reason=f"Task type '{task_type.value}' routed to {best_tier.value}",
            fallback_chain=fallback_chain[:3]  # Keep top 3 fallbacks
        )
        
        # Log routing decision
        self._log_decision(message, task_type, decision)
        
        return decision
    
    def _get_tier_priority(self, task_type: TaskType) -> List[ModelTier]:
        """Get tier priority based on task type"""
        if task_type in [TaskType.REASONING, TaskType.TOOL_SELECTION, TaskType.ANALYSIS]:
            # Prefer local reasoning for complex tasks
            return [
                ModelTier.LOCAL_REASONING,
                ModelTier.EXTERNAL_PREMIUM,
                ModelTier.LOCAL_CHAT,
                ModelTier.EXTERNAL_FAST,
            ]
        elif task_type == TaskType.CREATIVE:
            # Prefer premium external for creative
            return [
                ModelTier.EXTERNAL_PREMIUM,
                ModelTier.LOCAL_REASONING,
                ModelTier.LOCAL_CHAT,
                ModelTier.EXTERNAL_FAST,
            ]
        elif task_type == TaskType.CODE:
            # Prefer local for code (faster iteration)
            return [
                ModelTier.LOCAL_CHAT,
                ModelTier.LOCAL_REASONING,
                ModelTier.EXTERNAL_PREMIUM,
                ModelTier.EXTERNAL_FAST,
            ]
        else:
            # Default: local chat first
            return [
                ModelTier.LOCAL_CHAT,
                ModelTier.LOCAL_REASONING,
                ModelTier.EXTERNAL_FAST,
                ModelTier.EXTERNAL_PREMIUM,
            ]
    
    def _log_decision(self, message: str, task_type: TaskType, decision: RoutingDecision):
        """Log routing decision for learning"""
        from datetime import datetime
        
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message_preview": message[:100],
            "task_type": task_type.value,
            "model_tier": decision.model_tier.value,
            "model_name": decision.model_name,
            "provider": decision.provider,
            "reason": decision.reason,
        }
        
        self.routing_history.append(entry)
        
        # Keep only last 100 decisions
        if len(self.routing_history) > 100:
            self.routing_history = self.routing_history[-100:]
            
        logger.info(f"Routing: {task_type.value} -> {decision.model_name} ({decision.reason})")
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics for monitoring"""
        if not self.routing_history:
            return {"total_routes": 0}
            
        tier_counts = {}
        task_counts = {}
        
        for entry in self.routing_history:
            tier = entry.get("model_tier", "unknown")
            task = entry.get("task_type", "unknown")
            
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            task_counts[task] = task_counts.get(task, 0) + 1
            
        return {
            "total_routes": len(self.routing_history),
            "by_tier": tier_counts,
            "by_task_type": task_counts,
            "available_models": self.available_models,
        }


# Global singleton
intelligent_router = IntelligentRouter()
