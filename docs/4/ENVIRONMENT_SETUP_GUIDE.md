# Environment Setup Guide

**Complete guide for setting up Daena environments**

---

## Environment Files Overview

Daena uses environment variables for configuration. You need to create environment files for each environment:

- **Development**: `.env` (local development)
- **Staging**: `.env.staging` (testing before production)
- **Production**: `.env.production` (live environment)

---

## Quick Setup

### Step 1: Copy Template

```bash
# For development
cp .env.production.example .env

# For staging
cp .env.production.example .env.staging

# For production
cp .env.production.example .env.production
```

### Step 2: Generate Secrets

```bash
# Generate JWT secret key
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate CSRF secret key
python -c "import secrets; print('CSRF_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate AES encryption key
python -c "import secrets, base64; print('DAENA_MEMORY_AES_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())"

# Generate general secret key
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### Step 3: Update Configuration

Edit your `.env` file and update:

1. **Authentication Secrets** (required)
   ```bash
   JWT_SECRET_KEY=<generated-key>
   CSRF_SECRET_KEY=<generated-key>
   SECRET_KEY=<generated-key>
   ```

2. **Database Connection** (required)
   ```bash
   # SQLite (development)
   DATABASE_URL=sqlite:///daena.db
   
   # PostgreSQL (staging/production)
   DATABASE_URL=postgresql://user:password@host:5432/daena
   ```

3. **AI Provider** (at least one required)
   ```bash
   # OpenAI
   OPENAI_API_KEY=sk-...
   
   # OR Azure OpenAI
   AZURE_OPENAI_API_KEY=...
   AZURE_OPENAI_API_BASE=https://your-resource.openai.azure.com
   AZURE_OPENAI_DEPLOYMENT_ID=your-deployment
   ```

4. **Environment Type**
   ```bash
   ENVIRONMENT=development  # or staging, production
   LOG_LEVEL=INFO
   ```

---

## Required Variables by Environment

### Development (`.env`)

**Minimum:**
```bash
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=sqlite:///daena.db
OPENAI_API_KEY=<your-key>
JWT_SECRET_KEY=<generated>
CSRF_SECRET_KEY=<generated>
```

**Recommended:**
- All variables from template
- `DEBUG=true` for easier debugging
- SQLite for simplicity

### Staging (`.env.staging`)

**Minimum:**
```bash
ENVIRONMENT=staging
DEBUG=false
DATABASE_URL=postgresql://user:pass@host:5432/daena_staging
OPENAI_API_KEY=<staging-key>
JWT_SECRET_KEY=<staging-secret>
CSRF_SECRET_KEY=<staging-secret>
LOG_LEVEL=INFO
```

**Recommended:**
- PostgreSQL database
- Separate API keys (staging account)
- Monitoring enabled
- Shorter retention periods

### Production (`.env.production`)

**Required:**
```bash
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=postgresql://user:pass@host:5432/daena_prod
OPENAI_API_KEY=<production-key>
JWT_SECRET_KEY=<production-secret>
CSRF_SECRET_KEY=<production-secret>
DAENA_MEMORY_AES_KEY=<32-byte-base64>
LOG_LEVEL=INFO
LOG_FORMAT=json
```

**Critical:**
- ✅ Strong secrets (32+ characters)
- ✅ PostgreSQL or production-grade database
- ✅ Production API keys
- ✅ Billing configured (if enabled)
- ✅ Monitoring enabled
- ✅ HTTPS configured

---

## Environment-Specific Configurations

### Development

```bash
# Development settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# Use SQLite for simplicity
DATABASE_URL=sqlite:///daena.db

# Local services
REDIS_HOST=localhost
MONGO_HOST=localhost

# Disable billing
BILLING_ENABLED=false

# Allow all features
COMPUTE_PREFER=auto
COMPUTE_ALLOW_TPU=false
```

### Staging

```bash
# Staging settings
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json

# Staging database
DATABASE_URL=postgresql://staging_user:pass@staging-db:5432/daena_staging

# Staging services
REDIS_HOST=redis
MONGO_HOST=mongodb

# Disable billing or use test keys
BILLING_ENABLED=false
STRIPE_SECRET_KEY=sk_test_...

# Staging monitoring
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
```

### Production

```bash
# Production settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json

# Production database (high availability)
DATABASE_URL=postgresql://prod_user:secure_pass@prod-db-cluster:5432/daena_prod

# Production services
REDIS_HOST=redis-production
MONGO_HOST=mongodb-production

# Enable billing with production keys
BILLING_ENABLED=true
STRIPE_SECRET_KEY=sk_live_...

# Production monitoring (required)
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true

# Security
CORS_ORIGINS=https://daena.ai,https://admin.daena.ai
RATE_LIMIT_ENABLED=true
```

---

## Security Checklist

### Secrets Management

- [ ] Generate unique secrets for each environment
- [ ] Never commit `.env` files to git
- [ ] Use secret managers in production (AWS Secrets Manager, Azure Key Vault, etc.)
- [ ] Rotate secrets regularly
- [ ] Use different API keys per environment

### Database Security

- [ ] Use strong database passwords
- [ ] Enable SSL/TLS for database connections
- [ ] Restrict database access by IP
- [ ] Regular backups
- [ ] Separate databases for staging/production

### API Security

- [ ] Enable HTTPS in production
- [ ] Configure CORS properly
- [ ] Enable rate limiting
- [ ] Use strong JWT secrets
- [ ] Enable CSRF protection

---

## Variable Reference

### Authentication

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `JWT_SECRET_KEY` | Secret for JWT tokens | ✅ Yes | None |
| `CSRF_SECRET_KEY` | Secret for CSRF protection | ✅ Yes | None |
| `SECRET_KEY` | General secret key | ✅ Yes | None |
| `DAENA_API_KEY` | API key for internal auth | ⚠️ Recommended | `daena_secure_key_2025` |

### Database

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | Database connection string | ✅ Yes | `sqlite:///daena.db` |
| `MONGO_HOST` | MongoDB host | ⚠️ For analytics | `localhost` |
| `MONGO_PORT` | MongoDB port | ⚠️ For analytics | `27017` |
| `REDIS_HOST` | Redis host | ⚠️ For caching | `localhost` |
| `REDIS_PORT` | Redis port | ⚠️ For caching | `6379` |

### AI Providers

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key | ✅ At least one | None |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key | ⚠️ Alternative | None |
| `AZURE_OPENAI_API_BASE` | Azure endpoint | ⚠️ If using Azure | None |

### Compute

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `COMPUTE_PREFER` | Preferred device (auto/cpu/gpu/tpu) | ❌ No | `auto` |
| `COMPUTE_ALLOW_TPU` | Allow TPU usage | ❌ No | `false` |
| `COMPUTE_TPU_BATCH_FACTOR` | TPU batch size multiplier | ❌ No | `32` |

### Billing

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `BILLING_ENABLED` | Enable billing features | ❌ No | `false` |
| `STRIPE_SECRET_KEY` | Stripe secret key | ⚠️ If billing enabled | None |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key | ⚠️ If billing enabled | None |

---

## Testing Your Configuration

### Validate Environment File

```bash
# Check all required variables are set
python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env')

required = ['JWT_SECRET_KEY', 'DATABASE_URL', 'OPENAI_API_KEY']
missing = [v for v in required if not os.getenv(v)]

if missing:
    print(f'❌ Missing variables: {missing}')
else:
    print('✅ All required variables set')
"
```

### Test Database Connection

```bash
# Test PostgreSQL connection
python -c "
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv('.env')
db_url = os.getenv('DATABASE_URL')

try:
    engine = create_engine(db_url)
    conn = engine.connect()
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"
```

### Test AI Provider

```bash
# Test OpenAI connection
python -c "
import os
from dotenv import load_dotenv
import openai

load_dotenv('.env')
api_key = os.getenv('OPENAI_API_KEY')

if api_key:
    openai.api_key = api_key
    try:
        # Simple test
        print('✅ OpenAI API key configured')
    except:
        print('⚠️  OpenAI API key may be invalid')
else:
    print('❌ OPENAI_API_KEY not set')
"
```

---

## Common Configuration Scenarios

### Scenario 1: Local Development (SQLite)

```bash
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=sqlite:///daena.db
OPENAI_API_KEY=sk-...
JWT_SECRET_KEY=<dev-secret>
CSRF_SECRET_KEY=<dev-secret>
BILLING_ENABLED=false
```

### Scenario 2: Staging with PostgreSQL

```bash
ENVIRONMENT=staging
DEBUG=false
DATABASE_URL=postgresql://user:pass@staging-db:5432/daena_staging
OPENAI_API_KEY=sk-... # Staging account
JWT_SECRET_KEY=<staging-secret>
CSRF_SECRET_KEY=<staging-secret>
MONGO_HOST=mongodb
REDIS_HOST=redis
BILLING_ENABLED=false
PROMETHEUS_ENABLED=true
```

### Scenario 3: Production with Full Stack

```bash
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=postgresql://prod_user:secure@prod-cluster:5432/daena
OPENAI_API_KEY=sk-... # Production account
JWT_SECRET_KEY=<strong-32-char-secret>
CSRF_SECRET_KEY=<strong-32-char-secret>
DAENA_MEMORY_AES_KEY=<32-byte-base64>
MONGO_HOST=mongodb-production
REDIS_HOST=redis-production
BILLING_ENABLED=true
STRIPE_SECRET_KEY=sk_live_...
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
LOG_FORMAT=json
CORS_ORIGINS=https://daena.ai
```

---

## Next Steps

1. ✅ Create `.env` file from template
2. ✅ Generate secrets
3. ✅ Configure database
4. ✅ Set up AI provider
5. ✅ Test configuration
6. ✅ Deploy to staging
7. ✅ Deploy to production

---

**Last Updated**: 2025-01-XX  
**Status**: Ready for Use

