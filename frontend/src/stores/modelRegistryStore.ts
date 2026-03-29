import { create } from 'zustand'

import { api } from '@/lib/api'
import type { ApiResponse, ModelRegistryResponse } from '@/types/api'

const CACHE_TTL_MS = 60_000 // 60 seconds

interface ModelRegistryState {
  registry: ModelRegistryResponse | null
  loading: boolean
  error: string | null
  lastFetchedAt: number
  fetchRegistry: (forceRefresh?: boolean) => Promise<void>
}

export const useModelRegistryStore = create<ModelRegistryState>((set, get) => ({
  registry: null,
  loading: false,
  error: null,
  lastFetchedAt: 0,

  fetchRegistry: async (forceRefresh = false) => {
    const state = get()
    if (state.loading) return

    // Stale-while-revalidate: if cached data exists and is fresh, skip
    const now = Date.now()
    if (!forceRefresh && state.registry && (now - state.lastFetchedAt) < CACHE_TTL_MS) {
      return
    }

    // Show loading only if no cached data (first load)
    if (!state.registry) {
      set({ loading: true, error: null })
    }

    try {
      const { data } = await api.get<ApiResponse<ModelRegistryResponse>>(
        `/chat/model-registry?refresh=${forceRefresh ? 'true' : 'false'}`,
      )
      set({ registry: data.data, loading: false, lastFetchedAt: Date.now() })
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to load live model registry'
      // Keep stale data visible, just note the error
      set({ error: message, loading: false })
    }
  },
}))

export default useModelRegistryStore
