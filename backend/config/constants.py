"""
Constants for Daena AI System Configuration
DEPRECATED: Use backend.config.council_config.COUNCIL_CONFIG as single source of truth
This file maintained for backward compatibility only.
"""

# Import from canonical config (single source of truth)
from backend.config.council_config import (
    COUNCIL_CONFIG,
    DEPARTMENT_NAMES,
    DEPARTMENT_DISPLAY_NAMES,
    AGENT_ROLES,
    MAX_AGENTS_PER_DEPARTMENT,
    TOTAL_DEPARTMENTS,
    MAX_TOTAL_AGENTS
)

# Re-export for backward compatibility
__all__ = [
    'COUNCIL_CONFIG',
    'DEPARTMENT_NAMES',
    'DEPARTMENT_DISPLAY_NAMES',
    'AGENT_ROLES',
    'MAX_AGENTS_PER_DEPARTMENT',
    'TOTAL_DEPARTMENTS',
    'MAX_TOTAL_AGENTS'
]

# LLM Provider Names for Deep Search
LLM_PROVIDERS = [
    "openai",
    "gemini", 
    "anthropic",
    "deepseek",
    "grok",
    "mistral",
    "claude",
    "llama"
]

# Search Depth Options
SEARCH_DEPTH_OPTIONS = [
    "basic",
    "comprehensive", 
    "expert"
]

# Conclusion Methods
CONCLUSION_METHODS = [
    "llm_aggregation",
    "local_brain",
    "hybrid"
] 