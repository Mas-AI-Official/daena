/**
 * SelfDiagnosticCard -- Daena's runtime self-awareness widget.
 *
 * Sprint-6 PR-7: surfaces the GET /api/v1/system/self-diagnostic
 * payload as a compact card showing overall status, the per-check
 * grid, and the top 3 recommended actions.
 *
 * Honest UX:
 *   - Polls once on mount + on a Refresh button click. Not a live
 *     stream (the diagnostic is not free; rapid polling would burn
 *     budget on the local model probes).
 *   - Per-check status pills carry only the status word + the
 *     terse `detail` string -- never a secret, never an env value
 *     (the backend already enforces this; the frontend is consistent).
 *   - Boundary notice from the payload is rendered verbatim so the
 *     UI can never drift from the backend's safety statement.
 */

import { useEffect, useState } from 'react'
import {
  AlertTriangle, CheckCircle2, Loader2, RefreshCw, ShieldCheck,
} from 'lucide-react'

import { api } from '@/lib/api'


type Status = 'healthy' | 'warning' | 'blocked'

interface CheckEntry {
  status: Status
  detail: string
  [key: string]: unknown
}

interface DiagnosticPayload {
  overall_status: Status
  timestamp: string
  elapsed_ms: number
  checks: Record<string, CheckEntry>
  recommended_actions: string[]
  boundary_notice: string
}

const STATUS_TONE: Record<Status, { bg: string; text: string; border: string; dot: string }> = {
  healthy: {
    bg: 'bg-emerald-500/[0.06]',
    text: 'text-emerald-200',
    border: 'border-emerald-500/30',
    dot: 'bg-emerald-400',
  },
  warning: {
    bg: 'bg-amber-500/[0.06]',
    text: 'text-amber-200',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400',
  },
  blocked: {
    bg: 'bg-rose-500/[0.06]',
    text: 'text-rose-200',
    border: 'border-rose-500/30',
    dot: 'bg-rose-400',
  },
}

function humanizeKey(k: string): string {
  return k.replace(/_/g, ' ')
}

export function SelfDiagnosticCard() {
  const [data, setData] = useState<DiagnosticPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function fetchOnce() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get<{ data: DiagnosticPayload }>(
        '/system/self-diagnostic',
      )
      setData(res.data?.data ?? null)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'self-diagnostic failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchOnce()
  }, [])

  if (loading && !data) {
    return (
      <div className="rounded-xl border border-white/5 bg-midnight-400/30 p-4 text-[12px] text-starlight-400">
        <Loader2 size={12} className="mr-1 inline animate-spin" />
        Daena is checking her own runtime...
      </div>
    )
  }
  if (error && !data) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/[0.05] p-4 text-[12px] text-rose-200">
        Self-diagnostic call failed: {error}
      </div>
    )
  }
  if (!data) return null

  const tone = STATUS_TONE[data.overall_status]
  return (
    <section
      data-testid="self-diagnostic-card"
      className={`rounded-xl border ${tone.border} ${tone.bg} p-4`}
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] text-accent-cyan">
            <ShieldCheck size={12} className="mr-1 inline" />
            Daena self diagnostic
          </p>
          <h3 className={`mt-1 text-base font-semibold ${tone.text}`}>
            {data.overall_status === 'healthy' && 'Healthy'}
            {data.overall_status === 'warning' && 'Warning'}
            {data.overall_status === 'blocked' && 'Blocked'}
            <span className="ml-2 text-[11px] font-normal text-starlight-500">
              checked in {data.elapsed_ms}ms
            </span>
          </h3>
        </div>
        <button
          onClick={() => void fetchOnce()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-starlight-200 hover:bg-white/10 disabled:opacity-50"
        >
          {loading ? (
            <Loader2 size={11} className="animate-spin" />
          ) : (
            <RefreshCw size={11} />
          )}
          Refresh
        </button>
      </header>

      {/* Per-check grid */}
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        {Object.entries(data.checks).map(([key, entry]) => {
          const t = STATUS_TONE[entry.status]
          return (
            <div
              key={key}
              className={`rounded-md border ${t.border} ${t.bg} px-2.5 py-1.5`}
              title={entry.detail}
            >
              <div className="flex items-center gap-1.5">
                <span className={`inline-block h-1.5 w-1.5 rounded-full ${t.dot}`} />
                <p className={`text-[10px] uppercase tracking-wider ${t.text}`}>
                  {humanizeKey(key)}
                </p>
              </div>
              <p className="mt-0.5 truncate text-[10px] text-starlight-400">
                {entry.detail}
              </p>
            </div>
          )
        })}
      </div>

      {/* Top recommended actions */}
      <div className="mt-3">
        <p className="text-[10px] uppercase tracking-wider text-starlight-500">
          Recommended next actions
        </p>
        <ul className="mt-1 space-y-1">
          {data.recommended_actions.slice(0, 5).map((rec, i) => (
            <li
              key={i}
              className="flex items-start gap-1.5 text-[11px] text-starlight-300"
            >
              {data.overall_status === 'healthy' ? (
                <CheckCircle2 size={11} className="mt-0.5 shrink-0 text-emerald-300" />
              ) : (
                <AlertTriangle size={11} className="mt-0.5 shrink-0 text-amber-300" />
              )}
              <span>{rec}</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="mt-3 text-[10px] italic text-starlight-500">
        {data.boundary_notice}
      </p>
    </section>
  )
}

export default SelfDiagnosticCard
