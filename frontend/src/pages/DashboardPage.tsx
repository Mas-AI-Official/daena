/**
 * DashboardPage — Control Room with hex hive visualization.
 * Sunflower hive (Daena center + 10 department hexagons) +
 * system status badges + governance pulse + quick actions.
 */
import { useEffect, useState, memo } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  MessageSquare,
  ShieldCheck,
  Brain,
  Bot,
  Activity,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  Zap,
  DollarSign,
  Shield,
  Cpu,
  FolderKanban,
  BarChart3,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card } from '@/components/common'
import { SunflowerHive } from '@/components/visualizations/SunflowerHive'
import type { HiveDepartment } from '@/components/visualizations/SunflowerHive'
import { useUiStore } from '@/stores/uiStore'
import { api } from '@/lib/api'

// ── Stat card component ──

interface StatCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
  trend?: string
  trendUp?: boolean
  color: string
  delay?: number
  /** F-DASH-CLICKABLE fix: optional click target so e.g. "Pending Approvals: 5"
   *  navigates to /governance/approvals instead of being decoration-only. */
  linkTo?: string
  onClick?: () => void
}

const StatCard = memo(function StatCard({ label, value, icon, trend, trendUp, color, delay = 0, linkTo, onClick }: StatCardProps) {
  const navigate = useNavigate()
  const interactive = Boolean(linkTo || onClick)
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      onClick={interactive ? () => { if (onClick) onClick(); else if (linkTo) navigate(linkTo) } : undefined}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={interactive ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick ? onClick() : (linkTo && navigate(linkTo)) } } : undefined}
      className={interactive ? 'cursor-pointer' : undefined}
    >
      <Card variant="glass" padding="md" className={`group transition-all ${interactive ? 'hover:border-primary-400/30 hover:bg-white/[0.03]' : 'hover:border-white/10'}`}>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-starlight-400 mb-1">{label}</p>
            <p className="text-2xl font-display font-bold text-starlight-100">{value}</p>
            {trend && (
              <p className={`text-[10px] mt-1 flex items-center gap-1 ${trendUp ? 'text-status-success' : 'text-starlight-500'}`}>
                {trendUp && <TrendingUp size={10} />}
                {trend}
              </p>
            )}
          </div>
          <div className={`p-2.5 rounded-lg ${color}`}>{icon}</div>
        </div>
      </Card>
    </motion.div>
  )
})

// ── Status badge ──

function StatusBadge({ label, value, icon, variant }: {
  label: string
  value: string
  icon: React.ReactNode
  variant: 'success' | 'warning' | 'info' | 'danger'
}) {
  const colors = {
    success: 'bg-status-success/10 border-status-success/20 text-status-success',
    warning: 'bg-status-warning/10 border-status-warning/20 text-status-warning',
    info: 'bg-primary-500/10 border-primary-500/20 text-primary-400',
    danger: 'bg-status-error/10 border-status-error/20 text-status-error',
  }
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${colors[variant]}`}>
      {icon}
      <div>
        <p className="text-[10px] text-starlight-500">{label}</p>
        <p className="text-xs font-semibold">{value}</p>
      </div>
    </div>
  )
}

// ── Activity item ──

interface ActivityItem {
  id: string
  type: 'chat' | 'approval' | 'agent' | 'alert'
  title: string
  description: string
  time: string
}

const ICON_MAP = {
  chat: <MessageSquare size={14} className="text-primary-400" />,
  approval: <CheckCircle2 size={14} className="text-status-success" />,
  agent: <Bot size={14} className="text-accent-cyan" />,
  alert: <AlertTriangle size={14} className="text-status-warning" />,
}

// ── Relative time helper ──

function formatRelativeTime(dateString: string): string {
  const now = Date.now()
  const then = new Date(dateString).getTime()
  // F-DATE-EPOCH defensive: legacy rows with NULL created_at coerce to
  // Unix epoch 0 (1970-01-01) and render as "20568d ago". Treat any
  // pre-2020 timestamp as "no date" to hide the symptom while the
  // backend backfill migration runs.
  if (!Number.isFinite(then) || then < 1577836800000) return ''
  const diffMs = now - then
  if (diffMs < 0) return 'just now'
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

// ── Action type to activity type mapping ──

function mapActionType(actionType: string): ActivityItem['type'] {
  const upper = actionType.toUpperCase()
  if (upper.includes('APPROVAL')) return 'approval'
  if (upper === 'LLM_CALL' || upper.includes('CHAT') || upper.includes('MESSAGE')) return 'chat'
  if (upper.includes('SKILL') || upper.includes('AGENT') || upper.includes('INGESTION')) return 'agent'
  return 'alert'
}

function formatActionTitle(actionType: string): string {
  return actionType
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

const DEPT_SHORT_NAMES: Record<string, string> = {
  'Legal & Compliance': 'Legal',
  'Skill Governance': 'Skill Gov',
  'Security Operations': 'Security Ops',
}

function shortenDeptName(name: string): string {
  return DEPT_SHORT_NAMES[name] || name
}

// ── Module-level cache for the 9-call dashboard burst.
// Without this, every remount (sidebar nav, focus return, StrictMode double
// invoke in dev) refetches everything. TTL=30s matches the health poll
// cadence below — it's stale enough that one tab refresh always works,
// fresh enough that quick nav back is instant.
const CACHE_TTL_MS = 30_000
interface DashboardCache {
  ts: number
  stats: {
    sessions: number
    pendingApprovals: number
    blockedApprovals: number
    memories: number
    activeAgents: number
    pipelineTotal: number
    runtimesOnline: number
    runtimesTotal: number  // F-DASH-4 fix: dynamic denominator instead of hardcoded /5
  }
  departments: HiveDepartment[]
  systemHealth: SystemHealth | null
  recentActivity: ActivityItem[]
}
type SystemHealth = {
  uptime?: string
  ollama?: { status: string; model_loaded?: string | null }
  redis?: string
  database?: { total_sessions: number; total_messages: number; last_activity?: string | null }
}
let dashboardCache: DashboardCache | null = null

// ── Main component ──

export function DashboardPage() {
  usePageTitle('Dashboard')
  const navigate = useNavigate()
  const { autopilotActive } = useUiStore()
  const [stats, setStats] = useState(
    () => (dashboardCache && Date.now() - dashboardCache.ts < CACHE_TTL_MS)
      ? dashboardCache.stats
      : {
          sessions: 0,
          pendingApprovals: 0,
          blockedApprovals: 0,
          memories: 0,
          activeAgents: 10,  // 10 departments
          pipelineTotal: 0,
          runtimesOnline: 0,
          runtimesTotal: 6,  // F-DASH-4 fix: matches actual runtime count (claude_code, codex, gemini_cli, grok_cli, vllm, ollama)
        },
  )
  // Initialize from cache if fresh — instant remount with no network hit.
  const cached = dashboardCache && (Date.now() - dashboardCache.ts < CACHE_TTL_MS)
    ? dashboardCache
    : null
  const [departments, setDepartments] = useState<HiveDepartment[]>(cached?.departments ?? [])
  const [loading, setLoading] = useState(!cached)
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(cached?.systemHealth ?? null)
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>(cached?.recentActivity ?? [])

  useEffect(() => {
    // Skip the 9-call burst entirely if cache is fresh (set by a sibling
    // mount within the last 30s). The 30s health poll below still runs
    // to keep liveness fresh.
    if (dashboardCache && Date.now() - dashboardCache.ts < CACHE_TTL_MS) {
      // Schedule a background re-warm after TTL expires so the next mount
      // also gets cache hits.
      const remaining = CACHE_TTL_MS - (Date.now() - dashboardCache.ts)
      const t = setTimeout(() => {
        // Triggers full reload by clearing cache. Component is unaware.
        dashboardCache = null
      }, remaining)
      return () => clearTimeout(t)
    }

    const loadData = async () => {
      try {
        // Parallel fetch: stats + departments + memories + audit
        const [sessionsRes, approvalsRes, blockedRes, deptsRes, healthRes, memoriesRes, auditRes, pipelineRes, runtimesRes] = await Promise.allSettled([
          api.get('/chat/sessions?page_size=1'),
          api.get('/governance/approvals?status=PENDING&page_size=1'),
          api.get('/governance/approvals?status=REJECTED&page_size=1'),
          api.get('/agents/departments'),
          api.get('/health/detailed'),
          api.get('/memory/memories?page_size=1'),
          api.get('/governance/audit?page_size=5'),
          api.get('/pipeline/summary'),
          api.get('/runtimes'),
        ])

        // Compute every value into a local first so we can both setState
        // AND seed the module cache from the same snapshot.
        const health: SystemHealth | null = healthRes.status === 'fulfilled' ? healthRes.value.data : null

        const memoryCount = memoriesRes.status === 'fulfilled'
          ? memoriesRes.value.data?.pagination?.total ?? 0
          : 0
        const pipelineTotal = pipelineRes.status === 'fulfilled'
          ? pipelineRes.value.data?.data?.total ?? 0
          : 0
        const runtimesOnline = runtimesRes.status === 'fulfilled'
          ? (runtimesRes.value.data?.data?.runtimes?.filter((r: { status: string }) => r.status === 'online')?.length ?? 0)
          : 0
        // F-DASH-4 fix: pull total from same response so the denominator is live.
        const runtimesTotal = runtimesRes.status === 'fulfilled'
          ? (runtimesRes.value.data?.data?.runtimes?.length ?? 6)
          : 6

        const nextStats = {
          sessions: sessionsRes.status === 'fulfilled'
            ? sessionsRes.value.data?.pagination?.total ?? 0
            : 0,
          pendingApprovals: approvalsRes.status === 'fulfilled' ? approvalsRes.value.data?.pagination?.total ?? 0 : 0,
          blockedApprovals: blockedRes.status === 'fulfilled' ? blockedRes.value.data?.pagination?.total ?? 0 : 0,
          memories: memoryCount,
          activeAgents: deptsRes.status === 'fulfilled' && deptsRes.value.data?.data
            ? (deptsRes.value.data.data as Array<{ is_active: boolean }>).filter(d => d.is_active).length
            : 10,
          pipelineTotal,
          runtimesOnline,
          runtimesTotal,
        }

        let nextActivity: ActivityItem[]
        if (auditRes.status === 'fulfilled' && auditRes.value.data?.data) {
          const entries = auditRes.value.data.data as Array<{
            id: string
            action_type: string
            action_params?: Record<string, unknown>
            result?: Record<string, unknown>
            created_at: string
          }>
          // F-DASH-3 fix: previously dumped EVERY action_params field into a
          // comma-joined blob, which leaked top_candidates / diagnostics /
          // selection_reason / etc to the user-visible feed (same class of
          // bug as F-0011 codex stderr). Now we extract a short, useful
          // summary - just the user message excerpt + model + latency -
          // and skip the heavy debug fields. Operators who need the full
          // payload click into /governance/audit which has the AuditDetail
          // panel with the complete JSON.
          const SAFE_KEYS = new Set(['user_message', 'model', 'provider', 'latency_ms', 'intent', 'risk', 'tier', 'target', 'tool_name', 'action'])
          nextActivity = entries.map((entry) => {
            const params = (entry.action_params || {}) as Record<string, unknown>
            const result = (entry.result || {}) as Record<string, unknown>
            const src = Object.keys(params).length > 0 ? params : result
            const summary = Object.entries(src)
              .filter(([k]) => SAFE_KEYS.has(k))
              .map(([k, v]) => {
                const sv = typeof v === 'string' ? v : JSON.stringify(v)
                return `${k}: ${sv.slice(0, 80)}`
              })
              .slice(0, 4)
              .join(' . ')
            return {
              id: entry.id,
              type: mapActionType(entry.action_type),
              title: formatActionTitle(entry.action_type),
              description: summary || 'No details available',
              time: formatRelativeTime(entry.created_at),
            }
          })
        } else {
          nextActivity = [
            { id: 'empty', type: 'alert', title: 'No recent activity', description: 'Audit log is empty or unavailable', time: '' },
          ]
        }

        let nextDepartments: HiveDepartment[] = []
        if (deptsRes.status === 'fulfilled' && deptsRes.value.data?.data) {
          const depts = deptsRes.value.data.data as Array<{
            id: string
            name: string
            agent_count: number
            is_active: boolean
          }>
          nextDepartments = depts.map((d) => ({
            id: d.id,
            name: shortenDeptName(d.name),
            agentCount: d.agent_count,
            activeCount: d.is_active ? d.agent_count : 0,
            efficiency: d.is_active ? 95 : 0,
          }))
        }

        // Apply to React state.
        if (health) setSystemHealth(health)
        setStats(nextStats)
        setRecentActivity(nextActivity)
        if (nextDepartments.length > 0) setDepartments(nextDepartments)

        // Seed module cache from the same snapshot — next mount within
        // CACHE_TTL_MS reuses without firing the 9-call burst.
        dashboardCache = {
          ts: Date.now(),
          stats: nextStats,
          departments: nextDepartments.length > 0 ? nextDepartments : (dashboardCache?.departments ?? []),
          systemHealth: health ?? dashboardCache?.systemHealth ?? null,
          recentActivity: nextActivity,
        }
      } catch (err) {
        console.error('Dashboard data load failed:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()

    // Auto-refresh health every 30s — paused when tab is hidden so
    // background tabs don't keep hammering /health/detailed for liveness
    // the user isn't watching.
    let interval: ReturnType<typeof setInterval> | null = null
    const refreshHealth = async () => {
      try {
        const { data } = await api.get('/health/detailed')
        if (data) setSystemHealth(data)
      } catch { /* silent */ }
    }
    const start = () => { if (!interval) interval = setInterval(refreshHealth, 30_000) }
    const stop = () => { if (interval) { clearInterval(interval); interval = null } }
    if (!document.hidden) start()
    const onVisibility = () => {
      if (document.hidden) stop()
      else { void refreshHealth(); start() }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  // Rule-17 / ADR-001: no hardcoded demo-data fallback. When departments fail
  // to load (backend down -> deptsRes rejected -> departments stays []), the
  // hive renders the central orb with no department hexagons rather than
  // fabricating 10 fake departments with invented agent counts/efficiencies.
  // (Same remediation as the deleted RuntimeSwapper.DEFAULT_RUNTIMES, 2026-04-29.)
  const hiveDepts: HiveDepartment[] = departments

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
        {/* Stats grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Chat Sessions"
            value={loading ? '—' : stats.sessions}
            icon={<MessageSquare size={20} />}
            trend="Today"
            color="bg-primary-500/15 text-primary-400"
            delay={0.05}
            linkTo="/chat"
          />
          <StatCard
            label="Pending Approvals"
            value={loading ? '—' : stats.pendingApprovals}
            icon={<ShieldCheck size={20} />}
            trend={stats.pendingApprovals > 0 ? 'Needs attention' : 'All clear'}
            trendUp={stats.pendingApprovals === 0}
            color="bg-status-warning/15 text-status-warning"
            delay={0.1}
            linkTo="/governance/approvals"
          />
          <StatCard
            label="Memories"
            value={loading ? '—' : stats.memories}
            icon={<Brain size={20} />}
            trend="NBMF 5-tier"
            color="bg-accent-purple/15 text-accent-purple"
            delay={0.15}
            linkTo="/settings/memory"
          />
          <StatCard
            label="Active Capabilities"
            value={loading ? '—' : `${stats.activeAgents * 6}`}
            icon={<Bot size={20} />}
            trend={`${stats.activeAgents} active department${stats.activeAgents === 1 ? '' : 's'} × 6 capabilities`}
            trendUp
            color="bg-accent-cyan/15 text-accent-cyan"
            delay={0.2}
            linkTo="/departments"
          />
          <StatCard
            label="Pipeline"
            value={loading ? '—' : `${stats.pipelineTotal}`}
            icon={<BarChart3 size={20} />}
            trend="Active projects"
            color="bg-accent-purple/15 text-accent-purple"
            delay={0.25}
            linkTo="/pipeline"
          />
          <StatCard
            label="Runtimes"
            value={loading ? '—' : `${stats.runtimesOnline}/${stats.runtimesTotal || 6}`}
            icon={<Cpu size={20} />}
            trend="Online"
            trendUp={stats.runtimesOnline >= 3}
            color="bg-status-success/15 text-status-success"
            delay={0.3}
            linkTo="/connections"
          />
        </div>

        {/* Control Room: Hex Hive + Status Panels */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Hex Hive — center column (2 cols wide) */}
          <motion.div
            className="lg:col-span-2"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card variant="glass" padding="none">
              <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
                <div className="flex items-center gap-2">
                  <Activity size={16} className="text-primary-400" />
                  <h2 className="text-sm font-display font-semibold text-starlight-100">
                    Control Room
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono ${
                    autopilotActive
                      ? 'bg-status-success/20 text-status-success'
                      : 'bg-starlight-600/20 text-starlight-400'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${autopilotActive ? 'bg-status-success animate-pulse' : 'bg-starlight-500'}`} />
                    {autopilotActive ? 'AGI ACTIVE' : 'STANDBY'}
                  </span>
                </div>
              </div>
              <div
                className="flex items-center justify-center py-8"
                style={{
                  background: 'radial-gradient(circle at center, rgba(30,64,175,0.12), rgba(15,23,42,0.46) 54%, rgba(2,6,23,0.96) 92%)',
                }}
              >
                <SunflowerHive departments={hiveDepts} size={380} />
              </div>
            </Card>
          </motion.div>

          {/* Right column: Status + Governance Pulse + Quick Actions */}
          <motion.div
            className="space-y-4"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            {/* System Status Badges */}
            <Card variant="glass" padding="md">
              <h3 className="text-xs font-display font-semibold text-starlight-400 uppercase tracking-wider mb-3">
                System Status
              </h3>
              <div className="grid grid-cols-2 gap-2">
                {/* Same convention as the F-0001 Redis fix below: the badge
                    color must match the actual state. When systemHealth is
                    null (health endpoint unreachable) the value already shows
                    "Starting...", so the variant degrades to warning instead
                    of a green "success" that contradicts it. */}
                <StatusBadge
                  label="Platform"
                  value={systemHealth?.uptime ?? 'Starting...'}
                  icon={<Activity size={12} />}
                  variant={systemHealth ? 'success' : 'warning'}
                />
                <StatusBadge
                  label="Ollama"
                  value={systemHealth?.ollama?.status === 'healthy' ? 'Online' : systemHealth?.ollama?.status ?? '—'}
                  icon={<Brain size={12} />}
                  variant={systemHealth?.ollama?.status === 'healthy' ? 'success' : 'warning'}
                />
                {/* Same convention as the siblings above: when systemHealth is
                    null (health endpoint unreachable) the count is UNKNOWN, not
                    a definite 0 -- show the "--" unavailable glyph (matching
                    Ollama's "?? glyph" and AnalyticsPage's "--") instead of a
                    fabricated "0". A genuine zero count still renders "0". */}
                <StatusBadge
                  label="Messages"
                  value={String(systemHealth?.database?.total_messages ?? '--')}
                  icon={<Zap size={12} />}
                  variant="info"
                />
                {/* F-0001 fix: Redis status was hidden when unhealthy, so the
                    operator never knew the queue / rate limiter / SSE pubsub
                    was silently degraded. Now always rendered with variant
                    matching the actual state. */}
                <StatusBadge
                  label="Redis"
                  value={systemHealth?.redis === 'healthy' ? 'Connected' : (systemHealth?.redis ?? 'Unknown')}
                  icon={<Shield size={12} />}
                  variant={systemHealth?.redis === 'healthy' ? 'success' : 'warning'}
                />
                <StatusBadge
                  label="Runtime"
                  value={useUiStore.getState().selectedRuntime ?? 'Auto'}
                  icon={<Cpu size={12} />}
                  variant="info"
                />
              </div>
            </Card>

            {/* Governance Pulse */}
            <Card variant="glass" padding="md">
              <h3 className="text-xs font-display font-semibold text-starlight-400 uppercase tracking-wider mb-3">
                Governance Pulse
              </h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-starlight-300">Autopilot</span>
                  <span className={`text-xs font-mono ${autopilotActive ? 'text-status-success' : 'text-starlight-500'}`}>
                    {autopilotActive ? 'ON' : 'OFF'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-starlight-300">Pending</span>
                  <span className="text-xs font-mono text-starlight-400">
                    {loading ? '—' : stats.pendingApprovals}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-starlight-300">Blocked</span>
                  <span className={`text-xs font-mono ${stats.blockedApprovals > 0 ? 'text-status-danger' : 'text-starlight-500'}`}>
                    {loading ? '—' : stats.blockedApprovals}
                  </span>
                </div>
              </div>
            </Card>

            {/* Quick Actions */}
            <Card variant="glass" padding="none">
              <div className="px-4 py-3 border-b border-white/5">
                <h3 className="text-xs font-display font-semibold text-starlight-400 uppercase tracking-wider">
                  Quick Actions
                </h3>
              </div>
              <div className="p-2 space-y-0.5">
                {[
                  { label: 'Security Scan', path: '/scan', icon: <Shield size={14} /> },
                  { label: 'New Chat', path: '/chat', icon: <MessageSquare size={14} /> },
                  { label: 'Review Approvals', path: '/governance/approvals', icon: <ShieldCheck size={14} /> },
                  { label: 'View Departments', path: '/departments', icon: <Bot size={14} /> },
                  { label: 'Audit Log', path: '/governance/audit', icon: <Activity size={14} /> },
                ].map((action) => (
                  <button
                    key={action.path}
                    onClick={() => navigate(action.path)}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg
                               text-xs text-starlight-300 hover:text-starlight-100 hover:bg-white/5
                               transition-all cursor-pointer group"
                  >
                    {action.icon}
                    <span className="flex-1 text-left">{action.label}</span>
                    <ArrowRight size={12} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                  </button>
                ))}
              </div>
            </Card>
          </motion.div>
        </div>

        {/* Recent Activity — full width below */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
        >
          <Card variant="glass" padding="none">
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
              <div className="flex items-center gap-2">
                <Clock size={16} className="text-primary-400" />
                <h2 className="text-sm font-display font-semibold text-starlight-100">Recent Activity</h2>
              </div>
            </div>
            <div className="divide-y divide-white/5">
              {recentActivity.length === 0 || (recentActivity.length === 1 && recentActivity[0].id === 'empty') ? (
                <div className="px-5 py-8 text-center">
                  <Clock size={20} className="text-starlight-600 mx-auto mb-2" />
                  <p className="text-sm text-starlight-400">No recent activity</p>
                  <p className="text-[11px] text-starlight-600 mt-1">
                    Send a message in <button onClick={() => navigate('/chat')} className="text-primary-400 hover:text-primary-300 underline cursor-pointer">chat</button> to generate audit events.
                  </p>
                </div>
              ) : (
                recentActivity.map((item) => (
                  <div key={item.id} className="px-5 py-3 flex items-start gap-3 hover:bg-white/[0.02] transition-colors">
                    <div className="mt-0.5">{ICON_MAP[item.type]}</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-starlight-200">{item.title}</p>
                      <p className="text-[11px] text-starlight-500 truncate">{item.description}</p>
                    </div>
                    <span className="text-[10px] text-starlight-600 shrink-0 flex items-center gap-1">
                      <Clock size={10} />
                      {item.time}
                    </span>
                  </div>
                ))
              )}
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}

export default DashboardPage
