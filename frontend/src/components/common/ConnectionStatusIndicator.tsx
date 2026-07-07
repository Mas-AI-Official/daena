/**
 * ConnectionStatusIndicator -- discrete navbar dot that surfaces backend
 * health based on whatever the axios interceptor has pushed into the
 * useErrorStore.
 *
 * Visibility rule (read top to bottom, first match wins):
 *   - Any endpoint family with 3+ failures in 60s -> red dot ("down").
 *   - Any endpoint family with 1-2 failures in 60s -> yellow dot ("degraded").
 *   - Otherwise -> hidden.
 *
 * Click toggles a small popover listing each affected endpoint family
 * with the latest error message + code, plus two buttons:
 *   - Dismiss: clears the error store. Useful after the operator has
 *     read the failures and the backend has come back.
 *   - Retry pending fetches: emits a window CustomEvent so any active
 *     poll hook (mcp-registry, runtime-registry, heartbeat, ...) can
 *     re-run without waiting for the next interval. Hooks listen for
 *     "daena:retry-pending" and call their refresh callback.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, AlertCircle, X, RefreshCw } from 'lucide-react'
import { useErrorStore, type ErrorEntry } from '@/stores/errorStore'

const WINDOW_MS = 60_000

interface PrefixSummary {
  prefix: string
  status: 'degraded' | 'down'
  count: number
  latest: ErrorEntry
}

function summarizePrefixes(errors: ErrorEntry[]): PrefixSummary[] {
  const cutoff = Date.now() - WINDOW_MS
  const recent = errors.filter((e) => e.timestamp >= cutoff)
  const grouped = new Map<string, ErrorEntry[]>()
  for (const e of recent) {
    if (!grouped.has(e.prefix)) grouped.set(e.prefix, [])
    grouped.get(e.prefix)!.push(e)
  }
  const out: PrefixSummary[] = []
  for (const [prefix, list] of grouped.entries()) {
    if (list.length === 0) continue
    const latest = list.reduce((a, b) => (a.timestamp > b.timestamp ? a : b))
    out.push({
      prefix,
      status: list.length >= 3 ? 'down' : 'degraded',
      count: list.length,
      latest,
    })
  }
  // Sort: down first, then degraded, then most recent first.
  out.sort((a, b) => {
    if (a.status !== b.status) return a.status === 'down' ? -1 : 1
    return b.latest.timestamp - a.latest.timestamp
  })
  return out
}

export function ConnectionStatusIndicator() {
  const errors = useErrorStore((s) => s.recentErrors)
  const clearErrors = useErrorStore((s) => s.clearErrors)
  const [open, setOpen] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)
  // Re-render every 15s so the 60-second window slides as time passes,
  // even when no new errors arrive. Without this the indicator could
  // stay red after the backend recovered and we'd just be waiting on
  // the next failure to re-evaluate.
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 15_000)
    return () => clearInterval(id)
  }, [])

  // Outside-click closes the popover.
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const summaries = useMemo(() => summarizePrefixes(errors), [errors])
  const overall: 'ok' | 'degraded' | 'down' = useMemo(() => {
    if (summaries.some((s) => s.status === 'down')) return 'down'
    if (summaries.length > 0) return 'degraded'
    return 'ok'
  }, [summaries])

  const isDown = overall === 'down'
  const dotClass = isDown ? 'bg-status-error' : 'bg-status-warning'
  const Icon = isDown ? AlertCircle : AlertTriangle
  const tooltip = isDown
    ? `${summaries.length} endpoint${summaries.length === 1 ? '' : 's'} unreachable`
    : `${summaries.length} endpoint${summaries.length === 1 ? '' : 's'} degraded`

  const handleRetry = () => {
    window.dispatchEvent(new CustomEvent('daena:retry-pending'))
  }

  const handleDismiss = () => {
    clearErrors()
    setOpen(false)
  }

  return (
    <div className="relative" ref={popoverRef}>
      {/* Persistent polite live region -- gives screen-reader users the same
          passive backend-health signal the dot gives sighted users. Stays
          mounted even when healthy (this component no longer early-returns
          null) so a status transition announces on change; polite + atomic
          reads the short summary once without interrupting the current task.
          Honors the deliberately-discreet design: a background poll failure
          should not assertively interrupt, only surface quietly. */}
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {overall === 'ok' ? '' : tooltip}
      </span>
      {overall !== 'ok' && (
        <>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative flex items-center justify-center p-1.5 rounded-lg
                   text-starlight-400 hover:text-starlight-100 hover:bg-white/5
                   transition-colors cursor-pointer"
        aria-label={tooltip}
        title={tooltip}
      >
        <Icon size={16} className={isDown ? 'text-status-error' : 'text-status-warning'} />
        <span
          className={`absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full ${dotClass}
                      ${isDown ? 'animate-pulse' : ''}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.12 }}
            className="absolute top-full right-0 mt-2 w-80 z-50
                       bg-midnight-400/95 backdrop-blur-md border border-white/10
                       rounded-xl shadow-xl overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
              <div className="flex items-center gap-2">
                <Icon
                  size={14}
                  className={isDown ? 'text-status-error' : 'text-status-warning'}
                />
                <h3 className="text-xs font-display font-semibold text-starlight-200">
                  Backend health
                </h3>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="p-0.5 text-starlight-500 hover:text-starlight-200 cursor-pointer"
                aria-label="Close"
              >
                <X size={12} />
              </button>
            </div>

            <div className="max-h-[280px] overflow-y-auto">
              {summaries.map((s) => (
                <div
                  key={s.prefix}
                  className="flex items-start gap-3 px-4 py-3 border-b border-white/5 last:border-b-0"
                >
                  <div
                    className={`mt-1 w-2 h-2 rounded-full shrink-0 ${
                      s.status === 'down' ? 'bg-status-error' : 'bg-status-warning'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-starlight-200 truncate">
                        {s.prefix}
                      </span>
                      <span className="text-[10px] text-starlight-500 shrink-0">
                        {s.count} fail{s.count === 1 ? '' : 's'}/60s
                      </span>
                    </div>
                    <p className="text-[11px] text-starlight-500 mt-0.5 truncate">
                      {s.latest.category} {s.latest.status > 0 ? `${s.latest.status}` : ''}
                      {s.latest.code ? ` -- ${s.latest.code}` : ''}
                    </p>
                    <p className="text-[10px] text-starlight-600 mt-0.5 truncate">
                      {s.latest.url}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-end gap-2 px-3 py-2 border-t border-white/5 bg-midnight-300/40">
              <button
                onClick={handleRetry}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px]
                           text-starlight-300 hover:text-starlight-100 hover:bg-white/5
                           transition-colors cursor-pointer"
              >
                <RefreshCw size={11} />
                Retry pending fetches
              </button>
              <button
                onClick={handleDismiss}
                className="px-2 py-1 rounded-md text-[11px]
                           text-starlight-300 hover:text-starlight-100 hover:bg-white/5
                           transition-colors cursor-pointer"
              >
                Dismiss
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
        </>
      )}
    </div>
  )
}

export default ConnectionStatusIndicator
