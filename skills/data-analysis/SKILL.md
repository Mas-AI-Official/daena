---
name: data-analysis
description: "Analyze data from files, databases, or APIs. Generate summaries, charts, trends, and insights. Use when user provides data or asks for analysis."
department: Finance
cost_tier: medium
requires: {}
---

# Data Analysis Skill

Analyze structured data and produce actionable insights.

## When to Use

- CSV/JSON/Excel file analysis
- Database query results interpretation
- Financial data analysis (costs, revenue, trends)
- Log file analysis (errors, patterns, anomalies)
- API response data processing

## Process

1. **Load data**: Read file or query results
2. **Profile**: Row count, column types, null rates, distributions
3. **Clean**: Handle missing values, outliers, type issues
4. **Analyze**: Compute statistics, find patterns, identify trends
5. **Visualize**: Describe charts/tables (or generate if tools available)
6. **Summarize**: Key findings + recommendations

## Common Analysis Patterns

### Financial
```
- Total, average, median, min, max per category
- Month-over-month and year-over-year trends
- Top N by revenue/cost
- Cost breakdown by category
```

### Log Analysis
```
- Error frequency and distribution
- Peak hours/days for issues
- Most common error types
- Correlation between events
```

### Performance
```
- P50, P95, P99 latency
- Throughput over time
- Resource utilization trends
- Bottleneck identification
```
