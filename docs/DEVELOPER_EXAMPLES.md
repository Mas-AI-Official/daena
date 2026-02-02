# Developer Code Examples

**Complete code examples for common Daena use cases**

---

## 📚 Examples Index

1. [Basic Integration](#basic-integration)
2. [Memory Management](#memory-management)
3. [Multi-Agent Workflow](#multi-agent-workflow)
4. [Council System](#council-system)
5. [Knowledge Distillation](#knowledge-distillation)
6. [Error Handling](#error-handling)
7. [Real-Time Updates](#real-time-updates)

---

## 🔧 Basic Integration

### Python Example

```python
from daena_sdk import DaenaClient

# Initialize client
client = DaenaClient(
    api_key="your-api-key",
    base_url="https://api.daena.ai"
)

# Test connection
if client.test_connection():
    print("✅ Connected!")

# Get system health
health = client.get_health()
print(f"Status: {health['status']}")

# Get all agents
agents = client.get_agents()
print(f"Total Agents: {len(agents)}")
```

### JavaScript Example

```javascript
import { DaenaClient } from '@daena/sdk';

const client = new DaenaClient({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.daena.ai'
});

// Test connection
const connected = await client.testConnection();
console.log(`Connected: ${connected}`);

// Get system health
const health = await client.getHealth();
console.log(`Status: ${health.status}`);
```

---

## 💾 Memory Management

### Store and Retrieve

```python
# Store memory with NBMF compression
memory = client.store_memory(
    key="project:123:notes",
    payload={
        "title": "Project Notes",
        "content": "Important information...",
        "tags": ["important", "project"]
    },
    class_name="project_notes",
    metadata={"created_by": "user_123"}
)

print(f"Stored: {memory.record_id}")
print(f"Compression: {memory.compression_ratio}×")

# Retrieve memory
retrieved = client.retrieve_memory("project:123:notes")
print(f"Retrieved: {retrieved.payload}")

# Search memories
results = client.search_memory("project notes", limit=10)
print(f"Found {len(results)} results")
```

---

## 🤖 Multi-Agent Workflow

### Cross-Department Collaboration

```python
# Marketing agent analyzes campaign
marketing_decision = client.run_council_debate(
    department="marketing",
    topic="Q1 Campaign Strategy",
    context={
        "budget": 100000,
        "target_audience": "enterprise",
        "timeline": "Q1 2025"
    }
)

print(f"Marketing Decision: {marketing_decision.decision}")
print(f"Confidence: {marketing_decision.confidence:.2%}")

# Finance agent approves budget
finance_decision = client.run_council_debate(
    department="finance",
    topic="Campaign Budget Approval",
    context={
        "requested_budget": marketing_decision.estimated_cost,
        "department": "marketing"
    }
)

print(f"Finance Decision: {finance_decision.decision}")

# Sales agent predicts impact
sales_decision = client.run_council_debate(
    department="sales",
    topic="Sales Impact Prediction",
    context={
        "campaign": marketing_decision.decision,
        "budget": finance_decision.approved_budget
    }
)

print(f"Predicted Sales Impact: {sales_decision.predicted_revenue}")
```

---

## 🏛️ Council System

### Running Debates and Getting Approvals

```python
# Run council debate
decision = client.run_council_debate(
    department="engineering",
    topic="Should we refactor the API?",
    context={
        "current_status": "legacy code",
        "benefits": "better performance",
        "cost": "2 weeks development"
    }
)

print(f"Decision: {decision.decision}")
print(f"Impact Level: {decision.impact_level}")

# Check if approval needed
if decision.impact_level in ["HIGH", "CRITICAL"]:
    # Get pending approvals
    approvals = client.get_pending_approvals(impact="high")
    
    for approval in approvals:
        print(f"Pending: {approval['title']}")
        
        # Approve decision
        result = client.approve_decision(
            decision_id=approval['decision_id'],
            approver_id="manager_123"
        )
        print(f"Approved: {result['status']}")
```

---

## 🧠 Knowledge Distillation

### Extract and Use Patterns

```python
# Distill experience from data
vectors = client.distill_experience(
    data_items=[
        {"decision_time": 0.8, "consensus_score": 0.9, "outcome": "success"},
        {"decision_time": 0.7, "consensus_score": 0.95, "outcome": "success"},
        {"decision_time": 1.2, "consensus_score": 0.6, "outcome": "failure"}
    ]
)

print(f"Extracted {len(vectors)} patterns")

# Search similar patterns
similar = client.search_similar_patterns(
    query_features={"decision_time": 0.8, "consensus_score": 0.9},
    top_k=5,
    similarity_threshold=0.7
)

print(f"Found {len(similar)} similar patterns")

# Get recommendations
recommendations = client.get_pattern_recommendations(
    context={
        "decision_time": 0.8,
        "department": "engineering",
        "category": "technical"
    },
    top_k=3
)

print(f"Recommendations: {len(recommendations)}")
```

---

## ⚠️ Error Handling

### Comprehensive Error Handling

```python
from daena_sdk import (
    DaenaClient,
    DaenaAPIError,
    DaenaAuthenticationError,
    DaenaRateLimitError,
    DaenaNotFoundError,
    DaenaValidationError
)

client = DaenaClient(api_key="your-api-key")

try:
    agent = client.get_agent("agent_123")
    print(f"Agent: {agent.name}")
except DaenaNotFoundError:
    print("Agent not found. Please check the agent ID.")
except DaenaAuthenticationError:
    print("Authentication failed. Please check your API key.")
except DaenaRateLimitError as e:
    print(f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
except DaenaValidationError:
    print("Invalid request. Please check your parameters.")
except DaenaAPIError as e:
    print(f"API error: {e.message}")
    if e.status_code:
        print(f"Status code: {e.status_code}")
```

---

## 🔄 Real-Time Updates

### WebSocket Example (Coming Soon)

```python
# WebSocket real-time updates
# Example implementation coming soon
```

---

## 📊 Complete Example: Project Management Assistant

```python
from daena_sdk import DaenaClient
from datetime import datetime

client = DaenaClient(api_key="your-api-key")

class ProjectManager:
    def __init__(self, project_id):
        self.project_id = project_id
        self.client = client
    
    def create_project(self, name, description):
        """Create a new project and store in memory."""
        memory = self.client.store_memory(
            key=f"project:{self.project_id}",
            payload={
                "name": name,
                "description": description,
                "created_at": datetime.utcnow().isoformat(),
                "status": "active"
            },
            class_name="project"
        )
        return memory
    
    def add_task(self, task_name, priority="medium"):
        """Add a task to the project."""
        memory = self.client.retrieve_memory(f"project:{self.project_id}")
        if memory:
            tasks = memory.payload.get("tasks", [])
            tasks.append({
                "name": task_name,
                "priority": priority,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat()
            })
            
            updated = self.client.store_memory(
                key=f"project:{self.project_id}",
                payload={**memory.payload, "tasks": tasks},
                class_name="project"
            )
            return updated
        return None
    
    def get_recommendations(self):
        """Get AI recommendations for the project."""
        decision = self.client.run_council_debate(
            department="product",
            topic=f"Project {self.project_id} recommendations",
            context={"project_id": self.project_id}
        )
        return decision.decision

# Usage
pm = ProjectManager("proj_123")
pm.create_project("New Feature", "Build new feature for Q1")
pm.add_task("Design mockups", priority="high")
recommendations = pm.get_recommendations()
print(recommendations)
```

---

## 🔗 Additional Resources

- [API Reference](API_USAGE_EXAMPLES.md)
- [SDK Documentation](SDK_DOCUMENTATION.md)
- [Architecture Guide](ARCHITECTURE_GROUND_TRUTH.md)
- [Migration Guides](MIGRATION_GUIDE_OPENAI.md)

---

**Status**: ✅ **EXAMPLES READY**

