# Known Issues and Next Steps

**Date**: 2025-12-13  
**Status**: Local Launch Ready | Production Hardening Required

---

## Remaining Risks

### 1. Database Locking (Low Risk)

**Issue**: SQLite can lock if multiple processes access it simultaneously.

**Mitigation**:
- Launcher ensures only one backend instance
- Database operations are serialized

**Production Fix**:
- Migrate to PostgreSQL (recommended)
- Use connection pooling
- Set up database replication if needed

---

### 2. Port Conflicts (Low Risk)

**Issue**: Port 8000 may be in use by another application.

**Mitigation**:
- Launcher checks health endpoint (will fail if port in use)
- Error message shows which port is blocked

**Production Fix**:
- Use environment variable: `BACKEND_PORT=8000`
- Configure reverse proxy (Caddy/Nginx) to handle port mapping
- Use systemd service to manage port allocation

---

### 3. Missing Optional Dependencies (Low Risk)

**Issue**: Some optional packages (selenium, pyautogui, playwright) may fail to install.

**Mitigation**:
- Launcher continues if optional deps fail
- Features that require these deps are disabled gracefully

**Production Fix**:
- Document which features require which dependencies
- Provide separate `requirements-optional.txt`
- Use feature flags to enable/disable optional features

---

### 4. Windows-Specific Issues (Low Risk)

**Issue**: Some packages (pyaudio, porcupine) may not install on Windows without manual setup.

**Mitigation**:
- Audio features are optional (`ENABLE_AUDIO=0` by default)
- Launcher warns but continues if audio deps fail

**Production Fix**:
- Provide Windows-specific installation instructions
- Use pre-built wheels where available
- Consider Docker for consistent environments

---

## What to Fix Next

### Immediate (Before Production)

1. **Authentication**
   - [ ] Set `DISABLE_AUTH=0` in production
   - [ ] Generate strong `JWT_SECRET_KEY` (32+ chars)
   - [ ] Generate strong `CAPSULE_SECRET_KEY` (32+ chars)
   - [ ] Test authentication flows with real tokens
   - [ ] Configure user management system

2. **HTTPS & Reverse Proxy**
   - [ ] Set up Caddy or Nginx
   - [ ] Configure SSL/TLS certificates (Let's Encrypt)
   - [ ] Set proper CORS origins
   - [ ] Configure rate limiting at proxy level

3. **Database**
   - [ ] Migrate from SQLite to PostgreSQL
   - [ ] Set up database backups (automated)
   - [ ] Configure connection pooling
   - [ ] Test restore procedures

4. **Secrets Management**
   - [ ] Remove all hardcoded secrets from code
   - [ ] Use environment variables or secret manager
   - [ ] Rotate keys regularly
   - [ ] Audit secret access

5. **Monitoring & Logging**
   - [ ] Set up application monitoring (Prometheus/Grafana)
   - [ ] Configure log rotation
   - [ ] Set up alerting (email/Slack)
   - [ ] Monitor performance metrics

6. **Backup & Recovery**
   - [ ] Set up automated backups (database + files)
   - [ ] Test restore procedures
   - [ ] Document recovery process
   - [ ] Set up disaster recovery plan

---

### Short-Term (Within 1 Month)

1. **Rate Limiting**
   - [ ] Configure production rate limits
   - [ ] Set up per-user limits
   - [ ] Monitor rate limit violations
   - [ ] Adjust limits based on usage

2. **Security Hardening**
   - [ ] Review and update dependencies
   - [ ] Run security scans (OWASP, Snyk)
   - [ ] Set up WAF (Web Application Firewall)
   - [ ] Configure DDoS protection

3. **Performance Optimization**
   - [ ] Profile slow endpoints
   - [ ] Optimize database queries
   - [ ] Add caching (Redis) for frequently accessed data
   - [ ] Optimize static file serving

4. **Documentation**
   - [ ] Complete API documentation
   - [ ] Write deployment guide
   - [ ] Create troubleshooting runbook
   - [ ] Document all environment variables

---

### Long-Term (Within 3 Months)

1. **Scalability**
   - [ ] Set up load balancing
   - [ ] Configure horizontal scaling
   - [ ] Optimize for high concurrency
   - [ ] Set up CDN for static assets

2. **High Availability**
   - [ ] Set up database replication
   - [ ] Configure failover mechanisms
   - [ ] Set up health checks and auto-restart
   - [ ] Test disaster recovery scenarios

3. **Observability**
   - [ ] Set up distributed tracing (OpenTelemetry)
   - [ ] Configure APM (Application Performance Monitoring)
   - [ ] Set up log aggregation (ELK stack)
   - [ ] Create dashboards for key metrics

4. **Testing**
   - [ ] Increase test coverage (aim for 80%+)
   - [ ] Add integration tests
   - [ ] Set up CI/CD pipeline
   - [ ] Add automated security testing

---

## Go-Live Checklist

### Pre-Launch

- [ ] All tests passing (`pytest tests/`)
- [ ] No truncation markers (`python scripts\verify_no_truncation.py`)
- [ ] No duplicate modules (`python scripts\verify_no_duplicates.py`)
- [ ] Health endpoint returns 200 (`/api/v1/health/`)
- [ ] Dashboard loads (`/ui/dashboard`)
- [ ] All critical endpoints accessible
- [ ] Logs directory created and writable
- [ ] Database seeded (8 departments × 6 agents)

### Environment Setup

- [ ] `DISABLE_AUTH=0` (authentication enabled)
- [ ] `JWT_SECRET_KEY` set (32+ chars, strong random)
- [ ] `CAPSULE_SECRET_KEY` set (32+ chars, strong random)
- [ ] `ENVIRONMENT=production`
- [ ] `DATABASE_URL` set (PostgreSQL recommended)
- [ ] `LOG_LEVEL=INFO` or `WARNING`
- [ ] `LOG_FILE` set (writable path)
- [ ] `CORS_ORIGINS` set (your domain only)
- [ ] `CHAT_RATE_LIMIT_PER_MIN` set (e.g., 100)

### Infrastructure

- [ ] Reverse proxy configured (Caddy/Nginx)
- [ ] SSL/TLS certificates installed
- [ ] Domain DNS configured
- [ ] Firewall rules configured
- [ ] Database server running (PostgreSQL)
- [ ] Backup system configured
- [ ] Monitoring system configured
- [ ] Alerting system configured

### Security

- [ ] No hardcoded secrets in code
- [ ] All secrets in environment variables or secret manager
- [ ] API keys rotated
- [ ] Dependencies updated (no known vulnerabilities)
- [ ] Security scans passed
- [ ] WAF configured
- [ ] DDoS protection enabled
- [ ] Rate limiting enabled

### Documentation

- [ ] Deployment guide written
- [ ] Troubleshooting runbook created
- [ ] Environment variables documented
- [ ] API documentation complete
- [ ] User guide written (if applicable)

### Testing

- [ ] End-to-end tests passing
- [ ] Load testing completed
- [ ] Security testing completed
- [ ] Disaster recovery tested
- [ ] Backup restore tested

---

## Production Environment Variables

### Required

```bash
# Authentication
DISABLE_AUTH=0
JWT_SECRET_KEY=<generate-strong-secret-32-chars-min>
CAPSULE_SECRET_KEY=<generate-strong-secret-32-chars-min>

# Environment
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql://user:pass@host:5432/daena

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/daena_prod.log

# CORS
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Rate Limiting
CHAT_RATE_LIMIT_PER_MIN=100
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

### Optional (Features)

```bash
ENABLE_AUDIO=0                    # Audio features (default: disabled)
ENABLE_AUTOMATION_TOOLS=0         # Selenium, pyautogui (default: disabled)
ENABLE_HUMAN_RELAY_EXPLORER=1    # Human Relay Explorer (default: enabled)
```

---

## Reverse Proxy Configuration

### Caddy (Recommended)

**Caddyfile** (`/etc/caddy/Caddyfile`):
```
yourdomain.com {
    reverse_proxy localhost:8000
    encode gzip
}
```

**Enable**:
```bash
sudo systemctl enable caddy
sudo systemctl start caddy
```

### Nginx

**Config** (`/etc/nginx/sites-available/daena`):
```nginx
server {
    listen 80;
    server_name yourdomain.com;

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

---

## Backup Script

**Database Backup** (`scripts/backup_db.sh`):
```bash
#!/bin/bash
BACKUP_DIR=/opt/daena/backups
mkdir -p $BACKUP_DIR
pg_dump $DATABASE_URL > $BACKUP_DIR/daena_prod_$(date +%Y%m%d_%H%M%S).sql
# Keep last 30 days
find $BACKUP_DIR -name "daena_prod_*.sql" -mtime +30 -delete
```

**Cron Job**:
```bash
# Add to crontab
0 2 * * * /opt/daena/scripts/backup_db.sh
```

---

## Monitoring

### Health Checks

```bash
# Health endpoint
curl https://yourdomain.com/api/v1/health/

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

---

## Summary

**Current Status**: ✅ **Local launch ready**

**Next Priority**: Production hardening (authentication, HTTPS, database migration, monitoring)

**Timeline**:
- **Week 1**: Authentication + HTTPS setup
- **Week 2**: Database migration + backups
- **Week 3**: Monitoring + alerting
- **Week 4**: Security hardening + testing

---

**STATUS: ✅ LAUNCH STABILIZATION COMPLETE | ⚠️ PRODUCTION HARDENING REQUIRED**





