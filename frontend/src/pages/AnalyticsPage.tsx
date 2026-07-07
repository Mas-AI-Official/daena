/**
 * AnalyticsPage -- Live usage analytics, governance metrics, cost tracking,
 * and department activity. Fetches from /analytics/dashboard.
 * Lightweight SVG bar charts (no heavy chart library).
 */
import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart3,
  TrendingUp,
  Shield,
  DollarSign,
  Brain,
  Zap,
  RefreshCw,
  Clock,
  CheckCircle2,
  MessageSquare,
  Loader2,
  AlertTriangle,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { api } from '@/lib/api'

// ── Types ──

interface DashboardData {
  usage: { messages_today: number; messages_this_week: number; tokens_today: number; tokens_this_week: number }
  costs: { cost_today_usd: number; cost_this_week_usd: number; cost_this_month_usd: number }
  governance: { approvals_pending: number; approvals_decided_today: number; auto_approved_pct: number; avg_decision_time_ms: number }
  departments: { name: string; message_count: number; last_active: string | null }[]
  providers: { provider: string; cost_usd: number; calls: number; tokens: number }[]
  daily_usage: { date: string; messages: number; tokens: number; cost_usd: number }[]
}

const EMPTY: DashboardData = {
  usage: { messages_today: 0, messages_this_week: 0, tokens_today: 0, tokens_this_week: 0 },
  costs: { cost_today_usd: 0, cost_this_week_usd: 0, cost_this_month_usd: 0 },
  governance: { approvals_pending: 0, approvals_decided_today: 0, auto_approved_pct: 0, avg_decision_time_ms: 0 },
  departments: [],
  providers: [],
  daily_usage: [],
}

// ── Helpers ──

function fmtUsd(v: number): string {
  return v < 0.01 && v > 0 ? '<$0.01' : `$${v.toFixed(2)}`
}

function fmtTokens(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return String(v)
}

function fmtMs(ms: number): string {
  if (ms === 0) return '--'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// ── Mini Bar Chart (SVG) ──

function MiniBarChart({ data, valueKey, color, height = 120 }: {
  data: { date: string; [key: string]: unknown }[]
  valueKey: string
  color: string
  height?: number
}) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center border border-dashed border-white/5 rounded-lg" style={{ height }}>
        <p className="text-xs text-starlight-500">No data yet</p>
      </div>
    )
  }

  const values = data.map((d) => Number(d[valueKey] ?? 0))
  const max = Math.max(...values, 1)
  const barWidth = Math.max(4, Math.floor(600 / data.length) - 2)

  return (
    <svg viewBox={`0 0 ${data.length * (barWidth + 2)} ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none">
      {values.map((v, i) => {
        const barH = (v / max) * (height - 16)
        return (
          <g key={i}>
            <rect
              x={i * (barWidth + 2)}
              y={height - barH - 8}
              width={barWidth}
              height={Math.max(barH, 1)}
              rx={2}
              fill={color}
              opacity={0.7}
            />
            {/* Date label for first, middle, last */}
            {(i === 0 || i === data.length - 1 || i === Math.floor(data.length / 2)) && (
              <text
                x={i * (barWidth + 2) + barWidth / 2}
                y={height - 1}
                textAnchor="middle"
                fontSize="8"
                fill="#6B7280"
              >
                {data[i].date.slice(5)}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

// ── Stat Card ──

function StatCard({ label, value, subtitle, icon: Icon, color, bg, drillTo }: {
  label: string
  value: string
  subtitle?: string
  icon: React.ElementType
  color: string
  bg: string
  // Optional drill-down: when set the card becomes a clickable link to a
  // page where the operator can act on the stat (e.g. "Pending approvals"
  // → /governance/approvals?status=PENDING). Without this, stats are dead-end.
  drillTo?: string
}) {
  const Inner = (
    <>
      <Icon size={18} className={`${color} mb-3`} />
      <p className="text-2xl font-semibold text-starlight-100">{value}</p>
      <p className="text-xs text-starlight-500 mt-1">{label}</p>
      {subtitle && <p className="text-[10px] text-starlight-600 mt-0.5">{subtitle}</p>}
      {drillTo && <p className="text-[9px] text-primary-400/70 mt-2 uppercase tracking-wider">View details →</p>}
    </>
  )
  if (drillTo) {
    return (
      <motion.a
        href={drillTo}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className={`block p-4 rounded-xl ${bg} border border-white/5 hover:border-white/15 hover:bg-opacity-100 transition-all cursor-pointer`}
      >
        {Inner}
      </motion.a>
    )
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-4 rounded-xl ${bg} border border-white/5`}
    >
      {Inner}
    </motion.div>
  )
}

// ── Department Bar ──

function DeptBar({ name, count, maxCount }: { name: string; count: number; maxCount: number }) {
  const pct = maxCount > 0 ? (count / maxCount) * 100 : 0
  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] text-starlight-400 w-28 truncate">{name}</span>
      <div className="flex-1 h-1.5 rounded-full bg-midnight-400 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="h-full rounded-full bg-accent-cyan/60"
        />
      </div>
      <span className="text-[10px] text-starlight-500 w-8 text-right font-mono">{count}</span>
    </div>
  )
}

// ── Main Page ──

export function AnalyticsPage() {
  usePageTitle('Analytics')

  const [data, setData] = useState<DashboardData>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [period, setPeriod] = useState<'7d' | '30d' | '90d'>('30d')

  const fetchData = useCallback(async () => {
    try {
      const res = await api.get('/analytics/dashboard', { params: { period }, timeout: 8000 })
      const d = res.data?.data || res.data
      setData({
        usage: d?.usage || EMPTY.usage,
        costs: d?.costs || EMPTY.costs,
        governance: d?.governance || EMPTY.governance,
        departments: d?.departments || EMPTY.departments,
        providers: d?.providers || EMPTY.providers,
        daily_usage: d?.daily_usage || EMPTY.daily_usage,
      })
      setFetchError(null)
    } catch (err) {
      setData(EMPTY)
      // Surface the failure instead of silently rendering zeros — operators
      // need to know "the analytics service is down" vs "we have no data".
      const status = (err as { response?: { status?: number } })?.response?.status
      setFetchError(
        status === 401
          ? 'Session expired. Please reload the page to sign in again.'
          : status
          ? `Analytics service returned ${status}. Metrics are unavailable until this endpoint recovers.`
          : 'Analytics service unreachable. Metrics are unavailable until the backend responds.',
      )
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    void fetchData()
  }, [fetchData])

  const { usage, costs, governance, departments, providers, daily_usage } = data
  const maxDeptCount = Math.max(...departments.map((d) => d.message_count), 1)
  const analyticsUnavailable = Boolean(fetchError)

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-display font-semibold text-starlight-100">Analytics</h1>
            <p className="text-sm text-starlight-400 mt-0.5">
              Usage, governance, and cost analytics — scoped to your tenant only
            </p>
          </div>
          <button
            onClick={() => { setLoading(true); void fetchData() }}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-white/5 text-starlight-400 hover:bg-white/10 cursor-pointer disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>

        {fetchError && !loading && (
          <div role="alert" className="px-4 py-3 rounded-xl bg-status-warning/10 border border-status-warning/30 flex items-start gap-3">
            <AlertTriangle size={16} className="text-status-warning shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-status-warning font-medium">Analytics offline</p>
              <p className="text-xs text-starlight-400 mt-0.5">{fetchError}</p>
            </div>
            <button
              onClick={() => { setLoading(true); void fetchData() }}
              className="text-xs text-status-warning hover:text-status-warning/80 underline cursor-pointer shrink-0"
            >
              Retry
            </button>
          </div>
        )}

        {/* Overview cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Messages today"
            value={analyticsUnavailable ? '--' : String(usage.messages_today)}
            subtitle={analyticsUnavailable ? 'analytics unavailable' : `${usage.messages_this_week} this week`}
            icon={MessageSquare}
            color="text-primary-400"
            bg="bg-primary-500/10"
            drillTo="/chat"
          />
          <StatCard
            label="Tokens used"
            value={analyticsUnavailable ? '--' : fmtTokens(usage.tokens_today)}
            subtitle={analyticsUnavailable ? 'analytics unavailable' : `${fmtTokens(usage.tokens_this_week)} this week`}
            icon={TrendingUp}
            color="text-accent-cyan"
            bg="bg-accent-cyan/10"
            drillTo="/settings/billing"
          />
          <StatCard
            label="Cost today"
            value={analyticsUnavailable ? '--' : fmtUsd(costs.cost_today_usd)}
            subtitle={analyticsUnavailable ? 'analytics unavailable' : `${fmtUsd(costs.cost_this_month_usd)} this month`}
            icon={DollarSign}
            color="text-accent-amber"
            bg="bg-accent-amber/10"
            drillTo="/settings/billing"
          />
          <StatCard
            label="Governance actions"
            value={analyticsUnavailable ? '--' : String(governance.approvals_decided_today)}
            subtitle={analyticsUnavailable ? 'analytics unavailable' : `${governance.approvals_pending} pending`}
            icon={Shield}
            color="text-accent-purple"
            bg="bg-accent-purple/10"
            drillTo="/governance/approvals?status=PENDING"
          />
        </div>

        {/* Usage chart */}
        <div className="rounded-xl border border-white/5 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-starlight-200">Usage over time</h3>
            <div className="flex gap-1">
              {(['7d', '30d', '90d'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors cursor-pointer ${
                    period === p
                      ? 'bg-primary-500/20 text-primary-400'
                      : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/5'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          {loading ? (
            <div className="h-32 flex items-center justify-center">
              <Loader2 size={20} className="animate-spin text-starlight-400" />
            </div>
          ) : (
            <MiniBarChart data={daily_usage} valueKey="messages" color="#6366F1" height={120} />
          )}
        </div>

        {/* Cost chart */}
        <div className="rounded-xl border border-white/5 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200">
              <DollarSign size={14} /> Cost trend
            </h3>
          </div>
          {loading ? (
            <div className="h-24 flex items-center justify-center">
              <Loader2 size={20} className="animate-spin text-starlight-400" />
            </div>
          ) : (
            <MiniBarChart data={daily_usage} valueKey="cost_usd" color="#F59E0B" height={96} />
          )}
        </div>

        {/* Two-column: Departments + Governance */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Department activity */}
          <div className="rounded-xl border border-white/5 p-6">
            <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200 mb-4">
              <Brain size={14} /> Department activity
            </h3>
            <div className="space-y-3">
              {departments.length > 0 ? (
                departments.map((dept) => (
                  <DeptBar key={dept.name} name={dept.name} count={dept.message_count} maxCount={maxDeptCount} />
                ))
              ) : (
                <div className="rounded-lg border border-dashed border-white/10 bg-midnight-800/20 px-4 py-6 text-center">
                  <p className="text-xs text-starlight-500">
                    {analyticsUnavailable
                      ? 'Department activity is unavailable while analytics is offline.'
                      : 'No department activity recorded for this period.'}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Governance metrics */}
          <div className="rounded-xl border border-white/5 p-6">
            <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200 mb-4">
              <Shield size={14} /> Governance metrics
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-starlight-300">Auto-approved</p>
                  <p className="text-[10px] text-starlight-500">Actions auto-approved by governance</p>
                </div>
                <p className="text-sm font-mono text-starlight-200">
                  {governance.auto_approved_pct > 0 ? `${governance.auto_approved_pct.toFixed(0)}%` : '--'}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-starlight-300">Pending approvals</p>
                  <p className="text-[10px] text-starlight-500">Actions awaiting human decision</p>
                </div>
                <p className="text-sm font-mono text-starlight-200">{governance.approvals_pending}</p>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-starlight-300">Avg decision time</p>
                  <p className="text-[10px] text-starlight-500">Time from request to decision</p>
                </div>
                <p className="text-sm font-mono text-starlight-200">{fmtMs(governance.avg_decision_time_ms)}</p>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-starlight-300">Decided today</p>
                  <p className="text-[10px] text-starlight-500">Governance decisions made today</p>
                </div>
                <p className="text-sm font-mono text-starlight-200">{governance.approvals_decided_today}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Provider breakdown */}
        <div className="rounded-xl border border-white/5 p-6">
          <h3 className="flex items-center gap-2 text-sm font-medium text-starlight-200 mb-4">
            <Zap size={14} /> Provider breakdown
          </h3>
          {providers.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {providers.map((p) => (
                <div key={p.provider} className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-midnight-400/30 border border-white/5">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-starlight-200 capitalize">{p.provider}</p>
                    <p className="text-[10px] text-starlight-500">{p.calls} calls -- {fmtTokens(p.tokens)} tokens</p>
                  </div>
                  <p className="text-xs font-mono text-accent-amber shrink-0">{fmtUsd(p.cost_usd)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-starlight-500">
              {analyticsUnavailable
                ? 'Provider usage is unavailable while analytics is offline.'
                : 'No provider usage recorded in this period.'}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default AnalyticsPage
