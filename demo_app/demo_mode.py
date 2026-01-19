"""
Demo Mode Configuration for AI Tinkerers Toronto Jan 2026

Central configuration for demo-safe operation:
- DEMO_MODE toggle via environment variable
- Cached sample outputs for offline resilience
- Auto-fallback to local model when cloud fails
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Demo mode flag - set DEMO_MODE=1 to enable
DEMO_MODE = os.getenv("DEMO_MODE", "0").lower() in {"1", "true", "yes", "on"}

# Demo configuration
DEMO_CONFIG = {
    "enabled": DEMO_MODE,
    "default_cloud_provider": "gemini",  # Google venue, fits the event
    "fallback_to_local": True,
    "use_cached_on_failure": True,
    "cached_responses_path": Path(__file__).parent.parent / "demo_assets" / "cached_responses.json",
    "max_response_time_ms": 5000,
    "timeout_seconds": 10,
}

# Sample cached responses for offline demo
CACHED_DEMO_RESPONSES = {
    "explain_routing": {
        "prompt": "Explain how Daena routes requests to different AI models",
        "response": """Daena's Intelligent Router uses a multi-factor decision system:

1. **Task Type Detection**: Analyzes the prompt to detect if it's reasoning, creative, code, or chat
2. **Model Availability Check**: Pings local Ollama and cloud providers to find available models
3. **Sunflower Scoring**: Applies our proprietary routing algorithm to select the optimal model
4. **Cost/Latency Budget**: Considers configured budgets for each request type

For this demo, the router selected the cloud model for faster response time while maintaining quality.""",
        "router_decision": {
            "model_tier": "external_premium",
            "model_name": "gemini-pro",
            "provider": "gemini",
            "reason": "Cloud API available with lower latency",
            "latency_estimate_ms": 200,
            "cost_estimate_usd": 0.001
        }
    },
    "security_analysis": {
        "prompt": "Analyze the security implications of this API endpoint",
        "response": """Security Analysis Complete:

**Risk Assessment**: LOW
- Authentication: JWT validation present
- Authorization: Role-based access control enforced
- Input Validation: Schema validation active

**Recommendations**:
1. Add rate limiting for this endpoint
2. Consider IP whitelist for production
3. Enable audit logging for sensitive operations""",
        "router_decision": {
            "model_tier": "local_reasoning",
            "model_name": "deepseek-r1:8b",
            "provider": "ollama",
            "reason": "Security analysis requires step-by-step reasoning",
            "latency_estimate_ms": 800,
            "cost_estimate_usd": 0.0
        }
    },
    "default": {
        "prompt": "General query",
        "response": "Daena processed your request through the intelligent routing system. The council reviewed the response for security, reliability, and product alignment before delivery.",
        "router_decision": {
            "model_tier": "local_chat",
            "model_name": "qwen2.5:7b-instruct",
            "provider": "ollama",
            "reason": "General chat routed to local model for speed",
            "latency_estimate_ms": 150,
            "cost_estimate_usd": 0.0
        }
    }
}


def get_cached_response(prompt: str) -> Optional[Dict[str, Any]]:
    """Get cached response for demo fallback."""
    prompt_lower = prompt.lower()
    
    if "routing" in prompt_lower or "route" in prompt_lower:
        return CACHED_DEMO_RESPONSES["explain_routing"]
    elif "security" in prompt_lower or "threat" in prompt_lower:
        return CACHED_DEMO_RESPONSES["security_analysis"]
    else:
        return CACHED_DEMO_RESPONSES["default"]


def is_demo_mode() -> bool:
    """Check if demo mode is enabled."""
    return DEMO_MODE


def get_demo_config() -> Dict[str, Any]:
    """Get demo configuration."""
    return {
        **DEMO_CONFIG,
        "cached_responses_path": str(DEMO_CONFIG["cached_responses_path"])
    }


logger.info(f"Demo Mode: {'ENABLED' if DEMO_MODE else 'disabled'}")
