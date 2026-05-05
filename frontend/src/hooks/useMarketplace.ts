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

/**
 * PR-CONN-MCP-CATALOG-SKILL-BUNDLES (2026-05-03): officiality drives
 * the trust badge on the marketplace card.
 *   official        -- MCP steering group reference servers
 *   vendor-official -- First-party MCP shipped by the app's vendor
 *   vendor-blessed  -- Community but vendor-affiliated org
 *   verified        -- Manually reviewed by Daena
 *   community       -- Third-party, surfaced with caveat
 *   archived        -- Was reference, no longer maintained
 *   coming-soon     -- No MCP shipping yet
 */
export type Officiality =
  | 'official'
  | 'vendor-official'
  | 'vendor-blessed'
  | 'verified'
  | 'community'
  | 'archived'
  | 'coming-soon'

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
  /** PR-CONN-MCP-CATALOG-SKILL-BUNDLES: optional plugin-bundle metadata.
   * Backwards-compatible defaults: empty arrays + "community" tier. */
  officiality?: Officiality
  default_skills?: string[]
  suggested_prompts?: string[]
  permissions_summary?: string[]
  mcp_servers?: string[]
  source_refs?: string[]
  last_verified_at?: string
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
  | 'configure'
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
  /**
   * PR-CONN-PROVIDER-KEY-VISIBILITY (2026-05-03): tri-state.
   * - true: settings has a non-empty value for this card's credential
   * - false: settings attribute is empty / unset
   * - null: this card kind does not use a settings credential
   *   (oauth_app, mcp_server, browser_tool, computer_use, cli_runtime,
   *   skill_pack -- truth lives in the V2 probe instead)
   * Never carries the credential VALUE -- only the presence bit.
   */
  provider_key_present: boolean | null
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

// ──────────────────────────────────────────────────────────────────
// Diagnostic summary (Sprint-6 PR-2)
// ──────────────────────────────────────────────────────────────────
//
// Backed by GET /api/v1/connections/v2/marketplace/diagnostic. The
// classification logic (which cards are blocked and why) lives in the
// backend so frontend + backend never drift on what counts as
// "callable". The hook is read-only metadata; never carries config /
// secret / token data per the endpoint's contract.

export type BlockerReason =
  | 'not_imported'
  | 'coming_soon'
  | 'needs_api_key'
  | 'needs_oauth'
  | 'needs_probe'
  | 'probe_failed'
  | 'disabled'
  | 'archived'
  | 'skill_pack'

export interface DiagnosticTotals {
  catalog: number
  callable: number
  configured: number
  failed: number
  skill_packs: number
  coming_soon: number
  available: number
  blocked: number
}

export interface DiagnosticBlocker {
  reason: BlockerReason
  label: string
  next_action: string
  count: number
  examples: { entry_id: string; display_name: string }[]
}

export interface DiagnosticSummary {
  totals: DiagnosticTotals
  top_blockers: DiagnosticBlocker[]
}

export interface UseMarketplaceDiagnosticResult {
  summary: DiagnosticSummary | null
  loading: boolean
  error: string | null
  refresh: () => void
}

export function useMarketplaceDiagnostic(): UseMarketplaceDiagnosticResult {
  const [summary, setSummary] = useState<DiagnosticSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  const fetchOnce = useCallback(async () => {
    try {
      const res = await api.get<{
        success: boolean
        data: DiagnosticSummary
      }>('/connections/v2/marketplace/diagnostic')
      if (!mounted.current) return
      setSummary(res.data?.data ?? null)
      setError(null)
    } catch (err) {
      if (!mounted.current) return
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
    return () => {
      mounted.current = false
    }
  }, [fetchOnce])

  return { summary, loading, error, refresh }
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

// ── MCP install (preview + apply) ──────────────────────────────────
//
// PR-CONN-MCP-INSTALL-INTO-CLI: write an MCP catalog entry into a
// supported CLI's own config file (Claude Desktop / Claude Code /
// Codex / Gemini CLI). preview NEVER touches disk; apply does the
// actual backup + atomic write.

export type McpInstallTarget =
  | 'claude_desktop'
  | 'claude_code'
  | 'codex'
  | 'gemini_cli'

export interface McpInstallPreviewBody {
  target: McpInstallTarget
  allow_create?: boolean
  probe_after_apply?: boolean
  // PR-CONN-MCP-INSTALL-PLACEHOLDER-INPUT (Sprint-8 PR-1):
  // operator-supplied substitutions for <TOKEN> placeholders in the
  // catalog command_template. Validated server-side for shell safety.
  placeholder_values?: Record<string, string>
}

export interface McpServerBlock {
  command: string
  args: string[]
}

export interface McpInstallPreview {
  target: McpInstallTarget
  target_display_name: string
  config_path: string | null
  config_exists: boolean
  parse_ok: boolean
  candidates_tried: string[]
  server_name: string
  proposed_block: McpServerBlock | null
  existing_block: McpServerBlock | null
  action: 'create' | 'update' | 'skip' | 'create_file' | 'failed'
  backup_path: string | null
  required_env_vars: string[]
  risk_warnings: string[]
  apply_allowed: boolean
  failure_reason: string | null
  // PR-CONN-MCP-INSTALL-PLACEHOLDER-INPUT (Sprint-8 PR-1):
  // every <TOKEN> in the raw catalog template that still needs an
  // operator-supplied value. Empty list once all are resolved.
  unresolved_placeholders: string[]
}

export interface McpInstallApply {
  target: McpInstallTarget
  target_display_name: string
  config_path: string | null
  server_name: string
  action: 'created' | 'updated' | 'skipped' | 'create_file' | 'failed'
  backup_path: string | null
  failure_reason: string | null
  required_env_vars: string[]
  v2_row_id: string | null
  v2_label: string | null
  post_apply_probe: {
    success: boolean
    label_after: string
    failure_dim: string | null
    failure_reason: string | null
  } | null
}

export async function previewMcpInstall(
  entryId: string,
  body: McpInstallPreviewBody,
): Promise<{ ok: boolean; preview?: McpInstallPreview; error?: string }> {
  try {
    const res = await api.post<{ success: boolean; data: McpInstallPreview }>(
      `/connections/v2/marketplace/install-plan/${encodeURIComponent(entryId)}/preview`,
      body,
    )
    return { ok: true, preview: res.data?.data }
  } catch (err) {
    return { ok: false, error: readError(err) }
  }
}

export async function applyMcpInstall(
  entryId: string,
  body: McpInstallPreviewBody,
): Promise<{ ok: boolean; result?: McpInstallApply; error?: string }> {
  try {
    const res = await api.post<{ success: boolean; data: McpInstallApply }>(
      `/connections/v2/marketplace/install-plan/${encodeURIComponent(entryId)}/apply`,
      body,
    )
    return { ok: true, result: res.data?.data }
  } catch (err) {
    return { ok: false, error: readError(err) }
  }
}

// ── OAuth marketplace start (preview-only; the consent + callback
// happens out-of-band on the provider side) ────────────────────────
//
// PR-CONN-OAUTH-CONNECT: returns an authorization URL and an opaque
// state token. NEVER returns secret material. The frontend opens the
// URL in a popup; the provider's consent screen redirects back to
// /api/v1/connectors/oauth/callback which writes tokens (V1) AND
// imports the V2 oauth_app row (PR-CONN-OAUTH-CONNECT bridge).

export interface OAuthStartResponse {
  success: boolean
  provider: string | null
  authorization_url: string | null
  redirect_uri: string | null
  scopes: string[]
  state_ref: string | null
  failure_reason: string | null
}

export async function startMarketplaceOAuth(
  entryId: string,
): Promise<{ ok: boolean; data?: OAuthStartResponse; error?: string }> {
  try {
    const res = await api.post<OAuthStartResponse>(
      `/connections/v2/marketplace/oauth/${encodeURIComponent(entryId)}/start`,
      {},
    )
    return { ok: true, data: res.data }
  } catch (err) {
    return { ok: false, error: readError(err) }
  }
}

// ── Browser / computer-use local probe ────────────────────────────
//
// PR-CONN-BROWSER-PROBE: pre-install local check for catalog entries
// with kind=browser_tool / computer_use. Returns whether the
// operator's machine can actually run the tool BEFORE the MCP install
// flow lands the row as kind=mcp_server. Never persists state.

export interface BrowserProbeReport {
  success: boolean
  tool_id: string
  tool_display_name: string
  strategy: string
  package_status: 'installed' | 'not_found' | 'unknown'
  browser_status: 'ready' | 'not_installed' | 'not_required' | 'unknown'
  capabilities: string[]
  failure_reason: string | null
  safety_notes: string[]
}

export async function runBrowserProbe(
  entryId: string,
): Promise<{ ok: boolean; report?: BrowserProbeReport; error?: string }> {
  try {
    const res = await api.post<{ success: boolean; data: BrowserProbeReport }>(
      `/connections/v2/marketplace/browser-probe/${encodeURIComponent(entryId)}`,
      {},
    )
    return { ok: true, report: res.data?.data }
  } catch (err) {
    return { ok: false, error: readError(err) }
  }
}

// ── MCP install backups (PR-CONN-MCP-INSTALL-RESTORE) ──────────────
//
// List + restore Daena backup files created by the MCP install flow.
// Never returns file contents -- only filename, timestamp, size, and
// JSON validity. Restore creates a pre-restore backup of the current
// config before overwriting (atomic rename).

export interface BackupEntry {
  filename: string
  timestamp: string
  size_bytes: number
  valid_json: boolean
}

export interface BackupListReport {
  target: McpInstallTarget
  target_display_name: string
  config_path: string | null
  backups: BackupEntry[]
  failure_reason: string | null
}

export interface BackupRestoreReport {
  target: McpInstallTarget
  target_display_name: string
  config_path: string | null
  restored_from: string | null
  pre_restore_backup: string | null
  success: boolean
  failure_reason: string | null
}

export async function listMcpBackups(
  target: McpInstallTarget,
): Promise<{ ok: boolean; data?: BackupListReport; error?: string }> {
  try {
    const res = await api.get<{ success: boolean; data: BackupListReport }>(
      `/connections/v2/marketplace/install-backups?target=${encodeURIComponent(target)}`,
    )
    return { ok: true, data: res.data?.data }
  } catch (err) {
    return { ok: false, error: readError(err) }
  }
}

export async function restoreMcpBackup(
  body: { target: McpInstallTarget; backup_filename: string },
): Promise<{ ok: boolean; data?: BackupRestoreReport; error?: string }> {
  try {
    const res = await api.post<{ success: boolean; data: BackupRestoreReport }>(
      "/connections/v2/marketplace/install-backups/restore",
      body,
    )
    return { ok: true, data: res.data?.data }
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
