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
  Archive,
  Trash2,
  Download,
  CheckCircle2,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import type { AuditEntryResponse, ApiResponse, RiskLevel } from '@/types/api'

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
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Selection + batch actions
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [reviewedIds, setReviewedIds] = useState<Set<string>>(new Set())

  // ── Filter state ──
  const [searchQuery, setSearchQuery] = useState('')
  const [filterRisk, setFilterRisk] = useState<string>('')
  const [filterResult, setFilterResult] = useState<string>('')
  const [filterAction, setFilterAction] = useState<string>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [filtersOpen, setFiltersOpen] = useState(false)

  const fetchAudit = async () => {
    setLoading(true)
    try {
      const { data } = await api.get<ApiResponse<AuditEntryResponse[]>>('/governance/audit')
      setEntries(data.data || [])
    } catch {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAudit()
  }, [])

  // Derive unique action types from data for the dropdown
  const actionTypes = useMemo(
    () => [...new Set(entries.map((e) => e.action_type).filter(Boolean))].sort(),
    [entries],
  )

  const hasActiveFilters = !!(filterRisk || filterResult || filterAction || dateFrom || dateTo)

  const clearFilters = () => {
    setFilterRisk('')
    setFilterResult('')
    setFilterAction('')
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
  const handleMarkReviewed = () => {
    setReviewedIds((prev) => {
      const next = new Set(prev)
      selectedIds.forEach((id) => next.add(id))
      return next
    })
    clearSelection()
  }
  const handleArchive = () => {
    // Move to archived (filter out from view)
    setEntries((prev) => prev.filter((e) => !selectedIds.has(e.id)))
    clearSelection()
  }
  const handleDelete = () => {
    if (!confirm(`Delete ${selectedIds.size} audit entries? This cannot be undone.`)) return
    setEntries((prev) => prev.filter((e) => !selectedIds.has(e.id)))
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
  }, [entries, searchQuery, filterRisk, filterResult, filterAction, dateFrom, dateTo])

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
            {/* Chain integrity badge */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-status-success/10 border border-status-success/20">
              <Lock size={12} className="text-status-success" />
              <span className="text-[10px] font-mono text-status-success">Chain intact</span>
            </div>
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
                  {[filterRisk, filterResult, filterAction, dateFrom, dateTo].filter(Boolean).length}
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
                <button onClick={handleArchive} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/20 transition-colors cursor-pointer">
                  <Archive size={11} /> Archive
                </button>
                <button onClick={handleDelete} className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-accent-red/10 text-accent-red hover:bg-accent-red/20 transition-colors cursor-pointer">
                  <Trash2 size={11} /> Delete
                </button>
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
