/**
 * GovernanceAuditPage — hash-chain verified governance trail.
 * Shows audit log entries with filtering, chain integrity indicator.
 */
import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ScrollText,
  Shield,
  Lock,
  ChevronDown,
  RefreshCw,
  Search,
  Filter,
  X,
  Calendar,
  CheckSquare,
  Square,
  Download,
  CheckCircle2,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import type { AuditEntryResponse, ApiResponse, RiskLevel } from '@/types/api'

const REVIEWED_STORAGE_KEY = 'daena:auditReviewedIds'

interface AuditVerifyResponse {
  success: boolean
  data: {
    valid: boolean
    total_entries: number
    first_broken_id: string | null
    // PR-AUDIT-VERIFY: present in deep mode (?deep=true). Distinct
    // from first_broken_id because content tampering does not
    // necessarily break the chain links -- an attacker can flip
    // ``result`` and leave prev_hash/entry_hash intact, in which case
    // the structural walker still passes but the payload-recompute
    // catches the lie.
    first_corrupt_id?: string | null
  }
}

// Risk level color mapping
const RISK_COLORS: Record<string, string> = {
  NONE: 'text-starlight-500',
  LOW: 'text-status-success',
  MEDIUM: 'text-status-warning',
  HIGH: 'text-accent-amber',
  CRITICAL: 'text-status-error',
}

/** Build a human-readable sentence from action_type + action_params */
function formatActionDescription(entry: AuditEntryResponse): string {
  const params = entry.action_params as Record<string, string> | null
  if (!params) return entry.action_type || 'Governance action'

  if (entry.action_type === 'LLM_CALL') {
    const model = params.model || 'unknown model'
    const mode = params.applied_routing_mode || params.requested_routing_mode || 'Standard'
    const userMsg = params.user_message
    const latency = params.latency_ms
    const excerpt = userMsg ? userMsg.slice(0, 50).replace(/\n/g, ' ') : null

    let desc = excerpt ? `User: ${excerpt}${userMsg.length > 50 ? '…' : ''}` : ''
    desc += desc ? ' — ' : ''
    desc += `${mode} routed to ${model}`
    if (latency) desc += `, ${(Number(latency) / 1000).toFixed(1)}s`
    return desc
  }

  // Generic fallback: "ACTION_TYPE with key details"
  const reason = params.selection_reason || params.reason
  if (reason) return `${entry.action_type}: ${reason}`
  return entry.action_type || 'Governance action'
}

// ── Filter options ──
const RISK_OPTIONS: RiskLevel[] = ['NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const RESULT_OPTIONS = ['ALLOWED', 'BLOCKED', 'APPROVAL_REQUIRED'] as const

// ── Audit Detail Panel (expanded view) ──

/** Group keys into logical sections for clean display */
function AuditDetail({ entry }: { entry: AuditEntryResponse }) {
  const params = (entry.action_params ?? {}) as Record<string, unknown>
  const isLlmCall = entry.action_type === 'LLM_CALL'

  // Extract known fields into groups
  const model = params.model as string | undefined
  const provider = params.provider as string | undefined
  const routingMode = params.applied_routing_mode as string || params.requested_routing_mode as string
  const routingSource = params.routing_source as string | undefined
  const selectionReason = params.selection_reason as string | undefined
  const modeReason = params.mode_reason as string | undefined
  const intent = params.intent as string | undefined
  const latencyMs = params.latency_ms as number | undefined
  const providerStrategy = params.provider_strategy as string | undefined
  const suggestedModels = params.suggested_models as string | undefined
  const topCandidates = params.top_candidates as string | undefined
  const providersConsidered = params.providers_considered as string | undefined
  const userMessage = params.user_message as string | undefined

  // Keys already displayed in sections — skip from "other" dump
  const shownKeys = new Set([
    'model', 'provider', 'applied_routing_mode', 'requested_routing_mode',
    'routing_source', 'selection_reason', 'mode_reason', 'intent',
    'latency_ms', 'provider_strategy', 'suggested_models', 'top_candidates',
    'providers_considered', 'user_message',
    // Plugin invocation panel fields (Sprint-10 PR-5)
    'plugin_id', 'skill_id', 'outcome', 'read_only', 'target_tool',
    'url_host', 'result_length', 'blocked_reason', 'phase',
    'allowlist_match', 'execution_mode', 'backend_surface',
    'argument_shape', 'missing_inputs', 'goal_length', 'truncated',
    'worker_version',
  ])
  const otherParams = Object.entries(params).filter(([k, v]) => !shownKeys.has(k) && v != null && v !== '')

  const formatValue = (v: unknown): string => {
    if (v == null || v === '') return ''
    if (Array.isArray(v)) {
      return v.map(item => {
        if (typeof item === 'object' && item !== null) {
          const obj = item as Record<string, unknown>
          return obj.model_id || obj.model || obj.name || obj.display_name || JSON.stringify(item)
        }
        return String(item)
      }).join(', ')
    }
    if (typeof v === 'object') {
      const obj = v as Record<string, unknown>
      return obj.model_id || obj.model || obj.name || obj.display_name
        ? String(obj.model_id || obj.model || obj.name || obj.display_name)
        : JSON.stringify(v)
    }
    return String(v)
  }

  return (
    <div className="px-4 pb-4 pt-2 border-t border-white/5 space-y-3">
      {/* Routing section */}
      {isLlmCall && (
        <div className="space-y-2">
          <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Routing Decision</p>
          <div className="rounded-lg bg-midnight-800/50 border border-white/5 p-3 space-y-2">
            {/* Model + Provider row */}
            <div className="flex items-center gap-4 flex-wrap">
              {model && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-starlight-500">Model</span>
                  <span className="text-xs font-mono text-primary-400">{model}</span>
                </div>
              )}
              {provider && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-starlight-500">Provider</span>
                  <span className="text-xs font-mono text-starlight-200">{provider}</span>
                </div>
              )}
              {latencyMs != null && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-starlight-500">Latency</span>
                  <span className="text-xs font-mono text-starlight-200">{(Number(latencyMs) / 1000).toFixed(1)}s</span>
                </div>
              )}
            </div>

            {/* Routing flow */}
            <div className="flex items-center gap-2 flex-wrap text-[11px]">
              {routingMode && (
                <Badge variant={routingMode === 'QUINTESSENCE' ? 'purple' : routingMode === 'COUNCIL' ? 'amber' : 'default'} size="sm">
                  {routingMode}
                </Badge>
              )}
              {routingSource && (
                <>
                  <span className="text-starlight-600">via</span>
                  <span className="text-starlight-300">{routingSource.replace(/_/g, ' ')}</span>
                </>
              )}
              {providerStrategy && (
                <>
                  <span className="text-starlight-600">strategy</span>
                  <span className="text-starlight-300">{providerStrategy}</span>
                </>
              )}
            </div>

            {/* Selection reason */}
            {selectionReason && (
              <p className="text-[11px] text-starlight-400 leading-relaxed">{selectionReason}</p>
            )}
            {modeReason && modeReason !== selectionReason && (
              <p className="text-[11px] text-starlight-400 leading-relaxed">{modeReason}</p>
            )}

            {/* Models considered */}
            {(topCandidates || suggestedModels || providersConsidered) && (
              <div className="flex items-center gap-2 flex-wrap text-[10px] pt-1 border-t border-white/5">
                {topCandidates && (
                  <span className="text-starlight-400">Candidates: <span className="font-mono text-starlight-300">{formatValue(topCandidates)}</span></span>
                )}
                {providersConsidered && (
                  <span className="text-starlight-400">Providers: <span className="font-mono text-starlight-300">{formatValue(providersConsidered)}</span></span>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Plugin Invocation panel (Sprint-10 PR-5):
          structured rendering for plugin.skill_invocation rows.
          The brief mandates: plugin, skill, status, read-only/write,
          result preview, audit id.  No secret values. */}
      {entry.action_type === 'plugin.skill_invocation' && (
        <div
          data-testid="audit-detail-plugin-panel"
          className="space-y-2"
        >
          <p className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">
            Plugin Invocation
          </p>
          <div className="rounded-lg bg-midnight-800/50 border border-white/5 p-3 grid grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-2 text-xs">
            <div>
              <span className="text-[10px] text-starlight-500">Plugin</span>
              <p className="font-mono text-starlight-200">
                {String(params.plugin_id ?? '?')}
              </p>
            </div>
            <div>
              <span className="text-[10px] text-starlight-500">Skill</span>
              <p className="font-mono text-starlight-200">
                {String(params.skill_id ?? '?')}
              </p>
            </div>
            <div>
              <span className="text-[10px] text-starlight-500">Status</span>
              <p className="text-starlight-200">
                {String(params.outcome ?? entry.result ?? '?')}
              </p>
            </div>
            <div>
              <span className="text-[10px] text-starlight-500">Mode</span>
              <p className={params.read_only === false
                ? 'text-amber-300 font-semibold'
                : 'text-emerald-300 font-semibold'}>
                {params.read_only === false ? 'WRITE' : 'read-only'}
              </p>
            </div>
            {params.target_tool && (
              <div>
                <span className="text-[10px] text-starlight-500">Target tool</span>
                <p className="font-mono text-starlight-300">
                  {String(params.target_tool)}
                </p>
              </div>
            )}
            {params.url_host && (
              <div>
                <span className="text-[10px] text-starlight-500">Host</span>
                <p className="font-mono text-starlight-300 truncate">
                  {String(params.url_host)}
                </p>
              </div>
            )}
            {typeof params.result_length === 'number' && (
              <div>
                <span className="text-[10px] text-starlight-500">Result length</span>
                <p className="text-starlight-300">{String(params.result_length)} chars</p>
              </div>
            )}
            {params.blocked_reason && (
              <div className="col-span-2 lg:col-span-3">
                <span className="text-[10px] text-starlight-500">Reason</span>
                <p className="text-rose-300 font-mono break-all">
                  {String(params.blocked_reason)}
                </p>
              </div>
            )}
            <div className="col-span-2 lg:col-span-3">
              <span className="text-[10px] text-starlight-500">Audit id</span>
              <p className="font-mono text-starlight-400 text-[11px]">
                {entry.id}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Context section */}
      <div className="flex items-center gap-6 flex-wrap text-xs">
        {entry.actor_type && (
          <div>
            <span className="text-[10px] text-starlight-500 block">Actor</span>
            <span className="text-starlight-300">{entry.actor_type}</span>
          </div>
        )}
        <div>
          <span className="text-[10px] text-starlight-500 block">Action</span>
          <span className="text-starlight-300">{entry.action_type}</span>
        </div>
        {intent && (
          <div>
            <span className="text-[10px] text-starlight-500 block">Intent</span>
            <span className="text-starlight-300">{intent}</span>
          </div>
        )}
      </div>

      {/* User message excerpt */}
      {userMessage && (
        <div>
          <span className="text-[10px] text-starlight-500 block mb-0.5">User Message</span>
          <p className="text-[11px] text-starlight-300 leading-relaxed bg-midnight-800/30 rounded-lg px-3 py-2 border border-white/5">
            {userMessage.length > 200 ? userMessage.slice(0, 200) + '...' : userMessage}
          </p>
        </div>
      )}

      {/* Other params (if any) */}
      {otherParams.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] text-starlight-500 uppercase tracking-wider font-semibold">Additional Details</span>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-1.5 text-xs">
            {otherParams.map(([key, value]) => {
              const formatted = formatValue(value)
              if (!formatted) return null
              return (
                <div key={key}>
                  <span className="text-[10px] text-starlight-500">{key.replace(/_/g, ' ')}</span>
                  <p className="text-starlight-300 truncate">{formatted}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Integrity chain */}
      {(entry.entry_hash || entry.prev_hash) && (
        <div className="pt-2 border-t border-white/5">
          <span className="text-[9px] text-starlight-600 uppercase tracking-wider font-semibold">Integrity Chain</span>
          <div className="mt-1 space-y-0.5">
            {entry.entry_hash && (
              <p className="text-[9px] font-mono text-starlight-600 break-all">
                <span className="text-starlight-500">entry</span> {entry.entry_hash}
              </p>
            )}
            {entry.prev_hash && (
              <p className="text-[9px] font-mono text-starlight-600 break-all">
                <span className="text-starlight-500">prev</span> {entry.prev_hash}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function GovernanceAuditPage() {
  usePageTitle('Audit Log')
  const [entries, setEntries] = useState<AuditEntryResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Selection + batch actions
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // "Reviewed" is a per-operator UI annotation, NOT a backend mutation.
  // The audit log itself is immutable (hash-chained); persisting reviewed
  // ids client-side gives the operator a triage view without breaking
  // chain integrity.
  const [reviewedIds, setReviewedIds] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(REVIEWED_STORAGE_KEY)
      return raw ? new Set(JSON.parse(raw) as string[]) : new Set()
    } catch {
      return new Set()
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(REVIEWED_STORAGE_KEY, JSON.stringify([...reviewedIds]))
    } catch {
      // localStorage full or unavailable — annotation just won't persist
    }
  }, [reviewedIds])

  // Chain integrity status — verified against backend, NOT hardcoded.
  // PR-AUDIT-VERIFY: now distinguishes structural break (chain links
  // damaged) from content corruption (row payload modified post-write
  // while chain links untouched). Both are tamper but they need
  // different recovery: structural break may be a rolled-back commit;
  // content corruption is an intentional lie about what happened.
  const [chainStatus, setChainStatus] = useState<
    'verifying' | 'ok' | 'broken' | 'corrupt' | 'unknown'
  >('unknown')
  const [chainBrokenAt, setChainBrokenAt] = useState<string | null>(null)
  const [chainCorruptAt, setChainCorruptAt] = useState<string | null>(null)

  const verifyChain = async () => {
    setChainStatus('verifying')
    try {
      // deep=true triggers payload recompute on the backend (PR-AUDIT-VERIFY).
      // Structural-only verification cannot catch content tampering that
      // leaves the chain links intact.
      const { data } = await api.get<AuditVerifyResponse>(
        '/governance/audit/verify?deep=true',
      )
      const inner = data.data
      if (inner?.valid) {
        setChainStatus('ok')
        setChainBrokenAt(null)
        setChainCorruptAt(null)
      } else if (inner?.first_corrupt_id) {
        // Content tamper takes precedence in display: it is a quieter
        // attack than a chain break and the operator should know.
        setChainStatus('corrupt')
        setChainCorruptAt(inner.first_corrupt_id ?? null)
        setChainBrokenAt(inner?.first_broken_id ?? null)
      } else {
        setChainStatus('broken')
        setChainBrokenAt(inner?.first_broken_id ?? null)
        setChainCorruptAt(null)
      }
    } catch {
      setChainStatus('unknown')
    }
  }

  // ── Filter state ──
  const [searchQuery, setSearchQuery] = useState('')
  const [filterRisk, setFilterRisk] = useState<string>('')
  const [filterResult, setFilterResult] = useState<string>('')
  const [filterAction, setFilterAction] = useState<string>('')
  // PR-AUDIT-VIEWER-PLUGIN-FILTER (Sprint-10 PR-5, 2026-05-05):
  // narrow audit rows to a specific plugin's skill invocations. When
  // set, auto-implies action_type='plugin.skill_invocation' so the
  // operator doesn't have to combine two filters.
  const [filterPlugin, setFilterPlugin] = useState<string>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(false)

  const fetchAudit = async () => {
    setLoading(true)
    try {
      const { data } = await api.get<ApiResponse<AuditEntryResponse[]>>('/governance/audit')
      setEntries(data.data || [])
      setLoadError(null)
    } catch (err: unknown) {
      setEntries([])
      const msg =
        (err as { response?: { data?: { detail?: string; error?: { message?: string } } } })
          ?.response?.data?.detail ||
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ||
        'Audit trail unavailable. Check backend health and auditor permissions.'
      setLoadError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAudit()
    verifyChain()
  }, [])

  // Derive unique action types from data for the dropdown
  const actionTypes = useMemo(
    () => [...new Set(entries.map((e) => e.action_type).filter(Boolean))].sort(),
    [entries],
  )

  // PR-AUDIT-VIEWER-PLUGIN-FILTER (Sprint-10 PR-5, 2026-05-05).
  // Unique plugin_ids derived from plugin.skill_invocation rows so the
  // dropdown shows only what the operator has actually used.
  const pluginIds = useMemo(() => {
    const ids = new Set<string>()
    for (const e of entries) {
      if (e.action_type !== 'plugin.skill_invocation') continue
      const pid = (e.action_params as Record<string, unknown> | null)?.plugin_id
      if (typeof pid === 'string' && pid) ids.add(pid)
    }
    return [...ids].sort()
  }, [entries])

  const hasActiveFilters = !!(
    filterRisk || filterResult || filterAction || filterPlugin || dateFrom || dateTo
  )

  const clearFilters = () => {
    setFilterRisk('')
    setFilterResult('')
    setFilterAction('')
    setFilterPlugin('')
    setDateFrom('')
    setDateTo('')
    setSearchQuery('')
  }

  // ── Selection helpers ──
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }
  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filtered.map((e) => e.id)))
    }
  }
  const clearSelection = () => setSelectedIds(new Set())

  // ── Batch actions ──
  // The audit log is hash-chained and immutable by design. The only
  // operator-facing mutation is "mark reviewed", which is a local
  // annotation persisted to localStorage (not the backend).
  const handleMarkReviewed = () => {
    setReviewedIds((prev) => {
      const next = new Set(prev)
      selectedIds.forEach((id) => next.add(id))
      return next
    })
    clearSelection()
  }
  const handleUnmarkReviewed = () => {
    setReviewedIds((prev) => {
      const next = new Set(prev)
      selectedIds.forEach((id) => next.delete(id))
      return next
    })
    clearSelection()
  }
  const handleExportJson = () => {
    const toExport = selectedIds.size > 0
      ? filtered.filter((e) => selectedIds.has(e.id))
      : filtered
    const blob = new Blob([JSON.stringify(toExport, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `daena-audit-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      // Free text search
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        const descMatch = formatActionDescription(e).toLowerCase().includes(q)
        const typeMatch = e.action_type?.toLowerCase().includes(q)
        const riskMatch = e.risk_level?.toLowerCase().includes(q)
        const resultMatch = e.result?.toLowerCase().includes(q)
        if (!descMatch && !typeMatch && !riskMatch && !resultMatch) return false
      }
      // Risk level filter
      if (filterRisk && e.risk_level !== filterRisk) return false
      // Result filter
      if (filterResult && e.result !== filterResult) return false
      // Action type filter
      if (filterAction && e.action_type !== filterAction) return false
      // PR-AUDIT-VIEWER-PLUGIN-FILTER (Sprint-10 PR-5):
      // Plugin filter: when set, narrow to plugin.skill_invocation
      // rows for the chosen plugin_id. An operator filtering "what
      // did mcp-fetch do" should never have to also tick action_type.
      if (filterPlugin) {
        if (e.action_type !== 'plugin.skill_invocation') return false
        const pid = (e.action_params as Record<string, unknown> | null)?.plugin_id
        if (pid !== filterPlugin) return false
      }
      // Date range
      if (dateFrom) {
        const entryDate = new Date(e.created_at).toISOString().slice(0, 10)
        if (entryDate < dateFrom) return false
      }
      if (dateTo) {
        const entryDate = new Date(e.created_at).toISOString().slice(0, 10)
        if (entryDate > dateTo) return false
      }
      return true
    })
  }, [entries, searchQuery, filterRisk, filterResult, filterAction, filterPlugin, dateFrom, dateTo])

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-primary-500/15">
              <ScrollText size={22} className="text-primary-400" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold text-starlight-100">Audit Log</h1>
              <p className="text-sm text-starlight-400">Hash-chain verified governance trail</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Chain integrity badge — verified against /governance/audit/verify
                in deep mode (PR-AUDIT-VERIFY). 'corrupt' = payload tamper that
                the structural walker would have missed. 'broken' = chain link
                damage. Both render red but with distinct copy + tooltip so the
                operator can tell which class of tamper occurred. */}
            <button
              onClick={verifyChain}
              title={
                chainStatus === 'corrupt'
                  ? 'Content tamper detected: a row\'s payload no longer matches its stored entry_hash. Click to re-verify.'
                  : chainStatus === 'broken'
                  ? 'Structural break detected: a row\'s prev_hash link is invalid. Click to re-verify.'
                  : 'Click to re-verify hash-chain integrity (deep payload recompute).'
              }
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-colors cursor-pointer ${
                chainStatus === 'ok'
                  ? 'bg-status-success/10 border-status-success/20 hover:bg-status-success/15'
                  : chainStatus === 'broken' || chainStatus === 'corrupt'
                  ? 'bg-status-error/10 border-status-error/30 hover:bg-status-error/15'
                  : chainStatus === 'verifying'
                  ? 'bg-white/5 border-white/10'
                  : 'bg-white/5 border-white/10 hover:bg-white/10'
              }`}
            >
              {chainStatus === 'ok' && <ShieldCheck size={12} className="text-status-success" />}
              {(chainStatus === 'broken' || chainStatus === 'corrupt') && (
                <ShieldAlert size={12} className="text-status-error" />
              )}
              {(chainStatus === 'verifying' || chainStatus === 'unknown') && (
                <Lock size={12} className={`text-starlight-400 ${chainStatus === 'verifying' ? 'animate-pulse' : ''}`} />
              )}
              <span
                className={`text-[10px] font-mono ${
                  chainStatus === 'ok' ? 'text-status-success'
                  : chainStatus === 'broken' || chainStatus === 'corrupt' ? 'text-status-error'
                  : 'text-starlight-400'
                }`}
              >
                {chainStatus === 'ok' && 'Chain intact'}
                {chainStatus === 'broken' && (chainBrokenAt ? `Broken at ${chainBrokenAt.slice(0, 8)}` : 'Chain broken')}
                {chainStatus === 'corrupt' && (chainCorruptAt ? `Corrupt at ${chainCorruptAt.slice(0, 8)}` : 'Content tamper')}
                {chainStatus === 'verifying' && 'Verifying...'}
                {chainStatus === 'unknown' && 'Verify chain'}
              </span>
            </button>
            <button
              onClick={fetchAudit}
              className="p-2 rounded-lg text-starlight-400 hover:text-starlight-100 hover:bg-white/5 transition-colors cursor-pointer"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </motion.div>

        {/* Search + Filter bar */}
        <div className="space-y-3">
          <div className="flex gap-2">
            {/* Free text search */}
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search audit entries..."
                className="w-full glass-input pl-9 pr-4 py-2.5 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:ring-1 focus:ring-primary-500/40"
              />
            </div>
            {/* Toggle filters button */}
            <button
              onClick={() => setFiltersOpen(!filtersOpen)}
              className={`flex items-center gap-1.5 px-3 py-2.5 rounded-lg text-sm transition-colors cursor-pointer ${
                filtersOpen || hasActiveFilters
                  ? 'bg-primary-500/15 text-primary-400 border border-primary-500/30'
                  : 'glass-input text-starlight-400 hover:text-starlight-200'
              }`}
            >
              <Filter size={14} />
              Filters
              {hasActiveFilters && (
                <span className="ml-1 w-4 h-4 rounded-full bg-primary-500 text-[10px] text-white flex items-center justify-center font-medium">
                  {[filterRisk, filterResult, filterAction, filterPlugin, dateFrom, dateTo].filter(Boolean).length}
                </span>
              )}
            </button>
          </div>

          {/* Collapsible filter controls */}
          <AnimatePresence>
            {filtersOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <Card variant="glass" padding="md" className="space-y-3">
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                    {/* Action type dropdown */}
                    <div>
                      <label className="block text-[10px] text-starlight-500 uppercase tracking-wider mb-1">Action Type</label>
                      <select
                        value={filterAction}
                        onChange={(e) => setFilterAction(e.target.value)}
                        className="w-full glass-input px-2.5 py-2 rounded-lg text-xs text-starlight-200 bg-midnight-400/60 border border-white/5 focus:outline-none focus:ring-1 focus:ring-primary-500/40 cursor-pointer"
                      >
                        <option value="">All</option>
                        {actionTypes.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </div>

                    {/* Plugin dropdown (Sprint-10 PR-5) -- narrow to a
                        specific plugin's skill invocations. Auto-implies
                        action_type='plugin.skill_invocation'. */}
                    <div data-testid="audit-filter-plugin">
                      <label className="block text-[10px] text-starlight-500 uppercase tracking-wider mb-1">Plugin</label>
                      <select
                        value={filterPlugin}
                        onChange={(e) => setFilterPlugin(e.target.value)}
                        className="w-full glass-input px-2.5 py-2 rounded-lg text-xs text-starlight-200 bg-midnight-400/60 border border-white/5 focus:outline-none focus:ring-1 focus:ring-primary-500/40 cursor-pointer"
                        aria-label="Filter by plugin"
                      >
                        <option value="">All plugins</option>
                        {pluginIds.map((pid) => (
                          <option key={pid} value={pid}>{pid}</option>
                        ))}
                      </select>
                    </div>

                    {/* Risk level dropdown */}
                    <div>
                      <label className="block text-[10px] text-starlight-500 uppercase tracking-wider mb-1">Risk Level</label>
                      <select
                        value={filterRisk}
                        onChange={(e) => setFilterRisk(e.target.value)}
                        className="w-full glass-input px-2.5 py-2 rounded-lg text-xs text-starlight-200 bg-midnight-400/60 border border-white/5 focus:outline-none focus:ring-1 focus:ring-primary-500/40 cursor-pointer"
                      >
                        <option value="">All</option>
                        {RISK_OPTIONS.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </div>

                    {/* Result dropdown */}
                    <div>
                      <label className="block text-[10px] text-starlight-500 uppercase tracking-wider mb-1">Result</label>
                      <select
                        value={filterResult}
                        onChange={(e) => setFilterResult(e.target.value)}
                        className="w-full glass-input px-2.5 py-2 rounded-lg text-xs text-starlight-200 bg-midnight-400/60 border border-white/5 focus:outline-none focus:ring-1 focus:ring-primary-500/40 cursor-pointer"
                      >
                        <option value="">All</option>
                        {RESULT_OPTIONS.map((r) => (
                          <option key={r} value={r}>{r === 'APPROVAL_REQUIRED' ? 'Approval Required' : r.charAt(0) + r.slice(1).toLowerCase()}</option>
                        ))}
                      </select>
                    </div>

                    {/* Date from */}
                    <div>
                      <label className="block text-[10px] text-starlight-500 uppercase tracking-wider mb-1">
                        <Calendar size={9} className="inline mr-1" />From
                      </label>
                      <input
                        type="date"
                        value={dateFrom}
                        onChange={(e) => setDateFrom(e.target.value)}
                        className="w-full glass-input px-2.5 py-2 rounded-lg text-xs text-starlight-200 bg-midnight-400/60 border border-white/5 focus:outline-none focus:ring-1 focus:ring-primary-500/40"
                      />
                    </div>

                    {/* Date to */}
                    <div>
                      <label className="block text-[10px] text-starlight-500 uppercase tracking-wider mb-1">
                        <Calendar size={9} className="inline mr-1" />To
                      </label>
                      <input
                        type="date"
                        value={dateTo}
                        onChange={(e) => setDateTo(e.target.value)}
                        className="w-full glass-input px-2.5 py-2 rounded-lg text-xs text-starlight-200 bg-midnight-400/60 border border-white/5 focus:outline-none focus:ring-1 focus:ring-primary-500/40"
                      />
                    </div>
                  </div>

                  {/* Clear filters */}
                  {hasActiveFilters && (
                    <button
                      onClick={clearFilters}
                      className="flex items-center gap-1 text-[11px] text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
                    >
                      <X size={12} />
                      Clear all filters
                    </button>
                  )}
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {loadError && !loading && (
          <Card variant="glass" padding="sm" className="border-status-error/20 bg-status-error/5 flex items-start gap-2">
            <ShieldAlert size={14} className="text-status-error shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-status-error">Audit log not loaded</p>
              <p className="text-[11px] text-starlight-400 mt-0.5">{loadError}</p>
            </div>
          </Card>
        )}

        {/* Batch action bar */}
        {filtered.length > 0 && (
          <div className="flex items-center gap-3 px-1">
            <button onClick={toggleSelectAll} className="flex items-center gap-1.5 text-xs text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer">
              {selectedIds.size === filtered.length && filtered.length > 0
                ? <CheckSquare size={14} className="text-primary-400" />
                : <Square size={14} />}
              {selectedIds.size > 0 ? `${selectedIds.size} selected` : 'Select all'}
            </button>

            {selectedIds.size > 0 && (
              <>
                <div className="w-px h-4 bg-white/10" />
                <button onClick={handleMarkReviewed} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-status-success/10 text-status-success hover:bg-status-success/20 transition-colors cursor-pointer">
                  <CheckCircle2 size={11} /> Mark reviewed
                </button>
                <button onClick={handleUnmarkReviewed} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-white/5 text-starlight-400 hover:bg-white/10 transition-colors cursor-pointer">
                  <Square size={11} /> Unmark
                </button>
                <span className="text-[10px] text-starlight-600 italic ml-1" title="Audit log is hash-chained and immutable. Use filters to narrow your view; entries cannot be deleted.">
                  (audit log is immutable by design)
                </span>
              </>
            )}

            <div className="ml-auto">
              <button onClick={handleExportJson} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-white/5 text-starlight-400 hover:bg-white/10 transition-colors cursor-pointer">
                <Download size={11} /> Export JSON{selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}
              </button>
            </div>
          </div>
        )}

        {/* Entries */}
        {loading ? (
          <Shimmer count={5} layout="list" />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={ScrollText}
            title={searchQuery || hasActiveFilters ? 'No entries match your filters' : 'No audit entries yet'}
            description={searchQuery || hasActiveFilters ? undefined : 'Send a message to generate governance events'}
            action={hasActiveFilters ? { label: 'Clear all filters', onClick: clearFilters } : undefined}
          />
        ) : (
          <div className="space-y-2">
            <AnimatePresence mode="popLayout">
              {filtered.map((entry, i) => {
                const isExpanded = expandedId === entry.id
                return (
                  <motion.div
                    key={entry.id}
                    layout
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.02 }}
                  >
                    <Card variant="glass" padding="none" className={`overflow-hidden ${reviewedIds.has(entry.id) ? 'opacity-60' : ''}`}>
                      <div className="flex items-start gap-0">
                        {/* Selection checkbox */}
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleSelect(entry.id) }}
                          className="shrink-0 p-3 text-starlight-500 hover:text-primary-400 transition-colors cursor-pointer"
                        >
                          {selectedIds.has(entry.id)
                            ? <CheckSquare size={14} className="text-primary-400" />
                            : <Square size={14} />}
                        </button>
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                        className="flex-1 flex items-start gap-3 pr-4 py-3 text-left hover:bg-white/[0.02] transition-colors cursor-pointer"
                      >
                        {reviewedIds.has(entry.id)
                          ? <CheckCircle2 size={14} className="shrink-0 mt-0.5 text-status-success" />
                          : <Shield size={14} className={`shrink-0 mt-0.5 ${RISK_COLORS[entry.risk_level] || 'text-starlight-500'}`} />}
                        <div className="flex-1 min-w-0 space-y-1">
                          {/* Primary: readable description */}
                          <p className="text-sm text-starlight-200 leading-snug">
                            {formatActionDescription(entry)}
                          </p>
                          {/* Secondary: badges + timestamp row */}
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant={
                              entry.result === 'BLOCKED' ? 'danger'
                                : (entry.governance_tier ?? 0) >= 3 ? 'warning'
                                : 'success'
                            } size="sm">
                              {entry.result === 'BLOCKED' ? 'Blocked'
                                : (entry.governance_tier ?? 0) >= 3 ? 'Approval Required'
                                : (entry.governance_tier ?? 0) >= 2 ? 'Notified'
                                : 'Logged'}
                            </Badge>
                            <span className={`text-[10px] font-medium ${RISK_COLORS[entry.risk_level] || 'text-starlight-500'}`}>
                              {entry.risk_level} risk
                            </span>
                            <span className="text-[10px] font-mono text-starlight-500">
                              Tier {entry.governance_tier}
                            </span>
                            <span className="text-[10px] text-starlight-600">
                              {new Date(entry.created_at).toLocaleString()}
                            </span>
                          </div>
                          {/* Integrity badge — small gray hash */}
                          {entry.entry_hash && (
                            <div className="flex items-center gap-1 mt-0.5">
                              <Lock size={8} className="text-starlight-600" />
                              <span className="text-[9px] font-mono text-starlight-600 truncate max-w-[200px]">
                                {entry.entry_hash}
                              </span>
                            </div>
                          )}
                        </div>
                        <motion.span
                          className="shrink-0 mt-1"
                          animate={{ rotate: isExpanded ? 180 : 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <ChevronDown size={14} className="text-starlight-500" />
                        </motion.span>
                      </button>

                      <AnimatePresence>
                        {isExpanded && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <AuditDetail entry={entry} />
                          </motion.div>
                        )}
                      </AnimatePresence>
                      </div>
                    </Card>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  )
}

export default GovernanceAuditPage
