/**
 * useMcpRegistry -- polls the live stdio-bootstrap registry.
 *
 * Backed by GET /api/v1/connections/mcp-registry. Returns the set of
 * currently adapter-ready MCPs (what ``plugin.call_tool`` can dispatch
 * to RIGHT NOW), distinct from whatever is merely written to
 * ``claude_desktop_config.json``.
 *
 * Used by the Plugins tab to show a "Live" badge on each plugin the
 * user actually has spawnable. After installing a plugin, this hook
 * reflects the state within a single poll window (10s) or
 * immediately if a caller dispatches the `refresh` callback.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'

export interface McpRegistryEntry {
  server_key: string
  display_name: string
  description: string
  command: string
  args: string[]
  package: string | null
}

interface ResponseBody {
  success: boolean
  data: {
    count: number
    entries: McpRegistryEntry[]
  }
}

const POLL_MS = 10_000

export function useMcpRegistry() {
  const [entries, setEntries] = useState<McpRegistryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mounted = useRef(true)

  const fetchOnce = useCallback(async () => {
    try {
      const res = await api.get<ResponseBody>('/connections/mcp-registry')
      if (!mounted.current) return
      setEntries(res.data?.data?.entries || [])
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
    return () => {
      mounted.current = false
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [fetchOnce])

  // Quick lookup -- callers can ask "is this server_key live?"
  // without scanning the array every render.
  const liveKeys = new Set(entries.map((e) => e.server_key))
  const isLive = useCallback(
    (serverKey: string) => liveKeys.has(serverKey),
    // Recompute only when the set of keys changes, not on every
    // render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [entries],
  )

  return { entries, loading, error, refresh, isLive }
}
