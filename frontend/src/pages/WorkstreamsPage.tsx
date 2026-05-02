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
import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity,
  AlertCircle,
  Archive,
  CheckCircle2,
  Clock,
  FileText,
  Mail,
  MessageSquare,
  Pause,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Tag,
  Workflow,
  XCircle,
  Zap,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

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

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get(`/workstreams/${workstreamId}`)
      setData(res.data?.data ?? null)
    } catch {
      toast.error('Failed to load workstream')
    } finally {
      setLoading(false)
    }
  }, [workstreamId])

  useEffect(() => {
    void refresh()
  }, [refresh])

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
    try {
      await api.post(`/workstreams/${workstreamId}/${action}`)
      await refresh()
      onMutated()
      toast.success(`${action[0].toUpperCase() + action.slice(1)}d`)
    } catch {
      toast.error(`Failed to ${action}`)
    }
  }

  const archive = async () => {
    try {
      await api.patch(`/workstreams/${workstreamId}/archive`)
      onMutated()
      onClose()
      toast.success('Workstream archived')
    } catch {
      toast.error('Failed to archive')
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
                  className="px-2 py-1.5 rounded-md text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
                >
                  <Pause size={12} className="inline mr-1" />
                  Pause autopilot
                </button>
                <button
                  onClick={() => void lifecycleAction('resume')}
                  className="px-2 py-1.5 rounded-md text-xs bg-white/5 text-starlight-300 hover:bg-white/10 cursor-pointer"
                >
                  <Play size={12} className="inline mr-1" />
                  Resume
                </button>
                <button
                  onClick={() => void archive()}
                  className="ml-auto px-2 py-1.5 rounded-md text-xs bg-white/5 text-starlight-400 hover:bg-amber-500/15 hover:text-amber-300 cursor-pointer"
                  title="Soft-delete this workstream (status preserved for audit)"
                >
                  <Archive size={12} className="inline mr-1" />
                  Archive
                </button>
              </div>
            </div>

            {/* Timeline */}
            <div className="space-y-2 pt-3 border-t border-white/10">
              <div className="flex items-center justify-between">
                <div className="text-[10px] uppercase tracking-wider font-semibold text-starlight-500">
                  Governed execution timeline
                </div>
                <button
                  onClick={() => void refresh()}
                  className="text-[10px] text-starlight-400 hover:text-starlight-100 inline-flex items-center gap-1"
                >
                  <RefreshCw size={10} /> Refresh
                </button>
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

export default function WorkstreamsPage() {
  const [items, setItems] = useState<Workstream[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<WorkstreamStatus | 'ALL'>('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [demoLoading, setDemoLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = statusFilter === 'ALL' ? {} : { status: statusFilter }
      const res = await api.get('/workstreams', { params })
      setItems(res.data?.data?.workstreams ?? [])
    } catch {
      toast.error('Failed to load workstreams')
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    void load()
  }, [load])

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
