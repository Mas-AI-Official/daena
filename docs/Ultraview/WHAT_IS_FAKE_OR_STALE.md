# What Is Fake Or Stale

Date: 2026-04-30

- "Imported" was fake when it meant detected in config but not persisted/callable.
- Provider API key presence was being treated too much like imported/provider health.
- Daena MCP package existence was being treated as persisted state.
- `AGI ACTIVE` was fake health language; it represented autopilot preference.
- Billing/quota duplicate founder identity remains unproven and must not be shown as production truth.
- RAG must not be called online until retrieval works.
- Heartbeat configured checks must not be presented as executed checks.
- Backend health docs from earlier in the day are stale until `/health` returns 200 again.
