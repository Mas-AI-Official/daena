/**
 * Elevated security mode store.
 *
 * Neutrally named -- the internal codename for the offensive tier is
 * deliberately not referenced anywhere in the user-facing UI. This
 * store exposes a boolean ``isActive`` plus the capability list so the
 * navbar badge and governance pages can reflect current state without
 * leaking the hidden activation command string.
 *
 * Backing API: /api/v1/security/mode/{state,activate,deactivate}.
 */
import { create } from 'zustand'
import api from '@/lib/api'

export interface SecurityModeState {
  active: boolean
  environment: string
  capabilities: string[]
  activated_at: string
  activated_by: string
  reason_denied: string
}

interface SecurityModeStore {
  state: SecurityModeState
  loading: boolean
  lastFetched: number
  fetchState: () => Promise<void>
  activate: (key: string) => Promise<{ ok: boolean; reason?: string }>
  deactivate: () => Promise<void>
}

const DEFAULT_STATE: SecurityModeState = {
  active: false,
  environment: '',
  capabilities: [],
  activated_at: '',
  activated_by: '',
  reason_denied: '',
}

export const useSecurityModeStore = create<SecurityModeStore>((set, get) => ({
  state: DEFAULT_STATE,
  loading: false,
  lastFetched: 0,

  fetchState: async () => {
    if (get().loading) return
    set({ loading: true })
    try {
      const resp = await api.get<SecurityModeState>('/security/mode/state')
      set({ state: resp.data, lastFetched: Date.now(), loading: false })
    } catch {
      // Not authenticated yet or network error; keep previous state.
      set({ loading: false })
    }
  },

  activate: async (key: string) => {
    try {
      const resp = await api.post<SecurityModeState>(
        '/security/mode/activate',
        { key },
      )
      set({ state: resp.data, lastFetched: Date.now() })
      return { ok: true }
    } catch (err: unknown) {
      const detail = (err as {
        response?: { data?: { detail?: { reason_denied?: string } } }
      })?.response?.data?.detail
      const reason = detail?.reason_denied || 'Activation failed.'
      return { ok: false, reason }
    }
  },

  deactivate: async () => {
    try {
      const resp = await api.post<SecurityModeState>(
        '/security/mode/deactivate',
      )
      set({ state: resp.data, lastFetched: Date.now() })
    } catch {
      // Ignore; state polling will recover.
    }
  },
}))
