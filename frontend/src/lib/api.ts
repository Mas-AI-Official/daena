/**
 * Daena API client -- Axios instance with JWT interceptor + refresh logic.
 *
 * Error handling philosophy (rewrite, 2026-04-29):
 *   The previous shape silently swallowed every 5xx response on a wide
 *   allowlist of polling endpoints (/heartbeat/, /governance/approvals/,
 *   /runtimes/, /mcp/, /skills/, ...). When backends fell over, the user
 *   saw nothing -- the app FELT broken even though no toast had ever
 *   fired. That is a worse failure than a noisy toast, because the user
 *   has no thread to pull on.
 *
 *   New shape:
 *     - Every error is recorded to useErrorStore (no exception). The
 *       ConnectionStatusIndicator reads from there and surfaces a small
 *       navbar dot when an endpoint family starts failing.
 *     - Every error is logged to console.warn with category, status,
 *       url, code -- so devtools is the source of truth for diagnosis.
 *     - Toasts are still suppressed by default for known polling
 *       endpoints (the silent prefix list) so we don't spam the user
 *       when the heartbeat blips. But the suppression is now per-call
 *       overridable via `config.silent` -- a caller doing an explicit
 *       user-initiated mutation can force a toast even on a "silent"
 *       prefix, and a polling caller can opt out for a specific call.
 *     - Default for `silent`: true if the request url matches a silent
 *       prefix, false otherwise (any user-initiated mutation surfaces).
 *
 *   Cancellations (axios CanceledError) are skipped entirely -- they
 *   represent intentional aborts (route change, fetch refresh) and
 *   shouldn't lit the navbar or spam console.
 *
 * Other behavior:
 *  - 401: auto-refresh, fallback redirect to /login
 *  - 403: toast "Permission denied" unless silent
 *  - 404: toast "Resource not found" for /api/ paths unless silent
 *  - 5xx: toast "Server error" unless silent
 *  - Timeout (ECONNABORTED): toast unless silent
 *  - Network error (no response): toast unless silent
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { toast } from '@/stores/toastStore'
import { useErrorStore, extractEndpointPrefix, type ErrorEntry } from '@/stores/errorStore'

const API_BASE = '/api/v1'

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // send httpOnly refresh cookie
  timeout: 30_000, // 30s request timeout
})

// ── Silent prefixes ──
//
// Polling / background endpoints whose failures should NOT pop a toast
// by default. They still record to the error store + console.warn, so
// the navbar indicator + devtools both see them. A caller can override
// per-request with `config.silent = false`.
//
// Match is "url contains prefix" -- same logic the old wholesale block
// used, only now consulted as a default rather than as a hard mute.
const SILENT_PREFIXES = [
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

function isSilentByDefault(url: string): boolean {
  return SILENT_PREFIXES.some((p) => url.includes(p))
}

// ── Augment axios config so callers can pass `silent` ──
//
// Declaration merging on InternalAxiosRequestConfig lets a caller do:
//   api.get('/runtimes/foo', { silent: false })
// without a TS cast. Defaults to undefined; the interceptor falls back
// to the prefix-based default when undefined.
declare module 'axios' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  export interface AxiosRequestConfig {
    silent?: boolean
  }
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  export interface InternalAxiosRequestConfig {
    silent?: boolean
  }
}

// ── Request interceptor: attach JWT ──

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('daena_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: auto-refresh on 401 + classified error handling ──

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

/** Pull a backend error code out of the response payload, if present. */
function extractErrorCode(error: AxiosError): string | undefined {
  const body = error.response?.data as Record<string, unknown> | undefined
  if (!body) return undefined
  const errField = body.error
  if (typeof errField === 'object' && errField !== null) {
    const code = (errField as Record<string, unknown>).code
    if (typeof code === 'string') return code
  }
  return undefined
}

/** Classify the axios error so the store + console get a stable label. */
function categorize(error: AxiosError): ErrorEntry['category'] {
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) return 'timeout'
  if (!error.response) return 'network'
  const status = error.response.status
  if (status >= 500) return 'server'
  return 'client'
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    // Skip canceled requests entirely -- intentional aborts shouldn't
    // pollute the error store or console.
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }

    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // ── 401 auto-refresh path ──
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
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
        // Preserve the page the user was on so re-login can return them there instead of a
        // bare /chat. The path is read from window.location (same-origin by construction);
        // LoginPage re-sanitizes ?next= on read to block any crafted open-redirect, mirroring
        // the hardcoded 402 billing redirect below.
        const here = window.location.pathname
        const next = here && here !== '/login' && here !== '/register'
          ? `?next=${encodeURIComponent(here + window.location.search)}`
          : ''
        window.location.href = `/login${next}`
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // ── Classified error handling ──

    const url = originalRequest?.url || error.config?.url || 'unknown'
    const status = error.response?.status ?? 0
    const code = extractErrorCode(error)
    const category = categorize(error)
    const prefix = extractEndpointPrefix(url)

    // Resolve the silent flag:
    //   - Caller-supplied `config.silent` wins.
    //   - Otherwise, fall back to the prefix-based default. Polling
    //     endpoints are silent by default; user-initiated mutations to
    //     non-polling paths surface toasts.
    const callerSilent = originalRequest?.silent
    const silent = callerSilent !== undefined
      ? callerSilent
      : isSilentByDefault(url)

    // Always log -- this is the diagnosis breadcrumb. Format keeps the
    // category, status, url, code on a single greppable line.
    console.warn(
      `[Daena api] category=${category} status=${status} url=${url} code=${code ?? '-'} silent=${silent}`,
      error.message,
    )

    // Always record to the error store. The store is the source of
    // truth for ConnectionStatusIndicator regardless of toast policy.
    useErrorStore.getState().recordError({
      prefix,
      url,
      status,
      category,
      code,
      message: error.message ?? `HTTP ${status}`,
      silent,
    })

    // ── 402 upgrade_required path ──
    // Entitlement gates (require_tier / require_feature in app/api/deps.py)
    // answer 402 with an upgrade_url. Route the user to the billing surface so
    // a gated 402 always lands somewhere they can actually upgrade. Fires
    // regardless of the silent flag (this is navigation, not a toast); the path
    // guard prevents a redirect loop once already on the billing page. The
    // target is hardcoded rather than read from response.data.upgrade_url to
    // avoid an open-redirect via a crafted server response.
    if (status === 402 && !window.location.pathname.startsWith('/account/billing')) {
      window.location.href = '/account/billing#billing'
      return Promise.reject(error)
    }

    // Now decide whether to surface a toast.
    if (!silent) {
      if (status === 403) {
        toast.error(`Permission denied${code ? ` (${code})` : ''}. Check your role or governance settings.`)
      } else if (status === 404 && url.includes('/api/')) {
        toast.error('Resource not found.')
      } else if (status >= 500) {
        toast.error('Server error. Please try again in a moment.')
      } else if (category === 'timeout') {
        toast.error('Request timed out. Please check your connection.')
      } else if (category === 'network') {
        toast.error('Connection lost. Backend unreachable.')
      }
    }

    return Promise.reject(error)
  },
)

export default api
