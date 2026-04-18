/**
 * useDepartmentStates: polls the department state registry so the
 * Company Dashboard animates as departments start / finish work.
 *
 * Session A (Piece 1) of the "Daena as a Living Company" plan.
 * Backend endpoint materializes all 10 canonical departments on
 * every call so the caller does not need to special-case first-time
 * tenants with no rows yet.
 *
 * Polling cadence: 5s. Fast enough that user-initiated chat turns
 * show state transitions within a reasonable window, slow enough
 * that 100 open tabs do not DDoS the backend. If we later need
 * sub-second updates, swap this for a WebSocket -- backend already
 * exposes `/ws`.
 */
import { useEffect, useRef, useState } from 'react'

import { api } from '@/lib/api'

export type DepartmentStatus = 'IDLE' | 'WORKING' | 'OVERLOADED' | 'OFFLINE'

export interface DepartmentState {
  department_name: string
  status: DepartmentStatus
  current_task_id: string | null
  current_task_summary: string | null
  queue_depth: number
  last_activity_at: string | null
}

interface UseDepartmentStatesReturn {
  states: DepartmentState[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const POLL_MS = 5_000

export function useDepartmentStates(): UseDepartmentStatesReturn {
  const [states, setStates] = useState<DepartmentState[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Hold a ref to the interval handle so cleanup is race-free even if
  // React unmounts mid-fetch.
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchOnce = async () => {
    try {
      const res = await api.get<{ data: DepartmentState[] }>('/department-states')
      setStates(res.data.data)
      setError(null)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load department states'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchOnce()
    intervalRef.current = setInterval(() => {
      void fetchOnce()
    }, POLL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  return {
    states,
    loading,
    error,
    refresh: fetchOnce,
  }
}
