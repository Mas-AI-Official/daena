# Frontend XSS Mitigation – escapeHtml Audit (2026-01-29)

## Overview

User-controlled or API-sourced content that is rendered into the DOM via `innerHTML` (or equivalent) must be escaped to prevent XSS. The project uses `window.escapeHtml(s)` (defined in `frontend/templates/base.html`) to encode `&`, `<`, `>`, `"`, `'` for safe display.

## Where escapeHtml Is Used

### Already safe / updated this session

- **base.html**: Brain status indicator – `modelLabel` from API is escaped when set into `indicator.innerHTML`.
- **dashboard.html**: Brain status – `activeModel` escaped; activity list – `formatEventText(event)` and `timeAgo` escaped; task progress – department name escaped.
- **realtime-status-manager.js**: Brain indicator – `activeModel` escaped when setting `indicator.innerHTML`.
- **agent_detail.js**: User message already escaped; API `data.response` is escaped before `formatResponse()`; `data.error` and `error.message` escaped. Local `escapeHtml` made null-safe.
- **incident_room.html**: Decoy hits, IPs, user agents, and error messages use local `escapeHtml` / `escapeAttr`.

### Recommendation for other scripts

When rendering **API or user content** into the DOM with `innerHTML` or `.html()`, use:

- `window.escapeHtml(s)` when the page extends base (so `escapeHtml` is global), or
- A local escape that sets `div.textContent = s` and returns `div.innerHTML`.

Apply this in:

- **department-chat.js**: Chat message bodies (user and assistant).
- **change-audit.js** / **change-control.js**: Change titles, descriptions, and any text from API.
- **strategic-room.js**: Goal and initiative text from API.
- **conference-room.js**: Participant names and message text.
- **agents.js** / **connections.js**: Agent names, connection labels, and other API text.
- **agent-builder.js**: Template and capability names from API.
- **ui-components.js**, **connection-status-ui.js**, **toast-notifications.js**, **voice-client.js**, **god_mode.js**: Any dynamic text that comes from API or user input.

## Pattern

```javascript
// Safe: escape before inserting into HTML
el.innerHTML = '<div class="msg">' + (window.escapeHtml ? window.escapeHtml(userText) : userText) + '</div>';
// Or when building from API data
row.innerHTML = '<td>' + escapeHtml(apiRow.name) + '</td>';
```

Prefer `textContent` when you are only showing plain text (no HTML):

```javascript
el.textContent = userText;  // Safe, no HTML interpretation
```

## References

- `frontend/templates/base.html` – `window.escapeHtml` definition.
- `docs/2026-01-29/FRONTEND_AND_SECURITY_SUGGESTIONS.md` – General frontend and security notes.
