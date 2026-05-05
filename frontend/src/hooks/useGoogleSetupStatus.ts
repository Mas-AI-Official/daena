/**
 * useGoogleSetupStatus -- live status feed for GoogleAccountSetupGuide.
 *
 * PR-GOOGLE-OAUTH-LIVE-SETUP-HELPERS (Sprint-10 PR-1, 2026-05-05).
 *
 * Pulls the four-step checklist from
 * GET /api/v1/connections/google-setup-status. Auth-required. The
 * payload carries no secrets -- only booleans + the two pinned account
 * emails + which Google services are connected per account.
 *
 * Refresh on mount + when the operator returns to the page (the
 * Connections panel emits ``daena:retry-pending`` after install /
 * disconnect; we listen for it).
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import api from '@/lib/api'

export interface GoogleAccountStatus {
  email: string
  connected: boolean
  instance_id: string | null
  connected_services: string[]
}

export interface GoogleSetupStatus {
  client_configured: boolean
  client_id_present: boolean
  client_secret_present: boolean
  founder_account: GoogleAccountStatus
  agent_account: GoogleAccountStatus
  ready: boolean
}


interface UseGoogleSetupStatusReturn {
  status: GoogleSetupStatus | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}


export function useGoogleSetupStatus(): UseGoogleSetupStatusReturn {
  const [status, setStatus] = useState<GoogleSetupStatus | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const res = await api.get<GoogleSetupStatus>(
        '/connections/google-setup-status',
      )
      if (!mounted.current) return
      setStatus(res.data ?? null)
    } catch (e: unknown) {
      if (!mounted.current) return
      const message = e instanceof Error ? e.message : 'Failed to load Google setup status'
      setError(message)
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    const onRetry = () => { void refresh() }
    window.addEventListener('daena:retry-pending', onRetry)
    return () => {
      mounted.current = false
      window.removeEventListener('daena:retry-pending', onRetry)
    }
  }, [refresh])

  return { status, loading, error, refresh }
}
