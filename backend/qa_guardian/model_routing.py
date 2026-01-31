"""
Model Routing Policy - Routes QA tasks to appropriate models

Implements Part 6 of QA Guardian spec:
- Cheap models (gpt-4o-mini) for parsing/triage
- Strong models (o1) for complex reasoning
- Code models (Claude) for code generation/review
"""

import os
import logging
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger("qa_guardian.model_routing")


class TaskType(Enum):
    """Types of QA tasks that need model routing"""
    PARSING = "parsing"           # Extracting structured data from logs
    TRIAGE = "triage"             # Classifying incidents
    REASONING = "reasoning"       # Complex decision making
    CODE_REVIEW = "code_review"   # Reviewing code changes
    CODE_FIX = "code_fix"         # Generating code fixes
    REPORT = "report"             # Generating reports
    SUMMARY = "summary"           # Summarizing findings


@dataclass
class ModelConfig:
    """Configuration for a model"""
    provider: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.3
    

class ModelRoutingPolicy:
    """
    Routes QA tasks to appropriate models based on task type.
    
    Default Configuration:
    - FAST (gpt-4o-mini): Parsing, triage, summaries - fast and cheap
    - REASONING (o1): Complex decisions, root cause analysis
    - CODE (claude-3-5-sonnet): Code review, code generation
    
    All configurable via environment variables.
    """
    
    # Environment variable names
    ENV_MODEL_FAST = "QA_MODEL_FAST"
    ENV_MODEL_REASONING = "QA_MODEL_REASONING"
    ENV_MODEL_CODE = "QA_MODEL_CODE"
    ENV_PROVIDER_FAST = "QA_PROVIDER_FAST"
    ENV_PROVIDER_REASONING = "QA_PROVIDER_REASONING"
    ENV_PROVIDER_CODE = "QA_PROVIDER_CODE"
    
    # Default models
    DEFAULT_FAST = "gpt-4o-mini"
    DEFAULT_REASONING = "o1"
    DEFAULT_CODE = "claude-3-5-sonnet"
    
    # Default providers
    DEFAULT_PROVIDER_FAST = "openai"
    DEFAULT_PROVIDER_REASONING = "openai"
    DEFAULT_PROVIDER_CODE = "anthropic"
    
    # Task to model type mapping
    TASK_ROUTING = {
        TaskType.PARSING: "fast",
        TaskType.TRIAGE: "fast",
        TaskType.SUMMARY: "fast",
        TaskType.REPORT: "fast",
        TaskType.REASONING: "reasoning",
        TaskType.CODE_REVIEW: "code",
        TaskType.CODE_FIX: "code",
    }
    
    def __init__(self):
        self._load_config()
    
    def _load_config(self):
        """Load model configuration from environment"""
        self.models = {
            "fast": ModelConfig(
                provider=os.getenv(self.ENV_PROVIDER_FAST, self.DEFAULT_PROVIDER_FAST),
                model=os.getenv(self.ENV_MODEL_FAST, self.DEFAULT_FAST),
                max_tokens=2048,
                temperature=0.1
            ),
            "reasoning": ModelConfig(
                provider=os.getenv(self.ENV_PROVIDER_REASONING, self.DEFAULT_PROVIDER_REASONING),
                model=os.getenv(self.ENV_MODEL_REASONING, self.DEFAULT_REASONING),
                max_tokens=8192,
                temperature=0.2
            ),
            "code": ModelConfig(
                provider=os.getenv(self.ENV_PROVIDER_CODE, self.DEFAULT_PROVIDER_CODE),
                model=os.getenv(self.ENV_MODEL_CODE, self.DEFAULT_CODE),
                max_tokens=8192,
                temperature=0.0
            )
        }
    
    def get_model_for_task(self, task_type: TaskType) -> ModelConfig:
        """Get the appropriate model configuration for a task type"""
        model_type = self.TASK_ROUTING.get(task_type, "fast")
        return self.models[model_type]
    
    def get_model_for_agent(self, agent_id: str) -> ModelConfig:
        """Get model configuration for a specific QA agent"""
        agent_routing = {
            "qa_triage_agent": "fast",
            "qa_regression_agent": "fast",
            "qa_security_agent": "fast",
            "qa_code_review_agent": "code",
            "qa_auto_fix_agent": "code",
            "qa_reporter_agent": "fast",
        }
        
        model_type = agent_routing.get(agent_id, "fast")
        return self.models[model_type]
    
    def route(self, task_type: TaskType, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Route a task to the appropriate model.
        
        Returns a dict with provider, model, and parameters.
        """
        config = self.get_model_for_task(task_type)
        
        result = {
            "provider": config.provider,
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature
        }
        
        # Apply context overrides
        if context:
            if context.get("high_precision"):
                result["temperature"] = 0.0
            if context.get("long_output"):
                result["max_tokens"] = min(config.max_tokens * 2, 16384)
        
        logger.debug(f"Routing {task_type.value} to {config.provider}/{config.model}")
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current routing configuration status"""
        return {
            "fast_model": f"{self.models['fast'].provider}/{self.models['fast'].model}",
            "reasoning_model": f"{self.models['reasoning'].provider}/{self.models['reasoning'].model}",
            "code_model": f"{self.models['code'].provider}/{self.models['code'].model}",
        }


# Singleton instance
_routing_policy: Optional[ModelRoutingPolicy] = None

def get_routing_policy() -> ModelRoutingPolicy:
    """Get or create the singleton routing policy"""
    global _routing_policy
    if _routing_policy is None:
        _routing_policy = ModelRoutingPolicy()
    return _routing_policy
