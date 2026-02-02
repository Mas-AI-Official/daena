# Daena Quick Start - Deployment Guide

**Get Daena running in 5 minutes**

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- Docker & Docker Compose (optional, for full stack)

### Option 1: Local Python (Fastest)

```bash
# 1. Clone repository
git clone https://github.com/Masoud-Masoori/daena.git
cd daena

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.production.example .env  # Edit with your values

# 5. Seed database
python backend/scripts/seed_6x8_council.py

# 6. Start backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 7. Access
# Dashboard: http://localhost:8000/dashboard
# API Docs: http://localhost:8000/docs
```

### Option 2: Docker Compose (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/Masoud-Masoori/daena.git
cd daena

# 2. Create environment file
cp .env.production.example .env
# Edit .env with your configuration

# 3. Start all services
docker-compose up -d

# 4. Seed database (first time only)
docker-compose exec app python backend/scripts/seed_6x8_council.py

# 5. Access
# Dashboard: http://localhost:8000/dashboard
# API Docs: http://localhost:8000/docs
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```

---

## 🌐 Staging Deployment

### Prerequisites
- Docker installed
- Docker registry access (optional)
- Staging server access

### Automated Deployment

**Linux/Mac:**
```bash
chmod +x scripts/deploy_staging.sh
./scripts/deploy_staging.sh
```

**Windows:**
```powershell
.\scripts\deploy_staging.ps1
```

### Manual Deployment

```bash
# 1. Create staging environment file
cp .env.production.example .env.staging
# Edit .env.staging with staging values

# 2. Build image
docker build -t daena:staging .

# 3. Deploy
docker-compose -f docker-compose.staging.yml \
               --env-file .env.staging \
               up -d

# 4. Verify
curl https://staging.daena.ai/api/v1/slo/health
```

---

## 🔥 Production Deployment

### Prerequisites
- ✅ Staging deployment tested and verified
- ✅ Production environment configured
- ✅ Database backup strategy in place
- ✅ Monitoring dashboards set up

### Automated Deployment

```bash
chmod +x scripts/deploy_production.sh
./scripts/deploy_production.sh
```

**Features:**
- ✅ Safety confirmations
- ✅ Automatic database backup
- ✅ Zero-downtime deployment
- ✅ Automatic rollback on failure
- ✅ Comprehensive smoke tests

---

## ⚙️ Environment Configuration

### Minimum Required Variables

```bash
# Authentication
JWT_SECRET_KEY=<generate-with-openssl-or-python>
CSRF_SECRET_KEY=<generate-with-openssl-or-python>

# Database
DATABASE_URL=sqlite:///daena.db  # or PostgreSQL

# AI Provider (at least one)
OPENAI_API_KEY=<your-key>
```

### Generate Secrets

```bash
# Generate JWT secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate AES key
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Full Configuration Template

See `.env.production.example` for complete list of variables.

---

## 🔍 Verify Installation

### Health Checks

```bash
# Basic health
curl http://localhost:8000/api/v1/slo/health

# Council structure (requires API key)
curl -H "X-API-Key: daena_secure_key_2025" \
     http://localhost:8000/api/v1/health/council

# Metrics summary
curl -H "X-API-Key: daena_secure_key_2025" \
     http://localhost:8000/api/v1/monitoring/metrics/summary
```

### Expected Results

**Health Check:**
```json
{"status": "ok", "timestamp": "2025-01-XX..."}
```

**Council Health:**
```json
{
  "success": true,
  "structure_valid": true,
  "departments": 8,
  "agents": 48
}
```

---

## 📊 Access Points

### Local Development

- **Dashboard**: http://localhost:8000/dashboard
- **Enhanced Dashboard**: http://localhost:8000/enhanced-dashboard
- **Daena Office**: http://localhost:8000/daena-office
- **Command Center**: http://localhost:8000/command-center
- **API Docs**: http://localhost:8000/docs
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Monitoring (Docker Compose)

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
  - Default: admin/admin (change in production!)

---

## 🛠️ Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process or change port
export PORT=8001
python -m uvicorn backend.main:app --port 8001
```

### Database Not Seeded

```bash
# Seed council structure
python backend/scripts/seed_6x8_council.py

# Or with Docker
docker-compose exec app python backend/scripts/seed_6x8_council.py
```

### Docker Services Not Starting

```bash
# Check logs
docker-compose logs app
docker-compose logs mongodb
docker-compose logs redis

# Restart services
docker-compose restart

# Rebuild containers
docker-compose up -d --build
```

---

## 📚 Next Steps

1. **Configure Environment**
   - Edit `.env` file with your API keys
   - Set up database connection
   - Configure compute preferences

2. **Explore Dashboards**
   - Visit http://localhost:8000/dashboard
   - Check real-time metrics
   - Test council rounds

3. **Read Documentation**
   - `docs/DEPLOYMENT_GUIDE.md` - Full deployment guide
   - `docs/GO_LIVE_CHECKLIST.md` - Production readiness
   - `docs/DAENA_STRUCTURE_ANALYSIS_AND_UPGRADE_PLAN.md` - System blueprint

4. **Deploy to Staging**
   - Follow staging deployment guide
   - Test for 24 hours
   - Monitor metrics

---

## 🔗 Resources

- **GitHub**: https://github.com/Masoud-Masoori/daena
- **Documentation**: `docs/` directory
- **API Reference**: http://localhost:8000/docs
- **Issues**: https://github.com/Masoud-Masoori/daena/issues

---

**Last Updated**: 2025-01-XX  
**Status**: Production-Ready

