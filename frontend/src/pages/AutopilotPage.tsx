/**
 * AutopilotPage -- Accept-and-Go operator console (P0-5 MVP).
 *
 * A session-scoped control + live view over the EXISTING autopilot
 * backend (no new backend). It uses ONLY these routes:
 *   GET  /autopilot/state/{session_id}     -> run state (steps as IDs, cost, gate)
 *   GET  /autopilot/summary/{session_id}   -> completed/total/total_cost/notifications
 *   GET  /autopilot/queue/status           -> background-queue worker health
 *   GET  /autopilot/queue/events  (SSE)    -> live task lifecycle feed
 *   POST /autopilot/start                  -> begin the governed continuation loop
 *   POST /autopilot/stop                   -> kill switch
 *   POST /autopilot/approve                -> approve the paused step (gate)
 *   POST /autopilot/reject                 -> reject the paused step (stops the run)
 *
 * HONESTY (ADR-001): the backend state serializes steps as bare ID
 * strings (no per-step description / risk / cost). Those are shown as
 * "not available from backend yet", never faked. The plan itself is
 * produced by Daena's orchestrator when the session runs in Autopilot
 * chat mode; this console starts/monitors/approves that run.
 */
import { useCallback, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Rocket, ShieldCheck, ShieldAlert, CheckCircle2, XCircle, Loader2,
  RefreshCw, Square, AlertTriangle, Clock, ListChecks, Activity, ScrollText,
} from 'lucide-react'

import { usePageTitle } from '@/hooks/usePageTitle'
import { useGatedInterval } from '@/hooks/useGatedInterval'
import { useResilientSSE, type SSEEvent } from '@/lib/sse'
import { Card, Badge, Button, Input, EmptyState, Shimmer } from '@/components/common'
import { api } from '@/lib/api'
import { useChatStore } from '@/stores/chatStore'
import { toast } from '@/stores/toastStore'

// ── Backend contracts (exact, from autopilot.py + continuation.py) ──
interface AutopilotStateDto {
  enabled: boolean
  session_id: string
  current_plan_id: string | null
  completed_steps: string[]
  pending_steps: string[]
  paused_step: string | null
  total_cost_usd: number
  cost_ceiling_usd: number
  killed: boolean
  total_notifications: number
}
interface AutopilotResponseDto {
  success: boolean
  message: string
  state: AutopilotStateDto | null
}
interface AutopilotSummaryDto {
  session_id: string
  completed: number
  total: number
  total_cost: number
  notifications: Array<Record<string, unknown>>
}
interface QueueStatusDto {
  worker_running: boolean
  persistent: boolean
  storage: string
}
// A normalized live-feed row derived from a queue_channel SSE envelope.
interface QueueFeedItem {
  id: number
  type: string
  taskId?: string
  description?: string
  detail?: string
}

const GOVERNANCE_PRESETS = ['BALANCED', 'GOVERNED', 'UNLEASHED'] as const
const POLL_MS = 4_000
const FEED_LABELS: Record<string, string> = {
  'task.enqueued': 'Enqueued',
  'task.started': 'Started',
  'task.completed': 'Completed',
  'task.failed': 'Failed',
  'task.cancelled': 'Cancelled',
  'task.cancel_all': 'All cancelled',
}
const FEED_TONES: Record<string, string> = {
  'task.enqueued': 'bg-starlight-500',
  'task.started': 'bg-primary-400',
  'task.completed': 'bg-status-success',
  'task.failed': 'bg-status-error',
  'task.cancelled': 'bg-starlight-600',
  'task.cancel_all': 'bg-status-error',
}

function feedStatusPill(status: string): { label: string; variant: 'success' | 'warning' | 'danger' | 'default' } {
  switch (status) {
    case 'connected': return { label: 'Live', variant: 'success' }
    case 'connecting': return { label: 'Connecting', variant: 'default' }
    case 'reconnecting': return { label: 'Reconnecting', variant: 'warning' }
    case 'fallback': return { label: 'Polling', variant: 'warning' }
    default: return { label: 'Offline', variant: 'default' }
  }
}

function runStatus(state: AutopilotStateDto | null): { label: string; variant: 'success' | 'warning' | 'danger' | 'default' } {
  if (!state) return { label: 'No run', variant: 'default' }
  if (state.killed) return { label: 'Stopped', variant: 'danger' }
  if (state.paused_step) return { label: 'Paused at gate', variant: 'warning' }
  if (state.enabled) return { label: 'Running', variant: 'success' }
  return { label: 'Idle', variant: 'default' }
}

export default function AutopilotPage() {
  usePageTitle('Autopilot')
  const navigate = useNavigate()
  const activeSessionId = useChatStore((s) => s.activeSessionId)

  // Session the console operates on: defaults to the active chat session,
  // editable so the operator can attach to any session's autopilot run.
  const [sessionId, setSessionId] = useState<string>(activeSessionId ?? '')
  const [state, setState] = useState<AutopilotStateDto | null>(null)
  const [summary, setSummary] = useState<AutopilotSummaryDto | null>(null)
  const [queue, setQueue] = useState<QueueStatusDto | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadedOnce, setLoadedOnce] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [events, setEvents] = useState<QueueFeedItem[]>([])
  const seqRef = useRef(0)

  // Start-form inputs.
  const [costCeiling, setCostCeiling] = useState('1.0')
  const [preset, setPreset] = useState<(typeof GOVERNANCE_PRESETS)[number]>('BALANCED')

  const refresh = useCallback(async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      const [stateRes, summaryRes, queueRes] = await Promise.allSettled([
        api.get<AutopilotResponseDto>(`/autopilot/state/${encodeURIComponent(sessionId)}`),
        api.get<AutopilotSummaryDto>(`/autopilot/summary/${encodeURIComponent(sessionId)}`),
        api.get<{ success: boolean; data: QueueStatusDto }>('/autopilot/queue/status'),
      ])
      if (stateRes.status === 'fulfilled') setState(stateRes.value.data?.state ?? null)
      if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value.data ?? null)
      if (queueRes.status === 'fulfilled') setQueue(queueRes.value.data?.data ?? null)
      if (stateRes.status === 'rejected' && summaryRes.status === 'rejected') {
        const reason = stateRes.reason
        setError(reason instanceof Error ? reason.message : 'Autopilot API unavailable')
      } else {
        setError(null)
      }
    } finally {
      setLoading(false)
      setLoadedOnce(true)
    }
  }, [sessionId])

  // Visibility-gated poll (pauses when the tab is hidden).
  useGatedInterval(refresh, POLL_MS, { enabled: !!sessionId })

  // Live task feed over the queue_channel SSE. useResilientSSE now sends
  // the JWT bearer (BUGFIX-3), so this authenticates; if it ever drops
  // past its retry budget it falls back to the poll above.
  const { status: feedStatus } = useResilientSSE({
    // Full path: useResilientSSE does a raw fetch (no axios baseURL), so
    // the '/api/v1' prefix is required here (unlike the `api` client).
    url: sessionId ? '/api/v1/autopilot/queue/events' : '',
    eventTypes: ['task.enqueued', 'task.started', 'task.completed', 'task.failed', 'task.cancelled', 'task.cancel_all', 'ping'],
    onEvent: (ev: SSEEvent) => {
      if (!ev.type || ev.type === 'ping') return
      // Backend wraps each event as { type, data, channel, ts }; the
      // domain payload is the inner ``data``.
      const payload = ((ev.data as { data?: Record<string, unknown> })?.data
        ?? (ev.data as Record<string, unknown>)) || {}
      // queue_channel is tenant-wide; only show this session's events.
      const evSession = payload.session_id ? String(payload.session_id) : ''
      if (evSession && sessionId && evSession !== sessionId) return
      const item: QueueFeedItem = {
        id: (seqRef.current += 1),
        type: ev.type,
        taskId: payload.task_id ? String(payload.task_id) : undefined,
        description: payload.description ? String(payload.description) : undefined,
        detail: payload.error ? String(payload.error) : undefined,
      }
      setEvents((curr) => [item, ...curr].slice(0, 50))
    },
    fallbackPoll: () => { void refresh() },
  })

  async function startRun() {
    if (!sessionId) {
      toast.error('Enter a session id (or open an Autopilot chat) first.')
      return
    }
    const ceiling = Number(costCeiling)
    if (!Number.isFinite(ceiling) || ceiling <= 0) {
      toast.error('Cost ceiling must be a positive number.')
      return
    }
    setBusy('start')
    try {
      const res = await api.post<AutopilotResponseDto>('/autopilot/start', {
        session_id: sessionId,
        cost_ceiling: ceiling,
        governance_preset: preset,
      })
      if (res.data?.state) setState(res.data.state)
      toast.success(res.data?.message || 'Autopilot started')
      await refresh()
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409) toast.info('Autopilot is already running for this session.')
      else toast.error(err instanceof Error ? err.message : 'Failed to start autopilot')
    } finally {
      setBusy(null)
    }
  }

  async function stopRun() {
    if (!sessionId) return
    setBusy('stop')
    try {
      await api.post('/autopilot/stop', { session_id: sessionId })
      toast.success('Autopilot stopped')
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to stop autopilot')
    } finally {
      setBusy(null)
    }
  }

  async function decideGate(action: 'approve' | 'reject') {
    if (!sessionId || !state?.paused_step) return
    setBusy(action)
    try {
      await api.post(`/autopilot/${action}`, { session_id: sessionId, step_id: state.paused_step })
      toast.success(action === 'approve' ? 'Step approved, continuing.' : 'Step rejected, run stopped.')
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action} step`)
    } finally {
      setBusy(null)
    }
  }

  const status = runStatus(state)
  const naLabel = 'not available from backend yet'

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-display font-bold text-starlight-100 flex items-center gap-2">
              <Rocket size={20} className="text-accent-amber" /> Autopilot - Accept &amp; Go
            </h1>
            <p className="text-sm text-starlight-400 mt-1">
              Start, monitor, and approve a governed autopilot run. Daena builds the plan when the
              session runs in Autopilot (EXE) chat mode; this console controls and audits that run.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => void refresh()} disabled={loading || !sessionId}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </Button>
        </div>

        {/* Session + start controls */}
        <Card variant="glass" padding="md" className="space-y-3">
          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <div className="flex-1">
              <label className="text-[10px] uppercase tracking-wider text-starlight-500 font-semibold">Session id</label>
              <Input value={sessionId} onChange={(e) => setSessionId(e.target.value)} placeholder="active chat session id" />
            </div>
            <div className="w-28">
              <label className="text-[10px] uppercase tracking-wider text-starlight-500 font-semibold">Cost ceiling ($)</label>
              <Input value={costCeiling} onChange={(e) => setCostCeiling(e.target.value)} placeholder="1.0" />
            </div>
            <div className="w-40">
              <label className="text-[10px] uppercase tracking-wider text-starlight-500 font-semibold">Governance</label>
              <select
                value={preset}
                onChange={(e) => setPreset(e.target.value as typeof preset)}
                className="w-full glass-input px-3 py-2 rounded-lg text-xs text-starlight-200 mt-1"
              >
                {GOVERNANCE_PRESETS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="flex gap-2">
              <Button onClick={() => void startRun()} disabled={busy === 'start' || !sessionId}>
                {busy === 'start' ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />} Start run
              </Button>
              {state?.enabled && !state.killed && (
                <Button variant="danger" onClick={() => void stopRun()} disabled={busy === 'stop'}>
                  {busy === 'stop' ? <Loader2 size={14} className="animate-spin" /> : <Square size={14} />} Stop
                </Button>
              )}
            </div>
          </div>
          <p className="text-[11px] text-starlight-500">
            New goal? Open Daena chat, switch to Autopilot (EXE) mode, and describe the goal - the
            generated plan and its gates appear here for approval.
          </p>
        </Card>

        {/* Empty / loading / error */}
        {!sessionId && (
          <EmptyState
            icon={<Rocket size={28} />}
            title="No session selected"
            description="Enter a session id above, or start an Autopilot chat and its run will appear here."
          />
        )}
        {sessionId && !loadedOnce && (
          <div className="space-y-2"><Shimmer className="h-24 w-full" /><Shimmer className="h-32 w-full" /></div>
        )}
        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-status-error/30 bg-status-error/5 px-3 py-2 text-xs text-status-error">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {error}
          </div>
        )}
        {sessionId && loadedOnce && !error && !state && (
          <EmptyState
            icon={<Rocket size={28} />}
            title="No autopilot run for this session"
            description="Start a governed run above, or run this session in Autopilot chat mode to generate a plan."
          />
        )}

        {/* Gate (paused step awaiting approval) */}
        {state?.paused_step && (
          <Card variant="glass" padding="md" className="border-accent-amber/40 bg-accent-amber/5">
            <div className="flex items-center gap-2 mb-2">
              <ShieldAlert size={16} className="text-accent-amber" />
              <h2 className="text-sm font-semibold text-starlight-100">Approval gate</h2>
            </div>
            <p className="text-xs text-starlight-300">
              Step <span className="font-mono text-starlight-100">{state.paused_step}</span> is paused and needs your decision.
            </p>
            <p className="text-[11px] text-starlight-500 mt-1">Per-step risk and detail: {naLabel}.</p>
            <div className="flex gap-2 mt-3">
              <Button onClick={() => void decideGate('approve')} disabled={busy === 'approve'}>
                {busy === 'approve' ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />} Approve &amp; continue
              </Button>
              <Button variant="danger" onClick={() => void decideGate('reject')} disabled={busy === 'reject'}>
                {busy === 'reject' ? <Loader2 size={13} className="animate-spin" /> : <XCircle size={13} />} Reject
              </Button>
            </div>
          </Card>
        )}

        {/* Run state */}
        {state && (
          <Card variant="glass" padding="md" className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-starlight-100 flex items-center gap-2">
                <Activity size={15} className="text-primary-400" /> Run state
              </h2>
              <Badge variant={status.variant}>{status.label}</Badge>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div><p className="text-starlight-500">Plan id</p><p className="text-starlight-200 font-mono truncate">{state.current_plan_id ?? '-'}</p></div>
              <div><p className="text-starlight-500">Cost</p><p className="text-starlight-200">${state.total_cost_usd.toFixed(4)} / ${state.cost_ceiling_usd.toFixed(2)}</p></div>
              <div><p className="text-starlight-500">Completed</p><p className="text-starlight-200">{state.completed_steps.length}</p></div>
              <div><p className="text-starlight-500">Pending</p><p className="text-starlight-200">{state.pending_steps.length}</p></div>
            </div>

            <div>
              <p className="text-[11px] font-semibold text-starlight-300 flex items-center gap-1.5 mb-1.5"><ListChecks size={12} /> Steps</p>
              {state.completed_steps.length === 0 && state.pending_steps.length === 0 ? (
                <p className="text-[11px] text-starlight-500">Plan is empty. It populates when Daena plans this session in Autopilot chat mode.</p>
              ) : (
                <div className="space-y-1">
                  {state.completed_steps.map((id) => (
                    <div key={`c-${id}`} className="flex items-center gap-2 text-xs">
                      <CheckCircle2 size={12} className="text-status-success shrink-0" />
                      <span className="font-mono text-starlight-300 truncate">{id}</span>
                      <Badge variant="success" size="sm">done</Badge>
                    </div>
                  ))}
                  {state.pending_steps.map((id) => (
                    <div key={`p-${id}`} className="flex items-center gap-2 text-xs">
                      {id === state.paused_step
                        ? <ShieldAlert size={12} className="text-accent-amber shrink-0" />
                        : <Clock size={12} className="text-starlight-500 shrink-0" />}
                      <span className="font-mono text-starlight-300 truncate">{id}</span>
                      <Badge variant={id === state.paused_step ? 'warning' : 'default'} size="sm">
                        {id === state.paused_step ? 'gate' : 'pending'}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-[10px] text-starlight-500 mt-1.5">Per-step description / risk / cost: {naLabel} (state exposes step ids only).</p>
            </div>
          </Card>
        )}

        {/* Summary + queue health */}
        {state && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card variant="glass" padding="md">
              <h2 className="text-sm font-semibold text-starlight-100 mb-2">Summary</h2>
              {summary ? (
                <div className="text-xs space-y-1 text-starlight-300">
                  <p>{summary.completed} of {summary.total} steps complete</p>
                  <p>Total cost: ${summary.total_cost.toFixed(4)}</p>
                  <p className="text-starlight-500">{summary.notifications.length} recent notifications</p>
                </div>
              ) : <p className="text-xs text-starlight-500">No summary.</p>}
            </Card>
            <Card variant="glass" padding="md">
              <h2 className="text-sm font-semibold text-starlight-100 mb-2 flex items-center gap-1.5"><ShieldCheck size={14} /> Queue health</h2>
              {queue ? (
                <div className="text-xs space-y-1 text-starlight-300">
                  <p>Worker: <Badge variant={queue.worker_running ? 'success' : 'danger'} size="sm">{queue.worker_running ? 'running' : 'stopped'}</Badge></p>
                  <p>Storage: <span className="font-mono">{queue.storage}</span> {queue.persistent ? '(persistent)' : '(memory only)'}</p>
                </div>
              ) : <p className="text-xs text-starlight-500">Queue status unavailable.</p>}
            </Card>
          </div>
        )}


        {/* Live task feed (queue_channel SSE) */}
        {sessionId && (
          <Card variant="glass" padding="md" className="space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-starlight-100 flex items-center gap-1.5">
                <ScrollText size={14} className="text-primary-400" /> Live task feed
              </h2>
              <Badge variant={feedStatusPill(feedStatus).variant} size="sm">{feedStatusPill(feedStatus).label}</Badge>
            </div>
            {events.length === 0 ? (
              <p className="text-[11px] text-starlight-500">
                No task events yet. Enqueued / started / completed / failed events stream here in real time while the run is active.
              </p>
            ) : (
              <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                {events.map((e) => (
                  <div key={e.id} className="flex items-start gap-2 text-xs">
                    <span className={`mt-1 h-1.5 w-1.5 rounded-full shrink-0 ${FEED_TONES[e.type] ?? 'bg-starlight-500'}`} />
                    <div className="min-w-0 flex-1">
                      <span className="text-starlight-200">{FEED_LABELS[e.type] ?? e.type}</span>
                      {e.taskId && <span className="font-mono text-starlight-500 ml-1.5">{e.taskId.slice(0, 8)}</span>}
                      {e.description && <p className="text-starlight-400 truncate">{e.description}</p>}
                      {e.detail && <p className="text-status-error truncate">{e.detail}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* Audit link */}
        {state && (
          <button
            onClick={() => navigate('/governance/audit')}
            className="text-[11px] text-starlight-400 hover:text-accent-cyan underline cursor-pointer"
          >
            View the full audit trail for this run
          </button>
        )}
      </div>
    </div>
  )
}
