# Daena Deployment Guide

**Date**: 2025-01-XX  
**Status**: Production-Ready  
**Audience**: DevOps Engineers, System Administrators

---

## Overview

This guide provides step-by-step instructions for deploying Daena AI VP to staging and production environments.

---

## Prerequisites

### Required Tools
- **Docker**: 20.10+ ([Install Guide](https://docs.docker.com/get-docker/))
- **Docker Compose**: 2.0+ ([Install Guide](https://docs.docker.com/compose/install/))
- **Git**: For cloning repository
- **Python**: 3.10+ (for running tests locally)

### Required Accounts
- **GitHub**: For accessing repository
- **Docker Registry**: (Optional) For pushing images
  - GitHub Container Registry (ghcr.io)
  - Docker Hub
  - AWS ECR
  - Google Container Registry

---

## Quick Start

### Staging Deployment

**Linux/Mac:**
```bash
chmod +x scripts/deploy_staging.sh
./scripts/deploy_staging.sh
```

**Windows:**
```powershell
.\scripts\deploy_staging.ps1
```

### Production Deployment

**Linux/Mac:**
```bash
chmod +x scripts/deploy_production.sh
./scripts/deploy_production.sh
```

---

## Detailed Deployment Steps

### 1. Pre-Deployment Setup

#### Clone Repository
```bash
git clone https://github.com/Masoud-Masoori/daena.git
cd daena
```

#### Create Environment Files

**Staging:**
```bash
cp .env.production.example .env.staging
# Edit .env.staging with staging-specific values
```

**Production:**
```bash
cp .env.production.example .env.production
# Edit .env.production with production values
```

#### Required Environment Variables

See `docs/GO_LIVE_CHECKLIST.md` for complete list.

**Critical Variables:**
```bash
# Authentication
JWT_SECRET_KEY=<strong-random-key>
CSRF_SECRET_KEY=<strong-random-key>

# Database
DATABASE_URL=postgresql://user:pass@host:5432/daena

# AI Provider (at least one)
OPENAI_API_KEY=<your-key>

# Billing (if enabled)
BILLING_ENABLED=true
STRIPE_SECRET_KEY=<stripe-key>

# Environment
ENVIRONMENT=production  # or staging
LOG_LEVEL=INFO
```

---

### 2. Staging Deployment

#### Step-by-Step

1. **Pre-Deployment Checks**
   - Verify `.env.staging` exists
   - Ensure Docker is running
   - Check docker-compose availability

2. **Run Tests**
   - Automated pytest suite
   - Aborts if tests fail

3. **Build Docker Image**
   - Builds image with staging tag
   - Tags for registry push

4. **Deploy Services**
   - Starts services with docker-compose
   - Uses `docker-compose.staging.yml` if available

5. **Health Checks**
   - Waits up to 60 seconds
   - Tests health endpoints

6. **Smoke Tests**
   - Validates critical endpoints
   - Reports deployment status

#### Manual Deployment

If you prefer manual deployment:

```bash
# Build image
docker build -t daena:staging .

# Start services
docker-compose -f docker-compose.staging.yml --env-file .env.staging up -d

# Check logs
docker-compose -f docker-compose.staging.yml logs -f

# Verify health
curl https://staging.daena.ai/api/v1/slo/health
```

---

### 3. Production Deployment

#### Step-by-Step

1. **Pre-Deployment Checks**
   - Verify `.env.production` exists
   - Confirm production deployment (requires confirmation)

2. **Staging Verification**
   - Confirm staging has been tested

3. **Run Full Test Suite**
   - Complete pytest with coverage
   - Aborts on failure

4. **Build & Tag Images**
   - Builds production image
   - Tags with commit hash for traceability

5. **Push to Registry**
   - Pushes image to Docker registry
   - Multiple tags (latest, commit hash, production)

6. **Create Backup**
   - Backs up production database
   - Stores in `backups/` directory

7. **Deploy Services**
   - Zero-downtime rolling update
   - Automatic rollback on failure

8. **Health Checks**
   - Extended timeout (120 seconds)
   - Multiple health endpoint checks

9. **Comprehensive Smoke Tests**
   - Tests all critical endpoints
   - Validates SLO metrics
   - Automatic rollback on critical failures

#### Manual Production Deployment

```bash
# Build production image
docker build -t ghcr.io/masoud-masoori/daena:production .

# Tag with commit hash
COMMIT_HASH=$(git rev-parse --short HEAD)
docker tag ghcr.io/masoud-masoori/daena:production \
           ghcr.io/masoud-masoori/daena:prod-$COMMIT_HASH

# Push to registry
docker push ghcr.io/masoud-masoori/daena:production
docker push ghcr.io/masoud-masoori/daena:prod-$COMMIT_HASH

# Deploy with docker-compose
docker-compose -f docker-compose.production.yml \
               --env-file .env.production \
               up -d --no-deps --build app

# Monitor
docker-compose -f docker-compose.production.yml logs -f app
```

---

## Docker Compose Files

### Staging (`docker-compose.staging.yml`)

**Features:**
- Simplified configuration
- Shorter data retention (7 days)
- Staging-specific resource limits
- Optional monitoring (Prometheus/Grafana)

**Usage:**
```bash
docker-compose -f docker-compose.staging.yml --env-file .env.staging up -d
```

### Production (`docker-compose.production.yml`)

**Features:**
- Full resource allocation
- Extended data retention
- Production monitoring enabled
- High availability configuration

**Usage:**
```bash
docker-compose -f docker-compose.production.yml --env-file .env.production up -d
```

---

## Health Checks & Monitoring

### Health Endpoints

**Basic Health:**
```bash
curl https://daena.ai/api/v1/slo/health
```

**Council Health:**
```bash
curl -H "X-API-Key: $API_KEY" \
     https://daena.ai/api/v1/health/council
```

**Metrics Summary:**
```bash
curl -H "X-API-Key: $API_KEY" \
     https://daena.ai/api/v1/monitoring/metrics/summary
```

**SLO Metrics:**
```bash
curl -H "X-API-Key: $API_KEY" \
     https://daena.ai/api/v1/slo/metrics
```

### Monitoring Dashboards

**Prometheus:**
- URL: `http://localhost:9090`
- Metrics endpoint: `/api/v1/monitoring/metrics/prometheus`

**Grafana:**
- URL: `http://localhost:3000`
- Default credentials: `admin` / `admin` (change in production)

---

## Troubleshooting

### Common Issues

#### 1. Docker Build Fails

**Error**: `ERROR: failed to solve`

**Solution**:
- Check Docker daemon is running: `docker info`
- Clear Docker cache: `docker builder prune`
- Verify Dockerfile syntax

#### 2. Health Checks Fail

**Error**: Health check timeout

**Solution**:
- Check service logs: `docker-compose logs app`
- Verify environment variables
- Check port availability: `netstat -an | grep 8000`
- Increase timeout in deployment script

#### 3. Database Connection Fails

**Error**: `connection refused` or `authentication failed`

**Solution**:
- Verify `DATABASE_URL` in `.env` file
- Check database service is running: `docker-compose ps mongodb`
- Verify credentials
- Check network connectivity

#### 4. Registry Push Fails

**Error**: `unauthorized: authentication required`

**Solution**:
- Login to registry: `docker login ghcr.io`
- Verify credentials
- Check registry permissions

---

## Rollback Procedure

### Automatic Rollback

Deployment scripts automatically rollback on:
- Health check failure
- Multiple smoke test failures
- Service start failure

### Manual Rollback

```bash
# Stop current deployment
docker-compose -f docker-compose.production.yml down

# Pull previous image
docker pull ghcr.io/masoud-masoori/daena:prod-<previous-commit>

# Start with previous image
docker-compose -f docker-compose.production.yml \
               --env-file .env.production \
               up -d

# Verify
curl https://daena.ai/api/v1/slo/health
```

---

## Backup & Recovery

### Database Backup

**Manual Backup:**
```bash
docker-compose exec mongodb mongodump \
    --archive=/data/backup_$(date +%Y%m%d).archive
```

**Automated Backup:**
- Backups created before production deployments
- Stored in `backups/` directory
- Naming: `production_backup_YYYYMMDD_HHMMSS.tar.gz`

### Recovery

```bash
# Restore from backup
gunzip -c backups/production_backup_YYYYMMDD_HHMMSS.tar.gz | \
docker-compose exec -T mongodb mongorestore --archive
```

---

## Post-Deployment

### Monitoring Checklist

- [ ] Health endpoints responding
- [ ] Council structure valid (8×6)
- [ ] Metrics updating in real-time
- [ ] Error rates within acceptable range
- [ ] Latency within SLO targets
- [ ] No memory leaks
- [ ] Database connections stable

### Verification Tests

**Run Full Test Suite:**
```bash
pytest -v --tb=short
```

**E2E Tests:**
```bash
pytest tests/e2e/ -v
```

**Performance Tests:**
```bash
python Tools/daena_performance_test.py
```

---

## Security Considerations

### Secrets Management

- ✅ Never commit `.env.production` to git
- ✅ Use environment variables or secret managers
- ✅ Rotate keys regularly
- ✅ Use different keys for staging/production

### Network Security

- ✅ Use HTTPS in production
- ✅ Enable firewall rules
- ✅ Restrict database access
- ✅ Use VPN for admin access

### Access Control

- ✅ Enable JWT authentication
- ✅ Use role-based access control
- ✅ Enable CSRF protection
- ✅ Monitor access logs

---

## Scaling

### Horizontal Scaling

**Multiple Instances:**
```yaml
services:
  app:
    deploy:
      replicas: 3
```

**Load Balancer:**
- Use Nginx or Traefik
- Configure health checks
- Enable sticky sessions if needed

### Vertical Scaling

**Resource Limits:**
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 16G
```

---

## Maintenance

### Updates

1. Pull latest code: `git pull`
2. Run tests: `pytest`
3. Rebuild image: `docker build -t daena:latest .`
4. Deploy: Use deployment scripts

### Logs

**View Logs:**
```bash
docker-compose logs -f app
docker-compose logs -f mongodb
docker-compose logs -f redis
```

**Log Rotation:**
- Configured in `backend/config/logging_config.py`
- 10MB max size, 5 backups

---

## Support

### Documentation

- **Go-Live Checklist**: `docs/GO_LIVE_CHECKLIST.md`
- **Production Guide**: `docs/PRODUCTION_DEPLOYMENT_GUIDE.md`
- **System Blueprint**: `docs/DAENA_STRUCTURE_ANALYSIS_AND_UPGRADE_PLAN.md`

### Issues

- GitHub Issues: `https://github.com/Masoud-Masoori/daena/issues`
- Email: [Your support email]

---

**Last Updated**: 2025-01-XX  
**Status**: Production-Ready

