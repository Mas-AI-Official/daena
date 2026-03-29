# Daena Heartbeat Configuration

## Interval
- Default: 30 minutes
- Minimum: 1 minute (for testing)
- Overnight: 30 minutes

## Active Hours
- Start: 07:00
- End: 23:00
- Overnight mode: set End to 07:00 (next day) for 24/7 operation

## Autopilot Levels
- OFF: Run checks, queue ALL actions for human approval
- ON: Auto-execute non-critical actions, queue critical for approval
- AGI: Auto-execute everything including critical (with full audit trail)

## Default Checks
- [x] Runtime health (are Claude Code, Codex, Ollama online?)
- [x] Tasks (pending items in tasks.md)
- [x] Inbox (new items in inbox.md)
- [x] Project state (STATE.md changes)
- [x] Git status (uncommitted changes)
- [ ] Test suite (run pytest, report failures)
- [ ] Overnight queue (process work queue)

## Three-Question Reflection (per cycle)
1. "What can I do right now that hasn't been done?"
2. "Which action has the highest ROI?"
3. "What did I do last cycle and what happened?"

## Cost Guards
- Max per cycle: $0.10
- Max per day: $2.00
- Prefer Ollama (free) for routine checks
- Escalate to Claude Code only for real work

## Cron Jobs
- Morning Briefing: 07:00 daily (disabled by default)
- Weekly Review: 09:00 Monday (disabled by default)

## API
- GET  /api/v1/heartbeat/status
- POST /api/v1/heartbeat/start
- POST /api/v1/heartbeat/pause
- POST /api/v1/heartbeat/resume
- POST /api/v1/heartbeat/stop
- POST /api/v1/heartbeat/configure
- GET  /api/v1/heartbeat/history
- POST /api/v1/heartbeat/run-once
- GET  /api/v1/heartbeat/cron
