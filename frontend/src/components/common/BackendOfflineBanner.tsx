import { useEffect } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { useBackendHealthStore } from '@/stores/backendHealthStore'

async function readBackendHealth(signal: AbortSignal): Promise<{ status: 'ok' | 'degraded'; message: string }> {
  const response = await fetch('/api/v1/health', {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'include',
    signal,
  })

  if (!response.ok) {
    throw new Error(`Health check returned HTTP ${response.status}`)
  }

  const body = await response.json().catch(() => ({}))
  const status = String(body?.status ?? body?.data?.status ?? '').toLowerCase()
  if (status.includes('degraded')) {
    return { status: 'degraded', message: 'Backend is reachable but reports degraded health.' }
  }
  return { status: 'ok', message: 'Backend reachable.' }
}

export function BackendOfflineBanner() {
  const { status, message, lastChecked, setBackendHealth } = useBackendHealthStore()

  useEffect(() => {
    let stopped = false
    let timer: ReturnType<typeof setTimeout> | undefined

    // 2026-04-30 stabilization: bumped 3s -> 5s so the post-restart
    // warming window doesn't false-alarm "signal is aborted without
    // reason". Backend essentials complete in ~1.2s but seedings can
    // briefly tie up the event loop; 5s is well within the 10s polling
    // interval and matches the SecurityScopePage timeout we set in
    // Phase 5. We also retry ONCE on AbortError before declaring
    // offline -- the first stale-port abort right after a backend
    // restart is the noisiest false positive.
    const probe = async (timeoutMs: number) => {
      const controller = new AbortController()
      const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
      try {
        return await readBackendHealth(controller.signal)
      } finally {
        window.clearTimeout(timeout)
      }
    }

    const check = async () => {
      try {
        let next: Awaited<ReturnType<typeof probe>>
        try {
          next = await probe(5000)
        } catch (firstErr) {
          // Single retry on abort/network -- handles the post-restart
          // .daena-port-stale window that completes within 1-2s.
          if (firstErr instanceof DOMException && firstErr.name === 'AbortError') {
            next = await probe(5000)
          } else {
            throw firstErr
          }
        }
        if (!stopped) {
          setBackendHealth({
            status: next.status,
            message: next.message,
          })
        }
      } catch (error) {
        if (!stopped) {
          const detail = error instanceof Error ? error.message : 'Unknown health check failure'
          setBackendHealth({
            status: 'down',
            message: `Backend unreachable through frontend proxy: ${detail}`,
          })
        }
      } finally {
        if (!stopped) timer = window.setTimeout(check, 10000)
      }
    }

    check()
    return () => {
      stopped = true
      if (timer) window.clearTimeout(timer)
    }
  }, [setBackendHealth])

  if (status === 'ok' || status === 'checking') return null

  const checkedLabel = lastChecked
    ? new Date(lastChecked).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : 'not checked'

  return (
    <div className="border-b border-status-error/25 bg-status-error/10 px-4 py-2 text-xs text-starlight-100">
      <div className="flex items-center gap-3">
        <AlertTriangle size={16} className="shrink-0 text-status-error" />
        <div className="min-w-0 flex-1">
          <span className="font-semibold text-status-error">
            {status === 'down' ? 'Backend offline' : 'Backend degraded'}
          </span>
          <span className="mx-2 text-starlight-500">/</span>
          <span className="text-starlight-300">{message}</span>
          <span className="ml-2 text-starlight-500">Checked {checkedLabel}</span>
        </div>
        <RefreshCw size={14} className="hidden sm:block text-starlight-500" />
      </div>
    </div>
  )
}

export default BackendOfflineBanner
