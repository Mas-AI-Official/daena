/**
 * Auth store — JWT state, login/register/logout, user profile.
 */
import { create } from 'zustand'
import api from '@/lib/api'
import type { UserResponse, TokenData } from '@/types/api'

interface AuthState {
  user: UserResponse | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName: string, tenantName: string) => Promise<void>
  oauthExchange: (code: string) => Promise<void>
  logout: () => Promise<void>
  loadFromStorage: () => void
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post<{ success: boolean; data: TokenData }>('/auth/login', {
        email,
        password,
      })
      const { access_token, user } = data.data
      localStorage.setItem('daena_token', access_token)
      set({ user, token: access_token, isAuthenticated: true, isLoading: false })
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
          ?.message || 'Login failed'
      set({ error: message, isLoading: false })
    }
  },

  register: async (email, password, displayName, tenantName) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post<{ success: boolean; data: TokenData }>('/auth/register', {
        email,
        password,
        display_name: displayName,
        tenant_name: tenantName,
      })
      const { access_token, user } = data.data
      localStorage.setItem('daena_token', access_token)
      set({ user, token: access_token, isAuthenticated: true, isLoading: false })
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
          ?.message || 'Registration failed'
      set({ error: message, isLoading: false })
    }
  },

  oauthExchange: async (code) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await api.post<{ success: boolean; data: TokenData }>(
        '/auth/oauth/exchange',
        { code },
      )
      const { access_token, user } = data.data
      localStorage.setItem('daena_token', access_token)
      set({ user, token: access_token, isAuthenticated: true, isLoading: false })
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message || 'OAuth login failed'
      set({ error: message, isLoading: false })
    }
  },

  logout: async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // silent — server may be down
    }
    localStorage.removeItem('daena_token')
    set({ user: null, token: null, isAuthenticated: false })
  },

  loadFromStorage: () => {
    const token = localStorage.getItem('daena_token')
    if (token) {
      // Decode JWT payload to get user info (no verification — server validates)
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        set({
          token,
          isAuthenticated: true,
          user: {
            user_id: payload.sub || payload.user_id,
            email: payload.email || '',
            display_name: payload.display_name || '',
            role: payload.role || 'VIEWER',
            tenant_id: payload.tenant_id || '',
            created_at: '',
          },
        })
      } catch {
        localStorage.removeItem('daena_token')
      }
    }
  },

  clearError: () => set({ error: null }),
}))

// Hydrate auth state synchronously before first render
// so ProtectedRoute sees the token on initial mount.
useAuthStore.getState().loadFromStorage()
