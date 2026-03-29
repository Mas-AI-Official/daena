# Daena V2 Deploy Checklist

## Pre-Deploy Verification
- [ ] All backend tests pass (`pytest backend/tests/ --tb=short -q`)
- [ ] 0 TypeScript errors (`cd frontend && npx tsc --noEmit`)
- [ ] 0 ruff errors on backend (`ruff check backend/app/`)
- [ ] Vite build succeeds (`cd frontend && npx vite build`)
- [ ] Docker build passes (`docker build -t daena-test .`)
- [ ] `.env.production` configured with real keys

## Security Configuration
- [ ] `VAULT_ENCRYPTION_KEY` set to random 64-char string
- [ ] `JWT_SECRET_KEY` set to random 64-char string
- [ ] `POSTGRES_PASSWORD` set to random 32-char string
- [ ] `CORS_ORIGINS` set to production domain (`["https://daena.mas-ai.co"]`)
- [ ] `DEBUG=false` and `APP_ENV=production`
- [ ] No wildcard `*` in CORS origins
- [ ] `DISABLE_AUTH=false`

## Infrastructure
- [ ] `DATABASE_URL` points to production PostgreSQL (not SQLite)
- [ ] Redis running and accessible (or graceful degradation accepted)
- [ ] At least one LLM provider API key set (ANTHROPIC, OPENAI, or Ollama)
- [ ] DNS configured for `daena.mas-ai.co`
- [ ] SSL/TLS handled by Cloud Run (automatic)

## V2 Services
- [ ] Swarm config: `SWARM_MAX_PARALLEL_SUBTASKS=5`
- [ ] Autopilot limits: `AUTOPILOT_COST_CEILING_USD=10.00`
- [ ] MCP server: `MCP_SERVER_ENABLED=true`

## GCP Cloud Run
- [ ] `gcloud auth login` completed
- [ ] GCP project `daena-467315` accessible
- [ ] Artifact Registry repo exists
- [ ] Run `bash scripts/deploy-gcp.sh`
- [ ] Verify: `curl https://daena.mas-ai.co/health`
- [ ] Verify: `curl https://daena.mas-ai.co/api/v1/health/ready`
- [ ] Verify: `curl https://daena.mas-ai.co/api/v1/health/version`

## Post-Deploy Verification
- [ ] Registration flow works (create account)
- [ ] Login flow works (JWT issued)
- [ ] Chat streaming works (SSE response)
- [ ] Model registry populates (`/api/v1/chat/model-registry`)
- [ ] Governance audit log records entries
- [ ] Projects page loads and CRUD works
- [ ] RuntimeSwapper shows in header
- [ ] VoiceControls mic button visible in chat
- [ ] ExecutionPanel appears when EXE mode selected
- [ ] Monitor Cloud Run logs for first 30 minutes

## Rollback Plan
- [ ] Know previous revision ID (`gcloud run revisions list --service=daena`)
- [ ] Route traffic back: `gcloud run services update-traffic daena --to-revisions=PREV_REVISION=100`
