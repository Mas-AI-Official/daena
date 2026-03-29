# Changelog

All notable changes to Daena are documented in this file.

## [3.6.0] - 2026-03-28

### Added
- **Tool Lifecycle Manager (TLM)**: Dynamic tool activation/deactivation
  - Tool Registry with governance rules per department
  - Session Manager with configurable idle timeouts (cooldown=3, deactivate=5 turns)
  - Activation Proxy intercepts tool calls post-Orchestra, auto-activates on demand
  - Usage Tracker with cost savings reporting and co-occurrence pattern detection
  - NBMF Bridge for predictive tool pre-warming from L1-L3 memory tiers
  - Orchestra Integration at Stage 7.6 (recording) and Stage 10.1 (turn tick)
  - 10 built-in tools registered at startup (file, terminal, browser operations)
- **Cost Benchmark System**: Compare regular prompting vs Daena orchestrated routing
  - Token savings tracking per session (inactive tool schemas not loaded)
  - Model cost comparison across providers
  - Routing efficiency metrics (cost/quality ratio)
- **Mobile Command Interface**: Control Daena from phone
  - POST /api/mobile/command, GET /api/mobile/status, GET /api/mobile/tasks
  - POST /api/mobile/approve/:gateId for governance gates
  - Quick actions: status, pause, resume, kill
  - Mobile-optimized MobileResponse format (summary + detail + actions)
- **Stay-Awake System**: Prevents Windows sleep during agent runs
  - Three modes: TASK (auto on task start), SESSION, SCHEDULED
  - Safety timeout cap (default 8 hours)
  - PowerShell SetThreadExecutionState integration
  - Cooldown timer with notification hooks
- **Remote Gateway**: Execute on desktop from anywhere
  - Command queue with P0-P3 priority ordering
  - Rate limiting (60 requests/minute per device)
  - Auth validation with device fingerprint
  - Stay-awake integration (wake on command, idle when done)
  - Cloudflare Tunnel / ngrok support
- **Session Persistence**: Cross-device session continuity
  - Create on phone, join on desktop, transfer primary
  - Device capability-aware serialization (mobile gets truncated view)
  - TLM tool state + agent context preserved across device switches
  - Stale session cleanup

### Verified
- Execution layer end-to-end (22 new tests): smoke, pipeline, memory, edge cases, browser E2E
- Full 10-stage pipeline with mock LLM: SecurityGate through AuditLog
- Memory writeback (Stage 10.5) confirmed working
- Concurrent session isolation verified
- Large payload handling (10K characters)

### Metrics
- Test count: 1068 -> 1328 (+260 new tests, 0 regressions)
- New backend services: 8 modules across 4 packages
- New API endpoints: 7 mobile endpoints
- New test suites: 10 test files

## [3.5.2] - 2026-03-27

### Fixed
- User message disappearing after SSE stream (CLI runtime done event)
- Routing mode not sent on every request
- Primary Mind not influencing model selection
- Thinking/reasoning steps disappearing after stream
- Edit+regenerate always regenerates (like ChatGPT)
- Runtime status truthful (Connected only when authenticated)

### Added
- Claude Desktop-style expandable config panels for Connections
- Custom dark-themed permission dropdowns (no native select)
- Voice settings tab (Chrome TTS default, ElevenLabs optional)
- About page with Daena gold logo
- Professional Settings tab ordering (13 tabs)
- UI contrast improvements (toggle borders, disabled opacity, glass panels)

### Security
- Removed .env files, hardcoded API keys, personal paths from source
- Comprehensive .gitignore for sensitive files
- .env.example with documented placeholders

## [3.5.0] - 2026-03-25

### Added
- 10-stage governed pipeline (SecurityGate through AuditLog)
- Council/Quintessence multi-model synthesis
- DaenaBot Phase 1 (FileAgent, TerminalAgent, BrowserAgent)
- Skill Refinery Phase 1+2 (extraction, refinement, retrieval)
- 10 departments, 60 agents, 133 skills
- 26 frontend pages with lazy loading
- Voice integration (browser TTS/STT)
- Billing and cost tracking
- Settings persistence via backend JSONB

### Metrics
- 1068 tests passing
- 0 TypeScript errors
- Main bundle: 114KB (29KB gzip)
