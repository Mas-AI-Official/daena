import { useEffect, useState } from 'react'
import { useGraphStore } from '@/stores/graphStore'

/**
 * Honest freshness indicator for the live Brain (Rule 17). Two truthful states:
 *  - "Live" (emerald) ONLY while a graph SSE stream is genuinely connected
 *    (`live === true`); the brain updates on push, so "updated Ns ago" tracks
 *    the last real change.
 *  - "Auto-refresh" (teal) when there is no stream and the projection is being
 *    POLLED on an interval -- it never claims "Live" while really polling.
 * In both states a climbing "updated Ns ago" with an amber dot truthfully
 * signals a stalled loop. Hidden under the grounded fallback (the amber
 * architecture banner owns that state) and while the initial load chip shows.
 */
function relTime(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 3) return 'just now'
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  return `${m}m ago`
}

export default function LiveStatusPill() {
  const lastUpdated = useGraphStore((s) => s.lastUpdated)
  const usingFallback = useGraphStore((s) => s.usingFallback)
  const loading = useGraphStore((s) => s.loading)
  const live = useGraphStore((s) => s.live)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  if (loading || usingFallback || lastUpdated === null) return null
  const age = now - lastUpdated
  const stale = age > 30000
  // Dot: amber when stale (loop stalled), else emerald while truly streaming,
  // else teal for the honest polling state. Label flips with the real `live`
  // flag, never asserting "Live" while we are actually on the poll fallback.
  const dotClass = stale
    ? 'bg-amber-400'
    : live
      ? 'bg-emerald-400 animate-pulse'
      : 'bg-teal-400 animate-pulse'
  return (
    <div className="pointer-events-none absolute left-4 top-4 z-20 flex items-center gap-2 rounded-full border border-white/10 bg-black/60 px-3 py-1 text-xs text-white/70 backdrop-blur">
      <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} aria-hidden />
      <span>
        {live ? 'Live' : 'Auto-refresh'} - updated {relTime(age)}
      </span>
    </div>
  )
}
