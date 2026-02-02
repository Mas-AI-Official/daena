# Frontend Audit & Suggestions

## Key workflows verified (sync with backend)

| Page | Key actions | Backend / API | Status |
|------|-------------|---------------|--------|
| **Dashboard** | Hex departments, Quick Actions (Ask Daena, Agents, Projects, Analytics, Brain Settings, App Setup, Founder), Execution Layer (token Save, Run tool, tool toggles) | `/ui/*`, `/api/v1/brain/status`, `/api/v1/execution/*`, `/api/v1/events/recent`, `/api/v1/tasks/*` | Wired; brain/execution use API |
| **Daena Office** | Send message, New Chat, session list, Delete/Restore, Export, Say Daena (voice), Brain status, Categories | `/api/v1/daena/chat`, `/api/v1/chat-history/*`, `/api/v1/brain/status`, `/api/v1/voice/*` | Wired via `window.api` and fetch |
| **Brain Settings** | Scan models, Routing mode, Test model, Pull model, Select (enable/disable) model | `/api/v1/brain/scan`, `/api/v1/brain/routing_mode`, `/api/v1/brain/test`, `/api/v1/brain/pull`, `/api/v1/brain/models/{name}/select` | Wired; test accepts `model_name` in body |
| **App Setup** | Links to Brain Settings, Dashboard#execution-layer, Connections | Navigation only | Wired |
| **Connections** | Refresh, Load tools, Load active connections, Connect, Test, Disconnect, filterTools | `/api/v1/connections/tools`, `/api/v1/connections/list`, `/api/v1/connections/test`, `/api/v1/connections/connect`, `DELETE /connections/{id}` | Wired (inline script; duplicate block removed) |
| **Topbar (base)** | Brain indicator, Voice button | `RealtimeStatusManager`, `window.voiceWidget?.toggleRecording()` | Wired |
| **Sidebar** | Dashboard, Daena Office, Projects, Councils, Workspace, Analytics, Agents, Brain & API, App Setup, Founder | `/ui/*` | Wired |

## Fixes applied

1. **Connections page**: Removed duplicate `{% block scripts %}` that overwrote the inline script with `connections.js` (which targeted different DOM/API). Connections now uses the inline script and correct endpoints.
2. **Brain test endpoint**: Backend `/api/v1/brain/test` now accepts optional `model_name` in the request body so "Test" in Brain Settings tests the selected model.

## Checklist for new buttons/links

- [ ] `onclick` or `href` points to a defined function or URL.
- [ ] API calls use `window.api.request('/path')` (prefix `/api/v1` is in api-client) or `fetch('/api/v1/...')`.
- [ ] Errors show toast or message (e.g. `window.showToast('...', 'error')`).
- [ ] Loading state (e.g. spinner or disabled button) where appropriate.

## Suggestions to make the project better and more secure

### Security

1. **Auth and tokens**
   - In production, enable auth (`DISABLE_AUTH=0`) and use JWT or session cookies.
   - Keep Execution Layer token server-side only; require `EXECUTION_TOKEN` and `X-Execution-Token` for sensitive tool runs.
   - Do not log or expose API keys in frontend; keep cloud API keys in env/backend only.

2. **CSP and headers**
   - Add Content-Security-Policy (CSP) to limit script/style sources and reduce XSS risk.
   - Use secure cookies (SameSite, Secure in production) if you add session cookies.

3. **Input validation**
   - Sanitize user input before rendering in HTML (e.g. session titles, chat) to avoid XSS.
   - Backend already validates; keep frontend validation for UX and add sanitization where content is injected into DOM.

4. **Sensitive actions**
   - For destructive actions (e.g. delete session, disconnect, run tool), keep confirmations and consider requiring re-auth or a second factor in production.

### Reliability and UX

5. **API base URL**
   - Prefer `window.api.request('/path')` everywhere so base URL and headers (e.g. `X-Execution-Token`) are consistent. Replace raw `fetch('/api/v1/...')` with `window.api.request('/...')` where possible.

6. **Retries and offline**
   - For critical calls (e.g. send message, brain status), consider a single retry or "Reconnect" button when the request fails.
   - Show a clear "Backend offline" or "Reconnecting" state when health/status checks fail.

7. **Voice widget**
   - Ensure `window.voiceWidget` is set after voice-widget.js loads; topbar uses `window.voiceWidget?.toggleRecording()`. If the script loads late, show a short "Loading voice..." or disable the button until ready.

8. **Brain status**
   - When `using_fallback: true` in `/api/v1/brain/status`, show a small "Local brain (fallback)" label so users know they are on the fallback Ollama.

### Code quality

9. **Single block scripts**
   - Avoid two `{% block scripts %}` in one template; the second overrides the first. Put all script for that page in one block or in one external JS file.

10. **Centralized errors**
    - Use a small helper, e.g. `window.handleApiError(e, 'Label')`, that logs and shows a toast so error handling is consistent.

11. **Types / docs**
    - Consider JSDoc or TypeScript for api-client.js and main page scripts so request/response shapes are documented and easier to keep in sync with the backend.

### Performance and ops

12. **Caching**
    - For rarely changing data (e.g. connections list, brain models), consider short-lived client cache (e.g. 30s) to avoid repeated requests on tab switch.

13. **Health check**
    - Add a lightweight `/health` or `/api/v1/health` used by the frontend (e.g. dashboard) to show "Backend online/offline" and optionally trigger reconnect logic.

14. **Logging**
    - In production, avoid logging full request/response; log only method, path, and status (or use a backend-side audit log for sensitive actions).

---

Use this doc as a living checklist: update the table when adding pages or endpoints, and tick security/reliability items as you implement them.
