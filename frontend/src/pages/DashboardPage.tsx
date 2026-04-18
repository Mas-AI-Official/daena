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
}

const StatCard = memo(function StatCard({ label, value, icon, trend, trendUp, color, delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
    >
      <Card variant="glass" padding="md" className="group hover:border-white/10 transition-all">
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

// ── Main component ──

export function DashboardPage() {
  usePageTitle('Dashboard')
  const navigate = useNavigate()
  const { autopilotActive } = useUiStore()
  const [stats, setStats] = useState({
    sessions: 0,
    pendingApprovals: 0,
    blockedApprovals: 0,
    memories: 0,
    activeAgents: 10,  // 10 departments
    pipelineTotal: 0,
    runtimesOnline: 0,
  })
  const [departments, setDepartments] = useState<HiveDepartment[]>([])
  const [loading, setLoading] = useState(true)
  const [systemHealth, setSystemHealth] = useState<{
    uptime?: string
    ollama?: { status: string; model_loaded?: string | null }
    redis?: string
    database?: { total_sessions: number; total_messages: number; last_activity?: string | null }
  } | null>(null)
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([])

  useEffect(() => {
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

        // Parse health data for live stats
        const health = healthRes.status === 'fulfilled' ? healthRes.value.data : null
        if (health) setSystemHealth(health)

        // Parse memory count
        const memoryCount = memoriesRes.status === 'fulfilled'
          ? memoriesRes.value.data?.pagination?.total ?? 0
          : 0

        const pipelineTotal = pipelineRes.status === 'fulfilled'
          ? pipelineRes.value.data?.data?.total ?? 0
          : 0
        const runtimesOnline = runtimesRes.status === 'fulfilled'
          ? (runtimesRes.value.data?.data?.runtimes?.filter((r: { status: string }) => r.status === 'online')?.length ?? 0)
          : 0

        setStats({
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
        })

        // Parse audit entries into recent activity
        if (auditRes.status === 'fulfilled' && auditRes.value.data?.data) {
          const entries = auditRes.value.data.data as Array<{
            id: string
            action_type: string
            action_params?: Record<string, unknown>
            result?: Record<string, unknown>
            created_at: string
          }>
          setRecentActivity(
            entries.map((entry) => ({
              id: entry.id,
              type: mapActionType(entry.action_type),
              title: formatActionTitle(entry.action_type),
              description:
                (entry.action_params && Object.keys(entry.action_params).length > 0
                  ? Object.entries(entry.action_params).map(([k, v]) => `${k}: ${typeof v === 'object' && v !== null ? JSON.stringify(v) : v}`).join(', ')
                  : entry.result && Object.keys(entry.result).length > 0
                    ? Object.entries(entry.result).map(([k, v]) => `${k}: ${typeof v === 'object' && v !== null ? JSON.stringify(v) : v}`).join(', ')
                    : 'No details available'),
              time: formatRelativeTime(entry.created_at),
            }))
          )
        } else {
          setRecentActivity([
            { id: 'empty', type: 'alert', title: 'No recent activity', description: 'Audit log is empty or unavailable', time: '' },
          ])
        }

        // Map departments to hive format
        if (deptsRes.status === 'fulfilled' && deptsRes.value.data?.data) {
          const depts = deptsRes.value.data.data as Array<{
            id: string
            name: string
            agent_count: number
            is_active: boolean
          }>
          setDepartments(
            depts.map((d) => ({
              id: d.id,
              name: shortenDeptName(d.name),
              agentCount: d.agent_count,
              activeCount: d.is_active ? d.agent_count : 0,
              efficiency: d.is_active ? 95 : 0,
            }))
          )
        }
      } catch (err) {
        console.error('Dashboard data load failed:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
    // Auto-refresh health every 30 seconds
    const interval = setInterval(async () => {
      try {
        const { data } = await api.get('/health/detailed')
        if (data) setSystemHealth(data)
      } catch {
        // Silent refresh failure
      }
    }, 30_000)
    return () => clearInterval(interval)
  }, [])

  // Fallback departments if API fails
  const hiveDepts: HiveDepartment[] = departments.length > 0
    ? departments
    : [
        { id: '1', name: 'Engineering', agentCount: 6, activeCount: 6, efficiency: 91 },
        { id: '2', name: 'Product', agentCount: 6, activeCount: 6, efficiency: 94 },
        { id: '3', name: 'Marketing', agentCount: 6, activeCount: 6, efficiency: 88 },
        { id: '4', name: 'Sales', agentCount: 6, activeCount: 6, efficiency: 92 },
        { id: '5', name: 'Finance', agentCount: 6, activeCount: 6, efficiency: 96 },
        { id: '6', name: 'Operations', agentCount: 6, activeCount: 6, efficiency: 87 },
        { id: '7', name: 'Research', agentCount: 6, activeCount: 6, efficiency: 89 },
        { id: '8', name: 'Legal', agentCount: 6, activeCount: 6, efficiency: 93 },
        { id: '9', name: 'Skill Gov', agentCount: 6, activeCount: 6, efficiency: 90 },
        { id: '10', name: 'Security Ops', agentCount: 6, activeCount: 6, efficiency: 95 },
      ]

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
          />
          <StatCard
            label="Pending Approvals"
            value={loading ? '—' : stats.pendingApprovals}
            icon={<ShieldCheck size={20} />}
            trend={stats.pendingApprovals > 0 ? 'Needs attention' : 'All clear'}
            trendUp={stats.pendingApprovals === 0}
            color="bg-status-warning/15 text-status-warning"
            delay={0.1}
          />
          <StatCard
            label="Memories"
            value={loading ? '—' : stats.memories}
            icon={<Brain size={20} />}
            trend="NBMF 5-tier"
            color="bg-accent-purple/15 text-accent-purple"
            delay={0.15}
          />
          <StatCard
            label="Active Agents"
            value={loading ? '—' : `${stats.activeAgents * 6}`}
            icon={<Bot size={20} />}
            trend="10 departments x 6 capabilities"
            trendUp
            color="bg-accent-cyan/15 text-accent-cyan"
            delay={0.2}
          />
          <StatCard
            label="Pipeline"
            value={loading ? '—' : `${stats.pipelineTotal}`}
            icon={<BarChart3 size={20} />}
            trend="Active projects"
            color="bg-accent-purple/15 text-accent-purple"
            delay={0.25}
          />
          <StatCard
            label="Runtimes"
            value={loading ? '—' : `${stats.runtimesOnline}/5`}
            icon={<Cpu size={20} />}
            trend="Online"
            trendUp={stats.runtimesOnline >= 3}
            color="bg-status-success/15 text-status-success"
            delay={0.3}
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
                <StatusBadge
                  label="Platform"
                  value={systemHealth?.uptime ?? 'Starting...'}
                  icon={<Activity size={12} />}
                  variant="success"
                />
                <StatusBadge
                  label="Ollama"
                  value={systemHealth?.ollama?.status === 'healthy' ? 'Online' : systemHealth?.ollama?.status ?? '—'}
                  icon={<Brain size={12} />}
                  variant={systemHealth?.ollama?.status === 'healthy' ? 'success' : 'warning'}
                />
                <StatusBadge
                  label="Messages"
                  value={String(systemHealth?.database?.total_messages ?? 0)}
                  icon={<Zap size={12} />}
                  variant="info"
                />
                {systemHealth?.redis === 'healthy' && (
                  <StatusBadge
                    label="Redis"
                    value="Connected"
                    icon={<Shield size={12} />}
                    variant="success"
                  />
                )}
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
              {recentActivity.map((item) => (
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
              ))}
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}

export default DashboardPage
