# Distributed Tracing with OpenTelemetry

## Overview

Daena AI now supports distributed tracing using OpenTelemetry for end-to-end request tracking and performance analysis. This enables you to:

- Track requests across all services (FastAPI, Message Bus, Council Rounds, NBMF operations)
- Debug performance bottlenecks
- Understand system behavior and communication patterns
- Export traces to Jaeger, Tempo, or other OTLP-compatible backends

## Installation

Tracing is **optional** and requires OpenTelemetry packages:

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-exporter-otlp
```

## Configuration

### Enable Tracing

Set environment variable to enable tracing:

```bash
export DAENA_TRACING_ENABLED=true
```

### OTLP Endpoint (Optional)

If you want to export traces to a backend (Jaeger, Tempo, etc.):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

If not set, traces will be exported to console (useful for development).

## What Gets Traced

### 1. FastAPI Requests
- All HTTP requests/responses automatically instrumented
- Request duration, status codes, errors

### 2. Council Rounds
- Scout → Debate → Commit phases
- Department, topic, round_id attributes
- Phase transitions and timing

### 3. Message Bus Operations
- Topic-based pub/sub messages
- Message IDs, topics, sender information
- Rate limiting events

### 4. NBMF Memory Operations
- Read/write operations
- Item IDs, classes, tiers (L1/L2/L3)
- Operation types and metadata

### 5. LLM Exchanges
- Model information
- CAS hit/miss status
- Near-duplicate detection
- Cost tracking

## Usage Examples

### Basic Usage

```python
from backend.utils.tracing import get_tracing_service

tracing_service = get_tracing_service()
if tracing_service:
    with tracing_service.span("my_operation", {"key": "value"}):
        # Your code here
        pass
```

### Adding Events

```python
tracing_service = get_tracing_service()
if tracing_service:
    tracing_service.add_event("checkpoint_reached", {"items_processed": 100})
```

### Setting Attributes

```python
tracing_service = get_tracing_service()
if tracing_service:
    tracing_service.set_attribute("user_id", "user123")
    tracing_service.set_status("ok")
```

## Integration with Backends

### Jaeger

```bash
# Run Jaeger locally
docker run -d -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one:latest

# Set endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export DAENA_TRACING_ENABLED=true

# Start Daena
python backend/main.py
```

Access Jaeger UI at: http://localhost:16686

### Tempo

```bash
# Set Tempo endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export DAENA_TRACING_ENABLED=true
```

### Grafana Cloud

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=https://tempo-us-central1.grafana.net:443
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64-encoded-credentials>"
export DAENA_TRACING_ENABLED=true
```

## Trace Attributes

### Council Rounds
- `council.department`: Department name
- `council.phase`: Phase (scout/debate/commit)
- `council.round_id`: Unique round identifier

### Message Bus
- `message_bus.operation`: Operation type (publish/subscribe)
- `message_bus.topic`: Topic name
- `message_bus.message_id`: Message identifier

### NBMF Operations
- `nbmf.operation`: Operation (read/write)
- `nbmf.item_id`: Item identifier
- `nbmf.class`: Memory class
- `nbmf.tier`: Storage tier (l1/l2/l3)

### LLM Exchanges
- `llm.model`: Model name
- `llm.cas_hit`: CAS cache hit (true/false)
- `llm.near_dup`: Near-duplicate reuse (true/false)

## Performance Impact

Tracing has minimal performance impact:
- **Disabled**: Zero overhead (no-op functions)
- **Enabled (Console)**: ~1-2% overhead
- **Enabled (OTLP)**: ~2-5% overhead depending on network latency

## Troubleshooting

### Tracing Not Working

1. Check if tracing is enabled:
   ```bash
   echo $DAENA_TRACING_ENABLED
   ```

2. Check if OpenTelemetry is installed:
   ```bash
   pip list | grep opentelemetry
   ```

3. Check logs for initialization messages:
   ```
   ✅ Distributed tracing enabled
   ```

### Traces Not Appearing in Backend

1. Verify endpoint is correct:
   ```bash
   echo $OTEL_EXPORTER_OTLP_ENDPOINT
   ```

2. Check network connectivity:
   ```bash
   curl $OTEL_EXPORTER_OTLP_ENDPOINT
   ```

3. Check backend logs for errors

## Best Practices

1. **Enable in Production**: Use OTLP exporter, not console
2. **Sample Rate**: Consider sampling for high-traffic systems
3. **Attribute Limits**: Keep attribute values concise
4. **Error Handling**: Always check if tracing service exists before use
5. **Performance**: Monitor overhead in production

## Related Documentation

- [Production Readiness Checklist](./NBMF_PRODUCTION_READINESS.md)
- [Monitoring & Metrics](./docs/monitoring.md)
- [Grafana Dashboard](./monitoring/grafana_dashboard.json)

---

**Last Updated**: 2025-01-XX  
**Status**: ✅ Production Ready  
**Version**: 2.0.0

