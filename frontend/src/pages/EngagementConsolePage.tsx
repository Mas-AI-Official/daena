/**
 * EngagementConsolePage — Phase G of Roadmap V2.
 *
 * Kicks off governed security engagements against a scoped target and
 * shows the live scan progress + completed reports. Backed by
 * /api/v1/engagements (POST to start, GET list, GET {job_id} for
 * status, GET {job_id}/report when done).
 *
 * High-risk tiers (T4 Architect and the founder-gated T5) return an `approval_required`
 * payload in GOVERNED mode. The page surfaces that and routes the
 * user to /governance/approvals instead of treating it as an error.
 */
import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Crosshair,
  Shield,
  ShieldAlert,
  Loader2,
  CheckCircle2,
  XCircle,
  ExternalLink,
  RefreshCw,
  FileText,
  Target,
  Activity,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import type { ApiResponse } from '@/types/api'

// Public tier set. The T5 full-spectrum tier is intentionally OMITTED
// from this dropdown. It unlocks only via the founder secret-command
// flow (see /3vilbob handler in chat). Per founder rule, the legacy
// internal tier name is never rendered in any public surface.
type EngagementTier = string

const PUBLIC_TIERS: {
  value: string           // wire value expected by backend
  label: string           // ONLY string rendered to the user
  desc: string
  risk: 'low' | 'medium' | 'high' | 'critical'
}[] = [
  { value: 'SCOUT',     label: 'T1 Scout',     desc: 'Fast surface scan. Low signal, low risk.',        risk: 'low' },
  { value: 'ANALYST',   label: 'T2 Analyst',   desc: 'Static + enrichment. Typical paid engagement.',   risk: 'medium' },
  { value: 'OPERATOR',  label: 'T3 Operator',  desc: 'Full cognitive scan, deeper analysis.',           risk: 'medium' },
  { value: 'ARCHITECT', label: 'T4 Architect', desc: 'Post-exploit + proof of impact. Approval-gated.', risk: 'high' },
]

interface EngagementJob {
  id: string
  target: string
  tier: string
  status: string
  progress_pct: number
  files_scanned: number
  files_total: number
  findings_count: number
  error: string
  created_at: number
  updated_at: number
}

interface StartEngagementResponse {
  job_id: string
  status: string
  tier: string
  target: string
  approval_required: boolean
}

interface ApprovalRequiredBody {
  success: false
  approval_required: true
  reason: string
  tier: string
  target: string
}

const STATUS_VARIANT: Record<string, string> = {
  queued:     'default',
  profiling:  'info',
  scanning:   'info',
  analyzing:  'info',
  reporting:  'warning',
  complete:   'success',
  failed:     'danger',
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'complete') return <CheckCircle2 size={14} />
  if (status === 'failed')   return <XCircle size={14} />
  if (status === 'queued')   return <Activity size={14} />
  return <Loader2 size={14} className="animate-spin" />
}

export function EngagementConsolePage() {
  usePageTitle('Security Engagements')

  const [jobs, setJobs] = useState<EngagementJob[]>([])
  const [loading, setLoading] = useState(true)
  const [target, setTarget] = useState('')
  const [tier, setTier] = useState<EngagementTier>('ANALYST')
  const [submitting, setSubmitting] = useState(false)
  const [gateBanner, setGateBanner] = useState<ApprovalRequiredBody | null>(null)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [report, setReport] = useState<Record<string, unknown> | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  // T5 unlock state. Read from /engagements/shield-status; the tier
  // appears in the dropdown only when the founder secret command
  // has activated the mode in this process.
  const [t5Unlocked, setT5Unlocked] = useState(false)
  const [t5WireValue, setT5WireValue] = useState('')

  const fetchJobs = async () => {
    try {
      const { data } = await api.get<ApiResponse<EngagementJob[]>>('/engagements')
      setJobs(data.data || [])
    } catch {
      setJobs([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void fetchJobs() }, [])

  // Poll shield-status. Refreshes on mount and every 15s so the T5
  // option appears within seconds of the founder enabling it via the
  // chat secret command.
  useEffect(() => {
    let cancelled = false
    const fetchShield = async () => {
      try {
        const { data } = await api.get<{ success: boolean; data: { t5_unlocked: boolean; t5_wire_value: string } }>(
          '/engagements/shield-status',
        )
        if (!cancelled) {
          setT5Unlocked(!!data.data?.t5_unlocked)
          setT5WireValue(String(data.data?.t5_wire_value || ''))
        }
      } catch {
        // Degraded: hide T5 option.
      }
    }
    void fetchShield()
    const id = setInterval(() => { void fetchShield() }, 15000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  const visibleTiers = useMemo(() => {
    if (!t5Unlocked || !t5WireValue) return PUBLIC_TIERS
    return [
      ...PUBLIC_TIERS,
      { value: t5WireValue, label: 'T5 Shield (unlocked)', desc: 'Full-spectrum, leaves no trace. Founder approval required.', risk: 'critical' as const },
    ]
  }, [t5Unlocked, t5WireValue])

  // Live refresh while any job is still in flight.
  useEffect(() => {
    const inFlight = jobs.some((j) => j.status !== 'complete' && j.status !== 'failed')
    if (!inFlight) return
    const id = setInterval(() => { void fetchJobs() }, 4000)
    return () => clearInterval(id)
  }, [jobs])

  const start = async () => {
    if (!target.trim()) return
    setSubmitting(true)
    setGateBanner(null)
    try {
      const { data } = await api.post<ApiResponse<StartEngagementResponse> | ApprovalRequiredBody>(
        '/engagements',
        { target: target.trim(), tier },
      )
      if ((data as ApprovalRequiredBody).approval_required) {
        setGateBanner(data as ApprovalRequiredBody)
      } else {
        setTarget('')
        await fetchJobs()
      }
    } catch (err) {
      const { toast } = await import('@/stores/toastStore')
      toast.error(err instanceof Error ? err.message : 'Failed to start engagement')
    } finally {
      setSubmitting(false)
    }
  }

  const openReport = async (jobId: string) => {
    setSelectedJobId(jobId)
    setReport(null)
    setReportLoading(true)
    try {
      const { data } = await api.get<ApiResponse<Record<string, unknown>>>(
        `/engagements/${jobId}/report`,
      )
      setReport(data.data || null)
    } catch {
      setReport(null)
    } finally {
      setReportLoading(false)
    }
  }

  const sortedJobs = useMemo(
    () => [...jobs].sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0)),
    [jobs],
  )

  return (
    <motion.div
      className="h-full overflow-y-auto p-6 space-y-4"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Crosshair className="text-accent-amber" size={22} />
          <h1 className="text-xl font-semibold text-starlight-100">Security Engagements</h1>
          <Badge variant="warning">Phase G</Badge>
        </div>
        <Button variant="ghost" onClick={() => void fetchJobs()}>
          <RefreshCw size={14} /> Refresh
        </Button>
      </div>

      {/* New engagement */}
      <Card className="p-4 space-y-3">
        <div className="flex items-center gap-2">
          <Target size={16} className="text-accent-cyan" />
          <h2 className="text-sm font-medium text-starlight-100">Launch governed engagement</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-[1fr_240px_auto] gap-2">
          <input
            type="text"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="Repository URL, folder, or comma-separated files"
            className="px-3 py-2 rounded-md bg-midnight-300/60 border border-white/10 text-sm text-starlight-100 placeholder-starlight-500 focus:outline-none focus:border-primary-500/40"
          />
          <select
            value={tier}
            onChange={(e) => setTier(e.target.value as EngagementTier)}
            className="px-3 py-2 rounded-md bg-midnight-300/60 border border-white/10 text-sm text-starlight-100 focus:outline-none focus:border-primary-500/40"
          >
            {visibleTiers.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label} — {t.desc}
              </option>
            ))}
          </select>
          <Button onClick={() => void start()} disabled={!target.trim() || submitting}>
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <Shield size={14} />}
            Start
          </Button>
        </div>
        <p className="text-[11px] text-starlight-500">
          T4 Architect and higher open an approval row in GOVERNED mode. Approve at{' '}
          <Link to="/governance/approvals" className="text-accent-cyan underline">
            /governance/approvals
          </Link>{' '}
          then retry.
        </p>
      </Card>

      {/* Approval gate banner */}
      {gateBanner && (
        <Card className="p-4 border border-status-warning/40 bg-status-warning/5 flex items-start gap-3">
          <ShieldAlert className="text-status-warning shrink-0" size={18} />
          <div className="flex-1">
            <p className="text-sm font-medium text-status-warning">Approval required</p>
            <p className="text-xs text-starlight-300 mt-1">{gateBanner.reason}</p>
            <p className="text-[11px] text-starlight-500 mt-1">
              Target: <span className="text-starlight-300">{gateBanner.target}</span> · Tier:{' '}
              <span className="text-starlight-300">{gateBanner.tier}</span>
            </p>
          </div>
          <Link to="/governance/approvals" className="shrink-0">
            <Button variant="ghost"><ExternalLink size={14} /> Open approvals</Button>
          </Link>
        </Card>
      )}

      {/* Jobs list */}
      <div className="space-y-2">
        {loading && (
          <div className="space-y-2">
            <Shimmer className="h-12" /><Shimmer className="h-12" /><Shimmer className="h-12" />
          </div>
        )}
        {!loading && sortedJobs.length === 0 && (
          <EmptyState
            icon={<Crosshair size={28} />}
            title="No engagements yet"
            description="Launch a SCOUT-tier scan against a repository URL to see the full pipeline end to end."
          />
        )}
        {!loading && sortedJobs.map((j) => (
          <Card key={j.id} className="p-3 flex items-center gap-3">
            <Badge variant={STATUS_VARIANT[j.status] as 'default'|'info'|'warning'|'success'|'danger'}>
              <StatusIcon status={j.status} /> {j.status}
            </Badge>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-starlight-100 truncate">{j.target}</p>
              <p className="text-[11px] text-starlight-500">
                {j.tier} · {j.files_scanned}/{j.files_total || '?'} files · {j.findings_count} findings
                {j.error ? ` · error: ${j.error}` : ''}
              </p>
            </div>
            {j.status === 'complete' && (
              <Button variant="ghost" onClick={() => void openReport(j.id)}>
                <FileText size={14} /> Report
              </Button>
            )}
          </Card>
        ))}
      </div>

      {/* Report modal (inline panel) */}
      {selectedJobId && (
        <Card className="p-4 space-y-3 border border-primary-500/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-primary-400" />
              <h2 className="text-sm font-medium text-starlight-100">Engagement report · {selectedJobId}</h2>
            </div>
            <Button variant="ghost" onClick={() => { setSelectedJobId(null); setReport(null) }}>
              Close
            </Button>
          </div>
          {reportLoading && <Shimmer className="h-24" />}
          {!reportLoading && report && (
            <div className="space-y-2">
              <p className="text-xs text-starlight-300">
                <strong className="text-starlight-100">Summary:</strong> {String(report.summary || 'n/a')}
              </p>
              <p className="text-[11px] text-starlight-500">
                Duration {String(report.duration_secs ?? '?')}s · Cost ${String(report.cost_usd ?? '0')} ·
                Stages {Array.isArray(report.pipeline_stages_used) ? (report.pipeline_stages_used as string[]).join(', ') : 'n/a'}
              </p>
              {Array.isArray(report.findings) && (report.findings as unknown[]).length > 0 && (
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {(report.findings as Record<string, unknown>[]).map((f, i) => (
                    <div key={i} className="p-2 rounded-md bg-midnight-300/40 border border-white/5">
                      <p className="text-xs text-starlight-100">
                        <Badge variant={
                          String(f.severity) === 'CRITICAL' ? 'danger' :
                          String(f.severity) === 'HIGH' ? 'warning' :
                          String(f.severity) === 'MEDIUM' ? 'info' : 'default'
                        }>{String(f.severity)}</Badge>{' '}
                        <strong>{String(f.title)}</strong>
                      </p>
                      <p className="text-[11px] text-starlight-500 mt-1">{String(f.location ?? '')}</p>
                      <p className="text-[11px] text-starlight-400 mt-1">{String(f.remediation ?? '')}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      )}
    </motion.div>
  )
}

export default EngagementConsolePage
