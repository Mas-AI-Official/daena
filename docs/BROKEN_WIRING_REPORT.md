# Broken Wiring Report

**Generated:** 2026-01-21  
**Audit Scope:** Full repo analysis of Daena AI VP system  
**Auditor:** Antigravity QA System

---

## Executive Summary

After comprehensive audit of the Daena repository, I identified **47 wiring issues** across 5 categories:
- **Frontend controls not calling backend:** 12 issues
- **Backend features not exposed in frontend:** 18 issues  
- **Toggle desyncs:** 5 issues
- **Voice pipeline broken points:** 7 issues
- **Environment and launcher failures:** 5 issues

---

## A) Frontend Controls Not Calling Backend

### Issue A1: CMP Page - No Graph API Calls ⭐ FIXED
| Field | Value |
|-------|-------|
| **File** | `frontend/templates/cmp_voting.html` (506 bytes - stub only) |
| **Root Cause** | CMP page was minimal stub with no actual graph functionality |
| **Fix Plan** | Created full n8n-like canvas at `/cmp-canvas` with full API integration |
| **Status** | ✅ FIXED - See `frontend/templates/cmp_canvas.html` |
| **Tests** | `tests/test_cmp_graph.py` |

### Issue A2: QA Dashboard - No Approval Workflow ⭐ FIXED
| Field | Value |
|-------|-------|
| **File** | `frontend/templates/qa_guardian_dashboard.html` |
| **Root Cause** | No approval workflow UI for founder to approve fixes |
| **Fix Plan** | Created approval workflow page with diff preview and approve/deny buttons |
| **Status** | ✅ FIXED - See `frontend/templates/approval_workflow.html` |
| **Tests** | Manual UI testing |

### Issue A3: Control Center - Not Exposing Capabilities
| Field | Value |
|-------|-------|
| **File** | (Did not exist) |
| **Root Cause** | No centralized panel to see all backend capabilities |
| **Fix Plan** | Created Control Center that auto-renders all capabilities with actions |
| **Status** | ✅ FIXED - See `frontend/templates/control_center.html` |
| **Tests** | `tests/test_wiring_audit.py` |

### Issue A4: Voice Widget - TTS Playback Function Missing
| Field | Value |
|-------|-------|
| **File** | `frontend/static/js/voice-widget.js:303` |
| **Root Cause** | `window.speak()` referenced but may not be defined |
| **Fix Plan** | Add TTS playback function or use audio service |
| **Status** | 🔶 PENDING - Audio service exists but not always connected |
| **Tests** | Need `tests/test_voice_e2e.py` |

### Issue A5: WebSocket Connection - Reconnection Logic Missing
| Field | Value |
|-------|-------|
| **File** | `frontend/static/js/websocket-client.js` |
| **Root Cause** | Some pages don't auto-reconnect on connection drop |
| **Fix Plan** | Ensure all pages use same WS reconnection logic |
| **Status** | 🔶 PARTIAL - websocket-enhanced.js has reconnect but not all pages use it |
| **Tests** | Need WebSocket integration test |

### Issue A6-A12: Various Frontend Buttons Not Wired
| Issue | File | Button | Needs Backend Route |
|-------|------|--------|---------------------|
| A6 | `dashboard.html` | "Run Diagnostics" | `/api/v1/diagnostics` |
| A7 | `agents.html` | "Quick Train" btn | `/api/v1/agents/{id}/train` |
| A8 | `councils.html` | "Emergency Stop" | `/api/v1/councils/emergency-stop` |
| A9 | `founder_panel.html` | "Export Config" | `/api/v1/system/export` |
| A10 | `connections.html` | "Test Connection" | `/api/v1/connections/{id}/test` |
| A11 | `workspace.html` | "Sync Now" | `/api/v1/workspace/sync` |
| A12 | `strategic_room.html` | "Record Meeting" | `/api/v1/meetings/record` |

---

## B) Backend Features Not Exposed in Frontend

### Issue B1: Capabilities API ⭐ NEW
| Field | Value |
|-------|-------|
| **File** | `backend/routes/capabilities.py` |
| **Root Cause** | Created but needs UI exposure |
| **Status** | ✅ NOW EXPOSED at `/control-center` |

### Issue B2: SSE Fallback ⭐ NEW
| Field | Value |
|-------|-------|
| **File** | `backend/routes/sse.py` |
| **Root Cause** | SSE fallback created but frontend doesn't use it |
| **Status** | 🔶 NEEDS - Frontend should try SSE if WebSocket fails |

### Issue B3: CMP Graph API ⭐ NEW
| Field | Value |
|-------|-------|
| **File** | `backend/routes/cmp_graph.py` |
| **Status** | ✅ NOW EXPOSED at `/cmp-canvas` |

### Issue B4-B18: Backend Routes Without UI
| Issue | Backend Route | Purpose | Needs UI Panel |
|-------|---------------|---------|----------------|
| B4 | `/api/v1/qa/run-regression` | Run regression tests | QA Dashboard button |
| B5 | `/api/v1/qa/run-security-scan` | Security scanning | QA Dashboard button |
| B6 | `/api/v1/autonomous/execute` | Autonomous company mode | Founder panel toggle |
| B7 | `/api/v1/skills/capsules` | Skill capsule library | Skills panel |
| B8 | `/api/v1/snapshots/create` | Config snapshots | Backup panel |
| B9 | `/api/v1/learning/approve` | Approve Daena learning | Learning requests panel |
| B10 | `/api/v1/social-media/*` | Social media posting | Marketing panel |
| B11 | `/api/v1/hiring/*` | Hiring workflows | HR panel |
| B12 | `/api/v1/deep-search/*` | Deep search | Search panel |
| B13 | `/api/v1/experience/*` | Experience pipeline | Experience panel |
| B14 | `/api/v1/slo/*` | SLO monitoring | SRE panel |
| B15 | `/api/v1/audit/*` | Audit logs | Compliance panel |
| B16 | `/api/v1/env-sync/*` | Environment sync | DevOps panel |
| B17 | `/api/v1/file-system/*` | File operations | File browser |
| B18 | `/api/v1/ocr/*` | OCR comparison | Document panel |

---

## C) Toggle Desyncs

### Issue C1: QA Guardian Enabled Toggle
| Field | Value |
|-------|-------|
| **Frontend** | No toggle visible |
| **Backend** | `QA_GUARDIAN_ENABLED` env var |
| **Root Cause** | Frontend can't toggle QA Guardian state |
| **Fix Plan** | Add toggle in Control Center |
| **Status** | 🔶 PENDING |

### Issue C2: Auto-Fix Toggle
| Field | Value |
|-------|-------|
| **Frontend** | No toggle visible |
| **Backend** | `QA_GUARDIAN_AUTO_FIX` env var |
| **Root Cause** | Dangerous toggle - should have explicit UI with warning |
| **Fix Plan** | Add gated toggle requiring confirmation |
| **Status** | 🔶 PENDING |

### Issue C3: Voice Wake Word Toggle
| Field | Value |
|-------|-------|
| **Frontend** | voice-widget.js has `toggleWakeWord()` |
| **Backend** | No persist - resets on page reload |
| **Fix Plan** | Store in localStorage or user preferences |
| **Status** | 🔶 PARTIAL |

### Issue C4: Autonomous Mode Toggle
| Field | Value |
|-------|-------|
| **Frontend** | Not exposed |
| **Backend** | `/api/v1/autonomous/toggle` |
| **Status** | 🔶 NEEDS UI |

### Issue C5: Kill Switch
| Field | Value |
|-------|-------|
| **Frontend** | Not visible |
| **Backend** | `/api/v1/qa/kill-switch` |
| **Root Cause** | Critical safety control not visible |
| **Fix Plan** | Add prominent kill switch in QA Dashboard |
| **Status** | 🔶 PENDING |

---

## D) Voice Pipeline Broken Points

### Issue D1: STT Endpoint Returns Error
| Field | Value |
|-------|-------|
| **File** | `backend/routes/voice.py:180-245` |
| **Endpoint** | `/api/v1/voice/interact` |
| **Root Cause** | Depends on audio service running on port 5001 |
| **Fix** | Ensure audio service starts with main launcher |
| **Status** | ✅ LAUNCHER UPDATED to start audio service |

### Issue D2: TTS Audio Playback Missing
| Field | Value |
|-------|-------|
| **File** | `frontend/static/js/voice-widget.js:462` |
| **Root Cause** | `window.speak()` not always defined |
| **Fix Plan** | Add fallback to Web Speech API |
| **Status** | 🔶 PENDING |

### Issue D3: Wake Word Detection Restart Loop
| Field | Value |
|-------|-------|
| **File** | `frontend/static/js/voice-widget.js:111-114` |
| **Root Cause** | On error, restarts indefinitely which can spam console |
| **Fix Plan** | Add backoff and max retry limit |
| **Status** | 🔶 PENDING |

### Issue D4: Audio Service Health Check
| Field | Value |
|-------|-------|
| **File** | `frontend/static/js/voice-widget.js:341-371` |
| **Root Cause** | Checks `/api/v1/voice/status` but audio is on different port |
| **Fix Plan** | Main backend should proxy status from audio service |
| **Status** | 🔶 NEEDS PROXY |

### Issue D5: XTTS Model Loading
| Field | Value |
|-------|-------|
| **File** | `audio/audio_service/main.py` |
| **Root Cause** | XTTS model may not be downloaded |
| **Fix Plan** | Add model download check on first start |
| **Status** | 🔶 PENDING |

### Issue D6: HuggingFace Cache Path Hardcoded
| Field | Value |
|-------|-------|
| **Files** | Various Python files |
| **Root Cause** | HF cache path sometimes assumed in repo |
| **Fix Plan** | Use `HF_HOME` and `TRANSFORMERS_CACHE` env vars |
| **Status** | ✅ FIXED in launcher |

### Issue D7: Microphone Permission Not Checked
| Field | Value |
|-------|-------|
| **File** | `frontend/static/js/voice-widget.js:386-414` |
| **Root Cause** | Attempts mic access without pre-check |
| **Fix Plan** | Check permissions before trying to record |
| **Status** | 🔶 PENDING |

---

## E) Environment and Launcher Failures

### Issue E1: "\default-key" Error
| Field | Value |
|-------|-------|
| **Root Cause** | Environment variable with backslash in path |
| **Files** | Various .bat files with path handling |
| **Fix Plan** | Use forward slashes in paths, validate env vars |
| **Status** | ✅ FIXED in launcher |

### Issue E2: Port Conflict Detection
| Field | Value |
|-------|-------|
| **File** | `START_DAENA.bat` |
| **Root Cause** | Port detection already exists but could fail silently |
| **Fix Plan** | Already implemented - PowerShell port finder |
| **Status** | ✅ WORKS |

### Issue E3: Python venv Not Found
| Field | Value |
|-------|-------|
| **File** | `START_DAENA.bat:80-90` |
| **Root Cause** | If venv doesn't exist, gives helpful error |
| **Status** | ✅ WORKS |

### Issue E4: Audio venv Not Found
| Field | Value |
|-------|-------|
| **File** | `START_DAENA.bat:126-133` |
| **Root Cause** | Audio venv is optional - shows warning |
| **Status** | ✅ WORKS |

### Issue E5: QA Guardian Not Passing Through
| Field | Value |
|-------|-------|
| **File** | `START_DAENA.bat` |
| **Root Cause** | QA Guardian env vars not passed to backend |
| **Fix Plan** | Pass all QA_ vars in start command |
| **Status** | ✅ FIXED |

---

## Summary Table

| Category | Total Issues | Fixed | Partial | Pending |
|----------|--------------|-------|---------|---------|
| A) Frontend→Backend | 12 | 3 | 1 | 8 |
| B) Backend→Frontend | 18 | 3 | 0 | 15 |
| C) Toggle Desyncs | 5 | 0 | 2 | 3 |
| D) Voice Pipeline | 7 | 2 | 0 | 5 |
| E) Launchers | 5 | 4 | 0 | 1 |
| **TOTAL** | **47** | **12** | **3** | **32** |

---

## Priority Fixes for This Session

### Completed ✅
1. CMP n8n-like canvas (`/cmp-canvas`)
2. Capabilities API (`/api/v1/capabilities`)
3. Control Center UI (`/control-center`)
4. Approval Workflow UI (`/api/v1/qa/approvals`)
5. SSE Fallback (`/sse/events`)
6. Guardian Control API (`backend/qa_guardian/control_api.py`)
7. Quarantine Module (`backend/qa_guardian/quarantine.py`)
8. Updated Charter with frontend patching rules
9. Updated launcher with QA Guardian enabled
10. HF Cache configurable via env vars

### Next Priority 🔶
1. Voice diagnostics wizard
2. SSE fallback in frontend
3. Kill switch UI toggle
4. Backend routes for missing RPC endpoints

---

## Verification Commands

```bash
# Run wiring audit tests
cd d:\Ideas\Daena_old_upgrade_20251213
.\venv_daena_main_py310\Scripts\python.exe -m pytest tests/test_wiring_audit.py -v

# Run CMP graph tests
.\venv_daena_main_py310\Scripts\python.exe -m pytest tests/test_cmp_graph.py -v

# Start system with QA Guardian
START_DAENA.bat

# Access dashboards after startup:
# - QA Guardian: http://localhost:8000/api/v1/qa/ui
# - CMP Canvas: http://localhost:8000/cmp-canvas
# - Control Center: http://localhost:8000/control-center
# - Approval Workflow: http://localhost:8000/api/v1/qa/approvals
```

---

*Report generated by Antigravity QA System v1.0*
