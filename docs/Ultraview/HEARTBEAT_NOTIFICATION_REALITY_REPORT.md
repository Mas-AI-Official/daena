# Heartbeat / Notification Reality Report

Date: 2026-04-30

## Heartbeat Evidence

Authenticated probe before backend outage:

- `/api/v1/heartbeat/status` returned daemon state `stopped`.
- `cycle_count` was `0`.
- Many checks were configured, but no run history existed.

## Verdict

The old UI risk was real: configured checks can look like executed checks. That is fake operational confidence.

## Correct State Model

Heartbeat UI must show these as separate fields:

- Configured
- Enabled
- Running
- Stopped
- Last run
- Last result
- Last error
- Next run
- Runtime used
- Cost used

## Source Inspection

- Backend has real endpoints: `/heartbeat/status`, `/heartbeat/start`, `/heartbeat/pause`, `/heartbeat/resume`, `/heartbeat/stop`, `/heartbeat/run-once`, `/heartbeat/history`, `/heartbeat/cron`.
- `SettingsHeartbeat.tsx` maps backend `state`, `cycle_count`, `last_check`, and `next_check`, but the visible copy still frames heartbeat as autonomous background execution even when stopped.
- Run Now calls `/heartbeat/run-once`; if backend is available, it should record history or return a real error.

## Notifications

Notification UI remains unproven:

- Browser notification permission can be checked locally.
- Email notification configuration is not proven wired to backend delivery.
- Any email/SMS test button must be disabled or labeled `Not configured` unless it actually sends through a configured backend provider.

## Required P1 Repair

- Add explicit `Daemon stopped` state.
- Show `0 executed runs` separately from configured checks.
- Disable or honest-label notification tests without a configured delivery backend.
