# Wiring Gaps Analysis

Generated: 2026-01-19

## Executive Summary

After scanning **113 backend route files** and **33 frontend JS files**, this document identifies disconnects between backend capabilities and frontend UI.

---

## Gap Analysis by Area

### 1. 💬 Chat & History

| Gap | Root Cause | Fix Summary |
|-----|-----------|-------------|
| Keyboard Delete not working | Frontend: no keydown handler for Delete key | Add `keydown` listener for Delete on session list |
| Clear context does nothing | Frontend: just shows confirm, no API call | Wire to context reset endpoint or session clear |

**Status**: Mostly wired ✅, 2 minor fixes needed

---

### 2. 🧠 Brain & LLM

| Gap | Root Cause | Fix Summary |
|-----|-----------|-------------|
| No LLM provider priority UI | Backend has routing, frontend doesn't expose | Add provider priority toggle in brain settings |

**Status**: Well wired ✅

---

### 3. 🎤 Voice & Audio

| Gap | Root Cause | Fix Summary |
|-----|-----------|-------------|
| Voice status not always synced | Race condition on load | Add retry logic to voice status check |
| Self-test endpoint missing | Backend: endpoint not exposed | Add `GET /api/v1/voice/self-test` |

**Status**: Mostly wired ✅

---

### 4. 🔧 Tools & Automation

| Gap | Root Cause | Fix Summary |
|-----|-----------|-------------|
| Tools not visible in chat | Frontend: tool results go to console only | Show tool cards in chat UI |
| Web search tool stubbed | Backend: detect_and_execute_tool returns mock | Implement real web search API call |
| URL fetch tool stubbed | Backend: same as above | Implement real URL fetch + summarize |

**Status**: Major gap 🔴 - Need to implement 2 real tools

---

### 5. ❤️ Health & Monitoring

| Gap | Root Cause | Fix Summary |
|-----|-----------|-------------|
| System health panel outdated | Frontend: hardcoded statuses | Wire to `/api/v1/health/system` |
| Council health not shown | Frontend: missing panel | Add council health widget in Founder panel |

**Status**: Partially wired ⚠️

---

### 6. 📸 Snapshots & Rollback

| Gap | Root Cause | Fix Summary |
|-----|-----------|-------------|
| No snapshots endpoint | Backend: not implemented | Create `backend/routes/snapshots.py` |
| No snapshot UI | Frontend: missing panel | Add Snapshots panel in Founder UI |

**Status**: Not implemented 🔴

---

### 7. 🗳️ Council & Governance

| Gap | Root Cause | Fix Summary |
|-----|-----------|-------------|
| Debate doesn't show in real-time | Backend: no WebSocket events | Add debate progress events |
| Synthesis results not persistent | Backend: results ephemeral | Save synthesis to DB |

**Status**: Partially wired ⚠️

---

## Priority Fix List

### P0 - Critical for Demo
1. ✅ Chat delete works (already wired)
2. ✅ Demo page works (already wired)
3. 🔴 **Implement 2 real tools** (web search, URL fetch)
4. 🔴 **Implement snapshots API**

### P1 - Important
5. ⚠️ Add keyboard Delete for sessions
6. ⚠️ Wire clear context
7. ⚠️ Add system health panel refresh

### P2 - Nice to Have
8. Add voice self-test
9. Add provider priority UI
10. Add council debate real-time events

---

## Implementation Plan

### Step 1: Snapshots API (P0)
Create `backend/routes/snapshots.py`:
- `POST /api/v1/snapshots` - create snapshot
- `GET /api/v1/snapshots` - list snapshots
- `POST /api/v1/snapshots/{id}/restore` - restore

### Step 2: Real Tools (P0)
Modify `backend/routes/daena.py` `detect_and_execute_tool()`:
- Web search: use DuckDuckGo Instant Answer API
- URL fetch: use httpx + simple extraction

### Step 3: Keyboard Shortcuts (P1)
Add to `daena_office.html`:
```javascript
document.addEventListener('keydown', (e) => {
    if (e.key === 'Delete' && currentSessionId) {
        deleteSession(currentSessionId);
    }
});
```

### Step 4: Founder UI Updates (P1)
Add Snapshots panel and System Health widget to `founder_panel.html`
