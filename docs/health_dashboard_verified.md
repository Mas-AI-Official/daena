# Health Dashboard - Verified

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Root health (main.py:1914) |
| `/api/v1/health/` | Basic health check |
| `/api/v1/health/council` | Council structure validation |
| `/api/v1/health/system` | Comprehensive system check |

## System Health Response

```json
{
  "status": "healthy",
  "council": { ... },
  "database": { "connected": true },
  "llm": { "ollama_available": true, "active_model": "..." },
  "voice": { "available": true/false },
  "timestamp": "..."
}
```

## Frontend Integration
- System Health panel in Founder Panel reads from `/api/v1/health/system`
- Tool Console quick actions use `/api/v1/health/`

## Verification
- `GET http://127.0.0.1:8000/health` → 200
- `GET http://127.0.0.1:8000/api/v1/health/` → 200
