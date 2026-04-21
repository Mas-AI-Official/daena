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
      // Suppress toasts for background/polling endpoints that fire without user action
      const silentOn403 = ['/governance/approvals', '/heartbeat/', '/runtimes/']
      const isSilent403 = silentOn403.some((p) => url.includes(p))
      if (!isSilent403) {
        toast.error(`Permission denied${code ? ` (${code})` : ''}. Check your role or governance settings.`)
      }
    } else if (status === 404) {
      // Only toast for API calls, not page navigation
      const url = error.config?.url || ''
      if (url.includes('/api/')) {
        toast.error('Resource not found.')
      }
    } else if (status && status >= 500) {
      // Suppress toasts for background/polling endpoints that fire
      // without user action. Expanded 2026-04-18 after a backend
      // restart produced transient 500s on several polling surfaces
      // and the user saw 4 "Server error" toasts stack up even though
      // no action they took had failed. Poll hooks catch their own
      // errors; component-level fetchers should set their own inline
      // error state instead of relying on the global toast.
      const url = error.config?.url || ''
      const silentPrefixes = [
        '/execution/tasks', '/heartbeat/', '/governance/approvals',
        '/settings/user', '/billing/', '/chat/model-registry',
        '/chat/sessions', '/runtimes/', '/health', '/agents/',
        '/memory/', '/connections/', '/department-states',
        '/department-messages', '/department-signals',
        '/department-policies', '/department-budget',
        '/security/', '/pipeline/', '/projects/', '/autopilot/',
        '/dynamic-models/', '/mcp/', '/mcp-sync/', '/skills/',
        '/integrations/', '/prompts/',
      ]
      const isSilent = silentPrefixes.some((p) => url.includes(p))
      if (!isSilent) {
        toast.error('Server error. Please try again in a moment.')
      }
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      const url = error.config?.url || ''
      // Timeouts on polling endpoints are also transient -- don't
      // toast for those. A long-running LLM call timing out is not a
      // "please try again" situation; the caller decides what to do.
      const silentOnTimeout = [
        '/heartbeat/', '/governance/approvals', '/execution/tasks',
        '/runtimes/', '/department-', '/security/', '/pipeline/',
        '/chat/sessions', '/chat/model-registry',
      ]
      if (!silentOnTimeout.some((p) => url.includes(p))) {
        toast.error('Request timed out. Please check your connection.')
      }
    } else if (!error.response && error.message === 'Network Error') {
      // Backend unreachable -- don't spam toasts, components handle their own fallback
    }

    return Promise.reject(error)
  },
)

export default api
