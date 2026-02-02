# Production Deployment Guide

**Date**: 2025-01-XX  
**Status**: ✅ **PRODUCTION-READY**

---

## Overview

This guide provides step-by-step instructions for deploying Daena AI VP to production environments, including Docker, cloud platforms, and on-premise deployments.

---

## Prerequisites

### System Requirements
- **CPU**: 4+ cores (8+ recommended)
- **Memory**: 8GB+ RAM (16GB+ recommended)
- **Storage**: 50GB+ available space
- **OS**: Linux (Ubuntu 20.04+, Debian 11+, or similar)
- **Docker**: 20.10+ (for containerized deployment)
- **Python**: 3.10+ (for direct deployment)

### Software Dependencies
- Docker & Docker Compose
- Python 3.10+
- Redis (for message queue)
- MongoDB (optional, for advanced analytics)
- PostgreSQL/MySQL (optional, for production database)

---

## Quick Start (Docker)

### 1. Clone Repository
```bash
git clone https://github.com/Masoud-Masoori/daena.git
cd daena
```

### 2. Configure Environment
```bash
# Copy example environment file
cp .env.production.example .env.production

# Edit with your values
nano .env.production
```

**Critical Variables to Set**:
- `SECRET_KEY` - Generate strong secret key
- `DAENA_MEMORY_AES_KEY` - Generate 32-byte base64 key
- `OPENAI_API_KEY` - Your OpenAI API key
- `DATABASE_URL` - Database connection string

### 3. Generate Keys
```bash
# Generate AES key
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Start Services
```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f app

# Check health
docker-compose ps
```

### 5. Verify Deployment
```bash
# Check API health
curl http://localhost:8000/api/v1/system/summary

# Check metrics
curl http://localhost:8000/monitoring/memory

# Access Swagger UI
open http://localhost:8000/docs
```

---

## Production Configuration

### Environment Variables

See `.env.production.example` for complete list.

**Required**:
- `ENVIRONMENT=production`
- `DEBUG=false`
- `SECRET_KEY` (strong, random)
- `DAENA_MEMORY_AES_KEY` (32 bytes, base64)
- `OPENAI_API_KEY` (or other LLM provider)

**Recommended**:
- `COMPUTE_PREFER=auto` (auto-select CPU/GPU/TPU)
- `DAENA_READ_MODE=nbmf` (use NBMF memory)
- `PROMETHEUS_ENABLED=true` (enable metrics)
- `RATE_LIMIT_ENABLED=true` (enable rate limiting)

### Security Configuration

1. **Secrets Management**:
   ```bash
   # Use AWS Secrets Manager
   aws secretsmanager get-secret-value --secret-id daena/production
   
   # Or Azure Key Vault
   az keyvault secret show --vault-name daena-vault --name daena-key
   ```

2. **Key Rotation**:
   ```bash
   # Rotate encryption key
   python Tools/daena_key_rotate.py --new-key <new-key> --kms-log .kms/kms_log.jsonl
   ```

3. **SSL/TLS**:
   ```bash
   # Use Let's Encrypt
   certbot --nginx -d daena.mas-ai.co
   ```

---

## Docker Deployment

### Build Image
```bash
docker build -t daena:2.0.0 .
docker tag daena:2.0.0 daena:latest
```

### Run Container
```bash
docker run -d \
  --name daena \
  --env-file .env.production \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --restart always \
  daena:latest
```

### Docker Compose
```bash
# Start all services
docker-compose up -d

# Scale services
docker-compose up -d --scale app=3

# Update services
docker-compose pull
docker-compose up -d
```

---

## Cloud Deployment

### AWS (EC2/ECS/EKS)

#### EC2 Deployment
```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

# Clone and deploy
git clone https://github.com/Masoud-Masoori/daena.git
cd daena
docker-compose up -d
```

#### ECS Deployment
```bash
# Build and push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker build -t daena:2.0.0 .
docker tag daena:2.0.0 <account>.dkr.ecr.<region>.amazonaws.com/daena:2.0.0
docker push <account>.dkr.ecr.<region>.amazonaws.com/daena:2.0.0

# Deploy to ECS
aws ecs create-service --cluster daena-cluster --service-name daena --task-definition daena-task
```

#### EKS Deployment
```bash
# Build and push to ECR (same as above)

# Deploy to Kubernetes
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### Azure (Container Instances/App Service)

#### Container Instances
```bash
# Build and push to ACR
az acr build --registry <registry> --image daena:2.0.0 .

# Deploy
az container create \
  --resource-group daena-rg \
  --name daena \
  --image <registry>.azurecr.io/daena:2.0.0 \
  --environment-variables @.env.production
```

#### App Service
```bash
# Deploy via Azure CLI
az webapp create --resource-group daena-rg --plan daena-plan --name daena-app
az webapp config container set --name daena-app --docker-custom-image-name <registry>.azurecr.io/daena:2.0.0
```

### Google Cloud (GKE/Cloud Run)

#### Cloud Run
```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/<project>/daena:2.0.0

# Deploy
gcloud run deploy daena \
  --image gcr.io/<project>/daena:2.0.0 \
  --platform managed \
  --region us-central1 \
  --set-env-vars-from-file .env.production
```

#### GKE
```bash
# Build and push (same as above)

# Deploy to GKE
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

---

## Monitoring & Observability

### Prometheus Metrics
```bash
# Access metrics endpoint
curl http://localhost:8000/monitoring/memory/prometheus

# Configure Prometheus
# Add to prometheus.yml:
scrape_configs:
  - job_name: 'daena'
    static_configs:
      - targets: ['localhost:8000']
```

### Grafana Dashboards
```bash
# Access Grafana
open http://localhost:3000

# Import dashboard from:
# docs/grafana_dashboard.json
```

### Health Checks
```bash
# System health
curl http://localhost:8000/api/v1/system/summary

# Memory health
curl http://localhost:8000/monitoring/memory

# Agent health
curl http://localhost:8000/monitoring/agents
```

---

## Backup & Recovery

### Automated Backups
```bash
# Configure backup schedule in .env.production
BACKUP_ENABLED=true
BACKUP_SCHEDULE=0 2 * * *  # Daily at 2 AM
BACKUP_RETENTION_DAYS=30
```

### Manual Backup
```bash
# Backup database
sqlite3 data/daena.db ".backup backup/daena_$(date +%Y%m%d).db"

# Backup memory stores
tar -czf backup/memory_$(date +%Y%m%d).tar.gz .l2_store .l2q

# Backup configuration
tar -czf backup/config_$(date +%Y%m%d).tar.gz config/
```

### Recovery
```bash
# Restore database
sqlite3 data/daena.db < backup/daena_20250101.db

# Restore memory stores
tar -xzf backup/memory_20250101.tar.gz

# Restore configuration
tar -xzf backup/config_20250101.tar.gz
```

---

## Scaling

### Horizontal Scaling
```bash
# Docker Compose
docker-compose up -d --scale app=3

# Kubernetes
kubectl scale deployment daena --replicas=3
```

### Vertical Scaling
```yaml
# docker-compose.yml
services:
  app:
    cpus: 8
    memory: 16G
```

### Load Balancing
```nginx
# nginx.conf
upstream daena {
    least_conn;
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}

server {
    listen 80;
    server_name daena.mas-ai.co;
    
    location / {
        proxy_pass http://daena;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Security Hardening

### 1. Firewall Configuration
```bash
# Allow only necessary ports
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw enable
```

### 2. SSL/TLS
```bash
# Use Let's Encrypt
certbot --nginx -d daena.mas-ai.co

# Or use existing certificates
cp /path/to/cert.crt /etc/ssl/certs/daena.crt
cp /path/to/key.key /etc/ssl/private/daena.key
```

### 3. Rate Limiting
```bash
# Configure in .env.production
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_REQUESTS_PER_HOUR=1000
```

### 4. Key Rotation
```bash
# Rotate encryption key
python Tools/daena_key_rotate.py \
  --new-key <new-key> \
  --kms-log .kms/kms_log.jsonl \
  --manifest-dir .kms/manifests
```

---

## Troubleshooting

### Common Issues

1. **Database Connection Error**:
   ```bash
   # Check database file permissions
   ls -la data/daena.db
   chmod 644 data/daena.db
   ```

2. **Memory Store Errors**:
   ```bash
   # Check store permissions
   ls -la .l2_store .l2q
   chmod -R 755 .l2_store .l2q
   ```

3. **API Not Responding**:
   ```bash
   # Check logs
   docker-compose logs app
   tail -f logs/daena.log
   ```

4. **High Memory Usage**:
   ```bash
   # Check memory metrics
   curl http://localhost:8000/monitoring/memory
   
   # Restart services
   docker-compose restart
   ```

---

## Performance Tuning

### Database Optimization
```sql
-- SQLite optimizations
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
PRAGMA temp_store=MEMORY;
```

### Memory Optimization
```bash
# Configure in .env.production
DAENA_READ_MODE=nbmf
NBMF_ENABLED=true
CAS_ENABLED=true
```

### Compute Optimization
```bash
# Use GPU/TPU
COMPUTE_PREFER=gpu
JAX_PLATFORM_NAME=cuda
CUDA_VISIBLE_DEVICES=0
```

---

## Maintenance

### Regular Tasks
- **Daily**: Check logs for errors
- **Weekly**: Review metrics and performance
- **Monthly**: Rotate encryption keys
- **Quarterly**: Security audit

### Updates
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build
docker-compose up -d
```

---

## Support

For issues or questions:
- **Documentation**: `docs/` directory
- **GitHub Issues**: https://github.com/Masoud-Masoori/daena/issues
- **Email**: masoud.masoori@mas-ai.co

---

**Status**: ✅ **PRODUCTION-READY**  
**Version**: 2.0.0  
**Last Updated**: 2025-01-XX
