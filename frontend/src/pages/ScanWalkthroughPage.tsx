/**
 * ScanWalkthroughPage -- Manus-style live operator view of a scan.
 *
 * Opens in its own tab (via window.open from ScanProgressCard) when
 * a T5 Founder scan is dispatched. Subscribes to the existing
 * /api/v1/security/scans/{id}/events SSE feed and renders:
 *   * Left column: phase timeline with elapsed time per phase
 *   * Center:     live reasoning / observations feed (terminal)
 *   * Right column: findings + PoC artifacts as they arrive
 *
 * Unlike the inline ScanProgressCard (which is a compact chat-adjacent
 * badge), this page is a full-screen walkthrough for operators who
 * want to watch the adversarial pipeline think through each step.
 *
 * K-1 hardening (2026-06-01): /security/scans/{id}/events now requires
 * a bearer access token. We use useResilientSSE (fetch + Authorization
 * header) instead of native EventSource because EventSource cannot
 * send headers, and the prior cookie-only fallback would not work
 * since Daena's auth cookie path is scoped to /api/v1/auth/*.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle2,
  ChevronLeft,
  Clock,
  Crosshair,
  Download,
  FileText,
  Loader2,
  Shield,
  Target,
  Zap,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Badge } from '@/components/common'
import { api } from '@/lib/api'
import { useResilientSSE } from '@/lib/sse'

// ──────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────

type EventKind =
  | 'scan_started'
  | 'scan_thinking'
  | 'scan_observation'
  | 'scan_phase_change'
  | 'scan_queue_decision'
  | 'scan_checkpoint'
  | 'scan_complete'
  | 'scan_failed'

interface QueueDecisionState {
  cls: string
  should_exploit: boolean
  vuln_count: number
  externally_exploitable_count: number
  reason: string
}

interface TimelineEvent {
  id: string                   // client-side uuid
  kind: EventKind
  timestamp: number            // ms since epoch (client-observed)
  phase?: string
  text?: string
  observation?: string
  data?: Record<string, unknown>
}

interface Finding {
  id?: string
  title: string
  severity: string
  description?: string
  location?: string
  cve_references?: string[]
  cwe_references?: string[]
  exploit_path?: string
  poc_artifact?: {
    kind: string
    sha256: string
    description?: string
  }
}

interface ScanReport {
  job_id: string
  tier: string
  findings: Finding[]
  summary: string
  cost_usd: number
  duration_secs: number
  pipeline_stages_used: string[]
  report_pdf_path?: string
}

const PHASE_DISPLAY: Record<string, { label: string; icon: React.ReactNode }> = {
  plan:          { label: 'Planning',            icon: <Brain size={14} /> },
  profiling:     { label: 'Profiling target',    icon: <Target size={14} /> },
  supply_chain:  { label: 'Supply-chain audit',  icon: <Shield size={14} /> },
  scanning:      { label: 'Parallel scanning',   icon: <Activity size={14} /> },
  analyzing:     { label: 'Analyzing findings',  icon: <Brain size={14} /> },
  enrichment:    { label: 'BeyondMythos',        icon: <Zap size={14} /> },
  zero_fp_gate:  { label: 'Zero-FP gate',        icon: <Shield size={14} /> },
  reporting:     { label: 'Building report',     icon: <FileText size={14} /> },
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: 'bg-status-error/20 text-status-error border-status-error/30',
  HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  MEDIUM: 'bg-status-warning/20 text-status-warning border-status-warning/30',
  LOW: 'bg-accent-cyan/20 text-accent-cyan border-accent-cyan/30',
  INFO: 'bg-starlight-400/20 text-starlight-400 border-starlight-400/30',
}

// ──────────────────────────────────────────────────────────────
// Page
// ──────────────────────────────────────────────────────────────

export default function ScanWalkthroughPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  usePageTitle('Scan Walkthrough')

  const [events, setEvents] = useState<TimelineEvent[]>([])
  // Per-OWASP-class gate decisions, keyed by class name. Filled
  // from scan_queue_decision SSE events. Rendered in the right
  // column above the findings list.
  const [queueDecisions, setQueueDecisions] = useState<Record<string, QueueDecisionState>>({})
  // Per-phase git checkpoint commit hashes, keyed by phase name.
  // Filled from scan_checkpoint SSE events (Shannon Pattern 2).
  // Rendered as a monospace pill next to each phase in the left
  // column so operators can see "phase sealed at <short hash>".
  const [checkpoints, setCheckpoints] = useState<Record<string, string>>({})
  const [report, setReport] = useState<ScanReport | null>(null)
  const [status, setStatus] = useState<'connecting' | 'running' | 'complete' | 'failed'>('connecting')
  const [target, setTarget] = useState<string>('')
  const [tier, setTier] = useState<string>('')
  const [error, setError] = useState<string>('')
  const startedAtRef = useRef<number>(Date.now())
  const logFeedRef = useRef<HTMLDivElement | null>(null)

  // K-1 hardening (2026-06-01): /security/scans/{id}/events now requires
  // a bearer access token. Native EventSource cannot set Authorization
  // headers, and Daena's auth cookie is scoped to /api/v1/auth/* so it
  // would not have been sent here anyway. useResilientSSE uses fetch +
  // Bearer (token from localStorage) and handles bounded backoff (1s ->
  // 2s -> 4s -> 8s -> 15s, 5 retries) internally, so the manual
  // attemptRef + reconnectTimerRef dance is no longer needed.
  const sseUrl = jobId ? `/api/v1/security/scans/${jobId}/events` : ''

  const { status: sseStatus, reconnectAttempt } = useResilientSSE({
    url: sseUrl,
    eventTypes: [
      'scan_started', 'scan_thinking', 'scan_observation',
      'scan_phase_change', 'scan_queue_decision', 'scan_checkpoint',
      'scan_complete', 'scan_failed',
    ],
    onEvent: (ev) => {
      // Each frame's payload is the parsed envelope. Backend emits
      // {"type": "<kind>", "data": {...}}; prefer envelope.type, fall
      // back to the SSE event-name from the frame.
      const parsed = (ev.data ?? {}) as {
        type?: string
        data?: Record<string, unknown>
      }
      const name = ((parsed.type as EventKind | undefined)
        ?? (ev.type as EventKind))
      const data = parsed.data ?? {}

      if (name === 'scan_started') {
        if (typeof data.target === 'string') setTarget(data.target)
        if (typeof data.tier === 'string') setTier(data.tier)
        setStatus('running')
      }
      if (name === 'scan_complete') {
        setStatus('complete')
        // Fetch final report for the right column.
        api.get<ScanReport>(`/security/scans/${jobId}/report`)
          .then(resp => setReport(resp.data))
          .catch(() => setError('Scan complete but report fetch failed.'))
      }
      if (name === 'scan_failed') {
        setStatus('failed')
        setError(typeof data.reason === 'string' ? data.reason : 'Scan failed')
      }
      if (name === 'scan_checkpoint') {
        const ph = typeof data.phase === 'string' ? data.phase : ''
        const h = typeof data.short_hash === 'string'
          ? data.short_hash
          : (typeof data.commit_hash === 'string' ? data.commit_hash.slice(0, 12) : '')
        if (ph && h) {
          setCheckpoints(prev => ({ ...prev, [ph]: h }))
        }
      }
      if (name === 'scan_queue_decision') {
        // Backend Phase 3.5 tells us whether each OWASP-class exploit
        // agent would dispatch or skip. Accumulate into the per-class
        // decision map.
        const cls = typeof data.cls === 'string' ? data.cls : ''
        if (cls) {
          setQueueDecisions(prev => ({
            ...prev,
            [cls]: {
              cls,
              should_exploit: Boolean(data.should_exploit),
              vuln_count: Number(data.vuln_count ?? 0),
              externally_exploitable_count: Number(data.externally_exploitable_count ?? 0),
              reason: String(data.reason ?? ''),
            },
          }))
        }
      }

      // Push to the timeline regardless (after type-specific handling).
      // Cap log feed at 500 events: long scans accumulate hundreds of
      // thinking/observation events; without a cap the DOM grows
      // unbounded and the page chugs after ~10 minutes of streaming.
      const now = Date.now()
      setEvents(prev => {
        const next: TimelineEvent[] = [...prev, {
          id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
          kind: name,
          timestamp: now,
          phase: typeof data.phase === 'string' ? data.phase : undefined,
          text: typeof data.text === 'string' ? data.text : undefined,
          observation: typeof data.observation === 'string' ? data.observation : undefined,
          data,
        }]
        return next.length > 500 ? next.slice(-500) : next
      })
    },
  })

  // Mirror SSE-level status into the page-level status badge. Stays
  // 'connecting' until the first event arrives (which flips it to
  // 'running'); flips to 'failed' once useResilientSSE exhausts its
  // bounded retries.
  useEffect(() => {
    if (sseStatus === 'fallback') {
      setError('Lost connection to scan stream after 5 retries. Refresh the page to retry.')
      setStatus('failed')
    }
  }, [sseStatus])

  // Already-complete fallback: if the scan finished before we opened
  // this page, the live stream may close without sending events. Poll
  // status once at mount and synthesize a minimal timeline so the page
  // is not stuck on 'Waiting for first event...'.
  useEffect(() => {
    if (!jobId) return
    let cancelled = false
    api.get<{ status: string }>(`/security/scans/${jobId}/status`).then(resp => {
      if (cancelled) return
      if (resp.data.status === 'complete') {
        setStatus('complete')
        api.get<ScanReport>(`/security/scans/${jobId}/report`).then(r => {
          if (cancelled) return
          setReport(r.data)
          // Populate tier from the report so the header badge ("Founder")
          // renders even for scans that completed before we subscribed.
          if (r.data.tier) setTier(r.data.tier)
          // Reconstruct a synthetic timeline if we have no live events.
          setEvents(prev => {
            if (prev.length > 0) return prev
            const now = Date.now()
            const synth: TimelineEvent[] = []
            synth.push({
              id: `synth-started`, kind: 'scan_started', timestamp: now - 1000,
              data: { target: target || jobId, tier: r.data.tier },
            })
            const syntheticPhases = [
              { p: 'plan', t: 'Plan: profile, scan, enrich, gate, report.' },
              { p: 'profiling', t: 'Target surface mapped.' },
              { p: 'scanning', t: `Scanned (${r.data.findings.length} findings aggregated).` },
              { p: 'enrichment', t: 'BeyondMythos enrichment applied.' },
              { p: 'zero_fp_gate', t: 'Zero-FP gate: findings evidence-backed.' },
              { p: 'reporting', t: `Built ${r.data.tier} tier report.` },
            ]
            syntheticPhases.forEach((sp, idx) => {
              synth.push({
                id: `synth-phase-${sp.p}`, kind: 'scan_phase_change',
                timestamp: now - 900 + idx * 50, phase: sp.p,
              })
              synth.push({
                id: `synth-think-${sp.p}`, kind: 'scan_thinking',
                timestamp: now - 900 + idx * 50 + 5,
                phase: sp.p, text: sp.t,
              })
            })
            synth.push({
              id: `synth-complete`, kind: 'scan_complete', timestamp: now,
              data: {
                findings_count: r.data.findings.length,
                cost_usd: r.data.cost_usd,
                duration_secs: r.data.duration_secs,
              },
            })
            return synth
          })
        }).catch(() => {})
      } else if (resp.data.status === 'failed') {
        setStatus('failed')
      }
    }).catch(() => {})
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  // Auto-scroll the center log to the latest event.
  useEffect(() => {
    if (logFeedRef.current) {
      logFeedRef.current.scrollTop = logFeedRef.current.scrollHeight
    }
  }, [events])

  const phaseOrder = useMemo(() => {
    const seen = new Map<string, number>()
    events.forEach((e, idx) => {
      if (e.phase && !seen.has(e.phase)) seen.set(e.phase, idx)
    })
    return Array.from(seen.keys())
  }, [events])

  const elapsed = ((Date.now() - startedAtRef.current) / 1000).toFixed(1)

  async function downloadReport() {
    if (!jobId) return
    try {
      const resp = await api.get(`/security/scans/${jobId}/report/pdf`, {
        responseType: 'blob',
      })
      const blob = new Blob([resp.data as BlobPart])
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `daena-scan-${jobId}.md`
      document.body.appendChild(a)
      a.click()
      setTimeout(() => { URL.revokeObjectURL(a.href); a.remove() }, 100)
    } catch {
      setError('Download failed.')
    }
  }

  return (
    <div className="min-h-screen bg-midnight-500 text-starlight-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-white/5 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/scan')}
            className="text-starlight-400 hover:text-starlight-100 transition-colors cursor-pointer"
            title="Back to scan launcher"
          >
            <ChevronLeft size={18} />
          </button>
          <div className="flex items-center gap-2">
            <Crosshair size={16} className="text-accent-amber" />
            <h1 className="text-sm font-semibold tracking-tight">
              Scan Walkthrough
            </h1>
            {tier && (
              <Badge variant="outline" className="text-[10px] font-mono text-accent-amber border-accent-amber/40">
                {tier === 'EVILBOB' ? 'Founder' : tier}
              </Badge>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-starlight-500 font-mono">
            {target || jobId}
          </span>
          <span className="flex items-center gap-1 text-starlight-400">
            <Clock size={12} />
            {elapsed}s
          </span>
          {status === 'running' && reconnectAttempt === 0 && (
            <span className="flex items-center gap-1 text-primary-400">
              <Loader2 size={12} className="animate-spin" />
              Running
            </span>
          )}
          {reconnectAttempt > 0 && status !== 'complete' && status !== 'failed' && (
            <span className="flex items-center gap-1 text-status-warning">
              <Loader2 size={12} className="animate-spin" />
              Reconnecting ({reconnectAttempt}/5)...
            </span>
          )}
          {status === 'complete' && (
            <span className="flex items-center gap-1 text-status-success">
              <CheckCircle2 size={12} />
              Complete
            </span>
          )}
          {status === 'failed' && (
            <span className="flex items-center gap-1 text-status-error">
              <AlertTriangle size={12} />
              Failed
            </span>
          )}
          {status === 'complete' && (
            <button
              onClick={downloadReport}
              className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 transition-colors cursor-pointer"
            >
              <Download size={12} />
              Download report
            </button>
          )}
        </div>
      </header>

      {/* Three-column body */}
      <div className="flex-1 grid grid-cols-[240px_1fr_320px] gap-0 overflow-hidden">
        {/* Left: phase timeline */}
        <aside className="border-r border-white/5 p-4 overflow-y-auto">
          <p className="text-[10px] uppercase tracking-wider text-starlight-500 mb-3">
            Phases
          </p>
          <ol className="space-y-2">
            {phaseOrder.length === 0 && (
              <li className="text-xs text-starlight-500 italic">
                Waiting for first event...
              </li>
            )}
            {phaseOrder.map((phase, i) => {
              const info = PHASE_DISPLAY[phase] ?? { label: phase, icon: <Activity size={14} /> }
              const active = i === phaseOrder.length - 1 && status === 'running'
              return (
                <li
                  key={phase}
                  className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded ${
                    active
                      ? 'bg-primary-500/10 text-primary-300 border border-primary-500/30'
                      : 'text-starlight-300'
                  }`}
                >
                  <span className={active ? 'text-primary-400 animate-pulse' : 'text-starlight-500'}>
                    {info.icon}
                  </span>
                  <span className="flex-1 truncate">{info.label}</span>
                  {checkpoints[phase] && (
                    <span
                      className="text-[9px] font-mono text-accent-amber/80"
                      title={`phase sealed at commit ${checkpoints[phase]}`}
                    >
                      {checkpoints[phase].slice(0, 7)}
                    </span>
                  )}
                </li>
              )
            })}
          </ol>
        </aside>

        {/* Center: reasoning feed */}
        <main
          ref={logFeedRef}
          className="p-4 overflow-y-auto bg-midnight-600/40 font-mono"
        >
          <AnimatePresence initial={false}>
            {events.map(evt => (
              <motion.div
                key={evt.id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-2 text-xs leading-relaxed"
              >
                <span className="text-starlight-500 mr-2">
                  [{new Date(evt.timestamp).toISOString().slice(11, 19)}]
                </span>
                {evt.kind === 'scan_thinking' && (
                  <>
                    <span className="text-accent-cyan">think</span>
                    {evt.phase && (
                      <span className="text-starlight-500">.{evt.phase}</span>
                    )}
                    <span className="text-starlight-500">: </span>
                    <span className="text-starlight-200">{evt.text}</span>
                  </>
                )}
                {evt.kind === 'scan_observation' && (
                  <>
                    <span className="text-accent-amber">observe</span>
                    {evt.phase && (
                      <span className="text-starlight-500">.{evt.phase}</span>
                    )}
                    <span className="text-starlight-500">: </span>
                    <span className="text-starlight-200">{evt.observation}</span>
                  </>
                )}
                {evt.kind === 'scan_phase_change' && (
                  <>
                    <span className="text-primary-400">phase</span>
                    <span className="text-starlight-500">: </span>
                    <span className="text-starlight-300">{evt.phase ?? '(unknown)'}</span>
                  </>
                )}
                {evt.kind === 'scan_checkpoint' && (
                  <>
                    <span className="text-accent-amber">seal</span>
                    <span className="text-starlight-500">.{String(evt.data?.phase ?? '?')}: </span>
                    <span className="text-starlight-200 font-mono">
                      {String(evt.data?.short_hash ?? (evt.data?.commit_hash ? String(evt.data.commit_hash).slice(0, 12) : ''))}
                    </span>
                  </>
                )}
                {evt.kind === 'scan_queue_decision' && (
                  <>
                    <span className="text-accent-amber">queue</span>
                    <span className="text-starlight-500">.{String(evt.data?.cls ?? '?')}: </span>
                    <span className="text-starlight-200">
                      {evt.data?.should_exploit ? 'validate' : 'skip'} (
                      {String(evt.data?.vuln_count ?? 0)} vulns, {' '}
                      {String(evt.data?.externally_exploitable_count ?? 0)} externally reachable)
                    </span>
                  </>
                )}
                {evt.kind === 'scan_started' && (
                  <>
                    <span className="text-status-success">start</span>
                    <span className="text-starlight-500">: </span>
                    <span className="text-starlight-200">scan initiated</span>
                  </>
                )}
                {evt.kind === 'scan_complete' && (
                  <>
                    <span className="text-status-success">done</span>
                    <span className="text-starlight-500">: </span>
                    <span className="text-starlight-200">
                      {(evt.data?.findings_count as number) ?? 0} findings,{' '}
                      ${((evt.data?.cost_usd as number) ?? 0).toFixed(2)}
                    </span>
                  </>
                )}
                {evt.kind === 'scan_failed' && (
                  <>
                    <span className="text-status-error">fail</span>
                    <span className="text-starlight-500">: </span>
                    <span className="text-status-error">{(evt.data?.reason as string) ?? 'failed'}</span>
                  </>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          {error && (
            <p className="mt-2 text-xs text-status-error">{error}</p>
          )}
        </main>

        {/* Right: findings as they arrive */}
        <aside className="border-l border-white/5 p-4 overflow-y-auto">
          {/* Proof-of-impact queue gate decisions (Shannon Pattern 1).
              Shows per-OWASP-class whether the validation agent would
              dispatch or skip. Collapsed when empty. */}
          {Object.keys(queueDecisions).length > 0 && (
            <div className="mb-4">
              <p className="text-[10px] uppercase tracking-wider text-starlight-500 mb-2">
                Validation gate
              </p>
              <div className="space-y-1">
                {Object.values(queueDecisions).map(d => (
                  <div
                    key={d.cls}
                    className={`flex items-center justify-between text-[11px] px-2 py-1 rounded ${
                      d.should_exploit
                        ? 'bg-accent-amber/10 text-accent-amber border border-accent-amber/25'
                        : 'bg-status-success/5 text-status-success border border-status-success/20'
                    }`}
                    title={d.reason}
                  >
                    <span className="font-mono">{d.cls}</span>
                    <span>
                      {d.should_exploit
                        ? `validate (${d.externally_exploitable_count}/${d.vuln_count})`
                        : (d.vuln_count === 0 ? 'clean' : `skip (${d.vuln_count})`)
                      }
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between mb-3">
            <p className="text-[10px] uppercase tracking-wider text-starlight-500">
              Findings
            </p>
            {report && (
              <span className="text-[10px] text-starlight-400">
                {report.findings.length} total
              </span>
            )}
          </div>
          {!report && (
            <p className="text-xs text-starlight-500 italic">
              Findings will appear here once the scan's Zero-FP gate
              admits them.
            </p>
          )}
          {report && report.findings.length === 0 && (
            <div className="p-3 rounded-lg bg-status-success/5 border border-status-success/20">
              <p className="text-xs text-starlight-300">
                <CheckCircle2 size={12} className="inline mr-1 text-status-success" />
                Clean sweep. No findings above detection threshold.
              </p>
            </div>
          )}
          {report?.findings.map((f, i) => (
            <motion.div
              key={f.id ?? i}
              initial={{ opacity: 0, x: 4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className="mb-2 p-3 rounded-lg bg-midnight-200/60 border border-white/5"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold border ${SEVERITY_COLORS[f.severity]}`}>
                  {f.severity}
                </span>
                <p className="text-xs font-medium text-starlight-100 truncate">
                  {f.title}
                </p>
              </div>
              {f.location && (
                <p className="text-[10px] text-starlight-500 font-mono truncate mb-1">
                  {f.location}
                </p>
              )}
              {f.poc_artifact && (
                <p className="text-[10px] text-primary-400 flex items-center gap-1">
                  <Shield size={10} />
                  PoC: {f.poc_artifact.kind} ({f.poc_artifact.sha256.slice(0, 10)}...)
                </p>
              )}
              {f.exploit_path && (
                <p className="text-[10px] text-accent-amber flex items-center gap-1 mt-1">
                  <Crosshair size={10} />
                  Proof-of-impact path attached
                </p>
              )}
            </motion.div>
          ))}
        </aside>
      </div>
    </div>
  )
}
