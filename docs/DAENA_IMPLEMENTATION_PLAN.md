# DAENA — Cursor Implementation Plan

This document tracks the 8 prompts from the DAENA Control Plane Integration Guide and their implementation status.

## Quick Reference

| # | Prompt | Goal | Status | Key Files |
|---|--------|------|--------|-----------|
| 1 | Frontend-Backend Sync | WebSocket persistence, event routing, autopilot 3-way sync | In progress | control_plane_v2.html, event_bus.py, websocket.py |
| 2 | Pipeline Trigger Gaps | Chat→governance→execution wiring | Pending | chat.py, governance_loop.py, skills.py, packages.py |
| 3 | AGI Autopilot Real-Time | Enforce autopilot, pending actions table | Partial (governance has /pending, /approve) | governance_loop.py, governance.py |
| 4 | $DAENA Token Design | AGI-native token, contracts, docs | Pending | contracts/, docs/TOKENOMICS.md |
| 5 | NPM Security Audit | Lock versions, .npmrc, supply-chain | In progress | package.json, .npmrc |
| 6 | Dependabot Fixes | Merge security branch, dependabot.yml, SECURITY.md | In progress | .github/dependabot.yml, SECURITY.md |
| 7 | Local LLM + Governance | Ollama + governance gates | Pending | llm_service.py, brain_status.py, config |
| 8 | Architecture Audit | Wiring map, route audit, security audit | In progress | docs/WIRING_MAP.md, audit_scripts/ |

## Implementation Order

1. **Event bus & broadcast** — Add `broadcast(event_type, data, message)` to event_bus; ensure all pipeline/skill/package events use it.
2. **Chat pipeline** — Fix chat.py to use event_bus correctly; broadcast think/plan/act/report; wire governance assess before execution.
3. **Governance API** — Add `POST /approve/{decision_id}` and `POST /reject/{decision_id}`; ensure toggle-autopilot broadcasts event.
4. **Control Plane frontend** — WebSocket reconnect with backoff; handleWSEvent routing for all event types; loadTabData on event.
5. **Config & security** — .npmrc, dependabot.yml, SECURITY.md, requirements-lock.txt.
6. **Tests & push** — Run verification commands; push to GitHub.

## Verification Commands (from prompts)

```bash
# Backend
python -c "from backend.main import app; print('OK')"
curl -s http://127.0.0.1:8000/api/v1/governance/pending
curl -s -X POST http://127.0.0.1:8000/api/v1/governance/toggle-autopilot -H "Content-Type: application/json" -d '{"enabled":false}'
curl -s -X POST http://127.0.0.1:8000/api/v1/chat -H "Content-Type: application/json" -d '{"message":"hello"}'

# Frontend
cd frontend && npm audit
```

## Deliverables Checklist

- [ ] event_bus broadcasts all required event types
- [ ] Chat POST /api/v1/chat broadcasts pipeline stages
- [ ] Governance /pending, /approve/{id}, /reject/{id} working
- [ ] Control Plane WebSocket reconnect + event routing
- [ ] .github/dependabot.yml, SECURITY.md, requirements-lock.txt
- [ ] frontend .npmrc, exact versions where applicable
- [ ] docs/WIRING_MAP.md or audit report
- [ ] All tests run; push to GitHub
