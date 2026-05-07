import { create } from 'zustand'

export type BackendHealthStatus = 'checking' | 'ok' | 'degraded' | 'down'

interface BackendHealthState {
  status: BackendHealthStatus
  message: string
  lastChecked: number | null
  setBackendHealth: (next: {
    status: BackendHealthStatus
    message: string
    lastChecked?: number
  }) => void
}

export const useBackendHealthStore = create<BackendHealthState>((set) => ({
  status: 'checking',
  message: 'Checking Daena backend health.',
  lastChecked: null,
  setBackendHealth: (next) => set({
    status: next.status,
    message: next.message,
    lastChecked: next.lastChecked ?? Date.now(),
  }),
}))
