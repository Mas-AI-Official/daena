# Daena AI VP - Docker Cloud Deployment Guide

**Version**: 2.0.0  
**Status**: ✅ Production Ready

---

## Quick Start

### Development (Local)
```bash
docker-compose up -d
```

### Production (Cloud Profile)
```bash
docker-compose -f docker-compose.cloud.yml up -d
```

---

## Profiles

### 1. Development Profile (`docker-compose.yml`)
- Basic services: app, redis, mongodb
- Optional: prometheus, grafana
- Good for local development

### 2. Cloud Production Profile (`docker-compose.cloud.yml`)
- Full monitoring stack
- Production-ready resource limits
- Health checks enabled
- Distributed tracing (Jaeger)
- Log aggregation (Elasticsearch)
- Real-time metrics stream enabled

---

## Environment Variables

### Compute Device Configuration
```bash
COMPUTE_PREFER=auto          # auto, cpu, gpu, tpu
COMPUTE_ALLOW_TPU=true       # Enable TPU support
COMPUTE_TPU_BATCH_FACTOR=128 # TPU batch multiplier
```

### Monitoring & Observability
```bash
DAENA_TRACING_ENABLED=true           # Enable distributed tracing
DAENA_MQ_USE_REDIS=true              # Use Redis for message queue
DAENA_REALTIME_METRICS_ENABLED=true  # Enable real-time metrics stream
```

### Database
```bash
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=your-secure-password
```

### Grafana
```bash
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your-secure-password
GRAFANA_ROOT_URL=http://localhost:3000
```

---

## Building with TPU Support

To build Docker image with TPU (JAX) support:

```bash
docker build --build-arg ENABLE_TPU=true -t daena-ai-vp:latest .
```

---

## Services & Ports

| Service | Port | URL |
|---------|------|-----|
| Daena App | 8000 | http://localhost:8000 |
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3000 | http://localhost:3000 |
| Jaeger UI | 16686 | http://localhost:16686 |
| Elasticsearch | 9200 | http://localhost:9200 |
| Redis | 6379 | localhost:6379 |
| MongoDB | 27017 | localhost:27017 |

---

## Health Checks

### Basic Health
```bash
curl http://localhost:8000/api/v1/health/
```

### Council Structure Health
```bash
curl -H "X-API-Key: daena_secure_key_2025" \
     http://localhost:8000/api/v1/health/council
```

Expected response:
```json
{
  "status": "healthy",
  "departments": 8,
  "agents": 48,
  "roles_per_department": 6,
  "validation": {
    "structure_valid": true
  }
}
```

---

## Monitoring Dashboards

### Grafana Dashboards
Access at: http://localhost:3000

Default credentials:
- Username: `admin`
- Password: `secret` (change in production!)

### Prometheus Metrics
Access at: http://localhost:9090

Key metrics:
- `daena_council_departments` - Number of departments
- `daena_council_agents` - Number of agents
- `daena_nbmf_encode_latency_p95` - NBMF encode latency
- `daena_message_bus_queue_depth` - Message queue depth

---

## Real-Time Metrics Stream

The cloud profile enables real-time metrics streaming via SSE:

```bash
curl http://localhost:8000/api/v1/events/stream
```

Streams:
- Council counts (departments, agents)
- NBMF encode/decode latencies
- Message bus queue depth
- DeviceManager status

---

## Production Deployment

### 1. Set Environment Variables
Create `.env.production`:
```bash
COMPUTE_PREFER=auto
COMPUTE_ALLOW_TPU=true
MONGO_ROOT_PASSWORD=secure-password-here
GRAFANA_ADMIN_PASSWORD=secure-password-here
```

### 2. Deploy with Cloud Profile
```bash
docker-compose -f docker-compose.cloud.yml --env-file .env.production up -d
```

### 3. Verify Deployment
```bash
# Check all services are healthy
docker-compose -f docker-compose.cloud.yml ps

# Check logs
docker-compose -f docker-compose.cloud.yml logs -f app

# Verify council structure
curl -H "X-API-Key: your-api-key" \
     http://localhost:8000/api/v1/health/council
```

---

## Resource Limits

Cloud profile includes resource limits:

| Service | CPU Limit | Memory Limit |
|---------|-----------|--------------|
| app | 8 cores | 8GB |
| redis | - | 2GB |
| mongodb | - | 4GB |
| prometheus | - | 2GB |
| grafana | - | 512MB |

Adjust in `docker-compose.cloud.yml` if needed.

---

## Scaling

To scale the application:

```bash
docker-compose -f docker-compose.cloud.yml up -d --scale app=3
```

Note: Ensure Redis/MongoDB are properly configured for multiple instances.

---

## Backup & Restore

### MongoDB Backup
```bash
docker exec daena-mongodb mongodump --out=/data/backup
```

### Restore
```bash
docker exec daena-mongodb mongorestore /data/backup
```

---

## Troubleshooting

### Services Not Starting
```bash
# Check logs
docker-compose -f docker-compose.cloud.yml logs app

# Check health
docker-compose -f docker-compose.cloud.yml ps
```

### Council Structure Invalid
```bash
# Seed database
docker exec daena-app python backend/scripts/seed_6x8_council.py
```

### Port Conflicts
Update ports in `docker-compose.cloud.yml`:
```yaml
ports:
  - "8001:8000"  # Use 8001 instead of 8000
```

---

**For more details, see**: `docs/PRODUCTION_DEPLOYMENT_GUIDE.md`

