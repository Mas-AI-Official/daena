/**
 * usePermissionState: fetches the governance/autopilot banner copy
 * from the backend resolver so the Connections page can explain
 * WHY per-tool pills may or may not apply.
 *
 * Session 11: unifies the per-tool Allow/Ask/Block layer with the
 * UNLEASHED / BALANCED / GOVERNED governance modes. Operator should
 * see at a glance that setting a pill to Ask won't interrupt them
 * in UNLEASHED + Autopilot mode.
 *
 * Re-fetches when governance mode or autopilot toggle flips.
 */
import { useEffect, useState } from 'react'

import { api } from '@/lib/api'
import { useUiStore } from '@/stores/uiStore'

export interface PermissionState {
  governance_mode: string
  autopilot: boolean
  per_tool_override_active: string  // "true" | "false"
  banner_headline: string
  banner_body: string
}

export function usePermissionState(): PermissionState | null {
  const governanceMode = useUiStore((s) => s.governanceMode)
  const autopilotActive = useUiStore((s) => s.autopilotActive)
  const [state, setState] = useState<PermissionState | null>(null)

  useEffect(() => {
    let cancelled = false
    const params = new URLSearchParams({
      governance_mode: governanceMode,
      autopilot: String(autopilotActive),
    })
    api
      .get<{ data: PermissionState }>(`/governance/permission-state?${params.toString()}`)
      .then((res) => {
        if (!cancelled) setState(res.data.data)
      })
      .catch(() => {
        // Graceful: leave state null, frontend renders nothing.
      })
    return () => {
      cancelled = true
    }
  }, [governanceMode, autopilotActive])

  return state
}
