/**
 * SecurityDashboardPage -- security operations command center.
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
  ShieldCheck,
  Crosshair,
  Terminal,
  Package,
  Download,
  Search,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Activity,
  Eye,
  EyeOff,
  Zap,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Target,
  Brain,
  Wrench,
  TrendingUp,
  Lock,
  Unlock,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'

// ── Types ──

interface DashboardStatus {
  evilbob_active: boolean
  environment: string
  activated_at: string
  activated_by: string
  capabilities: string[]
  shield_status: Record<string, boolean>
  tool_stats: {
    total_known: number
    total_installed: number
    total_capabilities: number
    categories: string[]
    installed_names: string[]
  }
  scan_history: ScanSummary[]
  self_improvement: {
    total_traces: number
    upgrades_triggered: number
    next_upgrade_at: number
    traces_until_next: number
  }
}

interface ScanSummary {
  scan_id: string
  target: string
  target_type: string
  total_findings: number
  cycles_used: number
  strategies_tried: string[]
  offensive_mode: boolean
  exploits_succeeded: number
  waf_detected: string
}

interface ToolInfo {
  name: string
  category: string
  description: string
  capabilities: string[]
  installed: boolean
  install_cmd: string
  offensive_only: boolean
}

interface ShieldDetails {
  evilbob_active: boolean
  departments: Record<string, {
    mode: string
    active: boolean
    role_summary: string
  }>
  total_offensive: number
  total_departments: number
}

// ── Category colors ──
const CATEGORY_COLORS: Record<string, string> = {
  recon: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
  scanning: 'text-status-warning bg-status-warning/10 border-status-warning/20',
  exploitation: 'text-status-error bg-status-error/10 border-status-error/20',
  credential: 'text-accent-purple bg-accent-purple/10 border-accent-purple/20',
  network: 'text-primary-400 bg-primary-400/10 border-primary-400/20',
  osint: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  fuzzing: 'text-status-success bg-status-success/10 border-status-success/20',
  wireless: 'text-starlight-400 bg-starlight-400/10 border-starlight-400/20',
  cloud: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
  container: 'text-primary-300 bg-primary-300/10 border-primary-300/20',
  web: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
  reporting: 'text-starlight-500 bg-starlight-500/10 border-starlight-500/20',
}

// ── Component ──

export function SecurityDashboardPage() {
  usePageTitle('Security Dashboard')

  const [status, setStatus] = useState<DashboardStatus | null>(null)
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [shields, setShields] = useState<ShieldDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Filters
  const [toolSearch, setToolSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [installedFilter, setInstalledFilter] = useState<'all' | 'installed' | 'missing'>('all')
  const [activeTab, setActiveTab] = useState<'overview' | 'tools' | 'scans' | 'shields' | 'missions'>('overview')

  // Expanded scan detail
  const [expandedScan, setExpandedScan] = useState<string | null>(null)
  const [scanDetail, setScanDetail] = useState<Record<string, unknown> | null>(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [statusRes, toolsRes, shieldsRes] = await Promise.all([
        api.get('/security/status'),
        api.get('/security/tools'),
        api.get('/security/shields'),
      ])
      setStatus(statusRes.data)
      setTools(toolsRes.data)
      setShields(shieldsRes.data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load security dashboard'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

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

  const s = status!
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
                Security Dashboard
              </h1>
              <p className="text-sm text-starlight-500">
                {isActive
                  ? 'Full-spectrum mode active -- offensive + defensive'
                  : 'Defensive mode'}
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
              {isActive ? 'OFFENSIVE' : 'DEFENSIVE'}
            </div>

            <button
              onClick={fetchAll}
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
          {(['overview', 'tools', 'scans', 'shields', 'missions'] as const).map(tab => (
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
              <OverviewTab status={s} shields={shields} />
            )}
            {activeTab === 'tools' && (
              <ToolsTab
                tools={filteredTools}
                allTools={tools}
                categories={categories}
                search={toolSearch}
                onSearchChange={setToolSearch}
                categoryFilter={categoryFilter}
                onCategoryChange={setCategoryFilter}
                installedFilter={installedFilter}
                onInstalledChange={setInstalledFilter}
              />
            )}
            {activeTab === 'scans' && (
              <ScansTab
                scans={s.scan_history}
                expandedScan={expandedScan}
                scanDetail={scanDetail}
                onExpandScan={loadScanDetail}
              />
            )}
            {activeTab === 'shields' && (
              <ShieldsTab shields={shields} />
            )}
            {activeTab === 'missions' && (
              <MissionsTab />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}

// ── Overview Tab ──

function OverviewTab({ status, shields }: { status: DashboardStatus; shields: ShieldDetails | null }) {
  const ts = status.tool_stats
  const si = status.self_improvement

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={<Package size={20} />}
          label="Tools Known"
          value={ts.total_known}
          sub={`${ts.total_installed} installed`}
          color="text-accent-cyan"
        />
        <StatCard
          icon={<Zap size={20} />}
          label="Capabilities"
          value={ts.total_capabilities}
          sub={`${(ts.categories || []).length} categories`}
          color="text-accent-amber"
        />
        <StatCard
          icon={<Target size={20} />}
          label="Scans Run"
          value={si.total_traces}
          sub={`${si.upgrades_triggered} upgrades`}
          color="text-status-success"
        />
        <StatCard
          icon={<Brain size={20} />}
          label="Next Upgrade"
          value={si.traces_until_next}
          sub="scans remaining"
          color="text-accent-purple"
        />
      </div>

      {/* Mode + capabilities */}
      {status.evilbob_active && (
        <Card className="p-4 border-status-error/20 bg-status-error/5">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="text-status-error" size={18} />
            <span className="text-sm font-medium text-status-error">
              Full-Spectrum Mode Active
            </span>
            {status.activated_at && (
              <span className="text-xs text-starlight-500 ml-auto">
                Since {status.activated_at}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {status.capabilities.map(cap => (
              <span
                key={cap}
                className="px-2 py-0.5 text-xs rounded bg-status-error/10
                           text-status-error/80 border border-status-error/20"
              >
                {cap}
              </span>
            ))}
          </div>
        </Card>
      )}

      {/* SHIELD summary */}
      {shields && shields.total_offensive > 0 && (
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="text-accent-amber" size={18} />
            <span className="text-sm font-medium text-starlight-200">
              Hidden SHIELD Activation
            </span>
            <span className="text-xs text-starlight-500 ml-auto">
              {shields.total_offensive}/{shields.total_departments} departments offensive
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {Object.entries(shields.departments).map(([dept, info]) => (
              <div
                key={dept}
                className={`
                  px-3 py-2 rounded-lg text-xs border
                  ${info.active
                    ? 'bg-status-error/5 border-status-error/20 text-status-error'
                    : 'bg-starlight-800/50 border-starlight-700 text-starlight-500'}
                `}
              >
                <div className="font-medium truncate">{dept}</div>
                <div className="opacity-70">{info.mode}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Recent scans */}
      {status.scan_history.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="text-accent-cyan" size={18} />
            <span className="text-sm font-medium text-starlight-200">
              Recent Scans
            </span>
          </div>
          <div className="space-y-2">
            {status.scan_history.slice(0, 5).map(scan => (
              <ScanRow key={scan.scan_id} scan={scan} />
            ))}
          </div>
        </Card>
      )}

      {/* Self-improvement progress */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp className="text-accent-purple" size={18} />
          <span className="text-sm font-medium text-starlight-200">
            Self-Improvement Loop
          </span>
        </div>
        <div className="space-y-2 text-sm text-starlight-400">
          <div className="flex justify-between">
            <span>Total scan traces archived</span>
            <span className="text-starlight-200">{si.total_traces}</span>
          </div>
          <div className="flex justify-between">
            <span>Upgrade cycles triggered</span>
            <span className="text-starlight-200">{si.upgrades_triggered}</span>
          </div>
          <div className="flex justify-between">
            <span>Next upgrade in</span>
            <span className="text-starlight-200">{si.traces_until_next} scans</span>
          </div>
          {/* Progress bar */}
          <div className="w-full bg-starlight-800 rounded-full h-1.5 mt-2">
            <div
              className="bg-accent-purple rounded-full h-1.5 transition-all"
              style={{
                width: `${si.next_upgrade_at > 0
                  ? ((si.next_upgrade_at - si.traces_until_next) / si.next_upgrade_at) * 100
                  : 0}%`
              }}
            />
          </div>
        </div>
      </Card>
    </div>
  )
}

// ── Tools Tab ──

function ToolsTab({
  tools, allTools, categories, search, onSearchChange,
  categoryFilter, onCategoryChange, installedFilter, onInstalledChange,
}: {
  tools: ToolInfo[]
  allTools: ToolInfo[]
  categories: string[]
  search: string
  onSearchChange: (v: string) => void
  categoryFilter: string
  onCategoryChange: (v: string) => void
  installedFilter: 'all' | 'installed' | 'missing'
  onInstalledChange: (v: 'all' | 'installed' | 'missing') => void
}) {
  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-starlight-500" />
          <input
            type="text"
            value={search}
            onChange={e => onSearchChange(e.target.value)}
            placeholder="Search tools or capabilities..."
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-starlight-800 border border-starlight-700
                       text-sm text-starlight-200 placeholder:text-starlight-600
                       focus:outline-none focus:border-primary-500/50"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={e => onCategoryChange(e.target.value)}
          className="px-3 py-2 rounded-lg bg-starlight-800 border border-starlight-700
                     text-sm text-starlight-300 focus:outline-none"
        >
          <option value="">All categories</option>
          {categories.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>

        <div className="flex items-center rounded-lg border border-starlight-700 overflow-hidden">
          {(['all', 'installed', 'missing'] as const).map(f => (
            <button
              key={f}
              onClick={() => onInstalledChange(f)}
              className={`
                px-3 py-2 text-xs font-medium capitalize transition-colors
                ${installedFilter === f
                  ? 'bg-primary-600 text-white'
                  : 'bg-starlight-800 text-starlight-400 hover:text-starlight-200'}
              `}
            >
              {f}
            </button>
          ))}
        </div>

        <span className="text-xs text-starlight-500">
          {tools.length}/{allTools.length} tools
        </span>
      </div>

      {/* Tool grid */}
      {tools.length === 0 ? (
        <EmptyState
          icon={<Package className="text-starlight-500" size={40} />}
          title="No tools match"
          description="Try adjusting your filters"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {tools.map(tool => (
            <ToolCard key={tool.name} tool={tool} />
          ))}
        </div>
      )}
    </div>
  )
}

function ToolCard({ tool }: { tool: ToolInfo }) {
  const [showCmd, setShowCmd] = useState(false)
  const catColor = CATEGORY_COLORS[tool.category] || 'text-starlight-400 bg-starlight-800 border-starlight-700'

  return (
    <Card className="p-3 space-y-2">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Wrench size={14} className="text-starlight-400 flex-shrink-0" />
          <span className="text-sm font-medium text-starlight-200">{tool.name}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {tool.offensive_only && (
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-status-error/10
                             text-status-error border border-status-error/20">
              OFF
            </span>
          )}
          {tool.installed ? (
            <CheckCircle2 size={14} className="text-status-success" />
          ) : (
            <XCircle size={14} className="text-starlight-600" />
          )}
        </div>
      </div>

      <p className="text-xs text-starlight-500 line-clamp-2">{tool.description}</p>

      <div className="flex items-center gap-1.5 flex-wrap">
        <span className={`px-1.5 py-0.5 text-[10px] rounded border ${catColor}`}>
          {tool.category}
        </span>
        {tool.capabilities.slice(0, 3).map(cap => (
          <span
            key={cap}
            className="px-1.5 py-0.5 text-[10px] rounded
                       bg-starlight-800 text-starlight-500 border border-starlight-700"
          >
            {cap.replace(/_/g, ' ')}
          </span>
        ))}
        {tool.capabilities.length > 3 && (
          <span className="text-[10px] text-starlight-600">
            +{tool.capabilities.length - 3}
          </span>
        )}
      </div>

      {!tool.installed && (
        <button
          onClick={() => setShowCmd(!showCmd)}
          className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300
                     transition-colors mt-1"
        >
          <Terminal size={12} />
          {showCmd ? 'Hide' : 'Install command'}
        </button>
      )}

      <AnimatePresence>
        {showCmd && !tool.installed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <pre className="text-[10px] text-accent-cyan bg-starlight-900 rounded p-2 overflow-x-auto
                            border border-starlight-800">
              {tool.install_cmd}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}

// ── Scans Tab ──

function ScansTab({
  scans, expandedScan, scanDetail, onExpandScan,
}: {
  scans: ScanSummary[]
  expandedScan: string | null
  scanDetail: Record<string, unknown> | null
  onExpandScan: (id: string) => void
}) {
  if (scans.length === 0) {
    return (
      <EmptyState
        icon={<Crosshair className="text-starlight-500" size={40} />}
        title="No scans yet"
        description="No scans recorded yet"
      />
    )
  }

  return (
    <div className="space-y-2">
      {scans.map(scan => (
        <div key={scan.scan_id}>
          <button
            onClick={() => onExpandScan(scan.scan_id)}
            className="w-full text-left"
          >
            <ScanRow scan={scan} expanded={expandedScan === scan.scan_id} />
          </button>

          <AnimatePresence>
            {expandedScan === scan.scan_id && scanDetail && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <Card className="p-4 ml-4 mt-1 mb-2 border-starlight-700">
                  <pre className="text-xs text-starlight-400 overflow-x-auto max-h-96 overflow-y-auto">
                    {JSON.stringify(scanDetail, null, 2)}
                  </pre>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  )
}

function ScanRow({ scan, expanded }: { scan: ScanSummary; expanded?: boolean }) {
  return (
    <Card className={`
      p-3 flex items-center gap-3 transition-colors
      ${expanded ? 'border-primary-500/30' : 'hover:border-starlight-600'}
    `}>
      <div className={`
        p-1.5 rounded
        ${scan.offensive_mode ? 'bg-status-error/10 text-status-error' : 'bg-starlight-800 text-starlight-400'}
      `}>
        <Target size={14} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-starlight-200 truncate">
            {scan.target || scan.scan_id}
          </span>
          {scan.waf_detected && (
            <span className="px-1.5 py-0.5 text-[10px] rounded
                             bg-status-warning/10 text-status-warning border border-status-warning/20">
              WAF: {scan.waf_detected}
            </span>
          )}
        </div>
        <div className="text-xs text-starlight-500 mt-0.5">
          {scan.cycles_used} cycles, {scan.strategies_tried.length} strategies
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs">
        <div className="text-center">
          <div className="text-starlight-200 font-medium">{scan.total_findings}</div>
          <div className="text-starlight-600">findings</div>
        </div>
        {scan.exploits_succeeded > 0 && (
          <div className="text-center">
            <div className="text-status-error font-medium">{scan.exploits_succeeded}</div>
            <div className="text-starlight-600">exploited</div>
          </div>
        )}
      </div>

      <ChevronRight
        size={14}
        className={`text-starlight-600 transition-transform ${expanded ? 'rotate-90' : ''}`}
      />
    </Card>
  )
}

// ── Shields Tab ──

function ShieldsTab({ shields }: { shields: ShieldDetails | null }) {
  if (!shields) {
    return (
      <EmptyState
        icon={<Shield className="text-starlight-500" size={40} />}
        title="SHIELD data unavailable"
        description="SHIELD data not available"
      />
    )
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-1">
          <Shield className="text-accent-amber" size={18} />
          <span className="text-sm font-medium text-starlight-200">
            Department SHIELD Status
          </span>
        </div>
        <p className="text-xs text-starlight-500 mb-4">
          When full-spectrum mode activates, every department's SHIELD sub-capability gets
          an offensive security prompt overlay. This is invisible to the user
          but transforms each department into a security operator.
        </p>

        <div className="space-y-2">
          {Object.entries(shields.departments).map(([dept, info]) => (
            <div
              key={dept}
              className={`
                p-3 rounded-lg border flex items-start gap-3
                ${info.active
                  ? 'bg-status-error/5 border-status-error/20'
                  : 'bg-starlight-800/30 border-starlight-700'}
              `}
            >
              <div className={`p-1.5 rounded ${info.active ? 'bg-status-error/10' : 'bg-starlight-800'}`}>
                {info.active ? (
                  <ShieldAlert size={16} className="text-status-error" />
                ) : (
                  <ShieldCheck size={16} className="text-starlight-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-starlight-200">{dept}</span>
                  <span className={`
                    px-1.5 py-0.5 text-[10px] rounded font-medium
                    ${info.active
                      ? 'bg-status-error/15 text-status-error'
                      : 'bg-starlight-800 text-starlight-500'}
                  `}>
                    {info.mode.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-starlight-500 mt-1 line-clamp-2">
                  {info.role_summary}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Summary bar */}
      <div className="flex items-center gap-4 text-sm text-starlight-400">
        <div className="flex items-center gap-1.5">
          <ShieldAlert size={14} className="text-status-error" />
          <span>{shields.total_offensive} offensive</span>
        </div>
        <div className="flex items-center gap-1.5">
          <ShieldCheck size={14} className="text-starlight-500" />
          <span>{shields.total_departments - shields.total_offensive} defensive</span>
        </div>
      </div>
    </div>
  )
}

// ── Shared components ──

function StatCard({
  icon, label, value, sub, color,
}: {
  icon: React.ReactNode
  label: string
  value: number
  sub: string
  color: string
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className={color}>{icon}</span>
        <span className="text-xs text-starlight-500">{label}</span>
      </div>
      <div className="text-2xl font-semibold text-starlight-100">{value}</div>
      <div className="text-xs text-starlight-500 mt-0.5">{sub}</div>
    </Card>
  )
}

// ── Missions Tab ──

interface MissionInfo {
  mission_id: string
  goal: string
  target: string
  status: string
  engagement_level: string
  paths_total?: number
  nodes_discovered?: number
}

function MissionsTab() {
  const [missions, setMissions] = useState<MissionInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [goal, setGoal] = useState('')
  const [target, setTarget] = useState('')
  const [level, setLevel] = useState('pentest')
  const [selectedMission, setSelectedMission] = useState<string | null>(null)
  const [missionDetail, setMissionDetail] = useState<Record<string, unknown> | null>(null)

  const loadMissions = useCallback(async () => {
    try {
      const res = await api.get('/missions/active')
      setMissions(res.data)
    } catch {
      // No active missions
    }
  }, [])

  useEffect(() => { loadMissions() }, [loadMissions])

  const startMission = async () => {
    if (!goal || !target) return
    setLoading(true)
    try {
      const res = await api.post('/missions/start', {
        goal, target, engagement_level: level,
      })
      setGoal('')
      setTarget('')
      loadMissions()
      setSelectedMission(res.data.mission_id)
      loadMissionDetail(res.data.mission_id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start mission'
      alert(msg)
    } finally {
      setLoading(false)
    }
  }

  const loadMissionDetail = async (mid: string) => {
    try {
      const [statusRes, pathsRes] = await Promise.all([
        api.get(`/missions/${mid}/status`),
        api.get(`/missions/${mid}/paths`),
      ])
      setMissionDetail({
        status: statusRes.data,
        paths: pathsRes.data,
      })
    } catch {
      // Error loading detail
    }
  }

  const executeStep = async (mid: string) => {
    try {
      await api.post(`/missions/${mid}/execute`)
      loadMissionDetail(mid)
    } catch {
      // Error executing
    }
  }

  const LEVEL_COLORS: Record<string, string> = {
    audit: 'text-accent-cyan',
    pentest: 'text-status-warning',
    red_team: 'text-status-error',
    adversary: 'text-accent-purple',
  }

  return (
    <div className="space-y-6">
      {/* Start new mission */}
      <Card className="p-4">
        <h3 className="text-sm font-medium text-starlight-300 mb-3 flex items-center gap-2">
          <Crosshair size={16} className="text-accent-amber" />
          Start Mission
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            type="text"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            placeholder="Goal (e.g., Prove database access)"
            className="px-3 py-2 bg-starlight-900 border border-starlight-700 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-600 focus:border-accent-amber/50 focus:outline-none"
          />
          <input
            type="text"
            value={target}
            onChange={e => setTarget(e.target.value)}
            placeholder="Target (e.g., target.com)"
            className="px-3 py-2 bg-starlight-900 border border-starlight-700 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-600 focus:border-accent-amber/50 focus:outline-none"
          />
          <select
            value={level}
            onChange={e => setLevel(e.target.value)}
            className="px-3 py-2 bg-starlight-900 border border-starlight-700 rounded-lg text-sm text-starlight-200 focus:border-accent-amber/50 focus:outline-none"
          >
            <option value="audit">Audit</option>
            <option value="pentest">Pentest</option>
            <option value="red_team">Red Team</option>
            <option value="adversary">Adversary</option>
          </select>
          <button
            onClick={startMission}
            disabled={loading || !goal || !target}
            className="px-4 py-2 bg-accent-amber/20 text-accent-amber border border-accent-amber/30 rounded-lg text-sm font-medium hover:bg-accent-amber/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Planning...' : 'Launch Mission'}
          </button>
        </div>
      </Card>

      {/* Active missions */}
      {missions.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-starlight-400">Active Missions</h3>
          {missions.map(m => (
            <Card
              key={m.mission_id}
              className={`p-4 cursor-pointer transition-colors ${
                selectedMission === m.mission_id ? 'border-accent-amber/50' : 'hover:border-starlight-600'
              }`}
              onClick={() => { setSelectedMission(m.mission_id); loadMissionDetail(m.mission_id) }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-starlight-200 font-medium">{m.goal}</div>
                  <div className="text-xs text-starlight-500 mt-1">
                    Target: {m.target}
                    <span className={`ml-3 ${LEVEL_COLORS[m.engagement_level] || ''}`}>
                      {m.engagement_level?.toUpperCase()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={m.status === 'planned' ? 'warning' : m.status === 'executing' ? 'error' : 'success'}>
                    {m.status}
                  </Badge>
                  <button
                    onClick={e => { e.stopPropagation(); executeStep(m.mission_id) }}
                    className="px-3 py-1 bg-status-error/20 text-status-error border border-status-error/30 rounded text-xs hover:bg-status-error/30 transition-colors"
                  >
                    Execute Next
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Mission detail */}
      {selectedMission && missionDetail && (
        <Card className="p-4">
          <h3 className="text-sm font-medium text-starlight-300 mb-3">
            Mission Detail: {selectedMission}
          </h3>
          {/* Status */}
          {missionDetail.status && typeof missionDetail.status === 'object' && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              {['paths_total', 'paths_completed', 'paths_failed', 'nodes_discovered'].map(key => (
                <div key={key} className="bg-starlight-900 rounded-lg p-3">
                  <div className="text-xs text-starlight-500 capitalize">{key.replace(/_/g, ' ')}</div>
                  <div className="text-lg font-semibold text-starlight-200 mt-1">
                    {(missionDetail.status as Record<string, unknown>)[key] as number ?? 0}
                  </div>
                </div>
              ))}
            </div>
          )}
          {/* Attack paths */}
          {Array.isArray(missionDetail.paths) && (missionDetail.paths as Array<Record<string, unknown>>).map((path, i) => (
            <div key={i} className="mb-3 bg-starlight-900 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-starlight-300 font-medium capitalize">
                  {(path.type as string) ?? 'unknown'} Path
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-starlight-500">
                    Feasibility: {((path.feasibility as number) * 100).toFixed(0)}%
                  </span>
                  <Badge variant={(path.status as string) === 'planned' ? 'warning' : 'success'}>
                    {path.status as string}
                  </Badge>
                </div>
              </div>
              {Array.isArray(path.step_details) && (path.step_details as Array<Record<string, string>>).map((step, j) => (
                <div key={j} className="flex items-center gap-2 py-1 text-xs">
                  <span className={
                    step.status === 'succeeded' ? 'text-status-success' :
                    step.status === 'failed' ? 'text-status-error' :
                    'text-starlight-500'
                  }>
                    {step.status === 'succeeded' ? '\u2713' : step.status === 'failed' ? '\u2717' : '\u25CB'}
                  </span>
                  <span className="text-starlight-400">{step.description}</span>
                  <span className="text-starlight-600 ml-auto">{step.module}</span>
                </div>
              ))}
            </div>
          ))}
        </Card>
      )}

      {/* Empty state */}
      {missions.length === 0 && !loading && (
        <EmptyState
          icon={<Crosshair size={40} />}
          title="No Active Missions"
          description="Start a mission to begin autonomous red team operations. Daena will plan attack paths, map the target's proximity rings, and execute step by step."
        />
      )}
    </div>
  )
}

export default SecurityDashboardPage
