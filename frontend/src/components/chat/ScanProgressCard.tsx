/**
 * ScanProgressCard -- inline security scan progress under an assistant
 * message. Subscribes to the workflow events URL via useResilientSSE
 * and renders phase transitions + final findings summary with severity
 * badges.
 *
 * Lifecycle:
 *   1. Mounted when a `scan_dispatched` governance event fires.
 *   2. Opens an authenticated fetch-based SSE stream on `eventsUrl`.
 *      (K-1 hardening, 2026-06-01: the route now requires a bearer
 *      access token; native EventSource cannot send headers, so we
 *      use useResilientSSE which forwards Authorization: Bearer.)
 *   3. Updates local state as scan_phase_change / scan_complete /
 *      scan_failed events arrive.
 *   4. Tears down on scan_complete, scan_failed, or unmount.
 */
import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { ShieldAlert, CheckCircle2, XCircle, Loader2, ExternalLink } from 'lucide-react'
import { useResilientSSE } from '../../lib/sse'

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
  // Track whether we've auto-popped the walkthrough window once for
  // this card so remounts do not spawn a fresh window on every event.
  const autoOpenedRef = useRef(false)

  // Auto-open the Offensive walkthrough window for T5 scans. Defers
  // until after first render so the popup is associated with a user
  // gesture (the chat send) chrome-wide popup blockers usually
  // allow. For non-T5 tiers, the button below is the only path.
  useEffect(() => {
    if (autoOpenedRef.current) return
    if (tier !== 'EVILBOB') return
    autoOpenedRef.current = true
    try {
      window.open(
        `/scan/walkthrough/${jobId}`,
        `daena-scan-${jobId}`,
        'width=1280,height=820,noopener=no',
      )
    } catch {
      // Popup blocked; the manual button below remains available.
    }
  }, [jobId, tier])

  // Terminal-event flag so we can tear the stream down once the scan
  // resolves (useResilientSSE auto-reconnects otherwise).
  const [terminated, setTerminated] = useState(false)

  // K-1 hardening (2026-06-01): the events route now requires a bearer
  // access token. Native EventSource cannot set Authorization headers,
  // and the prior workaround of putting the token in the query string
  // (?token=...) leaked the bearer to browser history, server access
  // logs, Referer headers, and DevTools network panel during screen
  // sharing. useResilientSSE uses fetch with a real Bearer header.
  useResilientSSE({
    url: terminated || !eventsUrl ? '' : eventsUrl,
    eventTypes: [
      'scan_started',
      'scan_phase_change',
      'scan_complete',
      'scan_failed',
    ],
    onEvent: (ev) => {
      // The backend emits envelope = {"type": str, "data": {...}}. Prefer
      // envelope.type, fall back to the SSE event-name from the frame.
      const envelope = (ev.data ?? {}) as {
        type?: string
        data?: Record<string, unknown>
      }
      const type = envelope.type || ev.type
      const data = envelope.data ?? {}

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
        setTerminated(true)
      } else if (type === 'scan_failed') {
        setPhase('failed')
        setSummary({ reason: String(data.reason || 'Scan failed.') })
        setTerminated(true)
      }
    },
  })

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
            {tier === 'EVILBOB' ? 'Founder' : tier}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => window.open(
              `/scan/walkthrough/${jobId}`,
              `daena-scan-${jobId}`,
              'width=1280,height=820',
            )}
            className="flex items-center gap-1 text-[10px] text-accent-amber hover:text-accent-amber/80 cursor-pointer"
            title="Open the full walkthrough window"
          >
            <ExternalLink size={10} />
            Walkthrough
          </button>
          {onDismiss && !isRunning && (
            <button
              onClick={onDismiss}
              className="text-[10px] text-starlight-500 hover:text-starlight-200 cursor-pointer"
            >
              Dismiss
            </button>
          )}
        </div>
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
