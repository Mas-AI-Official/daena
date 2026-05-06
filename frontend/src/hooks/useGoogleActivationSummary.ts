/**
 * useGoogleActivationSummary -- Sprint-20 PR-1 (2026-05-06).
 *
 * Lightweight DB-only readiness check for cross-page banners (e.g.
 * OpportunityInboxPage). Distinct from useGoogleSetupStatus, which
 * powers the full setup-guide. The summary is always cheap because
 * the backend never touches Google here -- pure connector-instance
 * presence + client-config metadata.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import api from '@/lib/api'

export interface ActivationBlocker {
  role: 'client' | 'founder' | 'agent'
  email: string | null
  missing: string[]
}

export interface ActivationSummary {
  ready: boolean
  client_configured: boolean
  blockers: ActivationBlocker[]
}

interface UseActivationReturn {
  summary: ActivationSummary | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export function useGoogleActivationSummary(): UseActivationReturn {
  const [summary, setSummary] = useState<ActivationSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const res = await api.get<ActivationSummary>(
        '/connections/google-activation-summary',
      )
      if (!mounted.current) return
      setSummary(res.data ?? null)
    } catch (e: unknown) {
      if (!mounted.current) return
      const msg = e instanceof Error ? e.message : 'failed to load'
      setError(msg)
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    return () => { mounted.current = false }
  }, [refresh])

  return { summary, loading, error, refresh }
}
