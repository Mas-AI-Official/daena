# Daena Python SDK

**Official Python SDK for Daena AI VP System**

The Daena Python SDK provides a clean, type-safe interface to integrate with Daena AI VP System. It simplifies API interactions and provides a developer-friendly interface to all Daena capabilities.

---

## 🚀 Features

- ✅ **Complete API Coverage**: All Daena endpoints supported
- ✅ **Type-Safe**: Full type hints for better IDE support
- ✅ **Error Handling**: Comprehensive exception handling
- ✅ **Retry Logic**: Automatic retries for transient failures
- ✅ **Easy to Use**: Simple, intuitive API
- ✅ **Production Ready**: Battle-tested and reliable

---

## 📦 Installation

### From Source

```bash
cd sdk
pip install -e .
```

### Development Installation

```bash
cd sdk
pip install -e ".[dev]"
```

---

## 🔑 Quick Start

### Basic Usage

```python
from daena_sdk import DaenaClient

# Initialize client
client = DaenaClient(
    api_key="your-api-key",
    base_url="https://api.daena.ai"
)

# Test connection
if client.test_connection():
    print("✅ Connected to Daena!")

# Get system health
health = client.get_health()
print(f"System Status: {health['status']}")

# Get all agents
agents = client.get_agents()
print(f"Total Agents: {len(agents)}")

# Chat with Daena
response = client.chat("What's the status of our marketing campaigns?")
print(f"Daena: {response['response']}")
```

---

## 📚 API Reference

### System Operations

```python
# Get system health
health = client.get_health()

# Get system summary
summary = client.get_system_summary()

# Get system metrics
metrics = client.get_system_metrics()
```

### Agent Management

```python
# Get all agents
agents = client.get_agents()

# Get agents by department
ai_agents = client.get_agents(department_id="ai")

# Get specific agent
agent = client.get_agent("agent_123")

# Get agent metrics
metrics = client.get_agent_metrics()
```

### Daena Chat

```python
# Send a message
response = client.chat("Hello Daena!")

# Chat with context
response = client.chat(
    message="Analyze Q4 sales",
    context={"quarter": "Q4", "year": 2025}
)

# Get chat status
status = client.get_chat_status(session_id="session_123")
```

### Memory & NBMF

```python
# Store memory
record = client.store_memory(
    key="project:123:notes",
    payload={"content": "Project notes..."},
    class_name="project_notes"
)

# Retrieve memory
record = client.retrieve_memory("project:123:notes")

# Search memory
results = client.search_memory("project management", limit=10)

# Get memory metrics
metrics = client.get_memory_metrics()
```

### Council System

```python
# Run council debate
decision = client.run_council_debate(
    department="marketing",
    topic="Should we launch the new campaign?",
    context={"budget": 100000}
)

# Get recent conclusions
conclusions = client.get_council_conclusions(department="marketing")

# Get pending approvals
approvals = client.get_pending_approvals(impact="high")

# Approve decision
result = client.approve_decision(
    decision_id="decision_123",
    approver_id="user_456"
)
```

### Knowledge Distillation

```python
# Distill experience
vectors = client.distill_experience([
    {"decision_time": 0.8, "consensus_score": 0.9},
    {"decision_time": 0.7, "consensus_score": 0.95}
])

# Search similar patterns
patterns = client.search_similar_patterns(
    query_features={"decision_time": 0.8, "consensus_score": 0.9},
    top_k=5
)

# Get recommendations
recommendations = client.get_pattern_recommendations(
    context={"decision_time": 0.8, "category": "strategic"}
)
```

### OCR Comparison

```python
# Get comparison stats
stats = client.get_ocr_comparison_stats()

# Compare image
comparison = client.compare_with_ocr("/path/to/image.png")

# Get benchmark results
benchmark = client.get_ocr_benchmark()
```

### Analytics

```python
# Get analytics summary
summary = client.get_analytics_summary()

# Get advanced insights
insights = client.get_advanced_insights()
```

---

## 🔐 Authentication

The SDK uses API key authentication. You can provide the API key in several ways:

### 1. Direct Initialization

```python
client = DaenaClient(api_key="your-api-key")
```

### 2. Environment Variable

```bash
export DAENA_API_KEY="your-api-key"
```

```python
import os
client = DaenaClient(api_key=os.getenv("DAENA_API_KEY"))
```

---

## ⚠️ Error Handling

The SDK provides comprehensive error handling:

```python
from daena_sdk import (
    DaenaClient,
    DaenaAPIError,
    DaenaAuthenticationError,
    DaenaRateLimitError,
    DaenaNotFoundError
)

try:
    agent = client.get_agent("agent_123")
except DaenaNotFoundError:
    print("Agent not found")
except DaenaAuthenticationError:
    print("Invalid API key")
except DaenaRateLimitError as e:
    print(f"Rate limit exceeded. Retry after {e.retry_after}s")
except DaenaAPIError as e:
    print(f"API error: {e.message}")
```

---

## 🔄 Retry Logic

The SDK automatically retries failed requests with exponential backoff:

```python
client = DaenaClient(
    api_key="your-api-key",
    max_retries=3,      # Maximum retry attempts
    retry_backoff=1.0   # Backoff multiplier
)
```

---

## 📊 Examples

### Complete Integration Example

```python
from daena_sdk import DaenaClient

# Initialize
client = DaenaClient(
    api_key="your-api-key",
    base_url="https://api.daena.ai"
)

# 1. Check system health
health = client.get_health()
print(f"System: {health['status']}")

# 2. Get all marketing agents
marketing_agents = client.get_agents(department_id="marketing")
print(f"Marketing Agents: {len(marketing_agents)}")

# 3. Store project notes in memory
memory = client.store_memory(
    key="project:campaign-2025:notes",
    payload={
        "title": "Q1 Campaign Strategy",
        "content": "Focus on digital channels..."
    },
    class_name="project_notes"
)
print(f"Stored memory: {memory.record_id}")

# 4. Run council debate
decision = client.run_council_debate(
    department="marketing",
    topic="Approve Q1 campaign budget",
    context={"budget": 50000}
)
print(f"Decision: {decision.decision}")
print(f"Confidence: {decision.confidence:.2%}")

# 5. Get analytics insights
insights = client.get_advanced_insights()
print(f"Predictions: {insights.get('predictions', {})}")
```

---

## 🧪 Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=daena_sdk tests/
```

---

## 📖 Documentation

- [Full API Reference](docs/API_REFERENCE.md)
- [Examples](examples/)
- [Migration Guide](docs/MIGRATION_GUIDE.md)

---

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

**Status**: ✅ **Production-Ready**

