# Daena Python SDK Documentation

**Date**: 2025-01-XX  
**Status**: ✅ **SDK READY**

---

## 🎯 Overview

The Daena Python SDK provides a production-ready, type-safe interface to integrate with Daena AI VP System. It simplifies API interactions and provides comprehensive error handling.

---

## 📦 Installation

### From Source

```bash
cd sdk
pip install -e .
```

### Development

```bash
cd sdk
pip install -e ".[dev]"
```

---

## 🚀 Quick Start

```python
from daena_sdk import DaenaClient

# Initialize
client = DaenaClient(
    api_key="your-api-key",
    base_url="https://api.daena.ai"
)

# Use it
health = client.get_health()
agents = client.get_agents()
response = client.chat("Hello Daena!")
```

---

## 📚 Complete API Reference

### Client Initialization

```python
client = DaenaClient(
    api_key: str,                    # Required: Your API key
    base_url: str = "http://localhost:8000",  # API base URL
    timeout: int = 30,               # Request timeout
    max_retries: int = 3,            # Max retries
    retry_backoff: float = 1.0       # Backoff multiplier
)
```

### System Operations

#### `get_health() -> Dict[str, Any]`
Get system health status.

#### `get_system_summary() -> Dict[str, Any]`
Get comprehensive system summary.

#### `get_system_metrics() -> SystemMetrics`
Get current system metrics.

#### `test_connection() -> bool`
Test connection to Daena API.

### Agent Management

#### `get_agents(department_id, status, limit, offset) -> List[Agent]`
Get list of agents with optional filtering.

#### `get_agent(agent_id) -> Agent`
Get specific agent by ID.

#### `get_agent_metrics(agent_id) -> Dict[str, Any]`
Get agent performance metrics.

### Daena Chat

#### `chat(message, session_id, context) -> Dict[str, Any]`
Send a message to Daena chat.

#### `get_chat_status(session_id) -> Dict[str, Any]`
Get chat session status.

### Memory & NBMF

#### `store_memory(key, payload, class_name, metadata, tenant_id) -> MemoryRecord`
Store a memory record using NBMF.

#### `retrieve_memory(key, tenant_id) -> Optional[MemoryRecord]`
Retrieve a memory record.

#### `search_memory(query, limit, tenant_id) -> List[MemoryRecord]`
Search memory records.

#### `get_memory_metrics() -> Dict[str, Any]`
Get memory system metrics.

### Council System

#### `run_council_debate(department, topic, context, tenant_id) -> CouncilDecision`
Run a council debate on a topic.

#### `get_council_conclusions(department, limit) -> List[CouncilDecision]`
Get recent council conclusions.

#### `get_pending_approvals(department, impact, limit) -> List[Dict[str, Any]]`
Get pending approval requests.

#### `approve_decision(decision_id, approver_id) -> Dict[str, Any]`
Approve a council decision.

### Knowledge Distillation

#### `distill_experience(data_items, tenant_id) -> List[ExperienceVector]`
Distill experience vectors from data.

#### `search_similar_patterns(query_features, pattern_type, top_k, similarity_threshold) -> List[Dict[str, Any]]`
Search for similar patterns.

#### `get_pattern_recommendations(context, pattern_type, top_k) -> List[Dict[str, Any]]`
Get pattern recommendations.

### OCR Comparison

#### `get_ocr_comparison_stats() -> Dict[str, Any]`
Get OCR comparison statistics.

#### `compare_with_ocr(image_path) -> Dict[str, Any]`
Compare NBMF with OCR for an image.

#### `get_ocr_benchmark() -> Dict[str, Any]`
Get benchmark results.

### Analytics

#### `get_analytics_summary() -> Dict[str, Any]`
Get analytics summary.

#### `get_advanced_insights() -> Dict[str, Any]`
Get advanced insights.

---

## ⚠️ Error Handling

```python
from daena_sdk import (
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
    print(f"Rate limit. Retry after {e.retry_after}s")
```

---

## 🔄 Retry Logic

The SDK automatically retries failed requests:

- **429 (Rate Limit)**: Retries with backoff
- **500, 502, 503, 504**: Retries with exponential backoff
- **Configurable**: Set `max_retries` and `retry_backoff`

---

## 📊 Usage Examples

See `sdk/examples/` for complete examples:
- `basic_usage.py` - Basic operations
- `memory_operations.py` - Memory management
- `council_examples.py` - Council system
- `advanced_features.py` - Advanced features

---

## ✅ Status

**🏁 SDK READY FOR USE**

- ✅ Complete API coverage
- ✅ Type-safe interfaces
- ✅ Error handling
- ✅ Retry logic
- ✅ Documentation
- ✅ Examples

---

**Status**: ✅ **PRODUCTION-READY**

