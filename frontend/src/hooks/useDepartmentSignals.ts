/**
 * useDepartmentSignals -- polls the BorderAgent feed for a department.
 *
 * Backed by GET /api/v1/department-states/{department}/peer-signals.
 * Each department's BorderAgent maintains an in-memory ring buffer of
 * peer events that matched its relevance lens. This hook surfaces that
 * feed in the department room so the user sees, in real time, what
 * other departments are doing that relates to this one.
 *
 * Polling cadence: 10s. Ring-buffer lives in the Python process; on
 * backend restart the feed resets. That's intentional -- signals are
 * ephemeral situational-awareness, not audit log (the audit chain is
 * separate and persistent).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'

export interface PeerSignal {
  id: string
  source_department: string
  event_type: string
  payload: Record<string, unknown>
  created_at: number
  relevant_because: string
}

interface ResponseBody {
  success: boolean
  data: {
    department: string
    count: number
    signals: PeerSignal[]
  }
}

interface UseDepartmentSignalsReturn {
  signals: PeerSignal[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const POLL_MS = 10_000

export function useDepartmentSignals(
  departmentName: string | undefined,
  limit = 50,
): UseDepartmentSignalsReturn {
  const [signals, setSignals] = useState<PeerSignal[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchOnce = useCallback(async () => {
    if (!departmentName) return
    try {
      const res = await api.get<ResponseBody>(
        `/department-states/${encodeURIComponent(departmentName)}/peer-signals?limit=${limit}`,
      )
      setSignals(res.data.data?.signals ?? [])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'poll failed')
    } finally {
      setLoading(false)
    }
  }, [departmentName, limit])

  useEffect(() => {
    if (!departmentName) return
    setLoading(true)
    void fetchOnce()
    intervalRef.current = setInterval(() => {
      void fetchOnce()
    }, POLL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [departmentName, fetchOnce])

  return { signals, loading, error, refresh: fetchOnce }
}
