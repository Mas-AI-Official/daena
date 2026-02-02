# Frontend & Security Suggestions

## Done This Session

- Dashboard 2x2 layout; brain/voice from API; execution panel.
- App Setup page for core services configuration.
- Connections fix (single `{% block scripts %}`); global `handleApiError`; brain test with `model_name`.
- Realtime status and voice widget fixes for stable indicators.

## Recommendations

1. **Incident Room UI**: Add a page (or section in QA Guardian dashboard) that lists deception hits (`GET /api/v1/_decoy/hits`) and provides “Lockdown” / “Unlock” actions calling founder-panel endpoints.
2. **Rate limiting**: Enable `rate_limit_middleware` in production (`main.py` uncomment and configure) and document Cloudflare/Cloud Armor for edge.
3. **XSS**: Use `window.escapeHtml(s)` (defined in base.html) when setting innerHTML from user or API content (e.g. chat messages, user names). Backend validation remains primary; this reduces reflected XSS risk in the UI.
4. **Auth on decoy hits**: In production, require auth (e.g. founder or Guardian role) for `GET /api/v1/_decoy/hits`.
