/**
 * useGatedInterval - run a callback on an interval that PAUSES while the
 * browser tab is hidden, and fires once immediately when the tab becomes
 * visible again so the user never stares at stale data.
 *
 * This codifies the document.hidden visibility-gate pattern that was
 * previously hand-rolled in DashboardPage, TasksPage and
 * GovernanceApprovalsPage, and extends it to the department hooks and the
 * inline approval banner. Pausing background tabs is the single biggest
 * lever against the dashboard-mount polling storm: N hidden tabs stop
 * hitting the backend entirely instead of each firing every few seconds.
 *
 * The callback is held in a ref so passing a fresh closure every render
 * does NOT tear down and rebuild the interval; only `enabled` and
 * `intervalMs` changes resubscribe.
 */
import { useEffect, useRef } from 'react'

interface UseGatedIntervalOptions {
  /** When false, no interval is scheduled (e.g. a required id is missing). */
  enabled?: boolean
  /** Fire the callback immediately when the tab regains visibility. Default true. */
  runOnReshow?: boolean
}

export function useGatedInterval(
  callback: () => void | Promise<void>,
  intervalMs: number,
  { enabled = true, runOnReshow = true }: UseGatedIntervalOptions = {},
): void {
  const callbackRef = useRef(callback)
  // Keep the ref pointing at the latest callback, updated AFTER commit (not
  // during render) so we satisfy react-hooks/refs while still invoking the
  // freshest callback from the interval without re-subscribing it.
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    if (!enabled) return

    let id: ReturnType<typeof setInterval> | null = null
    const tick = () => {
      void callbackRef.current()
    }
    const start = () => {
      if (id === null) id = setInterval(tick, intervalMs)
    }
    const stop = () => {
      if (id !== null) {
        clearInterval(id)
        id = null
      }
    }

    // Only poll while the tab is visible.
    if (!document.hidden) start()

    const onVisibility = () => {
      if (document.hidden) {
        stop()
      } else {
        if (runOnReshow) tick()
        start()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      stop()
    }
  }, [enabled, intervalMs, runOnReshow])
}
