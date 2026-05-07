/**
 * Error store -- central, in-memory ledger of recent API/network errors.
 *
 * Why this exists:
 *   The previous shape of api.ts silently swallowed 5xx responses on a
 *   wide allowlist of polling endpoints (/heartbeat/, /governance/approvals/,
 *   /runtimes/, /mcp/, /skills/, ...). When backends fell over, the user
 *   saw nothing. The app FELT broken even though no toast had ever fired.
 *
 *   This store is the honest version. Every error from the axios interceptor
 *   lands here regardless of whether it produced a toast. The
 *   ConnectionStatusIndicator reads from it and shows a discreet dot in
 *   the navbar so the operator always has a way to ask "is something
 *   actually wrong right now?" without diving into devtools.
 *
 * Shape:
 *   - recentErrors:  rolling window of the last 50 entries (FIFO).
 *   - lastEndpointFailure: timestamp keyed by url-prefix (first segment
 *     under /api/v1, e.g. "/runtimes/" or "/heartbeat/"). Used by the
 *     status indicator to compute degraded vs down per endpoint family.
 *
 * The store is intentionally non-persistent. On page reload we start
 * clean -- a stale error from a previous session shouldn't light up the
 * navbar.
 */
import { create } from 'zustand'

// ── Types ──

export type EndpointStatus = 'ok' | 'degraded' | 'down'

export interface ErrorEntry {
  id: string
  /** Endpoint family prefix (e.g. "/runtimes/", "/heartbeat/"). Used as the bucket key. */
  prefix: string
  /** Full request url as seen by axios (path under /api/v1). */
  url: string
  /** HTTP status code, or 0 for network/timeout errors. */
  status: number
  /** Categorization of the underlying axios error (server, network, timeout, client). */
  category: 'server' | 'network' | 'timeout' | 'client'
  /** Backend error code if the response carried one. */
  code?: string
  /** Short human message (we don't store the full body to keep this light). */
  message: string
  /** Wall-clock timestamp -- ms since epoch. */
  timestamp: number
  /** Whether the interceptor decided to suppress the toast for this entry. */
  silent: boolean
}

interface ErrorState {
  recentErrors: ErrorEntry[]
  lastEndpointFailure: Record<string, number>

  // Actions
  recordError: (entry: Omit<ErrorEntry, 'id' | 'timestamp'>) => void
  clearErrors: () => void
  /**
   * Health for a given endpoint prefix.
   *   ok         -- no failures in the last 60s
   *   degraded   -- 1-2 failures in the last 60s
   *   down       -- 3+ failures in the last 60s
   */
  getEndpointStatus: (prefix: string) => EndpointStatus
}

const MAX_RECENT = 50
const WINDOW_MS = 60_000

let _counter = 0

export const useErrorStore = create<ErrorState>((set, get) => ({
  recentErrors: [],
  lastEndpointFailure: {},

  recordError: (entry) => {
    const id = `err-${++_counter}-${Date.now()}`
    const timestamp = Date.now()
    const full: ErrorEntry = { ...entry, id, timestamp }

    set((s) => {
      const next = [...s.recentErrors, full]
      // FIFO trim -- keep newest MAX_RECENT.
      const trimmed = next.length > MAX_RECENT ? next.slice(next.length - MAX_RECENT) : next
      return {
        recentErrors: trimmed,
        lastEndpointFailure: {
          ...s.lastEndpointFailure,
          [entry.prefix]: timestamp,
        },
      }
    })
  },

  clearErrors: () => set({ recentErrors: [], lastEndpointFailure: {} }),

  getEndpointStatus: (prefix) => {
    const cutoff = Date.now() - WINDOW_MS
    const recent = get().recentErrors.filter(
      (e) => e.prefix === prefix && e.timestamp >= cutoff,
    )
    if (recent.length === 0) return 'ok'
    if (recent.length >= 3) return 'down'
    return 'degraded'
  },
}))

// ── Helpers ──

/**
 * Extract a stable bucket prefix from an axios request url.
 * "/runtimes/abc/test" -> "/runtimes/"
 * "/heartbeat/status"  -> "/heartbeat/"
 * "/connections/mcp-registry" -> "/connections/"
 *
 * Uses only the first path segment after /api/v1. Adds trailing slash so
 * lookups against `silentPrefixes` (which all end with "/") line up.
 */
export function extractEndpointPrefix(url: string): string {
  if (!url) return '/'
  // Strip query string + leading /api/v1 if present.
  const pathOnly = url.split('?')[0].replace(/^\/api\/v1/, '')
  const trimmed = pathOnly.startsWith('/') ? pathOnly : `/${pathOnly}`
  const parts = trimmed.split('/').filter(Boolean)
  if (parts.length === 0) return '/'
  return `/${parts[0]}/`
}

/**
 * Pure helper -- compute "ok" / "degraded" / "down" across an arbitrary set
 * of recent errors. Useful for tests + for the indicator that wants to
 * roll all known endpoints into one summary dot.
 */
export function summarizeStatus(errors: ErrorEntry[]): EndpointStatus {
  if (errors.length === 0) return 'ok'
  if (errors.length >= 3) return 'down'
  return 'degraded'
}
