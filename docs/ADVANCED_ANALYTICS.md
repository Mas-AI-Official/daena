# Advanced Analytics System

## Overview

Daena AI now includes an advanced analytics system that tracks and analyzes agent behavior patterns, communication patterns, efficiency metrics, and detects anomalies. This provides deep insights into system operation and helps identify optimization opportunities.

## Features

- **Agent Behavior Tracking**: Comprehensive tracking of all agent interactions
- **Communication Pattern Analysis**: Visualize and analyze communication flows
- **Efficiency Metrics**: Calculate performance metrics per agent
- **Anomaly Detection**: Automatic detection of unusual behavior patterns
- **Interaction Graphs**: Network visualization of agent relationships
- **Real-time Analytics**: Sliding window analysis for current insights

## Interaction Types Tracked

- `MESSAGE_SENT`: Agent sends a message
- `MESSAGE_RECEIVED`: Agent receives a message
- `COUNCIL_PARTICIPATION`: Agent participates in council round
- `MEMORY_WRITE`: Agent writes to memory
- `MEMORY_READ`: Agent reads from memory
- `LLM_CALL`: Agent makes LLM API call
- `DECISION_MADE`: Agent makes a decision

## API Endpoints

### Get Analytics Summary

```bash
GET /api/v1/analytics/summary
```

Returns comprehensive analytics summary including:
- Total interactions in time window
- Unique agents active
- Top agents by activity
- Top communication paths
- Detected anomalies

**Response:**
```json
{
  "window_minutes": 60,
  "total_interactions": 1250,
  "unique_agents": 48,
  "top_agents": [
    {"agent_id": "agent_1", "interactions": 150},
    {"agent_id": "agent_2", "interactions": 120}
  ],
  "top_communications": [
    {"path": "agent_1 -> agent_2", "count": 45},
    {"path": "agent_3 -> agent_4", "count": 38}
  ],
  "anomalies_detected": 2,
  "anomalies": [...],
  "timestamp": 1234567890.0
}
```

### Get Agent Interaction Graph

```bash
GET /api/v1/analytics/agent-interaction-graph?department=engineering
```

Returns graph data for visualization:
- Nodes: Agents with interaction counts
- Edges: Communication paths with weights
- Filterable by department

**Response:**
```json
{
  "nodes": [
    {"id": "agent_1", "department": "engineering", "interactions": 150},
    {"id": "agent_2", "department": "engineering", "interactions": 120}
  ],
  "edges": [
    {"source": "agent_1", "target": "agent_2", "weight": 45},
    {"source": "agent_2", "target": "agent_3", "weight": 30}
  ],
  "window_minutes": 60,
  "total_interactions": 1250
}
```

### Get Communication Patterns

```bash
GET /api/v1/analytics/communication-patterns?agent_id=agent_1
```

Returns detailed communication patterns:
- Message counts between agents
- Average latency
- Success rates
- Interaction type breakdowns

**Response:**
```json
{
  "patterns": [
    {
      "source_agent": "agent_1",
      "target_agent": "agent_2",
      "message_count": 45,
      "avg_latency_ms": 12.5,
      "success_rate": 0.98,
      "last_interaction": 1234567890.0,
      "interaction_types": {
        "message_sent": 30,
        "council_participation": 15
      }
    }
  ],
  "total_patterns": 1
}
```

### Get Agent Efficiency Metrics

```bash
GET /api/v1/analytics/agent/{agent_id}/efficiency
```

Returns efficiency metrics for a specific agent:
- Total interactions
- Average response time
- Success rate
- CAS hit rate
- Memory efficiency
- LLM cost per interaction

**Response:**
```json
{
  "agent_id": "agent_1",
  "department": "engineering",
  "total_interactions": 150,
  "avg_response_time_ms": 25.5,
  "success_rate": 0.95,
  "cas_hit_rate": 0.65,
  "memory_efficiency": 0.85,
  "llm_cost_per_interaction": 0.0025
}
```

### Get All Agents Efficiency

```bash
GET /api/v1/analytics/agents/efficiency?department=engineering
```

Returns efficiency metrics for all agents, sorted by activity.

### Get Anomalies

```bash
GET /api/v1/analytics/anomalies
```

Returns detected anomalies:
- Unusual activity levels
- Severity (high/medium)
- Z-scores
- Baseline comparisons

**Response:**
```json
{
  "anomalies": [
    {
      "agent_id": "agent_5",
      "type": "unusual_activity",
      "severity": "high",
      "current_activity": 500,
      "baseline_activity": 50,
      "z_score": 8.5,
      "timestamp": 1234567890.0
    }
  ],
  "total_anomalies": 1,
  "threshold": 3.0
}
```

### Record Interaction

```bash
POST /api/v1/analytics/record-interaction
```

Manually record an interaction (for external systems).

**Request:**
```json
{
  "agent_id": "agent_1",
  "department": "engineering",
  "interaction_type": "message_sent",
  "target_agent": "agent_2",
  "target_department": "engineering",
  "latency_ms": 10.5,
  "success": true,
  "metadata": {"message_id": "msg_123"}
}
```

## Integration

### Automatic Tracking

The analytics service automatically tracks:
- Council round participation (via `council_scheduler.py`)
- Can be extended to track message bus operations
- Can be extended to track memory operations
- Can be extended to track LLM calls

### Manual Tracking

For custom interactions, use the analytics service directly:

```python
from backend.services.analytics_service import analytics_service, InteractionType

analytics_service.record_interaction(
    agent_id="agent_1",
    department="engineering",
    interaction_type=InteractionType.MESSAGE_SENT,
    target_agent="agent_2",
    latency_ms=10.5,
    success=True,
    metadata={"message_id": "msg_123"}
)
```

## Configuration

### Window Size

Default: 60 minutes (sliding window)

Can be configured when creating the service:

```python
from backend.services.analytics_service import AnalyticsService

analytics_service = AnalyticsService(
    max_history=20000,  # Max interactions to keep
    window_minutes=120  # Analysis window
)
```

### Anomaly Detection Threshold

Default: 3.0 standard deviations

```python
analytics_service.anomaly_threshold = 2.5  # More sensitive
```

## Use Cases

### 1. Performance Optimization

Identify agents with high latency or low success rates:

```python
metrics = analytics_service.calculate_efficiency_metrics("agent_1")
if metrics.avg_response_time_ms > 100:
    print(f"Agent {metrics.agent_id} has high latency")
```

### 2. Communication Bottlenecks

Find communication hotspots:

```python
patterns = analytics_service.get_communication_patterns()
top_pattern = patterns[0]  # Most active
print(f"Hotspot: {top_pattern['source_agent']} -> {top_pattern['target_agent']}")
```

### 3. Anomaly Detection

Monitor for unusual behavior:

```python
anomalies = analytics_service.detect_anomalies()
for anomaly in anomalies:
    if anomaly["severity"] == "high":
        alert(f"High severity anomaly: {anomaly}")
```

### 4. Resource Allocation

Identify high-value agents:

```python
summary = analytics_service.get_analytics_summary()
top_agents = summary["top_agents"]
# Allocate more resources to top agents
```

## Visualization

### Interaction Graph

Use the interaction graph endpoint with visualization libraries:

```python
import networkx as nx
import matplotlib.pyplot as plt

graph_data = requests.get("/api/v1/analytics/agent-interaction-graph").json()

G = nx.Graph()
for node in graph_data["nodes"]:
    G.add_node(node["id"], department=node["department"])

for edge in graph_data["edges"]:
    G.add_edge(edge["source"], edge["target"], weight=edge["weight"])

nx.draw(G, with_labels=True)
plt.show()
```

## Performance Considerations

- **Memory**: Uses deque with maxlen for efficient sliding window
- **CPU**: O(n) for most operations, optimized for real-time use
- **Storage**: In-memory only (can be extended to persistent storage)

## Future Enhancements

- Persistent storage for historical analysis
- Machine learning-based anomaly detection
- Predictive analytics for capacity planning
- Integration with Grafana dashboards
- Export to data warehouses

## Related Documentation

- [Monitoring & Metrics](./monitoring.md)
- [Distributed Tracing](./DISTRIBUTED_TRACING.md)
- [Production Readiness](./NBMF_PRODUCTION_READINESS.md)

---

**Last Updated**: 2025-01-XX  
**Status**: ✅ Production Ready  
**Version**: 2.0.0

