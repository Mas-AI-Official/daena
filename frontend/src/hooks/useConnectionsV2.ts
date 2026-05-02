/**
 * useConnectionsV2 -- polls GET /api/v1/connections/v2
 *
 * Phase 5 PR 1: V2 truth-backed connections list. Each row carries
 * the 6 truth dimensions (detected/configured/imported/reachable/
 * authenticated/callable) plus per-dim failure metadata and a
 * derived label. Status NEVER lies -- a row is "healthy" only when
 * a real probe has flipped callable=true.
 *
 * Pattern mirrors useRuntimeRegistry / useMcpRegistry: setTimeout
 * poll chain, mounted ref, refresh(), retry-pending event listener,
 * silent prefix in api.ts so failures land in the navbar dot rather
 * than as a toast.
 *
 * Behavior:
 *  - Initial fetch + 30s polling (cancellable)
 *  - Manual refresh callback
 *  - Mutation hooks: import, probe, enable, disable, archive
 *  - Mutations call api directly + trigger a refresh on success
 *  - Errors return as { error } and also recorded by api interceptor
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import type { AxiosError } from 'axios'

const POLL_MS = 30_000

export type ConnectionKind =
  | 'cli_runtime'
  | 'mcp_server'
  | 'provider'
  | 'plugin'
  | 'oauth_app'
  | 'local_model'
  | 'skill_pack'

export type ConnectionLabel =
  | 'unknown'
  | 'installable'
  | 'installing'
  | 'needs_config'
  | 'needs_auth'
  | 'auth_pending'
  | 'probing'
  | 'healthy'
  | 'healthy_stale'
  | 'degraded'
  | 'degraded_stale'
  | 'failed'
  | 'disabled'
  | 'archived'
  | 'skill_pack'

export interface TruthDim {
  value: boolean
  at: string | null
  failure_at: string | null
  failure_reason: string | null
}

export interface ConnectionTruth {
  detected: TruthDim
  configured: TruthDim
  imported: TruthDim
  reachable: TruthDim
  authenticated: TruthDim
  callable: TruthDim
}

export interface ConnectionV2Row {
  id: string
  tenant_id: string
  kind: ConnectionKind
  slug: string
  display_name: string
  auth_method: string
  trust_tier: string
  config: Record<string, unknown>
  truth: ConnectionTruth
  label: ConnectionLabel
  capabilities_count: number
  healthy_call_ratio: number
  archived: boolean
  disabled: boolean
  governance_tier: number
}

export interface ProbeOutcome {
  success: boolean
  label_after: string
  callable_at: string | null
  failure_dim: string | null
  failure_reason: string | null
}

interface UseConnectionsV2Result {
  rows: ConnectionV2Row[]
  loading: boolean
  error: string | null
  refresh: () => void

  // Mutations -- each returns a Promise<{ ok: boolean; error?: string }>
  probe: (id: string) => Promise<{ ok: boolean; outcome?: ProbeOutcome; error?: string }>
  enable: (id: string) => Promise<{ ok: boolean; error?: string }>
  disable: (id: string) => Promise<{ ok: boolean; error?: string }>
  archive: (id: string) => Promise<{ ok: boolean; error?: string }>
}

function readError(err: unknown): string {
  const axe = err as AxiosError<{ detail?: string }>
  return (
    axe?.response?.data?.detail ||
    (err instanceof Error ? err.message : 'unknown error')
  )
}

export function useConnectionsV2(
  kind?: ConnectionKind,
): UseConnectionsV2Result {
  const [rows, setRows] = useState<ConnectionV2Row[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mounted = useRef(true)
  const abortRef = useRef<AbortController | null>(null)

  const fetchOnce = useCallback(async () => {
    // Cancel a stale request that may still be in-flight from a kind switch.
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const params = kind ? { kind } : undefined
      const res = await api.get<ConnectionV2Row[]>('/connections/v2', {
        params,
        signal: controller.signal,
      })
      if (!mounted.current) return
      setRows(Array.isArray(res.data) ? res.data : [])
      setError(null)
    } catch (err: unknown) {
      if (!mounted.current) return
      // Cancellations are not errors.
      if ((err as AxiosError)?.code === 'ERR_CANCELED') return
      setError(readError(err))
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [kind])

  const refresh = useCallback(() => {
    void fetchOnce()
  }, [fetchOnce])

  useEffect(() => {
    mounted.current = true
    void fetchOnce()
    const tick = () => {
      void fetchOnce()
      pollRef.current = setTimeout(tick, POLL_MS)
    }
    pollRef.current = setTimeout(tick, POLL_MS)

    const onRetry = () => {
      if (mounted.current) void fetchOnce()
    }
    window.addEventListener('daena:retry-pending', onRetry)

    return () => {
      mounted.current = false
      if (pollRef.current) clearTimeout(pollRef.current)
      abortRef.current?.abort()
      window.removeEventListener('daena:retry-pending', onRetry)
    }
  }, [fetchOnce])

  // ── Mutations ──

  const probe = useCallback(
    async (id: string) => {
      try {
        const res = await api.post<ProbeOutcome>(
          `/connections/v2/${id}/probe`,
          undefined,
          { silent: false },
        )
        await fetchOnce()
        return { ok: true, outcome: res.data }
      } catch (err) {
        return { ok: false, error: readError(err) }
      }
    },
    [fetchOnce],
  )

  const enable = useCallback(
    async (id: string) => {
      try {
        await api.post(`/connections/v2/${id}/enable`, undefined, { silent: false })
        await fetchOnce()
        return { ok: true }
      } catch (err) {
        return { ok: false, error: readError(err) }
      }
    },
    [fetchOnce],
  )

  const disable = useCallback(
    async (id: string) => {
      try {
        await api.post(`/connections/v2/${id}/disable`, undefined, { silent: false })
        await fetchOnce()
        return { ok: true }
      } catch (err) {
        return { ok: false, error: readError(err) }
      }
    },
    [fetchOnce],
  )

  const archive = useCallback(
    async (id: string) => {
      try {
        await api.delete(`/connections/v2/${id}`, { silent: false })
        await fetchOnce()
        return { ok: true }
      } catch (err) {
        return { ok: false, error: readError(err) }
      }
    },
    [fetchOnce],
  )

  return { rows, loading, error, refresh, probe, enable, disable, archive }
}

// ── Helpers exported for components ──

const KIND_ORDER: ConnectionKind[] = [
  'cli_runtime',
  'mcp_server',
  'provider',
  'oauth_app',
  'plugin',
  'local_model',
  'skill_pack',
]

const KIND_LABEL: Record<ConnectionKind, string> = {
  cli_runtime: 'AI Runtimes (CLI)',
  mcp_server: 'MCP Servers',
  provider: 'API Providers',
  oauth_app: 'OAuth Apps',
  plugin: 'Plugins',
  local_model: 'Local Models',
  skill_pack: 'Skill Packs (not callable)',
}

export function kindLabel(k: ConnectionKind): string {
  return KIND_LABEL[k] ?? k
}

export function kindOrder(): ConnectionKind[] {
  return [...KIND_ORDER]
}

const LABEL_TONE: Record<
  ConnectionLabel,
  { dot: string; text: string; bg: string; border: string }
> = {
  healthy: {
    dot: 'bg-emerald-400', text: 'text-emerald-300',
    bg: 'bg-emerald-500/10', border: 'border-emerald-500/30',
  },
  healthy_stale: {
    dot: 'bg-emerald-300/70', text: 'text-emerald-200/80',
    bg: 'bg-emerald-500/5', border: 'border-emerald-400/20',
  },
  degraded: {
    dot: 'bg-amber-400', text: 'text-amber-200',
    bg: 'bg-amber-500/10', border: 'border-amber-500/30',
  },
  degraded_stale: {
    dot: 'bg-amber-300/70', text: 'text-amber-200/80',
    bg: 'bg-amber-500/5', border: 'border-amber-400/20',
  },
  needs_auth: {
    dot: 'bg-orange-400', text: 'text-orange-200',
    bg: 'bg-orange-500/10', border: 'border-orange-500/30',
  },
  auth_pending: {
    dot: 'bg-orange-300/70', text: 'text-orange-200/80',
    bg: 'bg-orange-500/5', border: 'border-orange-400/20',
  },
  installable: {
    dot: 'bg-cyan-400', text: 'text-cyan-200',
    bg: 'bg-cyan-500/10', border: 'border-cyan-500/30',
  },
  needs_config: {
    dot: 'bg-cyan-300/70', text: 'text-cyan-200/80',
    bg: 'bg-cyan-500/5', border: 'border-cyan-400/20',
  },
  installing: {
    dot: 'bg-cyan-200/70 animate-pulse', text: 'text-cyan-200/80',
    bg: 'bg-cyan-500/5', border: 'border-cyan-400/20',
  },
  probing: {
    dot: 'bg-blue-300/70 animate-pulse', text: 'text-blue-200/80',
    bg: 'bg-blue-500/5', border: 'border-blue-400/20',
  },
  failed: {
    dot: 'bg-rose-400', text: 'text-rose-200',
    bg: 'bg-rose-500/10', border: 'border-rose-500/30',
  },
  unknown: {
    dot: 'bg-slate-400', text: 'text-slate-300',
    bg: 'bg-slate-500/10', border: 'border-slate-500/30',
  },
  disabled: {
    dot: 'bg-slate-500', text: 'text-slate-300',
    bg: 'bg-slate-500/10', border: 'border-slate-500/30',
  },
  archived: {
    dot: 'bg-slate-500', text: 'text-slate-400',
    bg: 'bg-slate-500/5', border: 'border-slate-500/20',
  },
  skill_pack: {
    dot: 'bg-violet-400', text: 'text-violet-200',
    bg: 'bg-violet-500/10', border: 'border-violet-500/30',
  },
}

export function labelTone(label: ConnectionLabel) {
  return LABEL_TONE[label] ?? LABEL_TONE.unknown
}

export const TRUTH_DIM_ORDER = [
  'detected', 'configured', 'imported',
  'reachable', 'authenticated', 'callable',
] as const

export type TruthDimName = typeof TRUTH_DIM_ORDER[number]

// PR-CONN-V2-SEED-IMPORT (2026-05-02): manual discovery import.
// Walks real sources (CLI MCP configs, runtimes, local models, OAuth
// catalog, V1 plugin catalog) and materializes V2 rows for the
// caller's tenant. Idempotent. Never reads secrets, never auto-installs.

export interface DiscoverySourceResult {
  source: string
  created: string[]
  skipped_existing: string[]
  skipped_unconfigured: string[]
  failed: Array<{ slug: string; error_type: string; error: string }>
  total_created: number
  total_skipped_existing: number
  total_skipped_unconfigured: number
  total_failed: number
}

export interface DiscoveryReport {
  tenant_id: string
  sources: DiscoverySourceResult[]
  total_created: number
  total_skipped_existing: number
  total_skipped_unconfigured: number
  total_failed: number
}

export async function runDiscoveryRefresh(): Promise<{
  ok: boolean
  report?: DiscoveryReport
  v2_enabled?: boolean
  error?: string
}> {
  try {
    const res = await api.post<{
      success: boolean
      data: DiscoveryReport
      v2_enabled: boolean
    }>('/connections/v2/discovery/refresh', undefined, { silent: false })
    return {
      ok: true,
      report: res.data?.data,
      v2_enabled: !!res.data?.v2_enabled,
    }
  } catch (err) {
    return { ok: false, error: readError(err) }
  }
}
