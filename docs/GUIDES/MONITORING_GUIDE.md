# Daena Monitoring & Observability Guide

**Status**: ✅ **PRODUCTION READY**  
**Date**: 2025-01-XX

## Overview

This guide provides comprehensive instructions for setting up and using Daena's monitoring and observability infrastructure, including Grafana dashboards, Prometheus alerts, and real-time metrics.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Grafana Setup](#grafana-setup)
4. [Prometheus Setup](#prometheus-setup)
5. [Alert Configuration](#alert-configuration)
6. [Metrics Overview](#metrics-overview)
7. [Dashboard Usage](#dashboard-usage)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Docker and Docker Compose (for containerized deployment)
- Or: Prometheus, Grafana installed locally
- Access to Daena backend API endpoints

### 1. Start Monitoring Stack

```bash
# Using Docker Compose
docker-compose up -d prometheus grafana

# Or start individually
docker run -d -p 9090:9090 prom/prometheus
docker run -d -p 3000:3000 grafana/grafana
```

### 2. Configure Prometheus

Copy `config/prometheus.yml` to your Prometheus configuration directory, or update `docker-compose.yml` to mount it.

### 3. Import Grafana Dashboard

1. Open Grafana at `http://localhost:3000`
2. Login (default: admin/admin)
3. Go to **Dashboards** → **Import**
4. Upload `config/grafana/dashboard.json`
5. Select Prometheus as data source

### 4. Configure Alerts

Copy `config/prometheus/alerts.yml` to your Prometheus alerts directory.

---

## Architecture

### Components

```
┌─────────────┐
│   Daena     │
│   Backend   │───┐
└─────────────┘   │
                  │ HTTP Metrics
┌─────────────┐   │
│  Prometheus │◄──┘
└─────────────┘
       │
       │ Queries
       ▼
┌─────────────┐
│   Grafana   │
└─────────────┘
```

### Metrics Flow

1. **Daena Backend** exposes metrics at `/api/v1/monitoring/memory/prometheus`
2. **Prometheus** scrapes metrics every 30 seconds
3. **Grafana** queries Prometheus for visualization
4. **Alertmanager** (optional) sends alerts based on rules

---

## Grafana Setup

### 1. Install Grafana

```bash
# Docker
docker run -d \
  -p 3000:3000 \
  -v $(pwd)/config/grafana:/etc/grafana/provisioning \
  grafana/grafana

# Or use package manager
# Ubuntu/Debian
sudo apt-get install grafana
sudo systemctl start grafana-server
```

### 2. Configure Data Source

1. Go to **Configuration** → **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Set URL: `http://prometheus:9090` (or `http://localhost:9090` if local)
5. Click **Save & Test**

### 3. Import Dashboard

**Option A: Import JSON File**
1. Go to **Dashboards** → **Import**
2. Click **Upload JSON file**
3. Select `config/grafana/dashboard.json`
4. Click **Load**

**Option B: Provision Dashboard**
1. Copy `config/grafana/dashboard.json` to Grafana provisioning directory
2. Restart Grafana
3. Dashboard will appear automatically

### 4. Dashboard Features

The comprehensive dashboard includes:

- **System Health**: CPU, Memory, Disk usage
- **NBMF Metrics**: Read/Write latency, compression ratios
- **CAS Metrics**: Hit rates, cost savings
- **Agent Metrics**: Activity, status, efficiency
- **Cost Tracking**: Total costs, savings percentage
- **Network I/O**: Traffic monitoring
- **GPU Metrics**: Usage, temperature (if available)

---

## Prometheus Setup

### 1. Install Prometheus

```bash
# Docker
docker run -d \
  -p 9090:9090 \
  -v $(pwd)/config/prometheus:/etc/prometheus \
  prom/prometheus

# Or download from https://prometheus.io/download/
```

### 2. Configuration

Edit `config/prometheus.yml`:

```yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  - job_name: 'daena'
    metrics_path: '/api/v1/monitoring/memory/prometheus'
    static_configs:
      - targets: ['localhost:8000']  # Daena backend URL
        labels:
          service: 'daena'
          environment: 'production'
```

### 3. Alert Rules

Copy `config/prometheus/alerts.yml` to your Prometheus rules directory:

```yaml
# In prometheus.yml
rule_files:
  - "alerts.yml"
```

### 4. Verify Setup

1. Open Prometheus UI: `http://localhost:9090`
2. Go to **Status** → **Targets**
3. Verify `daena` target is **UP**
4. Go to **Graph** and query: `up{job="daena"}`

---

## Alert Configuration

### Alert Rules

The alert rules in `config/prometheus/alerts.yml` include:

#### Critical Alerts
- **SystemDown**: System health check failed
- **HighMemoryUsage**: Memory usage > 95%
- **HighGPUTemperature**: GPU temperature > 85°C
- **HighErrorRate**: Error rate > 0.01 errors/sec

#### Warning Alerts
- **HighEncodeLatency**: NBMF encode latency p95 > 1ms
- **LowCompressionRatio**: Compression ratio < 10x
- **LowCASHitRate**: CAS hit rate < 50%
- **HighCPULoad**: CPU usage > 90%
- **HighDiskUsage**: Disk usage > 90%
- **HighNBMFReadLatency**: Read latency p95 > 50ms
- **HighNBMFWriteLatency**: Write latency p95 > 100ms
- **HighDivergenceRate**: Divergence rate > 1%
- **LowCostSavings**: Cost savings < 40%
- **HighGPUUsage**: GPU usage > 95%
- **LowAgentActivity**: < 50% agents active
- **HighNetworkTraffic**: Network traffic > 1GB/s
- **DeviceUnavailable**: Preferred compute device unavailable

### Alertmanager Integration (Optional)

1. Install Alertmanager:
```bash
docker run -d -p 9093:9093 prom/alertmanager
```

2. Configure `config/prometheus/alertmanager.yml`:
```yaml
route:
  receiver: 'default'
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://your-webhook-url'
```

3. Update `prometheus.yml`:
```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

---

## Metrics Overview

### System Metrics

- `daena_memory_metric{name="cpu_usage"}` - CPU usage percentage
- `daena_memory_metric{name="memory_usage"}` - Memory usage percentage
- `daena_memory_metric{name="disk_usage"}` - Disk usage percentage
- `daena_memory_metric{name="network_io_bytes_sent"}` - Network bytes sent
- `daena_memory_metric{name="network_io_bytes_recv"}` - Network bytes received

### NBMF Metrics

- `daena_memory_metric{name="nbmf_reads"}` - Total NBMF reads
- `daena_memory_metric{name="nbmf_writes"}` - Total NBMF writes
- `daena_memory_metric{name="nbmf_read_p95_ms"}` - Read latency p95 (ms)
- `daena_memory_metric{name="nbmf_write_p95_ms"}` - Write latency p95 (ms)
- `daena_memory_metric{name="nbmf_read_avg_ms"}` - Read latency average (ms)
- `daena_memory_metric{name="nbmf_write_avg_ms"}` - Write latency average (ms)

### CAS Metrics

- `daena_memory_metric{name="llm_cas_hit"}` - CAS hits
- `daena_memory_metric{name="llm_cas_miss"}` - CAS misses
- `daena_memory_metric{name="llm_near_dup_reuse"}` - Near-duplicate reuses
- `daena_memory_metric{name="llm_cas_hit_rate"}` - CAS hit rate (0-1)

### Cost Metrics

- `daena_memory_metric{name="total_cost_usd"}` - Total LLM cost (USD)
- `daena_memory_metric{name="estimated_cost_savings_usd"}` - Estimated savings (USD)
- `daena_memory_metric{name="cost_savings_percentage"}` - Cost savings percentage

### Cache Metrics

- `daena_memory_metric{name="l1_read_p95_ms"}` - L1 cache read latency p95 (ms)
- `daena_memory_metric{name="l2_read_p95_ms"}` - L2 cache read latency p95 (ms)
- `daena_memory_metric{name="divergence_rate"}` - Divergence rate (0-1)

### Agent Metrics

- `sunflower_agent_status{status="active"}` - Active agents
- `sunflower_agent_status{status="idle"}` - Idle agents
- `sunflower_http_requests_total` - Total HTTP requests
- `sunflower_http_request_duration_seconds` - HTTP request duration

### GPU Metrics (if available)

- `sunflower_gpu_usage_percent` - GPU usage percentage
- `sunflower_gpu_temperature_celsius` - GPU temperature
- `sunflower_gpu_memory_bytes` - GPU memory usage

---

## Dashboard Usage

### Key Panels

1. **System Health Overview**: Quick status check
2. **Resource Usage**: CPU, Memory, Disk gauges
3. **CAS Hit Rate**: Cache efficiency indicator
4. **Cost Savings**: Financial impact tracking
5. **NBMF Latency**: Performance monitoring
6. **Agent Activity**: Multi-agent system status
7. **GPU Metrics**: Hardware utilization (if available)

### Time Ranges

- **Last 6 hours**: Default view
- **Last 24 hours**: Daily trends
- **Last 7 days**: Weekly patterns
- **Custom**: Select specific time range

### Refresh Intervals

- **10s**: Real-time monitoring
- **30s**: Standard refresh (default)
- **1m**: Reduced load
- **5m+**: Long-term analysis

### Exporting Data

1. Click panel title → **More** → **Export CSV**
2. Or use Grafana API for programmatic access

---

## Troubleshooting

### Metrics Not Appearing

**Problem**: No metrics in Grafana

**Solutions**:
1. Verify Prometheus is scraping: `http://localhost:9090/targets`
2. Check Daena backend is running: `curl http://localhost:8000/api/v1/system/health`
3. Verify metrics endpoint: `curl http://localhost:8000/api/v1/monitoring/memory/prometheus`
4. Check Prometheus data source in Grafana

### High Latency Alerts

**Problem**: Frequent latency alerts

**Solutions**:
1. Check system resources (CPU, Memory, Disk)
2. Review NBMF configuration for optimization
3. Check network connectivity
4. Verify device manager routing (CPU/GPU/TPU)

### Missing GPU Metrics

**Problem**: GPU panels show "No data"

**Solutions**:
1. Verify GPU is available: `nvidia-smi` (for NVIDIA)
2. Check `DeviceManager` configuration
3. Ensure GPU monitoring is enabled in backend
4. Verify Prometheus is scraping GPU metrics

### Alert Not Firing

**Problem**: Alert rule not triggering

**Solutions**:
1. Check alert rule syntax in Prometheus UI: **Status** → **Rules**
2. Verify metric names match exactly
3. Check `for` duration (alert must persist)
4. Verify Alertmanager is configured (if using)

### Dashboard Not Loading

**Problem**: Dashboard shows errors

**Solutions**:
1. Verify JSON syntax is valid
2. Check metric names match current backend
3. Update dashboard version if needed
4. Check Grafana logs: `docker logs grafana`

---

## Best Practices

### 1. Monitoring Strategy

- **Real-time**: Use 10-30s refresh for critical systems
- **Trends**: Use 5m+ refresh for historical analysis
- **Alerts**: Set appropriate thresholds to avoid alert fatigue

### 2. Alert Tuning

- Start with conservative thresholds
- Adjust based on actual system behavior
- Use different severities (critical, warning, info)
- Group related alerts

### 3. Dashboard Organization

- Group related metrics together
- Use consistent color schemes
- Add annotations for important events
- Document custom panels

### 4. Performance

- Limit dashboard refresh rate
- Use appropriate time ranges
- Avoid too many panels per dashboard
- Use data source caching

---

## Advanced Configuration

### Custom Metrics

Add custom metrics in `backend/routes/monitoring.py`:

```python
from memory_service.metrics import incr, observe

# Counter
incr("custom_metric_name")

# Latency
observe("custom_latency", duration_seconds)
```

### Custom Alerts

Add alerts in `config/prometheus/alerts.yml`:

```yaml
- alert: CustomAlert
  expr: daena_memory_metric{name="custom_metric"} > threshold
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Custom alert triggered"
    description: "Metric value: {{ $value }}"
```

### Dashboard Variables

Add variables in Grafana dashboard JSON:

```json
"templating": {
  "list": [
    {
      "name": "environment",
      "type": "query",
      "query": "label_values(up, environment)"
    }
  ]
}
```

---

## Integration Examples

### Slack Notifications

```yaml
# alertmanager.yml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#daena-alerts'
        title: 'Daena Alert'
        text: '{{ .CommonAnnotations.description }}'
```

### Email Notifications

```yaml
receivers:
  - name: 'email'
    email_configs:
      - to: 'admin@example.com'
        from: 'alerts@daena.ai'
        smarthost: 'smtp.example.com:587'
        auth_username: 'alerts@daena.ai'
        auth_password: 'password'
```

### PagerDuty Integration

```yaml
receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
```

---

## Related Documentation

- `docs/PERFORMANCE_TUNING_GUIDE.md` - Performance optimization
- `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` - Deployment guide
- `config/prometheus/alerts.yml` - Alert rules
- `config/grafana/dashboard.json` - Dashboard definition

---

## Support

For issues or questions:
1. Check this guide
2. Review Prometheus/Grafana logs
3. Verify backend metrics endpoint
4. Check GitHub issues

---

**Status**: ✅ **PRODUCTION READY**  
**Last Updated**: 2025-01-XX

