# Advanced Analytics & Insights Guide

**Status**: ✅ **PRODUCTION READY**  
**Date**: 2025-01-XX  
**Version**: 2.0.0

## Overview

Daena's Advanced Analytics & Insights system provides predictive analytics, cost optimization recommendations, performance trend analysis, and enhanced anomaly detection. This guide covers all features and how to use them.

---

## Table of Contents

1. [Features](#features)
2. [API Endpoints](#api-endpoints)
3. [Predictive Analytics](#predictive-analytics)
4. [Cost Optimization](#cost-optimization)
5. [Performance Trends](#performance-trends)
6. [Usage Examples](#usage-examples)
7. [Integration Guide](#integration-guide)

---

## Features

### 1. Predictive Analytics
- **Memory Usage Prediction**: Forecast memory usage for the next 7-30 days
- **Growth Rate Analysis**: Calculate memory growth trends
- **Confidence Scoring**: Assess prediction reliability
- **Automated Recommendations**: Get actionable insights

### 2. Cost Optimization
- **CAS Efficiency Analysis**: Identify opportunities to improve cache hit rates
- **Storage Compression**: Optimize NBMF compression settings
- **Access Pattern Optimization**: Improve read/write ratios
- **Device Selection**: Recommend GPU/TPU usage for cost savings
- **Data Lifecycle Management**: Enable aging policies

### 3. Performance Trend Analysis
- **Metric Tracking**: Monitor key performance indicators
- **Trend Detection**: Identify improving, stable, or degrading trends
- **Change Analysis**: Calculate percentage changes over time
- **Historical Data**: Maintain up to 30 days of history

### 4. Enhanced Anomaly Detection
- **Behavioral Anomalies**: Detect unusual agent activity
- **Statistical Analysis**: Z-score based detection
- **Severity Classification**: High, medium, low severity levels
- **Real-time Monitoring**: Continuous anomaly detection

---

## API Endpoints

### Base URL
All endpoints are under `/api/v1/analytics/`

### Authentication
All endpoints require authentication via `verify_monitoring_auth` (API key or JWT token).

---

### 1. Get Comprehensive Insights

**Endpoint**: `GET /api/v1/analytics/insights`

**Description**: Get all insights including predictions, recommendations, and trends.

**Response**:
```json
{
  "timestamp": "2025-01-XXT12:00:00",
  "memory_prediction": {
    "predicted_usage_gb": 45.2,
    "predicted_growth_rate_gb_per_day": 0.15,
    "confidence": 0.85,
    "timeframe_days": 7,
    "recommendations": [
      "Memory usage is growing at 0.15 GB/day. Consider enabling aging policies.",
      "Current usage is high. Consider archiving old data to L3 cold storage."
    ]
  },
  "cost_optimization": {
    "total_recommendations": 3,
    "total_potential_savings_usd": 125.50,
    "recommendations": [
      {
        "category": "CAS Efficiency",
        "current_cost_usd": 500.0,
        "potential_savings_usd": 75.0,
        "savings_percent": 15.0,
        "action": "Increase CAS hit rate by adjusting simhash_threshold",
        "priority": "high",
        "impact": "high"
      }
    ]
  },
  "performance_trends": {
    "nbmf_latency": {
      "current_value": 0.4,
      "trend": "improving",
      "change_percent": -12.5,
      "timeframe_days": 7,
      "data_points_count": 168
    }
  },
  "summary": {
    "high_priority_recommendations": 1,
    "total_potential_savings_usd": 125.50,
    "metrics_tracked": 5,
    "improving_metrics": 3,
    "degrading_metrics": 0
  }
}
```

---

### 2. Memory Usage Prediction

**Endpoint**: `GET /api/v1/analytics/memory/prediction?days_ahead=7`

**Parameters**:
- `days_ahead` (optional): Number of days to predict ahead (1-30, default: 7)

**Response**:
```json
{
  "predicted_usage_gb": 45.2,
  "predicted_growth_rate_gb_per_day": 0.15,
  "confidence": 0.85,
  "timeframe_days": 7,
  "recommendations": [
    "Memory usage is growing at 0.15 GB/day. Consider enabling aging policies."
  ]
}
```

**Example**:
```bash
curl -X GET "http://localhost:8000/api/v1/analytics/memory/prediction?days_ahead=14" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

### 3. Cost Optimization Recommendations

**Endpoint**: `GET /api/v1/analytics/cost/optimization`

**Response**:
```json
{
  "total_recommendations": 3,
  "total_potential_savings_usd": 125.50,
  "recommendations": [
    {
      "category": "CAS Efficiency",
      "current_cost_usd": 500.0,
      "potential_savings_usd": 75.0,
      "savings_percent": 15.0,
      "action": "Increase CAS hit rate by adjusting simhash_threshold",
      "priority": "high",
      "impact": "high"
    },
    {
      "category": "Storage Compression",
      "current_cost_usd": 50.0,
      "potential_savings_usd": 25.0,
      "savings_percent": 50.0,
      "action": "Optimize NBMF compression settings",
      "priority": "medium",
      "impact": "medium"
    }
  ]
}
```

**Recommendation Categories**:
- **CAS Efficiency**: Improve cache hit rates
- **Storage Compression**: Optimize NBMF compression
- **Access Pattern**: Optimize read/write ratios
- **Compute Device**: Use GPU/TPU for batch operations
- **Data Lifecycle**: Enable aging policies

---

### 4. Performance Trends

**Endpoint**: `GET /api/v1/analytics/performance/trends?metric_name=nbmf_latency&days=7`

**Parameters**:
- `metric_name` (optional): Specific metric name
- `days` (optional): Number of days to analyze (1-30, default: 7)

**Response (Single Metric)**:
```json
{
  "metric_name": "nbmf_latency",
  "current_value": 0.4,
  "trend": "improving",
  "change_percent": -12.5,
  "timeframe_days": 7,
  "data_points_count": 168
}
```

**Response (All Metrics)**:
```json
{
  "trends": {
    "nbmf_latency": {
      "current_value": 0.4,
      "trend": "improving",
      "change_percent": -12.5,
      "timeframe_days": 7,
      "data_points_count": 168
    },
    "cas_hit_rate": {
      "current_value": 0.75,
      "trend": "stable",
      "change_percent": 2.1,
      "timeframe_days": 7,
      "data_points_count": 168
    }
  },
  "total_metrics": 2
}
```

**Trend Values**:
- `improving`: Metric is getting better (lower latency, higher hit rate, etc.)
- `stable`: Metric is relatively constant
- `degrading`: Metric is getting worse

---

## Predictive Analytics

### Memory Usage Prediction

The system uses linear regression to predict future memory usage based on historical data.

**Algorithm**:
1. Collect hourly memory usage data points
2. Calculate growth rate (GB per day)
3. Predict future usage: `predicted = current + (growth_rate × days_ahead)`
4. Calculate confidence based on data consistency (coefficient of variation)

**Confidence Score**:
- **0.0-0.5**: Low confidence (high variance in data)
- **0.5-0.8**: Medium confidence
- **0.8-1.0**: High confidence (stable patterns)

**Recommendations**:
- Growth rate > 0.1 GB/day: Enable aging policies
- Predicted usage > 100 GB: Review data retention policies
- Current usage > 50 GB: Archive to L3 cold storage

---

## Cost Optimization

### Recommendation Types

#### 1. CAS Efficiency
**When**: CAS hit rate < 60%

**Action**: Increase CAS hit rate by:
- Adjusting `simhash_threshold` in NBMF config
- Improving deduplication logic
- Optimizing similarity search

**Potential Savings**: 10-30% of LLM costs

#### 2. Storage Compression
**When**: Compression ratio < 10×

**Action**: Optimize NBMF compression:
- Increase `zstd_level` (1-22)
- Enable quantization
- Adjust compression profiles

**Potential Savings**: 20-50% of storage costs

#### 3. Access Pattern
**When**: Read/write ratio < 2.0

**Action**: Optimize access patterns:
- Cache frequently read data in L1
- Batch write operations
- Use L1 for hot data

**Potential Savings**: 5-15% of total costs

#### 4. Compute Device
**When**: Using CPU for batch operations

**Action**: Use GPU/TPU for:
- Batch inference operations
- Large tensor operations
- Parallel processing

**Potential Savings**: 10-20% of compute costs

#### 5. Data Lifecycle
**When**: Memory usage > 20 GB

**Action**: Enable aging policies:
- Automatic compression
- Archive to L3 cold storage
- Delete old data

**Potential Savings**: 30-50% of storage costs

---

## Performance Trends

### Tracked Metrics

The system automatically tracks:
- `nbmf_latency`: NBMF encode/decode latency
- `cas_hit_rate`: CAS cache hit rate
- `memory_usage_gb`: Total memory usage
- `cost_per_day`: Daily costs
- `agent_efficiency`: Agent performance metrics

### Trend Analysis

**Algorithm**:
1. Collect hourly data points
2. Compare first half vs second half of time period
3. Calculate percentage change
4. Classify as improving, stable, or degrading

**Thresholds**:
- **Improving**: > 5% improvement
- **Stable**: -5% to +5% change
- **Degrading**: < -5% change

---

## Usage Examples

### Python Example

```python
import requests

# Get comprehensive insights
response = requests.get(
    "http://localhost:8000/api/v1/analytics/insights",
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)
insights = response.json()

# Memory prediction
prediction = insights["memory_prediction"]
print(f"Predicted usage: {prediction['predicted_usage_gb']:.2f} GB")
print(f"Growth rate: {prediction['predicted_growth_rate_gb_per_day']:.2f} GB/day")

# Cost optimization
recommendations = insights["cost_optimization"]["recommendations"]
for rec in recommendations:
    if rec["priority"] == "high":
        print(f"High priority: {rec['action']}")
        print(f"Potential savings: ${rec['potential_savings_usd']:.2f}")

# Performance trends
trends = insights["performance_trends"]
for metric, trend in trends.items():
    print(f"{metric}: {trend['trend']} ({trend['change_percent']:.1f}%)")
```

### JavaScript Example

```javascript
// Get insights
const response = await fetch('http://localhost:8000/api/v1/analytics/insights', {
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN'
  }
});
const insights = await response.json();

// Display memory prediction
const prediction = insights.memory_prediction;
console.log(`Predicted usage: ${prediction.predicted_usage_gb.toFixed(2)} GB`);

// Display cost recommendations
insights.cost_optimization.recommendations.forEach(rec => {
  if (rec.priority === 'high') {
    console.log(`${rec.action}: Save $${rec.potential_savings_usd.toFixed(2)}`);
  }
});
```

---

## Integration Guide

### Recording Data Points

To enable predictions and trends, record data points:

```python
from backend.services.advanced_analytics import advanced_analytics_service

# Record memory usage
advanced_analytics_service.record_memory_usage(usage_gb=42.5)

# Record cost
advanced_analytics_service.record_cost(cost_usd=125.50)

# Record performance metric
advanced_analytics_service.record_performance_metric(
    metric_name="nbmf_latency",
    value=0.4
)
```

### Automatic Integration

The system can automatically record metrics from:
- Memory service metrics (`memory_service/metrics.py`)
- Monitoring endpoints (`/api/v1/monitoring/memory`)
- System metrics (`/api/v1/system/metrics`)

### Scheduled Updates

Set up a cron job or scheduled task to:
1. Fetch current metrics
2. Record data points
3. Generate insights

**Example**:
```python
import schedule
import time
from backend.services.advanced_analytics import advanced_analytics_service
from memory_service.metrics import snapshot

def update_analytics():
    metrics = snapshot()
    
    # Record memory usage (convert bytes to GB)
    memory_bytes = metrics.get("total_memory_bytes", 0)
    memory_gb = memory_bytes / (1024 ** 3)
    advanced_analytics_service.record_memory_usage(memory_gb)
    
    # Record cost
    cost = metrics.get("total_cost_usd", 0.0)
    advanced_analytics_service.record_cost(cost)
    
    # Record performance metrics
    advanced_analytics_service.record_performance_metric(
        "nbmf_latency",
        metrics.get("nbmf_encode_p95_ms", 0.0)
    )

# Schedule hourly updates
schedule.every().hour.do(update_analytics)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Best Practices

1. **Regular Monitoring**: Check insights daily or weekly
2. **Act on High-Priority Recommendations**: Focus on high-impact, high-priority items
3. **Track Trends**: Monitor performance trends to catch issues early
4. **Maintain History**: Keep at least 7 days of history for accurate predictions
5. **Validate Predictions**: Compare predictions with actual usage to improve accuracy

---

## Related Documentation

- `docs/ADVANCED_ANALYTICS.md` - Basic analytics features
- `docs/MONITORING_GUIDE.md` - Monitoring setup
- `docs/PERFORMANCE_TUNING_GUIDE.md` - Performance optimization

---

**Status**: ✅ **PRODUCTION READY**  
**Last Updated**: 2025-01-XX

