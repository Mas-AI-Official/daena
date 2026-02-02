# Production Environment Guide

**Date**: 2025-12-13  
**Status**: ✅ Ready for Production

---

## Overview

This guide covers deploying Daena to production with proper authentication, security, and monitoring.

---

## Prerequisites

- Production server with Python 3.10+
- Reverse proxy (Caddy/Nginx) for HTTPS
- Domain name (optional but recommended)
- SSL certificate (Let's Encrypt recommended)

---

## Environment Variables

### Required for Production

```bash
# Authentication (REQUIRED in production)
DISABLE_AUTH=0
JWT_SECRET_KEY=<generate-strong-secret>
CAPSULE_SECRET_KEY=<generate-strong-secret>

# Database
DATABASE_URL=sqlite:///./data/daena_prod.db

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/daena_prod.log

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# CORS (adjust for your domain)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Automation (if enabled)
AUTOMATION_SAFE_MODE=1
AUTOMATION_ALLOWED_DOMAINS=yourdomain.com,api.yourdomain.com
AUTOMATION_ENABLE_BROWSER=0  # Disable in production unless needed
AUTOMATION_ENABLE_DESKTOP=0  # Disable in production
```

### Optional (Cloud LLMs)

```bash
# Cloud LLM APIs (optional)
ENABLE_CLOUD_LLM=1
OPENAI_API_KEY=<your-key>
GEMINI_API_KEY=<your-key>
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_API_BASE=<your-endpoint>
AZURE_OPENAI_DEPLOYMENT_ID=<your-deployment>
```

### Optional (Explorer Mode)

```bash
# Explorer Mode (human-in-the-loop)
ENABLE_EXPLORER_MODE=1  # Default: enabled
```

---

## Production Setup Steps

### 1. Deploy Code

```bash
# Copy canonical upgraded folder to production
scp -r Daena_old_upgrade_20251213/ user@production:/opt/daena/

# SSH into production
ssh user@production
cd /opt/daena
```

### 2. Create Production Environment

```bash
# Create venv
python3.10 -m venv venv_daena_main_py310

# Activate venv
source venv_daena_main_py310/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install requirements
pip install -r requirements.txt
```

### 3. Create Production Config

```bash
# Create .env file
cat > .env << EOF
DISABLE_AUTH=0
JWT_SECRET_KEY=$(openssl rand -hex 32)
CAPSULE_SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///./data/daena_prod.db
LOG_LEVEL=INFO
LOG_FILE=./logs/daena_prod.log
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=https://yourdomain.com
AUTOMATION_SAFE_MODE=1
AUTOMATION_ALLOWED_DOMAINS=yourdomain.com
EOF
```

### 4. Create Directories

```bash
mkdir -p data logs
chmod 700 data logs
```

### 5. Run Checkpoints

```bash
# Verify no truncation
python scripts/verify_no_truncation.py

# Verify no duplicates
python scripts/verify_no_duplicates.py
```

### 6. Test Locally

```bash
# Start server
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/api/v1/health

# Test authentication (should require token)
curl http://localhost:8000/api/v1/agents
# Expected: 401 Unauthorized
```

---

## Reverse Proxy Setup

### Caddy (Recommended)

**Caddyfile** (`/etc/caddy/Caddyfile`):
```
yourdomain.com {
    reverse_proxy localhost:8000 {
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

**Start Caddy:**
```bash
sudo systemctl start caddy
sudo systemctl enable caddy
```

### Nginx

**Config** (`/etc/nginx/sites-available/daena`):
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable:**
```bash
sudo ln -s /etc/nginx/sites-available/daena /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Systemd Service

**Service file** (`/etc/systemd/system/daena.service`):
```ini
[Unit]
Description=Daena AI VP System
After=network.target

[Service]
Type=simple
User=daena
WorkingDirectory=/opt/daena
Environment="PATH=/opt/daena/venv_daena_main_py310/bin"
ExecStart=/opt/daena/venv_daena_main_py310/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable daena
sudo systemctl start daena
sudo systemctl status daena
```

---

## Monitoring

### Health Checks

```bash
# Health endpoint
curl https://yourdomain.com/api/v1/health

# Council health
curl https://yourdomain.com/api/v1/health/council

# Registry summary
curl https://yourdomain.com/api/v1/registry/summary
```

### Logs

```bash
# Application logs
tail -f logs/daena_prod.log

# Systemd logs
sudo journalctl -u daena -f
```

### Rate Limiting

Rate limiting is configured in `backend/middleware/rate_limit.py`:
- Default: 500 requests/minute
- Auth: 10 requests/minute
- Chat: 100 requests/minute
- Council: 50 requests/minute

---

## Security Checklist

- ✅ `DISABLE_AUTH=0` (authentication enabled)
- ✅ Strong `JWT_SECRET_KEY` and `CAPSULE_SECRET_KEY`
- ✅ HTTPS enabled (reverse proxy)
- ✅ CORS configured for your domain only
- ✅ Automation tools disabled (unless needed)
- ✅ Rate limiting enabled
- ✅ Logs stored securely
- ✅ Database permissions restricted
- ✅ No hardcoded secrets in code
- ✅ Regular backups

---

## Backups

### Database Backup

```bash
# Backup script
#!/bin/bash
BACKUP_DIR=/opt/daena/backups
mkdir -p $BACKUP_DIR
cp data/daena_prod.db $BACKUP_DIR/daena_prod_$(date +%Y%m%d_%H%M%S).db
# Keep last 30 days
find $BACKUP_DIR -name "daena_prod_*.db" -mtime +30 -delete
```

### Cron Job

```bash
# Add to crontab
0 2 * * * /opt/daena/scripts/backup_db.sh
```

---

## Troubleshooting

### "401 Unauthorized" on all endpoints

**Cause**: `DISABLE_AUTH=0` but no valid token

**Solution**: 
- Verify `DISABLE_AUTH=0` in `.env`
- Use valid API key in requests
- Check `JWT_SECRET_KEY` is set

### "Database locked"

**Cause**: Multiple processes accessing SQLite

**Solution**: 
- Ensure only one uvicorn instance
- Use PostgreSQL for production (recommended)

### "CORS errors"

**Cause**: `CORS_ORIGINS` not configured correctly

**Solution**: 
- Add your domain to `CORS_ORIGINS`
- Restart server

---

## Production Checklist

Before going live:

- [ ] Code deployed to production
- [ ] Environment variables set (`.env` file)
- [ ] Database initialized
- [ ] Reverse proxy configured (HTTPS)
- [ ] Systemd service enabled
- [ ] Health checks passing
- [ ] Authentication working (`DISABLE_AUTH=0`)
- [ ] Logs configured
- [ ] Backups configured
- [ ] Monitoring in place
- [ ] Rate limiting enabled
- [ ] CORS configured
- [ ] Automation tools disabled (unless needed)

---

**STATUS: ✅ PRODUCTION GUIDE COMPLETE**









