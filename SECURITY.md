# Security Policy

## Overview

Daena is a **local-first AI platform** that runs on your machine with local LLMs. By design, no data leaves your machine unless you explicitly configure an outbound integration.

This document describes:
1. What runs locally
2. What CAN reach the network
3. Approval requirements for outbound operations
4. Security hardening guidelines

---

## What Runs Locally (100% Private)

| Component | Data Location | Network Access |
|-----------|---------------|----------------|
| Core LLM (Ollama) | `MODELS_ROOT/ollama` | ❌ None |
| Voice (XTTS) | `MODELS_ROOT/xtts` | ❌ None |
| Database | `daena.db` (SQLite) | ❌ None |
| Chat History | `local_brain/chat_history` | ❌ None |
| Files/Code | Your workspace paths | ❌ None |
| Council Debates | Memory only | ❌ None |
| Agent Orchestration | Memory only | ❌ None |

Your prompts, chat history, generated code, and decisions **never leave your machine** unless you enable external integrations.

---

## What CAN Reach the Network (Configurable)

| Feature | Network Access | When Enabled | Approval Required |
|---------|----------------|--------------|-------------------|
| Web Search | Outbound HTTPS | If Brave/Serper/Tavily key set | Per-search (auto for low-risk) |
| Cloud LLM Fallback | Outbound HTTPS | If OpenAI/Azure/Anthropic key set | Auto for configured provider |
| Discord/Telegram | Outbound HTTPS | If bot token set | Auto for messaging |
| DeFi Contract Deploy | Blockchain RPC | When deploying | **EXPLICIT user approval** |
| GitHub Clone | Outbound HTTPS | When cloning repos | User confirmation |
| Model Downloads | Outbound HTTPS | When pulling Ollama models | User confirmation |

### Inbound Network Access

| Feature | Port | Network Scope | Security |
|---------|------|---------------|----------|
| Backend API | 8000 | localhost only (default) | CORS restricted |
| Audio Service | 5001 | localhost only | No auth (local) |
| Mobile Remote | Tunnel | Via Tailscale/Cloudflare | WSS + token |

---

## Secrets Management

### Do NOT Hardcode

**Never** put API keys, passwords, or tokens in source code. All secrets must be in environment variables.

### Supported Secrets

| Variable | Purpose | Sensitivity |
|----------|---------|-------------|
| `EXECUTION_TOKEN` | Execution layer auth | CRITICAL |
| `JWT_SECRET_KEY` | Session signing | CRITICAL |
| `OPENAI_API_KEY` | OpenAI cloud fallback | HIGH |
| `AZURE_OPENAI_API_KEY` | Azure cloud fallback | HIGH |
| `ANTHROPIC_API_KEY` | Claude cloud fallback | HIGH |
| `ELEVENLABS_API_KEY` | Voice cloning | MEDIUM |
| `BRAVE_API_KEY` | Web search | MEDIUM |
| `DISCORD_BOT_TOKEN` | Discord integration | HIGH |
| `TELEGRAM_BOT_TOKEN` | Telegram integration | HIGH |
| `WINDOWS_NODE_TOKEN` | Remote Windows control | CRITICAL |

### Key Rotation

If you suspect keys are compromised:

1. **Azure OpenAI**: Azure Portal → Your Resource → Keys & Endpoint → Regenerate
2. **HuggingFace**: huggingface.co/settings/tokens → Revoke + Create new
3. **OpenAI**: platform.openai.com → API Keys → Revoke + Create new
4. **Update `.env`** with new values immediately

---

## Security Hardening Checklist

### Critical (Before First Run)

- [ ] `.env` file created (never commit to git)
- [ ] `.gitignore` includes `.env`, `.env_*`, `!.env.example`
- [ ] All exposed keys rotated
- [ ] Pre-commit hooks installed (`pre-commit install`)

### Important (Before Deployment)

- [ ] `DISABLE_AUTH=1` removed (required for production)
- [ ] `ENVIRONMENT=production` set
- [ ] CORS origins locked to specific domains
- [ ] Execution token set (`EXECUTION_TOKEN`)
- [ ] Rate limiting enabled (`RATE_LIMIT_ENABLED=1`)

### Recommended

- [ ] Gitleaks installed and running
- [ ] Regular `secrets_audit.py` scans
- [ ] Audit logs reviewed weekly
- [ ] Cloud keys rotated monthly

---

## Approval Gates

### Risk Levels

| Level | Examples | Approval |
|-------|----------|----------|
| MINIMAL | Read files, search web | Auto-approved |
| LOW | Write files, API access | Daena with notification |
| MEDIUM | Delete files, spawn agents | User prompt |
| HIGH | System config, credentials | User explicit confirmation |
| CRITICAL | DeFi deploy, terminate agents | Multi-factor confirmation |

### DeFi Operations (Always CRITICAL)

Any blockchain interaction requires:
1. Automatic security scan (Slither + Mythril)
2. Visual diff of contract changes
3. Gas estimate and risk score display
4. **Explicit user approval** (cannot be auto-approved)
5. Multi-sig wallet signature if treasury involved

---

## Incident Response

### Emergency Stop

Three ways to halt all operations immediately:

1. **UI**: Big red button in Founder Panel
2. **API**: `POST /api/v1/daena/emergency-stop`
3. **Terminal**: Ctrl+C in backend window

### Lockdown Mode

Enable full lockdown (blocks all non-essential requests):

```bash
# Set in environment
SECURITY_LOCKDOWN_MODE=1

# Or via API (requires execution token)
POST /api/v1/security/lockdown
```

### Audit Trail

All actions are logged to:
- `logs/daena_*.log` - Application logs
- `audit_*.json` - Security audit trail
- Database `audit_log` table - Persistent audit

---

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT** open a public GitHub issue
2. Email: masoud.masoori@mas-ai.co
3. Include: vulnerability description, reproduction steps, impact assessment
4. We will respond within 48 hours

---

## Technical Security Controls

### CORS Configuration

```python
# main.py - Only localhost allowed by default
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
]
```

### WebSocket Origin Validation

All WebSocket connections are validated against allowed hosts before establishing connection.

### Token Expiry

- Execution tokens: 15-minute idle timeout
- Session tokens: Configurable via `JWT_EXPIRY_MINUTES`
- Sub-agent permissions: Auto-revoked on task completion

### Input Sanitization

- All file paths canonicalized and validated against workspace allowlist
- Shell commands filtered through configurable allowlist
- SQL queries use parameterized statements only

---

*Last updated: 2026-01-31*
*Security contact: masoud.masoori@mas-ai.co*
