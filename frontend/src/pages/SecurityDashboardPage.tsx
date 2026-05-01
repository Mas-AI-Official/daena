/**
 * SecurityDashboardPage -- security operations command center.
 * (Split refactor 2026-04-25; types.ts renamed to types.tsx for JSX exports.)
 *
 * Thin orchestrator: header + mode indicator + tab nav + lifted state.
 * Each tab is its own component under ./security/. Per-tab fetches and
 * widget logic live there; this page only owns cross-tab state
 * (governance status, tool catalog + filters, expanded scan detail)
 * so a tab swap doesn't reset the dashboard.
 *
 * Consumes /api/v1/security/* endpoints:
 *   GET /status  -- mode, shields, tools, history, self-improvement
 *   GET /tools   -- catalog with filters
 *   GET /tools/recommend -- recommendations for target type
 *   GET /scans   -- recent scan traces
 *   GET /scans/:id -- full trace detail
 *   GET /shields -- per-department SHIELD activation
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Shield,
  ShieldAlert,
  RefreshCw,
  Lock,
  Unlock,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'

import SecurityOverview from './security/SecurityOverview'
import SecurityTools from './security/SecurityTools'
import SecurityScans from './security/SecurityScans'
import SecurityShields from './security/SecurityShields'
import SecurityMissions from './security/SecurityMissions'
import {
  type DashboardStatus,
  type ToolInfo,
  type ShieldDetails,
  type OpsecStatus,
  type InstalledFilter,
} from './security/types'

type TabId = 'overview' | 'tools' | 'scans' | 'shields' | 'missions'
const TABS: readonly TabId[] = ['overview', 'tools', 'scans', 'shields', 'missions'] as const

// F-SECURITY-CACHE: module-level 30s cache mirrors DashboardPage's pattern.
// Without this, every tab-bounce to /security re-fired 4 parallel
// /security/* fetches plus the lazy-chunk parse, contributing to the
// "chat feels heavy after security tabs" complaint. Cold-load still
// fetches; subsequent visits inside 30s hit the cache instantly.
const SECURITY_CACHE_TTL_MS = 30_000
const SECURITY_REQUEST_TIMEOUT_MS = 10_000
interface SecurityCache {
  ts: number
  status: DashboardStatus | null
  tools: ToolInfo[]
  shields: ShieldDetails | null
  opsec: OpsecStatus | null
}
let securityCache: SecurityCache | null = null

export function SecurityDashboardPage() {
  usePageTitle('Security Dashboard')

  const cachedFresh = securityCache && Date.now() - securityCache.ts < SECURITY_CACHE_TTL_MS
  const [status, setStatus] = useState<DashboardStatus | null>(cachedFresh ? securityCache!.status : null)
  const [tools, setTools] = useState<ToolInfo[]>(cachedFresh ? securityCache!.tools : [])
  const [shields, setShields] = useState<ShieldDetails | null>(cachedFresh ? securityCache!.shields : null)
  const [opsec, setOpsec] = useState<OpsecStatus | null>(cachedFresh ? securityCache!.opsec : null)
  const [loading, setLoading] = useState(!cachedFresh)
  const [error, setError] = useState('')

  // Filters live on the parent so they survive tab switches and the
  // bulk-install button can read the current category filter.
  const [toolSearch, setToolSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [installedFilter, setInstalledFilter] = useState<InstalledFilter>('all')
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  // Expanded scan detail -- lifted so the cached payload survives a
  // tab-swap back to Scans.
  const [expandedScan, setExpandedScan] = useState<string | null>(null)
  const [scanDetail, setScanDetail] = useState<Record<string, unknown> | null>(null)

  const fetchAll = useCallback(async (showLoader = true) => {
    if (showLoader) setLoading(true)
    setError('')
    // 2026-04-30 stabilization: switched from Promise.all to allSettled so
    // partial backend availability (e.g. /security/tools is the slow one,
    // ~5s; if it tips over the 10s ceiling under jitter the whole page
    // used to fail with "Security Dashboard Unavailable"). Now each
    // section renders independently and only the truly empty page shows
    // the unavailable card. Per-section "section unavailable" hints will
    // be rendered downstream.
    const results = await Promise.allSettled([
      api.get('/security/status', { timeout: SECURITY_REQUEST_TIMEOUT_MS }),
      api.get('/security/tools', { timeout: SECURITY_REQUEST_TIMEOUT_MS }),
      api.get('/security/shields', { timeout: SECURITY_REQUEST_TIMEOUT_MS }),
      api.get('/security/opsec/status', { timeout: SECURITY_REQUEST_TIMEOUT_MS }),
    ])

    const [statusR, toolsR, shieldsR, opsecR] = results
    const nextStatus = statusR.status === 'fulfilled' ? statusR.value.data : null
    const nextTools = toolsR.status === 'fulfilled' ? toolsR.value.data : []
    const nextShields = shieldsR.status === 'fulfilled' ? shieldsR.value.data : null
    const nextOpsec = opsecR.status === 'fulfilled' ? opsecR.value.data : null

    setStatus(nextStatus)
    setTools(nextTools)
    setShields(nextShields)
    setOpsec(nextOpsec)

    // Only declare the dashboard "unavailable" when the headline /status
    // failed AND we have nothing else useful to render. Otherwise we
    // render what we have.
    if (statusR.status === 'rejected' && toolsR.status === 'rejected' && shieldsR.status === 'rejected') {
      const reason = statusR.reason
      const msg = reason instanceof Error
        ? `Security Ops backend request failed: ${reason.message}`
        : 'Security Ops backend request failed before a response was returned'
      setError(msg)
    } else {
      // Cache only when we have at least the headline status payload --
      // otherwise we'd serve partial/incomplete data on subsequent mounts.
      if (nextStatus) {
        securityCache = {
          ts: Date.now(),
          status: nextStatus,
          tools: nextTools,
          shields: nextShields,
          opsec: nextOpsec,
        }
      }
    }
    if (showLoader) setLoading(false)
  }, [])

  useEffect(() => {
    // Skip the 4-call burst entirely if cache is fresh.
    if (securityCache && Date.now() - securityCache.ts < SECURITY_CACHE_TTL_MS) return
    fetchAll()
  }, [fetchAll])

  useEffect(() => {
    if (loading) return
    const toolInventoryRefreshing = Boolean(status?.tool_stats?.refreshing)
      || tools.some(t => t.install_state === 'pending' || t.install_state === 'stale')
    if (!toolInventoryRefreshing) return

    const timeout = window.setTimeout(() => {
      fetchAll(false)
    }, 2500)
    return () => window.clearTimeout(timeout)
  }, [fetchAll, loading, status?.tool_stats?.refreshing, tools])

  // Filtered tools
  const filteredTools = useMemo(() => {
    let result = tools
    if (toolSearch) {
      const q = toolSearch.toLowerCase()
      result = result.filter(
        t => t.name.toLowerCase().includes(q)
          || t.description.toLowerCase().includes(q)
          || t.capabilities.some(c => c.toLowerCase().includes(q))
      )
    }
    if (categoryFilter) {
      result = result.filter(t => t.category === categoryFilter)
    }
    if (installedFilter === 'installed') {
      result = result.filter(t => t.installed)
    } else if (installedFilter === 'missing') {
      result = result.filter(t => !t.installed)
    }
    return result
  }, [tools, toolSearch, categoryFilter, installedFilter])

  // Categories for filter
  const categories = useMemo(() => {
    const cats = new Set(tools.map(t => t.category))
    return Array.from(cats).sort()
  }, [tools])

  // Fetch scan detail
  const loadScanDetail = async (scanId: string) => {
    if (expandedScan === scanId) {
      setExpandedScan(null)
      setScanDetail(null)
      return
    }
    setExpandedScan(scanId)
    try {
      const res = await api.get(`/security/scans/${scanId}`)
      setScanDetail(res.data)
    } catch {
      setScanDetail(null)
    }
  }

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
          <Shimmer count={6} layout="list" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-8">
          <EmptyState
            icon={<ShieldAlert className="text-status-error" size={48} />}
            title="Security Dashboard Unavailable"
            description={error}
            action={{ label: 'Retry', onClick: fetchAll }}
          />
        </div>
      </div>
    )
  }

  const s: DashboardStatus = status ?? {
    evilbob_active: false,
    environment: '',
    activated_at: '',
    activated_by: '',
    capabilities: [],
    shield_status: {},
    tool_stats: {
      total_known: tools.length,
      total_installed: tools.filter((tool) => tool.installed).length,
      total_capabilities: categories.length,
      categories,
      installed_names: tools.filter((tool) => tool.installed).map((tool) => tool.name),
    },
    scan_history: [],
    self_improvement: {
      total_traces: 0,
      upgrades_triggered: 0,
      next_upgrade_at: 10,
      traces_until_next: 10,
    },
  }
  const isActive = s.evilbob_active

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        {/* ── Header ── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isActive ? (
              <ShieldAlert className="text-status-error" size={28} />
            ) : (
              <Shield className="text-starlight-500" size={28} />
            )}
            <div>
              <h1 className="text-xl font-semibold text-starlight-100">
                Security Operations Center
              </h1>
              <p className="text-sm text-starlight-500">
                {isActive
                  ? 'Elevated authorized security mode active'
                  : 'Defensive mode -- live shield counters, scan history, threat feed'}
              </p>
              {/*
                Audit-fix banner (2026-04-xx). Keeps users from confusing
                this dashboard ("what is being blocked") with Scan Scope
                in the sidebar ("what should we be scanning"). Do not
                remove without an explicit re-design ticket -- it was
                added to resolve cross-page confusion the audit caught.
              */}
              <p className="text-xs text-starlight-600 mt-0.5">
                This page shows WHAT Daena is blocking and monitoring.
                To declare scan targets, use <span className="text-primary-400">Scan Scope</span> in the sidebar.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Mode indicator */}
            <div className={`
              flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium
              ${isActive
                ? 'bg-status-error/15 text-status-error border border-status-error/30'
                : 'bg-starlight-800 text-starlight-400 border border-starlight-700'}
            `}>
              {isActive ? <Unlock size={14} /> : <Lock size={14} />}
              {isActive ? 'ELEVATED' : 'DEFENSIVE'}
            </div>

            <button
              onClick={() => fetchAll()}
              className="p-2 rounded-lg hover:bg-starlight-800 text-starlight-400
                         hover:text-starlight-200 transition-colors"
              title="Refresh"
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {/* ── Tab bar ── */}
        <div className="flex items-center gap-1 border-b border-starlight-800 pb-px">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                px-4 py-2 text-sm font-medium capitalize rounded-t-lg transition-colors
                ${activeTab === tab
                  ? 'text-accent-amber border-b-2 border-accent-amber bg-accent-amber/5'
                  : 'text-starlight-500 hover:text-starlight-300 hover:bg-starlight-800/50'}
              `}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* ── Tab content ── */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
          >
            {activeTab === 'overview' && (
              <SecurityOverview status={s} shields={shields} opsec={opsec} />
            )}
            {activeTab === 'tools' && (
              <SecurityTools
                tools={filteredTools}
                allTools={tools}
                categories={categories}
                search={toolSearch}
                onSearchChange={setToolSearch}
                categoryFilter={categoryFilter}
                onCategoryChange={setCategoryFilter}
                installedFilter={installedFilter}
                onInstalledChange={setInstalledFilter}
                onReload={fetchAll}
              />
            )}
            {activeTab === 'scans' && (
              <SecurityScans
                scans={s.scan_history}
                expandedScan={expandedScan}
                scanDetail={scanDetail}
                onExpandScan={loadScanDetail}
              />
            )}
            {activeTab === 'shields' && (
              <SecurityShields shields={shields} />
            )}
            {activeTab === 'missions' && (
              <SecurityMissions />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

export default SecurityDashboardPage
