# Go-Live Next Steps (Production Deployment)

**Date**: 2025-12-13  
**Status**: ✅ **LOCAL GO-LIVE READY** | Production Planning Ready

---

## Quick Start (Local Development)

### Exact Run Commands

**One-Command Launch** (Double-Click):
```batch
START_DAENA.bat
```

**Or from Command Line**:
```batch
cd D:\Ideas\Daena_old_upgrade_20251213
START_DAENA.bat
```

**That's it!** The launcher handles everything automatically.

**What it does**:
1. Creates/activates venv if missing
2. Upgrades pip, setuptools, wheel
3. Installs from `requirements.txt`
4. Runs guardrails (truncation, duplicates)
5. Optionally updates requirements (if `DAENA_UPDATE_REQUIREMENTS=1`)
6. Optionally runs tests (if `DAENA_RUN_TESTS=1`)
7. Sets `DISABLE_AUTH=1`
8. Starts uvicorn server
9. Opens browser to `http://127.0.0.1:8000/ui/dashboard`

**Manual Steps** (if launcher fails):
```batch
REM 1. Setup environment
setup_environments.bat

REM 2. Verify guardrails
call venv_daena_main_py310\Scripts\activate.bat
python scripts\verify_no_truncation.py
python scripts\verify_no_duplicates.py

REM 3. Run tests (optional)
if "%DAENA_RUN_TESTS%"=="1" (
    pytest tests/test_daena_end_to_end.py tests/test_human_relay_explorer.py -v
)

REM 4. Start server
set DISABLE_AUTH=1
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Environment Variables (Local Development)

**Required (Local Dev)**:
```batch
set DISABLE_AUTH=1                      # Bypass authentication (local only)
```

**Optional**:
```batch
set DAENA_LAUNCHER_STAY_OPEN=1          # Keep window open on error (default: 1)
set DAENA_UPDATE_REQUIREMENTS=1         # Update requirements.txt from lockfile
set DAENA_RUN_TESTS=1                   # Run tests before launch
set ENABLE_HUMAN_RELAY_EXPLORER=1       # Enable Human Relay Explorer (default: 1)
set ENABLE_AUTOMATION_TOOLS=1           # Install selenium, pyautogui (optional)
set ENABLE_AUDIO=1                      # Enable audio features (optional)
```

### Test Commands

**Run all tests**:
```batch
pytest tests/test_daena_end_to_end.py tests/test_human_relay_explorer.py -v
```

**Run specific test**:
```batch
pytest tests/test_daena_end_to_end.py::test_daena_full_workflow_vibeagent -v
```

**Verify endpoints**:
```batch
python scripts\verify_endpoints.py
```

---

## Production Environment Variables

### Required

```bash
# Authentication (REQUIRED in production)
DISABLE_AUTH=0
JWT_SECRET_KEY=<generate-strong-secret-32-chars-min>
CAPSULE_SECRET_KEY=<generate-strong-secret-32-chars-min>

# Environment
ENVIRONMENT=production

# Rate Limiting
CHAT_RATE_LIMIT_PER_MIN=100

# Server
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# Database
DATABASE_URL=sqlite:///./data/daena_prod.db
# OR for production: postgresql://user:pass@host:5432/daena

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/daena_prod.log

# CORS (adjust for your domain)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Optional (Cloud LLMs)

```bash
ENABLE_CLOUD_LLM=1
OPENAI_API_KEY=<your-key>
GEMINI_API_KEY=<your-key>
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_API_BASE=<your-endpoint>
AZURE_OPENAI_DEPLOYMENT_ID=<your-deployment>
```

### Optional (Automation)

```bash
AUTOMATION_SAFE_MODE=1
AUTOMATION_ALLOWED_DOMAINS=yourdomain.com,api.yourdomain.com
AUTOMATION_ENABLE_BROWSER=0  # Disable in production unless needed
AUTOMATION_ENABLE_DESKTOP=0  # Disable in production
```

---

## Production Deployment Steps

### 1. Generate Secrets

```bash
# Generate JWT secret
openssl rand -hex 32

# Generate Capsule secret
openssl rand -hex 32
```

### 2. Create Production Config

```bash
cat > .env.production << EOF
DISABLE_AUTH=0
JWT_SECRET_KEY=<generated-secret>
CAPSULE_SECRET_KEY=<generated-secret>
ENVIRONMENT=production
CHAT_RATE_LIMIT_PER_MIN=100
DATABASE_URL=sqlite:///./data/daena_prod.db
LOG_LEVEL=INFO
LOG_FILE=./logs/daena_prod.log
CORS_ORIGINS=https://yourdomain.com
EOF
```

### 3. Reverse Proxy Setup

#### Option A: Caddy (Recommended - Auto HTTPS)

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

**Start Caddy**:
```bash
sudo systemctl start caddy
sudo systemctl enable caddy
```

#### Option B: Nginx

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

**Enable**:
```bash
sudo ln -s /etc/nginx/sites-available/daena /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Systemd Service

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
EnvironmentFile=/opt/daena/.env.production
ExecStart=/opt/daena/venv_daena_main_py310/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable daena
sudo systemctl start daena
sudo systemctl status daena
```

### 5. Backups

**Database Backup Script** (`scripts/backup_db.sh`):
```bash
#!/bin/bash
BACKUP_DIR=/opt/daena/backups
mkdir -p $BACKUP_DIR
cp data/daena_prod.db $BACKUP_DIR/daena_prod_$(date +%Y%m%d_%H%M%S).db
# Keep last 30 days
find $BACKUP_DIR -name "daena_prod_*.db" -mtime +30 -delete
```

**Cron Job**:
```bash
# Add to crontab
0 2 * * * /opt/daena/scripts/backup_db.sh
```

### 6. Monitoring

**Health Checks**:
```bash
# Health endpoint
curl https://yourdomain.com/api/v1/health

# Council health
curl https://yourdomain.com/api/v1/health/council

# Registry summary
curl https://yourdomain.com/api/v1/registry/summary
```

**Logs**:
```bash
# Application logs
tail -f logs/daena_prod.log

# Systemd logs
sudo journalctl -u daena -f
```

---

## Security Checklist

Before going live:

- [ ] `DISABLE_AUTH=0` (authentication enabled)
- [ ] Strong `JWT_SECRET_KEY` and `CAPSULE_SECRET_KEY` (32+ chars)
- [ ] HTTPS enabled (reverse proxy)
- [ ] CORS configured for your domain only
- [ ] Rate limiting enabled (`CHAT_RATE_LIMIT_PER_MIN=100`)
- [ ] Automation tools disabled (unless needed)
- [ ] Logs stored securely
- [ ] Database permissions restricted
- [ ] No hardcoded secrets in code
- [ ] Regular backups configured
- [ ] Monitoring in place

---

## Rate Limiting

Rate limiting is configured in `backend/middleware/rate_limit.py`:
- Default: 500 requests/minute
- Auth: 10 requests/minute
- Chat: 100 requests/minute (configurable via `CHAT_RATE_LIMIT_PER_MIN`)
- Council: 50 requests/minute

---

## Troubleshooting (Top 5 Likely Failures)

### 1. "Python not found" or "venv not found"

**Cause**: Python not installed or venv not created

**Solution**:
```batch
REM Check Python version
python --version  # Should be 3.10+

REM Create venv manually
python -m venv venv_daena_main_py310

REM Activate venv
call venv_daena_main_py310\Scripts\activate.bat
```

### 2. "Failed to install requirements.txt"

**Cause**: Package installation failed

**Solution**:
- Check error message for failing package name
- Install manually: `pip install <package-name>`
- Check if package is available for Python 3.10
- Verify internet connection

**Common failing packages**:
- `torch` - May need CUDA version
- `transformers` - Large download, may timeout
- `playwright` - Requires browser binaries

### 3. "Truncation markers detected"

**Cause**: File was truncated by editor

**Solution**:
```batch
REM Check which file
python scripts\verify_no_truncation.py

REM Restore from git
git checkout <file-path>

REM Or restore from backup
```

### 4. "Duplicate modules detected"

**Cause**: Duplicate files found

**Solution**:
```batch
REM Check which files
python scripts\verify_no_duplicates.py

REM Consolidate duplicates
REM Keep canonical file, update imports
```

### 5. "401 Unauthorized" on all endpoints (Local Dev)

**Cause**: `DISABLE_AUTH` not set to 1

**Solution**:
```batch
REM Set environment variable
set DISABLE_AUTH=1

REM Or add to .env file
echo DISABLE_AUTH=1 > .env

REM Restart server
```

### 6. "Database locked"

**Cause**: Multiple processes accessing SQLite

**Solution**: 
- Ensure only one uvicorn instance running
- Close other Daena instances
- Use PostgreSQL for production (recommended)

### 7. "CORS errors"

**Cause**: `CORS_ORIGINS` not configured correctly

**Solution**: 
- Add your domain to `CORS_ORIGINS`
- For local dev, add `http://localhost:8000`
- Restart server

---

## Production Checklist

Before going live:

- [ ] Code deployed to production
- [ ] Environment variables set (`.env.production`)
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

**STATUS: ✅ PRODUCTION DEPLOYMENT GUIDE COMPLETE**

**Follow these steps to deploy Daena to production with proper authentication, HTTPS, and monitoring.**

