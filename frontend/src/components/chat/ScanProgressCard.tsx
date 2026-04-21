/**
 * ScanProgressCard -- inline security scan progress under an assistant
 * message. Opens its own SSE connection to the workflow events URL and
 * renders phase transitions + final findings summary with severity
 * badges.
 *
 * Lifecycle:
 *   1. Mounted when a `scan_dispatched` governance event fires.
 *   2. Opens EventSource on `eventsUrl`.
 *   3. Updates local state as scan_phase_change / scan_complete /
 *      scan_failed events arrive.
 *   4. Closes EventSource on scan_complete, scan_failed, or unmount.
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { ShieldAlert, CheckCircle2, XCircle, Loader2 } from 'lucide-react'

export interface ScanProgressCardProps {
  jobId: string
  target: string
  targetKind: string
  tier: string
  eventsUrl: string
  onDismiss?: () => void
}

type Phase =
  | 'queued'
  | 'profiling'
  | 'scanning'
  | 'analyzing'
  | 'reporting'
  | 'complete'
  | 'failed'

interface ScanSummary {
  findings_count?: number
  critical?: number
  high?: number
  cost_usd?: number
  duration_secs?: number
  reason?: string
}

const PHASE_LABEL: Record<Phase, string> = {
  queued: 'Queued',
  profiling: 'Profiling target',
  scanning: 'Scanning',
  analyzing: 'Analyzing findings',
  reporting: 'Building report',
  complete: 'Complete',
  failed: 'Failed',
}

export function ScanProgressCard({
  jobId,
  target,
  targetKind,
  tier,
  eventsUrl,
  onDismiss,
}: ScanProgressCardProps) {
  const [phase, setPhase] = useState<Phase>('queued')
  const [summary, setSummary] = useState<ScanSummary | null>(null)

  useEffect(() => {
    if (!eventsUrl) return
    const token = localStorage.getItem('daena_token')
    // EventSource does not support custom headers; if the events
    // endpoint is behind auth we piggy-back on cookie-based auth that
    // the rest of the app already uses via `withCredentials: true`.
    const url = token
      ? `${eventsUrl}?token=${encodeURIComponent(token)}`
      : eventsUrl
    const es = new EventSource(url, { withCredentials: true })

    const handle = (ev: MessageEvent) => {
      try {
        const envelope = JSON.parse(ev.data)
        const type = envelope.type as string
        const data = (envelope.data || {}) as Record<string, unknown>

        if (type === 'scan_phase_change') {
          const p = String(data.phase || 'scanning') as Phase
          setPhase(p)
        } else if (type === 'scan_complete') {
          setPhase('complete')
          setSummary({
            findings_count: Number(data.findings_count ?? 0),
            critical: Number(data.critical ?? 0),
            high: Number(data.high ?? 0),
            cost_usd: Number(data.cost_usd ?? 0),
            duration_secs: Number(data.duration_secs ?? 0),
          })
          es.close()
        } else if (type === 'scan_failed') {
          setPhase('failed')
          setSummary({ reason: String(data.reason || 'Scan failed.') })
          es.close()
        }
      } catch {
        // Malformed event; ignore.
      }
    }

    es.addEventListener('scan_started', handle)
    es.addEventListener('scan_phase_change', handle)
    es.addEventListener('scan_complete', handle)
    es.addEventListener('scan_failed', handle)
    es.onmessage = handle

    return () => es.close()
  }, [eventsUrl])

  const isRunning = phase !== 'complete' && phase !== 'failed'
  const phaseIcon = phase === 'complete'
    ? <CheckCircle2 size={16} className="text-status-success" />
    : phase === 'failed'
      ? <XCircle size={16} className="text-status-error" />
      : <Loader2 size={16} className="text-accent-amber animate-spin" />

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="my-3 rounded-xl border border-accent-amber/30 bg-accent-amber/5 p-4 shadow-sm"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <ShieldAlert size={16} className="text-accent-amber" />
          <span className="text-sm font-semibold text-starlight-100">
            Security scan
          </span>
          <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-midnight-400/60 text-starlight-300">
            {tier}
          </span>
        </div>
        {onDismiss && !isRunning && (
          <button
            onClick={onDismiss}
            className="text-[10px] text-starlight-500 hover:text-starlight-200 cursor-pointer"
          >
            Dismiss
          </button>
        )}
      </div>

      <div className="text-xs text-starlight-400 mb-2 font-mono truncate">
        {targetKind}: {target}
      </div>

      <div className="flex items-center gap-2 mb-2">
        {phaseIcon}
        <span className="text-xs text-starlight-200">
          {PHASE_LABEL[phase]}
        </span>
      </div>

      {summary && phase === 'complete' && (
        <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
          <div className="flex items-center gap-1">
            <span className="text-starlight-500">Findings:</span>
            <span className="text-starlight-100 font-semibold">
              {summary.findings_count ?? 0}
            </span>
          </div>
          {(summary.critical ?? 0) > 0 && (
            <div className="flex items-center gap-1">
              <span className="text-status-error">Critical:</span>
              <span className="text-status-error font-semibold">
                {summary.critical}
              </span>
            </div>
          )}
          {(summary.high ?? 0) > 0 && (
            <div className="flex items-center gap-1">
              <span className="text-accent-amber">High:</span>
              <span className="text-accent-amber font-semibold">
                {summary.high}
              </span>
            </div>
          )}
          <div className="flex items-center gap-1">
            <span className="text-starlight-500">Duration:</span>
            <span className="text-starlight-300">
              {summary.duration_secs?.toFixed(1)}s
            </span>
          </div>
        </div>
      )}

      {summary && phase === 'failed' && (
        <div className="mt-2 text-[11px] text-status-error">
          {summary.reason}
        </div>
      )}

      <div className="mt-2 text-[10px] text-starlight-500 font-mono">
        Job {jobId}
      </div>
    </motion.div>
  )
}
