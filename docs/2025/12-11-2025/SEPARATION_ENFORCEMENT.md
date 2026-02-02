# Daena ↔ VibeAgent Separation Enforcement

## Quick Reference

### Agent Namespaces
- `daena_internal_*` - Daena internal agents (8 departments, 6 agents each)
- `vibeagent_public_*` - VibeAgent user agents
- `council_governance_*` - Council governance agents

### Knowledge Exchange
- **ONLY** patterns, methodologies, anonymized metrics
- **NEVER** raw data, PII, or internal secrets
- Endpoint: `/api/v1/knowledge-exchange/*`

### Code Rules
1. **NEVER** import Daena internal types into VibeAgent
2. **ALWAYS** use namespace prefixes for agent IDs
3. **ALWAYS** sanitize data before exchange
4. **ALWAYS** validate namespace in agent operations

### Testing
Run namespace validation:
```python
from backend.config.agent_namespace import AgentNamespace, AGENT_NAMESPACE_CONFIG

# Validate namespace
AGENT_NAMESPACE_CONFIG.validate_namespace("vibeagent_public_123", AgentNamespace.PUBLIC)  # True
AGENT_NAMESPACE_CONFIG.validate_namespace("daena_internal_123", AgentNamespace.INTERNAL)  # True

# Prevent drift
AGENT_NAMESPACE_CONFIG.enforce_namespace_separation(
    "vibeagent_public_123",
    AgentNamespace.PUBLIC,
    AgentNamespace.PUBLIC
)  # True (allowed)

AGENT_NAMESPACE_CONFIG.enforce_namespace_separation(
    "vibeagent_public_123",
    AgentNamespace.INTERNAL,
    AgentNamespace.PUBLIC
)  # False (blocked - drift prevention)
```






