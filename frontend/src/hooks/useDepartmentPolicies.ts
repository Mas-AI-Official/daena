/**
 * useDepartmentPolicies: CRUD for the cross-department rule book.
 *
 * Session D (Piece 4) of the "Daena as a Living Company" plan.
 * Powers the Policy Rules page. Loads policies on mount + after
 * any mutation.
 */
import { useCallback, useEffect, useState } from 'react'

import { api } from '@/lib/api'

export type PolicyType = 'EXPENSE' | 'DEPLOYMENT' | 'EXTERNAL_COMMS' | 'EXTERNAL_DATA' | 'NEW_VENDOR' | 'CUSTOM'

export interface TriggerCondition {
  field: string
  op: string
  value: unknown
}

export interface DepartmentPolicy {
  id: string
  name: string
  description: string
  policy_type: PolicyType
  trigger_condition: { conditions?: TriggerCondition[] }
  required_approvers: string[]
  escalation_chain: string[]
  enabled: boolean
  seed_key: string
  created_at: string | null
  updated_at: string | null
}

export interface PolicyDraft {
  name: string
  description: string
  policy_type: PolicyType
  trigger_condition: { conditions?: TriggerCondition[] }
  required_approvers: string[]
  escalation_chain?: string[]
  enabled?: boolean
}

interface UsePoliciesReturn {
  policies: DepartmentPolicy[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  createPolicy: (draft: PolicyDraft) => Promise<DepartmentPolicy | null>
  updatePolicy: (id: string, updates: Partial<PolicyDraft>) => Promise<DepartmentPolicy | null>
  deletePolicy: (id: string) => Promise<boolean>
  seedDefaults: () => Promise<number>
}

export function useDepartmentPolicies(): UsePoliciesReturn {
  const [policies, setPolicies] = useState<DepartmentPolicy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await api.get<DepartmentPolicy[]>(
        '/department-policies?include_disabled=true',
      )
      setPolicies(res.data)
      setError(null)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load policies'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  const createPolicy = useCallback(async (draft: PolicyDraft): Promise<DepartmentPolicy | null> => {
    try {
      const res = await api.post<DepartmentPolicy>('/department-policies', draft)
      void refresh()
      return res.data
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Create failed'
      setError(msg)
      return null
    }
  }, [refresh])

  const updatePolicy = useCallback(
    async (id: string, updates: Partial<PolicyDraft>): Promise<DepartmentPolicy | null> => {
      try {
        const res = await api.patch<DepartmentPolicy>(
          `/department-policies/${encodeURIComponent(id)}`,
          updates,
        )
        void refresh()
        return res.data
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Update failed'
        setError(msg)
        return null
      }
    },
    [refresh],
  )

  const deletePolicy = useCallback(async (id: string): Promise<boolean> => {
    try {
      await api.delete(`/department-policies/${encodeURIComponent(id)}`)
      void refresh()
      return true
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Delete failed'
      setError(msg)
      return false
    }
  }, [refresh])

  const seedDefaults = useCallback(async (): Promise<number> => {
    try {
      const res = await api.post<{ inserted: number; message: string }>(
        '/department-policies/seed',
      )
      void refresh()
      return res.data.inserted
    } catch {
      return 0
    }
  }, [refresh])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return {
    policies,
    loading,
    error,
    refresh,
    createPolicy,
    updatePolicy,
    deletePolicy,
    seedDefaults,
  }
}
