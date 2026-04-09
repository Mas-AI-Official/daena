/**
 * Daena API client -- Axios instance with JWT interceptor + refresh logic.
 *
 * Error handling:
 *  - 401: auto-refresh, fallback redirect to /login
 *  - 403: toast "Permission denied"
 *  - 404: toast "Not found"
 *  - 500: toast "Server error"
 *  - Network error: toast "Connection lost"
 *  - Timeout: 30s default, toast "Request timed out"
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { toast } from '@/stores/toastStore'

const API_BASE = '/api/v1'

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // send httpOnly refresh cookie
  timeout: 30_000, // 30s request timeout
})

// ── Request interceptor: attach JWT ──

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('daena_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: auto-refresh on 401 ──

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

const processQueue = (error: unknown, token: string | null) => {
  failedQueue.forEach((p) => {
    if (error) p.reject(error)
    else p.resolve(token!)
  })
  failedQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`
              resolve(api(originalRequest))
            },
            reject,
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const { data } = await axios.post(`${API_BASE}/auth/refresh`, {}, { withCredentials: true })
        const newToken = data.data.access_token
        localStorage.setItem('daena_token', newToken)
        processQueue(null, newToken)
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        localStorage.removeItem('daena_token')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // ── Classified error handling for non-401 errors ──
    const status = error.response?.status

    if (status === 403) {
      // Log the specific endpoint for debugging
      const url = error.config?.url || 'unknown'
      const code = (error.response?.data as Record<string, unknown>)?.error
        ? ((error.response?.data as Record<string, unknown>).error as Record<string, string>)?.code
        : ''
      console.warn(`[Daena 403] ${url} — ${code}`)
      if (code === 'INSUFFICIENT_ROLE') {
        // Stale token with wrong role -- force re-login
        toast.error('Session expired. Logging out...')
        localStorage.removeItem('daena_token')
        setTimeout(() => { window.location.href = '/login' }, 1000)
      } else {
        toast.error(`Permission denied${code ? ` (${code})` : ''}. Check your role or governance settings.`)
      }
    } else if (status === 404) {
      // Only toast for API calls, not page navigation
      const url = error.config?.url || ''
      if (url.includes('/api/')) {
        toast.error('Resource not found.')
      }
    } else if (status && status >= 500) {
      // Suppress toasts for background polling endpoints
      const url = error.config?.url || ''
      const isSilentPoll = url.includes('/execution/tasks') || url.includes('/heartbeat/')
      if (!isSilentPoll) {
        toast.error('Server error. Please try again in a moment.')
      }
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      toast.error('Request timed out. Please check your connection.')
    } else if (!error.response && error.message === 'Network Error') {
      toast.error('Connection lost. Please check your internet connection.')
    }

    return Promise.reject(error)
  },
)

export default api
