# Daena UI/UX Roadmap -- Session Handoff

## COMPLETED THIS SESSION

### P0: Agentic Tool Use (THE gap -- FIXED)
- Wired `ToolUseLoop` into `chat_orchestrator.py` as Step C
- Pipeline now: regex match -> ActionPlanner -> **ToolUseLoop (LLM decides tools)**
- 37 tools available to LLM: file ops, terminal, browser, desktop, MCP, Gmail, Calendar, Notion, web search, vision loop
- In EXE mode, Daena now behaves like OpenClaw -- LLM calls tools inline, sees results, keeps going
- Auto-install: if a tool/package is missing, Daena installs it and retries (AGI mode)
- Self-repair: if code fails, Daena tries to fix it (AGI mode)
- Desktop control: pyautogui for mouse/keyboard/screenshot, falls back to Windows-MCP

### P0: Security Architecture (39 capabilities)
- MissionIntelligence: autonomous mission brain with detective wall graph
- ProximityMapper, AttractionSimulator, CreativePathGenerator
- TraceManager, EngagementController, OpSecShield
- Mission API: 15 REST endpoints
- 76/76 tests passing


## REMAINING ISSUES (next sessions)

### P0: Backend Errors
- [ ] `estimated_cost=0.05` hardcoded in cost preflight (chat_orchestrator.py:606)
      Fix: calculate from model pricing, not hardcoded
- [ ] OPENROUTER "no_key" warning -- not an error, just info log. Suppress or demote to debug
- [ ] GROQ registered but may not have key -- same, demote warning level

### P1: Execution View
- [ ] Frontend has "Execution View" toggle above chat input bar
- [ ] Currently shows nothing -- needs to display `daenabot_activity` events
- [ ] Wire SSE events of type "tool_call", "tool_result", "daenabot_activity" to this view
- [ ] Show: tool name, status (executing/completed/failed), result preview
- [ ] This is where users SEE Daena working (like Claude Code's tool output)

### P1: Orb Colors
- [ ] CMD mode: orb should be blue
- [ ] EXE mode: orb should be gold
- [ ] Aurora around orb should change with reasoning mode:
      Standard = default, Council = blue, Quintessence = purple/shiny
- [ ] Currently orb colors may not match between council selector and top nav

### P1: Broken Pages
- [ ] `/account/api-keys` -- page not loading. Check route exists and component renders
- [ ] Connections OAuth -- "Google Calendar OAuth not configured" is expected (no env vars set)
      But the error UX should be better: show setup instructions, not raw error
- [ ] Files upload -- file goes somewhere but user can't see where or what for
      Needs: upload destination visible, file list, file preview, delete option
- [ ] Pipeline in Projects -- unclear purpose. Either document it or remove it

### P1: Department Stars
- [ ] Some departments have stars, others don't
- [ ] Need to clarify: stars = active? = has skills? = has workflows?
- [ ] Make consistent and add tooltip explaining what stars mean

### P2: Settings Cleanup
- [ ] Audit all settings tabs for duplicates
- [ ] Arrange logically top-to-bottom: identity, preferences, models, display, advanced
- [ ] Remove any settings that aren't wired to backend
- [ ] Ensure all settings persist on save (backend JSONB)

### P2: Projects Page Redesign
- [ ] Current projects page is basic -- needs workspace concept
- [ ] Perplexity model: 1 project = 1 workspace with files, tasks, connections, skills
- [ ] Each project scopes context for agents (when chatting in a project, agents only see project files)
- [ ] Design decision: local files vs cloud storage vs both
- [ ] For local users: project folder on disk (like Claude Code projects)
- [ ] For cloud users: Google Drive / Dropbox integration (future)

### P2: Tasks Page
- [ ] Wire to real backend task data
- [ ] Show: task name, status, assigned department, created date
- [ ] Perplexity-style: simple list with status badges
- [ ] Link tasks to projects

### P2: Skills Dropdown
- [ ] Current dropdown design is poor
- [ ] Redesign: categorized grid or searchable list
- [ ] Show: skill name, department, confidence score, last used

### P3: Strategic Decisions

#### Cloud vs Local Model
- Perplexity Computer: cloud-first, simple, 1 task/1 file/1 connection
- Zoo Computer: downloadable tools installed on user's PC
- Daena decision: **local-first with cloud option**
  - FREE tier: everything runs locally (Ollama + local tools)
  - PRO tier: cloud APIs + remote runtimes
  - Tools install on user's computer (makes sense, cheaper for us)
  - Cloud storage optional (Google Drive / Dropbox connector)
  - DaenaBot bridge for cloud users who want local access

#### File/Document Strategy
- Local users: project folder on disk, Daena reads/writes directly
- Cloud users: bridge connection to their machine OR cloud storage
- We should NOT host user files (expensive, liability)
- Perplexity approach: simple file upload with context injection
- Our approach: file references (point to file, Daena reads when needed)

### P3: Data Sync
- [ ] All frontend data should be realtime from backend
- [ ] No stale data on page refresh
- [ ] SSE or WebSocket for live updates (governance, tasks, heartbeat)
- [ ] Currently some pages fetch once and don't refresh
