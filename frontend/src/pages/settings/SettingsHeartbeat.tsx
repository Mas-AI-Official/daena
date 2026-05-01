/**
 * SettingsHeartbeat -- heartbeat daemon configuration tab.
 *
 * Controls: interval, active hours, check toggles, cost guard,
 * recent heartbeat history, and manual trigger.
 */
import { useEffect, useState, useCallback } from 'react'
import {
  Heart,
  Clock,
  Play,
  Pause,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Loader2,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { Card, Badge, Switch } from '@/components/common'

interface DaenaHeartbeatStatus {
  running: boolean
  paused: boolean
  last_run: string | null
  next_run: string | null
  total_runs: number
  interval_minutes: number
  active_hours: { start: string; end: string }
  checks: Record<string, boolean>
}

/** Raw shape returned by the backend daemon.get_status() */
interface BackendHeartbeatStatus {
  state: 'running' | 'paused' | 'stopped' | string
  interval_minutes: number
  autopilot_level?: number
  cycle_count: number
  last_check: string | null
  next_check: string | null
  active_hours: string          // e.g. "07:00-23:00"
  checks_enabled: string[]      // e.g. ["inbox", "tasks"]
}

/**
 * Maps the backend daemon status shape to the frontend DaenaHeartbeatStatus shape.
 */
function mapBackendStatus(raw: BackendHeartbeatStatus): DaenaHeartbeatStatus {
  const running = raw.state === 'running' || raw.state === 'paused'
  const paused = raw.state === 'paused'

  const [start = '07:00', end = '23:00'] = (raw.active_hours ?? '07:00-23:00').split('-')

  const checks: Record<string, boolean> = {}
  for (const key of Object.keys(CHECK_LABELS)) {
    checks[key] = raw.checks_enabled?.includes(key) ?? false
  }

  return {
    running,
    paused,
    last_run: raw.last_check,
    next_run: raw.next_check,
    total_runs: raw.cycle_count,
    interval_minutes: raw.interval_minutes,
    active_hours: { start, end },
    checks,
  }
}

interface DaenaHeartbeatHistoryEntry {
  timestamp: string
  status: string
  actions_taken: number
  cost_usd: number
  message: string
}

const INTERVAL_OPTIONS = [
  { label: '15 min', value: 15 },
  { label: '30 min', value: 30 },
  { label: '1 hr', value: 60 },
  { label: '2 hr', value: 120 },
]

// Must match backend app/services/heartbeat/heartbeat_config.CheckType.
// Aligned 2026-04-16 after audit showed the old list missed 8 check
// types (autonomous_work, department_workflows, test_suite, github_issues,
// failed_tasks, git_status, queue, ollama_health, ollama_model_updates,
// daily_report) and had two legacy keys (self_audit, email) that no
// longer map to any backend check. If you add a new CheckType enum
// value on the backend, mirror it here or the toggle stays invisible
// in the settings UI.
const CHECK_LABELS: Record<string, string> = {
  runtime_health: 'Runtime health (all CLIs)',
  tasks: 'Task queue (tasks.md)',
  inbox: 'Inbox (inbox.md)',
  project_state: 'Project state (STATE.md)',
  git_status: 'Git status (uncommitted / unpushed)',
  queue: 'Autonomous work queue',
  test_suite: 'Test suite health',
  github_issues: 'GitHub issues (assigned / mentions)',
  failed_tasks: 'Failed-task retry sweep',
  ollama_health: 'Ollama daemon health',
  ollama_model_updates: 'Ollama model update check',
  department_workflows: 'Department workflow ticks',
  autonomous_work: 'Autonomous work scanner',
  daily_report: 'Daily digest generator',
}

export function SettingsHeartbeat() {
  const [status, setStatus] = useState<DaenaHeartbeatStatus | null>(null)
  const [history, setHistory] = useState<DaenaHeartbeatHistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.get('/heartbeat/status')
      if (res.data?.data) setStatus(mapBackendStatus(res.data.data as BackendHeartbeatStatus))
    } catch {
      /* graceful degradation */
    }
  }, [])

  const fetchHistory = useCallback(async () => {
    try {
      const res = await api.get('/heartbeat/history?limit=10')
      if (res.data?.data) setHistory(res.data.data)
    } catch {
      /* graceful */
    }
  }, [])

  useEffect(() => {
    Promise.all([fetchStatus(), fetchHistory()]).finally(() => setLoading(false))
  }, [fetchStatus, fetchHistory])

  const handleToggle = async () => {
    if (!status) return
    setActionLoading('toggle')
    try {
      if (status.running && !status.paused) {
        await api.post('/heartbeat/pause')
        toast.success('Daena Heartbeat paused')
      } else {
        await api.post('/heartbeat/start')
        toast.success('Daena Heartbeat started')
      }
      await fetchStatus()
    } catch {
      toast.error('Failed to toggle heartbeat')
    } finally {
      setActionLoading(null)
    }
  }

  const handleTriggerNow = async () => {
    setActionLoading('trigger')
    try {
      await api.post('/heartbeat/run-once')
      toast.success('Daena Heartbeat triggered')
      await Promise.all([fetchStatus(), fetchHistory()])
    } catch {
      toast.error('Failed to trigger heartbeat')
    } finally {
      setActionLoading(null)
    }
  }

  const handleIntervalChange = async (minutes: number) => {
    setActionLoading('interval')
    try {
      await api.post('/heartbeat/configure', { interval_minutes: minutes })
      toast.success(`Interval set to ${minutes} min`)
      await fetchStatus()
    } catch {
      toast.error('Failed to update interval')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCheckToggle = async (check: string, enabled: boolean) => {
    if (!status) return
    try {
      const updated = { ...status.checks, [check]: enabled }
      await api.post('/heartbeat/configure', { checks: updated })
      await fetchStatus()
    } catch {
      toast.error('Failed to update check')
    }
  }

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-6 w-40 rounded bg-white/5" />
        <div className="h-32 rounded-lg bg-white/[0.02]" />
      </div>
    )
  }

  const isActive = status?.running && !status?.paused

  return (
    <div className="space-y-6">
      {/* Header with toggle */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-display font-bold text-starlight-100">Daena Heartbeat</h2>
          <p className="text-xs text-starlight-400 mt-0.5">
            Autonomous background monitoring and task execution
          </p>
        </div>
        <Switch
          checked={!!isActive}
          onChange={handleToggle}
          disabled={actionLoading === 'toggle'}
          label=""
          size="md"
        />
      </div>

      {/* Status card */}
      <Card variant="glass" padding="md">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isActive ? 'bg-accent-green/10' : 'bg-white/5'}`}>
            <Heart
              size={18}
              className={isActive ? 'text-accent-green animate-pulse' : 'text-starlight-500'}
            />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-starlight-100">
                {isActive ? 'Active' : status?.paused ? 'Paused' : 'Stopped'}
              </span>
              <Badge variant={isActive ? 'success' : 'default'} size="sm">
                {status?.total_runs || 0} runs
              </Badge>
            </div>
            {status?.last_run && (
              <p className="text-[10px] text-starlight-500 mt-0.5">
                Last: {new Date(status.last_run).toLocaleTimeString()}
                {status.next_run && ` | Next: ${new Date(status.next_run).toLocaleTimeString()}`}
              </p>
            )}
          </div>
          <button
            onClick={handleTriggerNow}
            disabled={actionLoading === 'trigger'}
            className="px-3 py-1.5 rounded-lg text-xs bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {actionLoading === 'trigger' ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Play size={12} />
            )}
            Run Now
          </button>
        </div>
      </Card>

      {/* Phase 10C-D banner: interval / active hours / checks / cost guard
          persist only in daemon process memory; uvicorn restart resets them.
          Phase 11 PR-H1 will move daemon config to a heartbeat_config table. */}
      <div
        className="flex items-start gap-2 rounded-lg border border-accent-amber/20 bg-accent-amber/5 px-3 py-2"
        title="Phase 10C-D: the controls below (interval, active hours, checks) write to the daemon's in-memory config object. A backend restart erases them. Phase 11 PR-H1 will move all daemon config to a persistent heartbeat_config table."
      >
        <Badge variant="warning" size="sm">Daemon-memory only</Badge>
        <p className="text-[10px] text-starlight-400 leading-relaxed">
          Interval, active hours, and checks below write to the daemon's in-memory
          config object — a backend restart erases them. Phase 11 PR-H1 moves these
          to a persistent <code>heartbeat_config</code> table.
        </p>
      </div>

      {/* Interval selector */}
      <div>
        <label className="block text-xs font-semibold text-starlight-300 mb-2">
          <Clock size={12} className="inline mr-1.5" />
          Interval
        </label>
        <div className="flex gap-2">
          {INTERVAL_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleIntervalChange(opt.value)}
              disabled={actionLoading === 'interval'}
              className={`px-3 py-2 rounded-lg text-xs border transition-all cursor-pointer ${
                status?.interval_minutes === opt.value
                  ? 'bg-primary-500/15 text-primary-400 border-primary-500/20'
                  : 'bg-white/5 text-starlight-400 border-white/5 hover:bg-white/10'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Active hours */}
      <div>
        <label className="block text-xs font-semibold text-starlight-300 mb-2">Active Hours</label>
        <div className="flex items-center gap-3">
          <input
            type="time"
            defaultValue={status?.active_hours?.start || '07:00'}
            className="glass-input px-3 py-2 rounded-lg text-xs text-starlight-200"
          />
          <span className="text-xs text-starlight-500">to</span>
          <input
            type="time"
            defaultValue={status?.active_hours?.end || '23:00'}
            className="glass-input px-3 py-2 rounded-lg text-xs text-starlight-200"
          />
        </div>
      </div>

      {/* Checks toggles */}
      <div>
        <label className="block text-xs font-semibold text-starlight-300 mb-2">Checks</label>
        <div className="space-y-2">
          {Object.entries(CHECK_LABELS).map(([key, label]) => {
            const enabled = status?.checks?.[key] ?? false
            return (
              <label
                key={key}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/[0.02] hover:bg-white/[0.04] transition-colors cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => handleCheckToggle(key, e.target.checked)}
                  className="w-3.5 h-3.5 rounded border-white/20 bg-transparent text-primary-500 focus:ring-primary-500/30"
                />
                <span className="text-xs text-starlight-300">{label}</span>
              </label>
            )
          })}
        </div>
      </div>

      {/* Cost guard */}
      <Card variant="glass" padding="md" className="space-y-2">
        <h3 className="text-xs font-semibold text-starlight-300">Cost Guard</h3>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-starlight-500">Max tokens per heartbeat:</span>
          <input
            type="number"
            defaultValue={1000}
            className="glass-input w-20 px-2 py-1.5 rounded text-xs text-starlight-200 text-center"
          />
        </div>
        <label className="flex items-center gap-2 text-[10px] text-starlight-400 cursor-pointer">
          <input
            type="checkbox"
            defaultChecked
            className="w-3 h-3 rounded border-white/20 bg-transparent text-primary-500"
          />
          Use cheapest runtime first (Ollama)
        </label>
      </Card>

      {/* Recent history */}
      <div>
        <h3 className="text-xs font-semibold text-starlight-300 mb-2">Recent Daena Heartbeats</h3>
        {history.length === 0 ? (
          <p className="text-[10px] text-starlight-500 italic">No heartbeat history yet</p>
        ) : (
          <div className="space-y-1.5">
            {history.map((entry, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.02]"
              >
                {entry.status === 'ok' ? (
                  <CheckCircle2 size={12} className="text-accent-green shrink-0" />
                ) : (
                  <XCircle size={12} className="text-accent-red shrink-0" />
                )}
                <span className="text-[10px] text-starlight-500 shrink-0">
                  {new Date(entry.timestamp).toLocaleTimeString()}
                </span>
                <span className="text-xs text-starlight-300 flex-1 truncate">{entry.message}</span>
                {entry.actions_taken > 0 && (
                  <Badge variant="default" size="sm">
                    {entry.actions_taken} actions
                  </Badge>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default SettingsHeartbeat
