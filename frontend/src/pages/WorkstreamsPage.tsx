/**
 * WorkstreamsPage — Daena's Live Workstream Console.
 *
 * Per the Council R3 lock (see Doc/COUNCIL_DESIGN_LOCK_2026-04-25.md),
 * the workstream is Daena's visible unit of autonomy. This page shows
 * three things per workstream:
 *
 *   1. Goal + owner department
 *   2. Current state + one-line blocker / next step
 *   3. Governed Execution Timeline (the audit trace)
 *
 * One action: REDIRECT WORKSTREAM. The user types a free-form
 * instruction like "pause file edits, ask Council, only produce a
 * migration plan" and the backend parser maps it to structured
 * actions via `services/workstream_redirect_parser.py`.
 *
 * Status pill colors map to WorkstreamStatus:
 *   RUNNING           -> teal     (alive, doing things)
 *   BLOCKED           -> amber    (stuck, needs attention)
 *   WAITING_APPROVAL  -> orange   (gated, founder action required)
 *   COMPLETE          -> green    (done, terminal)
 *   FAILED            -> red      (failed, terminal)
 */
import { useEffect, useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity,
  AlertCircle,
  Archive,
  Briefcase,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  Mail,
  MessageSquare,
  Newspaper,
  Pause,
  Play,
  RadioTower,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Tag,
  Workflow,
  XCircle,
  Zap,
  Brain,
  Users,
  ArrowRightCircle,
  Loader2,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'
import { useResilientSSE, type SSEStatus } from '@/lib/sse'
import { AutonomyMissionControl } from '@/components/common/AutonomyMissionControl'

type WorkstreamStatus =
  | 'RUNNING'
  | 'BLOCKED'
  | 'WAITING_APPROVAL'
  | 'COMPLETE'
  | 'FAILED'

type EscalationLevel =
  | 'STANDARD'
  | 'HIGH_EFFORT'
  | 'COUNCIL'
  | 'QUINTESSENCE'
  | 'HUMAN_REVIEW'

type WorkstreamSourceType =
  | 'chat'
  | 'scan'
  | 'task'
  | 'department'
  | 'company_mode'
  | 'manual'
  | 'dev_demo'

interface Workstream {
  id: string
  department_id: string
  user_id: string
  goal: string
  status: WorkstreamStatus
  blocker_text: string | null
  next_step_text: string | null
  escalation_level: EscalationLevel
  total_tokens: number
  total_cost_cents: number
  autopilot_paused: boolean
  last_activity_at: string | null
  created_at: string | null
  // PR-5 spine skeleton fields
  source_type: WorkstreamSourceType
  source_ref_id: string | null
  progress_percent: number
  artifact_refs: Record<string, string[]>
  audit_event_refs: string[]
  notification_refs: string[]
  archived_at: string | null
}

interface WorkstreamEvent {
  id: string
  kind: string
  summary: string
  payload: Record<string, unknown>
  occurred_at: string | null
}

interface AppliedAction {
  kind: string
  payload: Record<string, string>
  matched_phrase: string
}

const STATUS_STYLE: Record<WorkstreamStatus, { label: string; cls: string; icon: React.ReactNode }> = {
  RUNNING: {
    label: 'Running',
    cls: 'bg-accent-teal/15 text-accent-teal border-accent-teal/30',
    icon: <Activity size={12} />,
  },
  BLOCKED: {
    label: 'Blocked',
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    icon: <AlertCircle size={12} />,
  },
  WAITING_APPROVAL: {
    label: 'Waiting approval',
    cls: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    icon: <ShieldAlert size={12} />,
  },
  COMPLETE: {
    label: 'Complete',
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    icon: <CheckCircle2 size={12} />,
  },
  FAILED: {
    label: 'Failed',
    cls: 'bg-red-500/15 text-red-300 border-red-500/30',
    icon: <XCircle size={12} />,
  },
}

function StatusPill({ status }: { status: WorkstreamStatus }) {
  const meta = STATUS_STYLE[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold border ${meta.cls}`}
    >
      {meta.icon}
      {meta.label}
    </span>
  )
}

function EscalationBadge({ level }: { level: EscalationLevel }) {
  if (level === 'STANDARD') return null
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-primary-500/15 text-primary-300 border border-primary-500/30">
      <Sparkles size={10} />
      {level.replace('_', ' ').toLowerCase()}
    </span>
  )
}

const SOURCE_STYLE: Record<
  WorkstreamSourceType,
  { label: string; cls: string; icon: React.ReactNode }
> = {
  chat: {
    label: 'chat',
    cls: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    icon: <MessageSquare size={9} />,
  },
  scan: {
    label: 'scan',
    cls: 'bg-red-500/15 text-red-300 border-red-500/30',
    icon: <ShieldCheck size={9} />,
  },
  task: {
    label: 'task',
    cls: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    icon: <Workflow size={9} />,
  },
  department: {
    label: 'department',
    cls: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
    icon: <Tag size={9} />,
  },
  company_mode: {
    label: 'company',
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    icon: <Sparkles size={9} />,
  },
  manual: {
    label: 'manual',
    cls: 'bg-starlight-700/40 text-starlight-300 border-starlight-600/30',
    icon: <Tag size={9} />,
  },
  dev_demo: {
    label: 'dev demo',
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    icon: <Zap size={9} />,
  },
}

function SourceBadge({ source }: { source: WorkstreamSourceType }) {
  const meta = SOURCE_STYLE[source] ?? SOURCE_STYLE.manual
  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border ${meta.cls}`}
      title={`Source: ${meta.label}`}
    >
      {meta.icon}
      {meta.label}
    </span>
  )
}

function ProgressBar({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent || 0))
  return (
    <div
      className="w-full h-1 rounded bg-white/5 overflow-hidden"
      title={`Progress: ${clamped}%`}
    >
      <div
        className="h-full bg-accent-teal/70 transition-all"
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}

/**
 * Count refs across all artifact buckets (scan_report_ids, draft_ids, ...).
 * Returns 0 when artifact_refs is empty or undefined.
 */
function countArtifactRefs(refs: Record<string, string[]> | undefined): number {
  if (!refs) return 0
  return Object.values(refs).reduce(
    (sum, list) => sum + (Array.isArray(list) ? list.length : 0),
    0,
  )
}

function formatCost(cents: number): string {
  if (cents === 0) return '$0'
  return `$${(cents / 100).toFixed(2)}`
}

function formatRelative(iso: string | null): string {
  if (!iso) return '—'
  const ms = Date.now() - new Date(iso).getTime()
  if (ms < 60_000) return `${Math.floor(ms / 1000)}s ago`
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`
  return `${Math.floor(ms / 86_400_000)}d ago`
}

function WorkstreamCard({
  ws,
  onSelect,
}: {
  ws: Workstream
  onSelect: () => void
}) {
  const artifactCount = countArtifactRefs(ws.artifact_refs)
  const auditCount = ws.audit_event_refs?.length ?? 0
  const notificationCount = ws.notification_refs?.length ?? 0
  return (
    <button
      type="button"
      onClick={onSelect}
      className="text-left w-full glass-panel rounded-xl p-4 hover:bg-white/[.04] transition cursor-pointer space-y-2"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill status={ws.status} />
          <SourceBadge source={ws.source_type} />
          <EscalationBadge level={ws.escalation_level} />
          {ws.autopilot_paused && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-starlight-700/40 text-starlight-300 border border-starlight-600/30">
              <Pause size={9} /> autopilot paused
            </span>
          )}
        </div>
        <div className="text-[10px] text-starlight-500 whitespace-nowrap">
          {formatRelative(ws.last_activity_at ?? ws.created_at)}
        </div>
      </div>
      <div className="text-sm text-starlight-100 font-medium leading-snug">
        {ws.goal}
      </div>
      <div className="text-xs text-starlight-400">
        {ws.status === 'BLOCKED' && ws.blocker_text ? (
          <span>
            <span className="text-amber-300 font-semibold">Blocked on:</span>{' '}
            {ws.blocker_text}
          </span>
        ) : ws.next_step_text ? (
          <span>
            <span className="text-starlight-300">Next:</span>{' '}
            {ws.next_step_text}
          </span>
        ) : (
          <span className="italic text-starlight-500">no next-step note</span>
        )}
      </div>
      {ws.progress_percent > 0 && ws.progress_percent < 100 && (
        <ProgressBar percent={ws.progress_percent} />
      )}
      <div className="flex items-center gap-3 text-[10px] text-starlight-500 flex-wrap">
        <span>{ws.total_tokens.toLocaleString()} tokens</span>
        <span>{formatCost(ws.total_cost_cents)}</span>
        {artifactCount > 0 && (
          <span className="inline-flex items-center gap-1" title="Artifacts produced">
            <FileText size={9} /> {artifactCount}
          </span>
        )}
        {auditCount > 0 && (
          <span className="inline-flex items-center gap-1" title="Audit events">
            <ShieldCheck size={9} /> {auditCount}
          </span>
        )}
        {notificationCount > 0 && (
          <span className="inline-flex items-center gap-1" title="Notifications">
            <Mail size={9} /> {notificationCount}
          </span>
        )}
      </div>
    </button>
  )
}

/**
 * Three side-by-side reference panels: artifacts produced, audit events
 * emitted, notifications fanned out. Honest empty states -- never render
 * a panel as if it had content when it does not.
 *
 * Per the Execution Spine PRD section 11.2 row 4-5, every artifact must
 * be reachable from the workstream. Phase 12 will wire deep-links to
 * the right routes (e.g. scan_report -> /security/reports/<id>); this
 * skeleton renders ids as monospace chips so the data is visible even
 * before the deep-link routing lands.
 */
function ReferencePanels({ ws }: { ws: Workstream }) {
  const artifactBuckets = Object.entries(ws.artifact_refs ?? {}).filter(
    ([, ids]) => Array.isArray(ids) && ids.length > 0,
  )
  const auditCount = ws.audit_event_refs?.length ?? 0
  const notificationCount = ws.notification_refs?.length ?? 0
  const hasAny =
    artifactBuckets.length > 0 || auditCount > 0 || notificationCount > 0

  if (!hasAny) {
    return (
      <div className="pt-3 border-t border-white/10">
        <div className="text-[10px] uppercase tracking-wider font-semibold text-starlight-500 mb-1">
          Artifacts, audit, notifications
        </div>
        <div className="text-[11px] text-starlight-500 italic">
          no references emitted yet
        </div>
      </div>
    )
  }

  return (
    <div className="pt-3 border-t border-white/10 space-y-3">
      {artifactBuckets.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] uppercase tracking-wider font-semibold text-starlight-500">
            Artifacts produced
          </div>
          {artifactBuckets.map(([kind, ids]) => (
            <div key={kind} className="text-[11px] text-starlight-300">
              <span className="text-starlight-400 mr-1">{kind}:</span>
              <span className="inline-flex flex-wrap gap-1 align-middle">
                {ids.map((id) => (
                  <span
                    key={id}
                    className="px-1.5 py-0.5 rounded bg-white/5 font-mono text-[10px]"
                    title={id}
                  >
                    {id.length > 18 ? `${id.slice(0, 18)}…` : id}
                  </span>
                ))}
              </span>
            </div>
          ))}
        </div>
      )}
      {auditCount > 0 && (
        <div className="text-[11px]">
          <span className="text-starlight-400">Audit events: </span>
          <a
            href={`/governance/audit?workstream_id=${ws.id}`}
            className="text-accent-teal hover:underline inline-flex items-center gap-1"
          >
            <ShieldCheck size={11} /> view {auditCount} event
            {auditCount === 1 ? '' : 's'}
          </a>
        </div>
      )}
      {notificationCount > 0 && (
        <div className="text-[11px]">
          <span className="text-starlight-400">Notifications: </span>
          <a
            href={`/notifications?workstream_id=${ws.id}`}
            className="text-accent-teal hover:underline inline-flex items-center gap-1"
          >
            <Mail size={11} /> view {notificationCount} notification
            {notificationCount === 1 ? '' : 's'}
          </a>
        </div>
      )}
    </div>
  )
}

type StreamSnapshotPayload = {
  workstream_id: string
  snapshot: Partial<Workstream>
}

type StreamEventPayload = {
  workstream_id: string
  event: WorkstreamEvent
  snapshot: Partial<Workstream>
}

type StreamBootstrapPayload = {
  workstream_id: string
  snapshot: Workstream
  events: WorkstreamEvent[]
}

/**
 * Compose a Workstream by merging an SSE snapshot patch into the current
 * row. Snapshots only carry mutable fields; immutable fields (department,
 * goal source_type / source_ref_id, created_at) keep their prior values.
 */
function applySnapshot(
  prior: Workstream,
  patch: Partial<Workstream>,
): Workstream {
  return { ...prior, ...patch }
}

const SSE_STATUS_STYLE: Record<
  SSEStatus,
  { label: string; cls: string; icon: React.ReactNode }
> = {
  connecting: {
    label: 'Connecting…',
    cls: 'text-starlight-500',
    icon: <RadioTower size={10} className="animate-pulse" />,
  },
  connected: {
    label: 'Live',
    cls: 'text-emerald-300',
    icon: <RadioTower size={10} />,
  },
  reconnecting: {
    label: 'Reconnecting…',
    cls: 'text-amber-300',
    icon: <RadioTower size={10} className="animate-pulse" />,
  },
  fallback: {
    label: 'Live updates unavailable, use Refresh.',
    cls: 'text-amber-400',
    icon: <AlertCircle size={10} />,
  },
  closed: {
    label: 'Stream closed',
    cls: 'text-starlight-500',
    icon: <RadioTower size={10} />,
  },
}

function LiveStatusBadge({
  status,
  reconnectAttempt,
  maxRetries,
}: {
  status: SSEStatus
  reconnectAttempt: number
  maxRetries: number
}) {
  const meta = SSE_STATUS_STYLE[status]
  const labelWithAttempt =
    status === 'reconnecting'
      ? `Reconnecting (${reconnectAttempt}/${maxRetries})…`
      : meta.label
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-semibold ${meta.cls}`}
      title={labelWithAttempt}
    >
      {meta.icon}
      <span>{labelWithAttempt}</span>
    </span>
  )
}

function WorkstreamDetailDrawer({
  workstreamId,
  onClose,
  onMutated,
}: {
  workstreamId: string
  onClose: () => void
  onMutated: () => void
}) {
  const [data, setData] = useState<{
    workstream: Workstream
    events: WorkstreamEvent[]
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [redirectInput, setRedirectInput] = useState('')
  const [redirectError, setRedirectError] = useState<string | null>(null)
  const [redirectApplied, setRedirectApplied] = useState<AppliedAction[] | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  // Tracks ids we've already appended via SSE so duplicates between
  // bootstrap + a fast follow-up event can't render twice.
  const seenEventIdsRef = useRef<Set<string>>(new Set())

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get(`/workstreams/${workstreamId}`)
      const next = res.data?.data ?? null
      if (next) {
        seenEventIdsRef.current = new Set(
          (next.events as WorkstreamEvent[]).map((e) => e.id),
        )
      }
      setData(next)
    } catch {
      toast.error('Failed to load workstream')
    } finally {
      setLoading(false)
    }
  }, [workstreamId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  // PR-SPINE-06: subscribe to per-workstream SSE for live updates.
  // Bootstrap arrives first (full snapshot + last 50 events), then a
  // workstream.event for every state change and workstream.snapshot for
  // informational mutations. ResilientSSE handles bounded reconnect +
  // fallbackPoll on retry exhaustion.
  const handleStreamEvent = useCallback(
    ({ type, data: payload }: { type: string; data: unknown }) => {
      if (type === 'workstream.bootstrap') {
        const body = payload as StreamBootstrapPayload
        if (!body || body.workstream_id !== workstreamId) return
        seenEventIdsRef.current = new Set(body.events.map((e) => e.id))
        setData({ workstream: body.snapshot, events: body.events })
        setLoading(false)
        return
      }
      if (type === 'workstream.event') {
        const body = payload as StreamEventPayload
        if (!body || body.workstream_id !== workstreamId) return
        setData((cur) => {
          if (!cur) return cur
          const merged = applySnapshot(cur.workstream, body.snapshot)
          if (seenEventIdsRef.current.has(body.event.id)) {
            return { workstream: merged, events: cur.events }
          }
          seenEventIdsRef.current.add(body.event.id)
          return { workstream: merged, events: [...cur.events, body.event] }
        })
        return
      }
      if (type === 'workstream.snapshot') {
        const body = payload as StreamSnapshotPayload
        if (!body || body.workstream_id !== workstreamId) return
        setData((cur) =>
          cur
            ? { workstream: applySnapshot(cur.workstream, body.snapshot), events: cur.events }
            : cur,
        )
        return
      }
      if (type === 'workstream.closed') {
        // Server signaled the workstream was archived (or stream errored).
        // Trigger an upstream refresh so the list drops the row, then
        // close the drawer.
        onMutated()
        onClose()
      }
    },
    [workstreamId, onMutated, onClose],
  )

  const fallbackPoll = useCallback(async () => {
    await refresh()
  }, [refresh])

  const SSE_MAX_RETRIES = 5
  const { status: sseStatus, reconnectAttempt } = useResilientSSE({
    url: `/api/v1/workstreams/${workstreamId}/stream`,
    eventTypes: [
      'workstream.bootstrap',
      'workstream.event',
      'workstream.snapshot',
      'workstream.closed',
    ],
    onEvent: handleStreamEvent,
    fallbackPoll,
    maxRetries: SSE_MAX_RETRIES,
  })

  const submitRedirect = async () => {
    const instruction = redirectInput.trim()
    if (!instruction) return
    setSubmitting(true)
    setRedirectError(null)
    setRedirectApplied(null)
    try {
      const res = await api.post(`/workstreams/${workstreamId}/redirect`, {
        instruction,
      })
      const body = res.data
      if (body?.success === false) {
        setRedirectError(body?.error?.message ?? 'Redirect not understood')
      } else {
        setRedirectApplied(body?.data?.applied_actions ?? [])
        setRedirectInput('')
        await refresh()
        onMutated()
        toast.success(`Applied ${(body?.data?.applied_actions ?? []).length} actions`)
      }
    } catch (err) {
      setRedirectError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const lifecycleAction = async (action: 'pause' | 'resume' | 'cancel') => {
    if (actionBusy) return
    setActionBusy(true)
    try {
      await api.post(`/workstreams/${workstreamId}/${action}`)
      await refresh()
      onMutated()
      toast.success(`${action[0].toUpperCase() + action.slice(1)}d`)
    } catch {
      toast.error(`Failed to ${action}`)
    } finally {
      setActionBusy(false)
    }
  }

  const archive = async () => {
    if (actionBusy) return
    const ok = await confirmDialog({
      title: 'Archive this workstream?',
      message:
        'It will be soft-deleted and removed from your active workstreams. The record and its status are preserved for audit.',
      confirmLabel: 'Archive',
      variant: 'danger',
    })
    if (!ok) return
    setActionBusy(true)
    try {
      await api.patch(`/workstreams/${workstreamId}/archive`)
      onMutated()
      onClose()
      toast.success('Workstream archived')
    } catch {
      toast.error('Failed to archive')
    } finally {
      setActionBusy(false)
    }
  }

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 28 }}
      className="fixed top-0 right-0 bottom-0 w-full max-w-xl glass-panel border-l border-white/10 z-50 overflow-y-auto"
    >
      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-starlight-100">Workstream</h2>
          <button
            onClick={onClose}
            className="text-xs text-starlight-400 hover:text-starlight-100"
          >
            Close
          </button>
        </div>

        {loading || !data ? (
          <div className="text-xs text-starlight-400">Loading…</div>
        ) : (
          <>
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={data.workstream.status} />
                <SourceBadge source={data.workstream.source_type} />
                <EscalationBadge level={data.workstream.escalation_level} />
                {data.workstream.autopilot_paused && (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-starlight-700/40 text-starlight-300">
                    <Pause size={9} /> autopilot paused
                  </span>
                )}
              </div>
              <div className="text-sm font-semibold text-starlight-100">
                {data.workstream.goal}
              </div>
              {data.workstream.status === 'BLOCKED' && data.workstream.blocker_text && (
                <div className="text-xs text-amber-300">
                  Blocked on: {data.workstream.blocker_text}
                </div>
              )}
              {data.workstream.next_step_text && (
                <div className="text-xs text-starlight-400">
                  Next: {data.workstream.next_step_text}
                </div>
              )}
              {data.workstream.progress_percent > 0 && (
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[10px] text-starlight-500">
                    <span>Progress</span>
                    <span>{data.workstream.progress_percent}%</span>
                  </div>
                  <ProgressBar percent={data.workstream.progress_percent} />
                </div>
              )}
              <div className="flex items-center gap-3 text-[10px] text-starlight-500 flex-wrap">
                <span>{data.workstream.total_tokens.toLocaleString()} tokens</span>
                <span>{formatCost(data.workstream.total_cost_cents)}</span>
                <span>started {formatRelative(data.workstream.created_at)}</span>
                {data.workstream.source_ref_id && (
                  <span
                    className="font-mono"
                    title="Upstream artifact id (source_ref_id)"
                  >
                    src:{data.workstream.source_ref_id.slice(0, 8)}
                  </span>
                )}
              </div>
            </div>

            {/* PR-5: artifact / audit / notification reference panels */}
            <ReferencePanels ws={data.workstream} />

            {/* Redirect input */}
            <div className="space-y-2 pt-3 border-t border-white/10">
              <div className="text-[10px] uppercase tracking-wider font-semibold text-starlight-500">
                Redirect Workstream
              </div>
              <textarea
                value={redirectInput}
                onChange={e => setRedirectInput(e.target.value)}
                aria-label="Redirect workstream instructions"
                placeholder="pause file edits, ask Council, only produce a migration plan"
                rows={2}
                className="w-full glass-input rounded-lg px-3 py-2 text-xs text-starlight-100"
              />
              {redirectError && (
                <div className="text-[11px] text-amber-300 leading-snug">
                  {redirectError}
                </div>
              )}
              {redirectApplied && redirectApplied.length > 0 && (
                <div className="text-[11px] text-accent-teal leading-snug">
                  Applied: {redirectApplied.map(a => a.kind).join(', ')}
                </div>
              )}
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => void submitRedirect()}
                  disabled={submitting || !redirectInput.trim()}
                  className="px-3 py-1.5 rounded-md text-xs bg-primary-500 text-white hover:bg-primary-600 disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? 'Applying…' : 'Apply redirect'}
                </button>
                <button
                  onClick={() => void lifecycleAction('pause')}
                  disabled={actionBusy}
                  className="px-2 py-1.5 rounded-md text-xs bg-white/5 text-starlight-300 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  <Pause size={12} className="inline mr-1" />
                  Pause autopilot
                </button>
                <button
                  onClick={() => void lifecycleAction('resume')}
                  disabled={actionBusy}
                  className="px-2 py-1.5 rounded-md text-xs bg-white/5 text-starlight-300 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  <Play size={12} className="inline mr-1" />
                  Resume
                </button>
                <button
                  onClick={() => void archive()}
                  disabled={actionBusy}
                  className="ml-auto px-2 py-1.5 rounded-md text-xs bg-white/5 text-starlight-400 hover:bg-amber-500/15 hover:text-amber-300 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                  title="Soft-delete this workstream (status preserved for audit)"
                >
                  <Archive size={12} className="inline mr-1" />
                  Archive
                </button>
              </div>
            </div>

            {/* Timeline */}
            <div className="space-y-2 pt-3 border-t border-white/10">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="text-[10px] uppercase tracking-wider font-semibold text-starlight-500">
                  Governed execution timeline
                </div>
                <div className="flex items-center gap-3">
                  <LiveStatusBadge
                    status={sseStatus}
                    reconnectAttempt={reconnectAttempt}
                    maxRetries={SSE_MAX_RETRIES}
                  />
                  <button
                    onClick={() => void refresh()}
                    className="text-[10px] text-starlight-400 hover:text-starlight-100 inline-flex items-center gap-1"
                  >
                    <RefreshCw size={10} /> Refresh
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                {data.events.length === 0 ? (
                  <div className="text-[11px] text-starlight-500 italic">
                    no events yet
                  </div>
                ) : (
                  data.events.map(ev => (
                    <div
                      key={ev.id}
                      className="text-[11px] text-starlight-300 border-l-2 border-white/10 pl-2 py-0.5"
                    >
                      <span className="font-mono text-[9px] text-starlight-500 mr-1.5">
                        {ev.kind}
                      </span>
                      <span>{ev.summary}</span>
                      <span className="text-[9px] text-starlight-600 ml-2">
                        <Clock size={8} className="inline mr-0.5" />
                        {formatRelative(ev.occurred_at)}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </motion.div>
  )
}

// ── Sprint-11 PR-2: Drafts lane ────────────────────────────────────
//
// Surfaces career + content research drafts (and -- once PR-3 lands --
// form drafts) inside the existing Workstreams console. Per the audit,
// we do NOT spin up a parallel "Work Command Center" page. Drafts are
// the unit of supervised research; workstreams are the unit of
// supervised action. They live next to each other on one page.
//
// The lane is read-only here -- the Apply / Edit / Approve buttons land
// inside dedicated draft surfaces (PR-3 form drafts, PR-4 approval
// queue extension). For now: count, last-three preview, click to expand
// the structured_payload JSON for inspection.

interface ResearchDraftSummary {
  id: string
  kind: 'career' | 'content'
  source_url: string
  source_host: string
  goal: string
  summary: string
  status: string
  created_at: string
  structured_payload: Record<string, unknown> | null
}

function PendingBadge() {
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30"
      title="Deterministic shape only. Click Enrich to run the routed main brain."
    >
      llm pending
    </span>
  )
}

function PillBadge({
  tone,
  text,
  title,
}: {
  tone: 'emerald' | 'sky' | 'amber' | 'violet'
  text: string
  title?: string
}) {
  const toneClass: Record<typeof tone, string> = {
    emerald: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    sky: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    violet: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  }
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border ${toneClass[tone]}`}
    >
      {text}
    </span>
  )
}

/**
 * StatusBadges — Sprint-MORNING PR-3.
 *
 * Renders a compact set of badges describing the lifecycle state of a
 * draft. Read-only: every badge is derived from already-loaded data.
 * - llm pending   -- payload._llm_pending === true (no enrichment yet)
 * - enriched      -- payload._llm_pending === false
 * - QE: full|deg  -- payload._qe_mode set by QE service after a real run
 * - workstream    -- a workstream exists with source_ref_id == draft.id
 */
function StatusBadges({
  payload,
  hasWorkstream,
}: {
  payload: Record<string, unknown> | null | undefined
  hasWorkstream: boolean
}) {
  const llmPending = payload && payload._llm_pending === true
  const enriched = payload && payload._llm_pending === false
  const qeMode =
    payload && typeof payload._qe_mode === 'string'
      ? (payload._qe_mode as string)
      : null

  return (
    <>
      {llmPending && <PendingBadge />}
      {enriched && (
        <PillBadge tone="sky" text="enriched" title="LLM enrichment ran" />
      )}
      {qeMode === 'full' && (
        <PillBadge
          tone="emerald"
          text="QE: full"
          title="Three-stage council ran with 2+ distinct runtimes"
        />
      )}
      {qeMode === 'degraded' && (
        <PillBadge
          tone="amber"
          text="QE: degraded"
          title="Council ran with fewer reviewers than full mode"
        />
      )}
      {hasWorkstream && (
        <PillBadge
          tone="violet"
          text="workstream"
          title="Promoted to a workstream"
        />
      )}
    </>
  )
}

/**
 * DraftActions — Sprint-MORNING PR-2.
 *
 * Inline action row for Enrich / QE Review / Create Workstream against a
 * ResearchDraft or FormDraft. Each action targets the existing Sprint-12
 * endpoints; refusals (no main brain ready, etc.) surface via toast +
 * inline status. No external action fires from these buttons.
 */
type DraftActionStatus = 'idle' | 'running' | 'done' | 'refused'

interface DraftActionsProps {
  draftId: string
  draftKind: 'career' | 'content' | 'form'
  onRefresh?: () => void
}

function DraftActions({ draftId, draftKind, onRefresh }: DraftActionsProps) {
  const [enrichStatus, setEnrichStatus] = useState<DraftActionStatus>('idle')
  const [qeStatus, setQeStatus] = useState<DraftActionStatus>('idle')
  const [wsStatus, setWsStatus] = useState<DraftActionStatus>('idle')
  const [lastNote, setLastNote] = useState<string | null>(null)

  const enrichUrl =
    draftKind === 'form'
      ? `/form-drafts/${draftId}/enrich`
      : `/research/drafts/${draftId}/enrich`
  const qeUrl =
    draftKind === 'form'
      ? `/form-drafts/${draftId}/qe-review`
      : `/research/drafts/${draftId}/qe-review`

  const onEnrich = async () => {
    setEnrichStatus('running')
    setLastNote(null)
    try {
      const { data } = await api.post(enrichUrl, { allow_metered: false }, { silent: true })
      const refusal = data?.refusal_code as string | undefined
      if (refusal) {
        setEnrichStatus('refused')
        const next = (data?.next_action as string | undefined) ?? 'See logs.'
        setLastNote(next)
        toast.error(`Enrich refused: ${refusal}`)
      } else {
        setEnrichStatus('done')
        toast.success('Enriched ✓')
        onRefresh?.()
      }
    } catch (err) {
      setEnrichStatus('refused')
      const msg = err instanceof Error ? err.message : 'failed'
      setLastNote(msg)
      toast.error(`Enrich failed: ${msg}`)
    }
  }

  const onQeReview = async () => {
    setQeStatus('running')
    setLastNote(null)
    try {
      const { data } = await api.post(
        qeUrl,
        { allow_metered: false, allow_web_grounding: false },
        { silent: true },
      )
      const mode = (data?.mode as string | undefined) ?? 'unknown'
      if (mode === 'unavailable') {
        setQeStatus('refused')
        setLastNote('Council unavailable — no reviewers ready.')
        toast.error('Council unavailable')
      } else {
        setQeStatus('done')
        toast.success(`Council ran in mode=${mode}`)
        onRefresh?.()
      }
    } catch (err) {
      setQeStatus('refused')
      const msg = err instanceof Error ? err.message : 'failed'
      setLastNote(msg)
      toast.error(`Council failed: ${msg}`)
    }
  }

  const onCreateWorkstream = async () => {
    setWsStatus('running')
    setLastNote(null)
    try {
      const { data } = await api.post(
        '/workstreams/from-draft',
        { draft_kind: draftKind, draft_ref: draftId },
        { silent: true },
      )
      setWsStatus('done')
      const wsId = (data?.id as string | undefined)?.slice(0, 8) ?? 'created'
      toast.success(`Workstream ${wsId} created`)
      onRefresh?.()
    } catch (err) {
      setWsStatus('refused')
      const msg = err instanceof Error ? err.message : 'failed'
      setLastNote(msg)
      toast.error(`Create workstream failed: ${msg}`)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1">
      <ActionButton
        label="Enrich"
        Icon={Brain}
        status={enrichStatus}
        onClick={onEnrich}
      />
      <ActionButton
        label="Council"
        Icon={Users}
        status={qeStatus}
        onClick={onQeReview}
      />
      <ActionButton
        label="Create Workstream"
        Icon={ArrowRightCircle}
        status={wsStatus}
        onClick={onCreateWorkstream}
      />
      {lastNote && (
        <div className="basis-full mt-1 text-[10px] text-amber-300">
          {lastNote}
        </div>
      )}
    </div>
  )
}

function ActionButton({
  label,
  Icon,
  status,
  onClick,
}: {
  label: string
  Icon: typeof Brain
  status: DraftActionStatus
  onClick: () => void
}) {
  const disabled = status === 'running'
  const tone =
    status === 'done'
      ? 'border-emerald-500/40 text-emerald-200 bg-emerald-500/10'
      : status === 'refused'
        ? 'border-rose-500/40 text-rose-200 bg-rose-500/10'
        : 'border-white/10 text-starlight-300 hover:bg-white/5'
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      disabled={disabled}
      className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] border ${tone} ${
        disabled ? 'opacity-60 cursor-wait' : 'cursor-pointer'
      }`}
    >
      {status === 'running' ? (
        <Loader2 size={11} className="animate-spin" />
      ) : (
        <Icon size={11} />
      )}
      {label}
    </button>
  )
}

function DraftRow({
  draft,
  onRefresh,
  hasWorkstream,
}: {
  draft: ResearchDraftSummary
  onRefresh?: () => void
  hasWorkstream: boolean
}) {
  const [open, setOpen] = useState(false)
  const payload = draft.structured_payload
  const company = payload && typeof payload.company === 'string' ? payload.company : null
  const headline = company || draft.source_host || 'untitled draft'
  return (
    <div className="border border-white/5 rounded-md bg-white/[.02] hover:bg-white/[.04] transition">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        className="w-full flex items-start gap-2 p-2.5 text-left cursor-pointer"
      >
        {open ? <ChevronDown size={12} className="mt-0.5 text-starlight-500" /> : <ChevronRight size={12} className="mt-0.5 text-starlight-500" />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] font-semibold text-starlight-100 truncate">
              {headline}
            </span>
            <StatusBadges payload={payload} hasWorkstream={hasWorkstream} />
            <span className="text-[9px] text-starlight-500 font-mono">{draft.source_host}</span>
          </div>
          <div className="text-[10px] text-starlight-400 line-clamp-1 mt-0.5">
            {draft.goal}
          </div>
        </div>
        <span className="text-[9px] text-starlight-500 whitespace-nowrap">
          {formatRelative(draft.created_at)}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-0 space-y-2 text-[11px] text-starlight-300 border-t border-white/5">
          {payload ? (
            <pre className="text-[10px] overflow-x-auto bg-black/20 rounded p-2 whitespace-pre-wrap">
              {JSON.stringify(payload, null, 2)}
            </pre>
          ) : (
            <div className="italic text-starlight-500">no structured payload yet</div>
          )}
          <DraftActions
            draftId={draft.id}
            draftKind={draft.kind}
            onRefresh={onRefresh}
          />
        </div>
      )}
    </div>
  )
}

interface FormDraftSummary {
  id: string
  title: string
  source_kind: string
  source_url: string | null
  source_host: string | null
  goal: string
  status: string
  created_at: string
  structured_payload?: null
}

/**
 * StartHereCard — Sprint-MORNING PR-3.
 *
 * The morning landing card. Renders the suggested first workflow + a
 * compact totals row so the operator sees at a glance: how many drafts
 * exist, how many already have workstreams, what to do next. The card
 * is read-only — the suggested steps are buttons-as-text, not actions.
 */
function StartHereCard({
  careerCount,
  contentCount,
  formCount,
  workstreamCount,
}: {
  careerCount: number
  contentCount: number
  formCount: number
  workstreamCount: number
}) {
  const totalDrafts = careerCount + contentCount + formCount
  return (
    <div className="rounded-lg border border-primary-500/20 bg-primary-500/[0.04] p-3">
      <div className="flex items-start gap-2">
        <Sparkles size={14} className="mt-0.5 text-primary-400" />
        <div className="flex-1">
          <div className="text-[12px] font-semibold text-starlight-100">
            Start here tomorrow
          </div>
          <ol className="mt-1.5 space-y-0.5 list-decimal list-inside text-[11px] text-starlight-300">
            <li>Open <span className="text-starlight-100">Settings → Models &amp; Runtimes</span> to confirm the main brain is ready.</li>
            <li>Pick a draft below, click <span className="text-starlight-100">Enrich</span> for the routed brain to fill it.</li>
            <li>Run <span className="text-starlight-100">Council</span> for an honest cross-check.</li>
            <li>Click <span className="text-starlight-100">Create Workstream</span> to promote the draft to a work plan.</li>
            <li>Ask the chat: <span className="font-mono text-primary-300">what should I do next?</span></li>
          </ol>
          <div className="mt-2 flex items-center gap-3 text-[10px] text-starlight-400">
            <span>{totalDrafts} drafts</span>
            <span>·</span>
            <span>{careerCount} career</span>
            <span>·</span>
            <span>{contentCount} content</span>
            <span>·</span>
            <span>{formCount} form</span>
            <span>·</span>
            <span className="text-violet-300">{workstreamCount} workstreams</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function DraftsLane() {
  const [careerDrafts, setCareerDrafts] = useState<ResearchDraftSummary[]>([])
  const [contentDrafts, setContentDrafts] = useState<ResearchDraftSummary[]>([])
  // Sprint-13 PR-2: business opportunity drafts (grants / hackathons /
  // freelance / customer / partnership / security_bounty / rfp /
  // content / startup_program / accelerator).
  const [opportunityDrafts, setOpportunityDrafts] = useState<ResearchDraftSummary[]>([])
  const [formDrafts, setFormDrafts] = useState<FormDraftSummary[]>([])
  // Sprint-MORNING PR-3: source_ref_ids of drafts that already have a
  // workstream so we can render a "workstream created" badge on each row.
  const [draftIdsWithWorkstream, setDraftIdsWithWorkstream] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'career' | 'content' | 'opportunity' | 'form'>('career')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [careerRes, contentRes, opportunityRes, formsRes, wsRes] = await Promise.all([
        api.get('/research/drafts', { params: { kind: 'career', limit: 25 } }),
        api.get('/research/drafts', { params: { kind: 'content', limit: 25 } }),
        api.get('/research/drafts', { params: { kind: 'business_opportunity', limit: 25 } })
          .catch(() => ({ data: { drafts: [] } })),
        api.get('/form-drafts', { params: { limit: 25 } }).catch(() => ({ data: { drafts: [] } })),
        api.get('/workstreams', { params: { limit: 200 } }).catch(() => ({ data: { data: { workstreams: [] } } })),
      ])
      setCareerDrafts(careerRes.data?.drafts ?? [])
      setContentDrafts(contentRes.data?.drafts ?? [])
      setOpportunityDrafts(opportunityRes.data?.drafts ?? [])
      setFormDrafts(formsRes.data?.drafts ?? [])
      const wsList = (wsRes.data?.data?.workstreams ?? []) as Array<{
        source_type?: string | null
        source_ref_id?: string | null
      }>
      setDraftIdsWithWorkstream(
        new Set(
          wsList
            .filter(w => w.source_type === 'draft' && w.source_ref_id)
            .map(w => w.source_ref_id as string),
        ),
      )
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const careerCount = careerDrafts.length
  const contentCount = contentDrafts.length
  const opportunityCount = opportunityDrafts.length
  const formCount = formDrafts.length

  const TABS: Array<{ key: 'career' | 'content' | 'opportunity' | 'form'; label: string; icon: React.ReactNode; count: number }> = [
    { key: 'career', label: 'Career', icon: <Briefcase size={11} />, count: careerCount },
    { key: 'content', label: 'Content', icon: <Newspaper size={11} />, count: contentCount },
    { key: 'opportunity', label: 'Opportunities', icon: <Sparkles size={11} />, count: opportunityCount },
    { key: 'form', label: 'Forms', icon: <FileText size={11} />, count: formCount },
  ]

  const visibleResearch = tab === 'career'
    ? careerDrafts
    : tab === 'content'
      ? contentDrafts
      : tab === 'opportunity'
        ? opportunityDrafts
        : []

  return (
    <div className="glass-panel rounded-xl p-4 space-y-3">
      <StartHereCard
        careerCount={careerCount}
        contentCount={contentCount}
        formCount={formCount}
        workstreamCount={draftIdsWithWorkstream.size}
      />
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <div className="text-sm font-bold text-starlight-100">Drafts to review</div>
          <div className="text-[11px] text-starlight-500">
            Local-only research artifacts. Daena prepared, you decide what's next. No external action fires from this lane.
          </div>
        </div>
        <button
          onClick={() => void load()}
          className="text-[10px] text-starlight-400 hover:text-starlight-100 inline-flex items-center gap-1"
        >
          <RefreshCw size={10} /> Refresh
        </button>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-2 py-1 rounded text-[10px] inline-flex items-center gap-1 cursor-pointer ${
              tab === t.key
                ? 'bg-primary-500 text-white'
                : 'bg-white/5 text-starlight-300 hover:bg-white/10'
            }`}
          >
            {t.icon}
            {t.label}
            <span className="px-1 text-[9px] rounded bg-black/20">{t.count}</span>
          </button>
        ))}
      </div>

      {error && (
        <div className="text-[11px] text-amber-300">Failed to load drafts: {error}</div>
      )}

      {loading ? (
        <div className="text-[11px] text-starlight-400">Loading drafts…</div>
      ) : tab === 'form' ? (
        formDrafts.length === 0 ? (
          <div className="text-[11px] text-starlight-500 italic px-1">
            No form drafts yet. Daena prepares answers locally; you submit
            manually. Use <code className="bg-white/5 px-1 rounded">POST /api/v1/form-drafts/from-questions</code>,
            <code className="bg-white/5 px-1 rounded">/from-html</code>,
            or <code className="bg-white/5 px-1 rounded">/from-url</code>.
          </div>
        ) : (
          <div className="space-y-1.5">
            {formDrafts.map(d => (
              <div key={d.id} className="border border-white/5 rounded-md bg-white/[.02] p-2.5 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-[11px] font-semibold text-starlight-100 truncate flex items-center gap-2">
                    <span className="truncate">{d.title}</span>
                    <StatusBadges
                      payload={null}
                      hasWorkstream={draftIdsWithWorkstream.has(d.id)}
                    />
                  </div>
                  <div className="text-[9px] text-starlight-500">{formatRelative(d.created_at)}</div>
                </div>
                <div className="text-[10px] text-starlight-400 truncate">
                  source: {d.source_kind}{d.source_host ? ` · ${d.source_host}` : ''}
                </div>
                <DraftActions
                  draftId={d.id}
                  draftKind="form"
                  onRefresh={load}
                />
              </div>
            ))}
          </div>
        )
      ) : visibleResearch.length === 0 ? (
        <div className="text-[11px] text-starlight-500 italic px-1">
          No {tab} drafts yet. Run a research flow from chat or call <code className="bg-white/5 px-1 rounded">POST /api/v1/research/{tab}</code>.
        </div>
      ) : (
        <div className="space-y-1.5">
          {visibleResearch.map(d => (
            <DraftRow
              key={d.id}
              draft={d}
              onRefresh={load}
              hasWorkstream={draftIdsWithWorkstream.has(d.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}


export default function WorkstreamsPage() {
  const [items, setItems] = useState<Workstream[]>([])
  const [loading, setLoading] = useState(true)
  // PR-A11Y-PHASE35: distinct fetch-error state. Without it a failed
  // GET /workstreams fell through to the "No workstreams yet" empty copy
  // (a false-empty LIE -- Rule 17) with only a transient toast as the signal.
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<WorkstreamStatus | 'ALL'>('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [demoLoading, setDemoLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = statusFilter === 'ALL' ? {} : { status: statusFilter }
      const res = await api.get('/workstreams', { params })
      setItems(res.data?.data?.workstreams ?? [])
    } catch {
      setItems([])
      setError('The workstreams service is unreachable. Retry to refresh.')
      toast.error('Failed to load workstreams')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    void load()
  }, [load])

  // PR-SPINE-06: honor ?focus=<workstream_id> to deep-link from PR-SCAN-WS-01
  // ("Create remediation task" success toast) and any future surface that
  // wants to drop the user straight into the live drawer. We read the
  // value once on mount and clear the param so a later interaction
  // (close + reopen) does not silently reopen the same workstream.
  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    const focus = params.get('focus')
    if (!focus) return
    setSelectedId(focus)
    params.delete('focus')
    const search = params.toString()
    const next = `${window.location.pathname}${search ? `?${search}` : ''}${window.location.hash}`
    window.history.replaceState({}, '', next)
  }, [])

  const launchDemo = async () => {
    setDemoLoading(true)
    try {
      const res = await api.post('/workstreams/dev-safe-demo', {})
      const newId = res.data?.data?.id ?? null
      await load()
      if (newId) setSelectedId(newId)
      toast.success('Dev-safe demo workstream created')
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: { error?: { message?: string } } } } })
          ?.response?.data?.detail?.error?.message
      toast.error(detail ?? 'Failed to create demo workstream')
    } finally {
      setDemoLoading(false)
    }
  }

  const FILTERS: Array<{ key: WorkstreamStatus | 'ALL'; label: string }> = [
    { key: 'ALL', label: 'All' },
    { key: 'RUNNING', label: 'Running' },
    { key: 'BLOCKED', label: 'Blocked' },
    { key: 'WAITING_APPROVAL', label: 'Waiting approval' },
    { key: 'COMPLETE', label: 'Complete' },
    { key: 'FAILED', label: 'Failed' },
  ]

  return (
    <div className="p-6 space-y-5 max-w-5xl mx-auto">
      <div>
        <h1 className="text-xl font-bold text-starlight-100">Workstreams</h1>
        <p className="text-xs text-starlight-400 mt-1 max-w-prose">
          Daena's visible unit of autonomy — a governed, interruptible thread of
          work with a goal, owner department, decisions, artifacts, blockers,
          and audit trail. Click a workstream to inspect its timeline or
          redirect it mid-flight.
        </p>
      </div>

      {/* Sprint-13 PR-1: Business Autonomy Mission Control. The 5-state
          meta-control over what classes of action Daena is allowed to
          take autonomously. Mounted ABOVE Drafts so the operator sees
          the policy before they see what Daena did under it. */}
      <AutonomyMissionControl />

      {/* Sprint-11 PR-2: Drafts lane. Local-only research drafts live
          alongside the live workstream feed. No external action fires
          from this lane -- it is preparation surface only. */}
      <DraftsLane />

      <div className="flex items-center gap-2 flex-wrap">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setStatusFilter(f.key)}
            className={`px-2.5 py-1 rounded-md text-[11px] cursor-pointer ${
              statusFilter === f.key
                ? 'bg-primary-500 text-white'
                : 'bg-white/5 text-starlight-300 hover:bg-white/10'
            }`}
          >
            {f.label}
          </button>
        ))}
        <button
          onClick={() => void launchDemo()}
          disabled={demoLoading}
          className="ml-auto px-2.5 py-1 rounded-md text-[11px] bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/25 disabled:opacity-50 cursor-pointer inline-flex items-center gap-1"
          title="Spin up a populated demo workstream so you can see source / progress / artifacts rendered without wiring chat or scan first"
        >
          <Zap size={11} /> {demoLoading ? 'Starting…' : 'Demo workstream'}
        </button>
        <button
          onClick={() => void load()}
          className="text-[11px] text-starlight-400 hover:text-starlight-100 inline-flex items-center gap-1"
        >
          <RefreshCw size={11} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="text-xs text-starlight-400">Loading…</div>
      ) : error ? (
        <div className="glass-panel rounded-xl p-6 text-center">
          <AlertCircle size={20} className="mx-auto text-rose-300 mb-2" />
          <div className="text-sm text-starlight-200 font-medium mb-1">
            Could not load workstreams
          </div>
          <div className="text-xs text-starlight-500 max-w-prose mx-auto mb-3">
            {error}
          </div>
          <button
            onClick={() => void load()}
            className="text-[11px] text-starlight-400 hover:text-starlight-100 inline-flex items-center gap-1"
          >
            <RefreshCw size={11} /> Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="glass-panel rounded-xl p-6 text-center">
          <div className="text-sm text-starlight-300 font-medium mb-1">
            No workstreams yet
          </div>
          <div className="text-xs text-starlight-500 max-w-prose mx-auto">
            Workstreams appear when EXE-mode chat in Autopilot, manual tasks
            with the <code className="px-1 py-0.5 rounded bg-white/5">also_create_workstream</code> flag,
            or future scan / company-mode flows kick off. To see what one looks
            like populated end-to-end, click <strong className="text-amber-300">Demo workstream</strong> above.
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map(ws => (
            <WorkstreamCard
              key={ws.id}
              ws={ws}
              onSelect={() => setSelectedId(ws.id)}
            />
          ))}
        </div>
      )}

      <AnimatePresence>
        {selectedId && (
          <WorkstreamDetailDrawer
            workstreamId={selectedId}
            onClose={() => setSelectedId(null)}
            onMutated={() => void load()}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
