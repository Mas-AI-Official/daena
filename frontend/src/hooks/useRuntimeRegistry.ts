/**
 * useRuntimeRegistry -- polls the live runtime registry.
 *
 * Backed by GET /api/v1/runtimes. The backend responds with the shape
 *   { success: true, data: { runtimes: RuntimeData[], primary_runtime: string|null,
 *                            cloud_mode: boolean, api_providers: [...] } }
 * where each RuntimeData carries: runtime_id, display_name, installed,
 * status, subscription. The hook adapts that into the leaner RuntimeInfo
 * shape used by the Mind Control surfaces.
 *
 * Behaviour:
 *  - First fetch happens immediately on mount.
 *  - Subsequent fetches every 30s while mounted.
 *  - `refresh()` triggers an immediate re-fetch.
 *  - The hook listens for the global "daena:retry-pending" CustomEvent
 *    (emitted by ConnectionStatusIndicator's "Retry pending fetches"
 *    button) so the operator can force a re-poll without waiting.
 *  - Errors are surfaced via the `error` return value AND recorded in
 *    useErrorStore by the api.ts interceptor (silent by default for
 *    /runtimes/, but still visible to the navbar indicator).
 *
 * Pattern mirrors useMcpRegistry.ts -- mounted ref, setTimeout poll
 * chain, cleanup on unmount, refresh callback.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import type { RuntimeInfo, RuntimeStatus } from '@/types/api'

// ── Backend response types ──

interface BackendRuntimeData {
  runtime_id: string
  display_name: string
  installed: boolean
  status: string
  subscription: {
    is_authenticated: boolean
    plan_name: string | null
    user_display: string | null
    [key: string]: unknown
  } | null
  capabilities?: Record<string, number>
  cost_per_1k_tokens?: number
  is_free?: boolean
}

interface BackendResponse {
  success: boolean
  data: {
    runtimes: BackendRuntimeData[]
    primary_runtime?: string | null
    cloud_mode?: boolean
  }
}

const POLL_MS = 30_000

/** Map the backend's free-form `status` string to the RuntimeStatus union. */
function normalizeStatus(raw: string, installed: boolean): RuntimeStatus {
  const s = (raw || '').toLowerCase()
  if (!installed) return 'not_installed'
  if (s.includes('rate') && s.includes('limit')) return 'rate_limited'
  if (s.includes('error')) return 'error'
  if (s.includes('online') || s.includes('ready') || s.includes('connected')) return 'online'
  if (s.includes('offline') || s.includes('disconnected')) return 'offline'
  // Default for installed-but-unknown: treat as offline (the Mind
  // Control surfaces filter on "online", so an unknown runtime stays
  // hidden, which is the safer call than mis-labelling it online).
  return 'offline'
}

/** Adapt one backend RuntimeData row into the lean RuntimeInfo shape. */
function adapt(row: BackendRuntimeData): RuntimeInfo {
  return {
    id: row.runtime_id,
    name: row.display_name,
    status: normalizeStatus(row.status, row.installed),
    capabilities: row.capabilities ?? {},
    cost_per_1k_tokens: row.cost_per_1k_tokens ?? 0,
    is_free: row.is_free ?? row.runtime_id === 'ollama',
  }
}

interface UseRuntimeRegistryResult {
  runtimes: RuntimeInfo[]
  loading: boolean
  error: string | null
  refresh: () => void
}

export function useRuntimeRegistry(): UseRuntimeRegistryResult {
  const [runtimes, setRuntimes] = useState<RuntimeInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mounted = useRef(true)

  const fetchOnce = useCallback(async () => {
    try {
      const res = await api.get<BackendResponse>('/runtimes')
      if (!mounted.current) return
      const rows = res.data?.data?.runtimes ?? []
      setRuntimes(rows.map(adapt))
      setError(null)
    } catch (err: unknown) {
      if (!mounted.current) return
      setError(err instanceof Error ? err.message : 'unknown error')
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  const refresh = useCallback(() => {
    void fetchOnce()
  }, [fetchOnce])

  useEffect(() => {
    mounted.current = true
    void fetchOnce()
    const tick = () => {
      void fetchOnce()
      pollRef.current = setTimeout(tick, POLL_MS)
    }
    pollRef.current = setTimeout(tick, POLL_MS)

    // Operator-triggered retry from the ConnectionStatusIndicator
    // popover. We call refresh() rather than reset the poll loop so
    // the next regular tick still fires on schedule.
    const onRetry = () => {
      if (mounted.current) void fetchOnce()
    }
    window.addEventListener('daena:retry-pending', onRetry)

    return () => {
      mounted.current = false
      if (pollRef.current) clearTimeout(pollRef.current)
      window.removeEventListener('daena:retry-pending', onRetry)
    }
  }, [fetchOnce])

  return { runtimes, loading, error, refresh }
}
