/**
 * useMarketplace -- Connections marketplace catalog + per-tenant overlay.
 *
 * PR-CONNECTIONS-MARKETPLACE-UX (2026-05-02): the catalog (curated,
 * source-tree-versioned) tells us what Daena KNOWS HOW TO support.
 * The V2 truth registry tells us what is ACTUALLY working in this
 * tenant. The /marketplace/cards endpoint merges both so each card
 * carries an honest lifecycle.
 *
 * Honesty rules:
 *   - lifecycle "callable" only when the V2 row's last probe was
 *     successful AND failure_at < callable_at
 *   - "available" cards have NO V2 row and surface a Setup Guide CTA
 *   - "coming-soon" entries always render as available + setup_guide
 *
 * Hooks:
 *   - useMarketplaceCards()      polls /api/v1/connections/v2/marketplace/cards
 *   - useMarketplaceCatalog()    fetches /api/v1/connections/v2/catalog (static)
 *   - fetchInstallPlan(entryId)  fetches /install-plan/{entryId}
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { AxiosError } from 'axios'

import { api } from '@/lib/api'

const POLL_MS = 30_000

// ── Catalog types (mirrors marketplace_catalog.CatalogEntry) ──

export type CatalogKind =
  | 'mcp_server'
  | 'oauth_app'
  | 'browser_tool'
  | 'computer_use'
  | 'cli_runtime'
  | 'api_provider'
  | 'local_model'
  | 'skill_pack'

export type CatalogCategory =
  | 'filesystem'
  | 'browser'
  | 'computer_use'
  | 'code_platform'
  | 'communication'
  | 'productivity'
  | 'design'
  | 'data_storage'
  | 'payment'
  | 'research'
  | 'local_llm'
  | 'ai_provider'
  | 'dev_tools'
  | 'cli_runtime'

export type InstallMethod =
  | 'npm'
  | 'docker'
  | 'local'
  | 'manual'
  | 'subscription'
  | 'built-in'
  | 'coming-soon'

export type AuthType =
  | 'none'
  | 'oauth'
  | 'api_key'
  | 'token'
  | 'subscription'

export type ProbeType =
  | 'mcp_initialize'
  | 'oauth_token'
  | 'http_get'
  | 'binary_check'
  | 'skill_pack_only'
  | 'none'

export type RiskLevel = 'low' | 'medium' | 'high'

export interface CatalogEntry {
  id: string
  display_name: string
  vendor: string
  category: CatalogCategory
  kind: CatalogKind
  short_description: string
  capabilities: string[]
  install_method: InstallMethod
  command_template: string
  required_env_vars: string[]
  auth_type: AuthType
  official_url: string
  risk_level: RiskLevel
  probe_type: ProbeType
  compatible_os: string[]
  matches_v2_slug: string
  setup_notes: string
}

export interface CategoryDefinition {
  id: CatalogCategory
  display_name: string
  short_description: string
}

// ── Marketplace card (catalog + V2 overlay) ──

export type LifecycleState =
  | 'available'
  | 'needs_setup'
  | 'installed'
  | 'configured'
  | 'reachable'
  | 'callable'
  | 'enabled'
  | 'failed'
  | 'disabled'
  | 'archived'
  | 'skill_pack'

export type PrimaryAction =
  | 'setup_guide'
  | 'test'
  | 'enable'
  | 'open'
  | 'none'

export interface TruthDimSnapshot {
  value: boolean
  at: string | null
  failure_at: string | null
  failure_reason: string | null
}

export interface V2TruthSnapshot {
  detected: TruthDimSnapshot
  configured: TruthDimSnapshot
  imported: TruthDimSnapshot
  reachable: TruthDimSnapshot
  authenticated: TruthDimSnapshot
  callable: TruthDimSnapshot
}

export interface MarketplaceCard {
  catalog: CatalogEntry
  v2_row_id: string | null
  v2_label: string | null
  v2_truth: V2TruthSnapshot | null
  v2_disabled: boolean
  v2_archived: boolean
  v2_last_probe_at: string | null
  v2_failure_reason: string | null
  lifecycle: LifecycleState
  primary_action: PrimaryAction
  primary_action_label: string
}

// ── Install plan ──

export type InstallPlanStepKind = 'info' | 'command' | 'env' | 'auth' | 'link' | 'note'

export interface InstallPlanStep {
  kind: InstallPlanStepKind
  text: string
  command?: string
  url?: string
}

export interface InstallPlan {
  entry_id: string
  install_method: InstallMethod
  executable: boolean
  steps: InstallPlanStep[]
  entry: CatalogEntry
}

// ── Helpers ──

function readError(err: unknown): string {
  const axe = err as AxiosError<{ detail?: string }>
  return (
    axe?.response?.data?.detail ||
    (err instanceof Error ? err.message : 'unknown error')
  )
}

// ── Hooks ──

export interface UseMarketplaceCardsResult {
  cards: MarketplaceCard[]
  loading: boolean
  error: string | null
  refresh: () => void
}

export function useMarketplaceCards(): UseMarketplaceCardsResult {
  const [cards, setCards] = useState<MarketplaceCard[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mounted = useRef(true)
  const abortRef = useRef<AbortController | null>(null)

  const fetchOnce = useCallback(async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const res = await api.get<{
        success: boolean
        data: { cards: MarketplaceCard[] }
      }>('/connections/v2/marketplace/cards', { signal: controller.signal })
      if (!mounted.current) return
      setCards(res.data?.data?.cards ?? [])
      setError(null)
    } catch (err: unknown) {
      if (!mounted.current) return
      if ((err as AxiosError)?.code === 'ERR_CANCELED') return
      setError(readError(err))
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

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

  return { cards, loading, error, refresh }
}

export interface UseMarketplaceCatalogResult {
  catalog: CatalogEntry[]
  categories: CategoryDefinition[]
  loading: boolean
  error: string | null
}

export function useMarketplaceCatalog(): UseMarketplaceCatalogResult {
  const [catalog, setCatalog] = useState<CatalogEntry[]>([])
  const [categories, setCategories] = useState<CategoryDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const res = await api.get<{
          success: boolean
          data: { entries: CatalogEntry[]; categories: CategoryDefinition[] }
        }>('/connections/v2/catalog')
        if (cancelled) return
        setCatalog(res.data?.data?.entries ?? [])
        setCategories(res.data?.data?.categories ?? [])
        setError(null)
      } catch (err) {
        if (cancelled) return
        setError(readError(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return { catalog, categories, loading, error }
}

export async function fetchInstallPlan(entryId: string): Promise<{
  ok: boolean
  plan?: InstallPlan
  error?: string
}> {
  try {
    const res = await api.get<{ success: boolean; data: InstallPlan }>(
      `/connections/v2/marketplace/install-plan/${encodeURIComponent(entryId)}`,
      { silent: false },
    )
    return { ok: true, plan: res.data?.data }
  } catch (err) {
    return { ok: false, error: readError(err) }
  }
}

// ── Lifecycle display tone ──

export const LIFECYCLE_TONE: Record<
  LifecycleState,
  { dot: string; text: string; bg: string; border: string; label: string }
> = {
  available: {
    dot: 'bg-cyan-300',
    text: 'text-cyan-200',
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
    label: 'Available',
  },
  needs_setup: {
    dot: 'bg-amber-400',
    text: 'text-amber-200',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    label: 'Needs setup',
  },
  installed: {
    dot: 'bg-blue-300',
    text: 'text-blue-200',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    label: 'Installed',
  },
  configured: {
    dot: 'bg-blue-400',
    text: 'text-blue-200',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    label: 'Configured',
  },
  reachable: {
    dot: 'bg-emerald-300',
    text: 'text-emerald-200',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    label: 'Reachable',
  },
  callable: {
    dot: 'bg-emerald-400',
    text: 'text-emerald-200',
    bg: 'bg-emerald-500/15',
    border: 'border-emerald-500/40',
    label: 'Callable',
  },
  enabled: {
    dot: 'bg-emerald-400',
    text: 'text-emerald-200',
    bg: 'bg-emerald-500/15',
    border: 'border-emerald-500/40',
    label: 'Enabled',
  },
  failed: {
    dot: 'bg-rose-400',
    text: 'text-rose-200',
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    label: 'Failed',
  },
  disabled: {
    dot: 'bg-slate-400',
    text: 'text-slate-300',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/30',
    label: 'Disabled',
  },
  archived: {
    dot: 'bg-slate-500',
    text: 'text-slate-400',
    bg: 'bg-slate-500/5',
    border: 'border-slate-500/20',
    label: 'Archived',
  },
  skill_pack: {
    dot: 'bg-violet-400',
    text: 'text-violet-200',
    bg: 'bg-violet-500/10',
    border: 'border-violet-500/30',
    label: 'Skill pack',
  },
}

export function lifecycleTone(state: LifecycleState) {
  return LIFECYCLE_TONE[state] ?? LIFECYCLE_TONE.available
}

// ── Risk display tone ──

export const RISK_TONE: Record<RiskLevel, { text: string; bg: string }> = {
  low: { text: 'text-emerald-300', bg: 'bg-emerald-500/10' },
  medium: { text: 'text-amber-300', bg: 'bg-amber-500/10' },
  high: { text: 'text-rose-300', bg: 'bg-rose-500/10' },
}
