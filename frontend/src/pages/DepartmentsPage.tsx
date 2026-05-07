/**
 * DepartmentsPage -- Grid view of all 10 departments.
 * Each department has 6 sub-capabilities (MIND, EYES, HANDS, VOICE, SHIELD, MEMORY).
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Wrench,
  Layers,
  Megaphone,
  TrendingUp,
  Calculator,
  Settings,
  Microscope,
  Scale,
  GraduationCap,
  ShieldCheck,
  Bot,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Shimmer, EmptyState, Button } from '@/components/common'
import { api } from '@/lib/api'
import { useDepartmentStates, type DepartmentState } from '@/hooks/useDepartmentStates'
import type { DepartmentResponse, ApiResponse } from '@/types/api'

// Map the per-department live-status -> Badge variant. Absorbed from
// the deleted CompanyDashboard so this page is the single source of
// truth for department presence + activity.
const STATUS_VARIANT: Record<string, 'default' | 'info' | 'warning' | 'success' | 'danger'> = {
  // IDLE used to be 'success' (green) which read as "good". IDLE is
  // not a positive state — it's neutral. WORKING is the active state.
  IDLE:       'default',
  WORKING:    'success',
  OVERLOADED: 'warning',
  OFFLINE:    'danger',
}

// Department icons + Tailwind color classes.
// ``dotColor`` is an explicit static class string so Tailwind JIT can
// see and compile it. Previously the dot used
// ``bgColor.replace('/15', '/40')`` which produces strings Tailwind
// never sees at build time -- only Engineering rendered because
// ``bg-primary-500/40`` happened to be referenced elsewhere in the
// bundle. Explicit dotColor per department fixes all 9 other cards.
const DEPT_META: Record<
  string,
  { icon: React.ReactNode; color: string; bgColor: string; dotColor: string }
> = {
  Engineering:           { icon: <Wrench size={24} />,         color: 'text-primary-400',    bgColor: 'bg-primary-500/15',      dotColor: 'bg-primary-400' },
  Product:               { icon: <Layers size={24} />,         color: 'text-accent-purple',  bgColor: 'bg-accent-purple/15',    dotColor: 'bg-accent-purple' },
  Marketing:             { icon: <Megaphone size={24} />,      color: 'text-status-success', bgColor: 'bg-status-success/15',   dotColor: 'bg-status-success' },
  Sales:                 { icon: <TrendingUp size={24} />,     color: 'text-accent-cyan',    bgColor: 'bg-accent-cyan/15',      dotColor: 'bg-accent-cyan' },
  Finance:               { icon: <Calculator size={24} />,     color: 'text-status-warning', bgColor: 'bg-status-warning/15',   dotColor: 'bg-status-warning' },
  Operations:            { icon: <Settings size={24} />,       color: 'text-accent-amber',   bgColor: 'bg-accent-amber/15',     dotColor: 'bg-accent-amber' },
  Research:              { icon: <Microscope size={24} />,     color: 'text-blue-400',       bgColor: 'bg-blue-500/15',         dotColor: 'bg-blue-400' },
  'Legal & Compliance':  { icon: <Scale size={24} />,          color: 'text-status-error',   bgColor: 'bg-status-error/15',     dotColor: 'bg-status-error' },
  'Skill Governance':    { icon: <GraduationCap size={24} />,  color: 'text-fuchsia-400',    bgColor: 'bg-fuchsia-500/15',      dotColor: 'bg-fuchsia-400' },
  'Security Operations': { icon: <ShieldCheck size={24} />,    color: 'text-pink-400',       bgColor: 'bg-pink-500/15',         dotColor: 'bg-pink-400' },
}

const FALLBACK = {
  icon: <Bot size={24} />,
  color: 'text-primary-400',
  bgColor: 'bg-primary-500/15',
  dotColor: 'bg-primary-400',
}

// Sub-capabilities
const SUB_CAPS = ['MIND', 'EYES', 'HANDS', 'VOICE', 'SHIELD', 'MEMORY'] as const

export function DepartmentsPage() {
  usePageTitle('Departments')
  const navigate = useNavigate()
  const [departments, setDepartments] = useState<DepartmentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Live status polled every 5s from /api/v1/department-states. Merged
  // in from the deleted CompanyDashboard so operators do not need a
  // separate page to see who is WORKING vs IDLE.
  const { states } = useDepartmentStates()

  // Search box state — filters the visible department cards by name.
  const [searchQuery, setSearchQuery] = useState('')
  const stateByName: Record<string, DepartmentState | undefined> = Object.fromEntries(
    states.map((s) => [s.department_name, s]),
  )

  useEffect(() => {
    const fetchDepts = async () => {
      try {
        const { data } = await api.get<ApiResponse<DepartmentResponse[]>>('/agents/departments')
        const depts = data.data || []
        if (depts.length > 0) {
          setDepartments(depts)
          setLoadError(null)
        } else {
          setDepartments([])
          setLoadError('Backend returned no departments. Seed or create departments before using this page.')
        }
      } catch (err) {
        console.error('Failed to load departments:', err)
        setDepartments([])
        setLoadError('Could not reach the departments API. Daena may be offline or your session may have expired.')
      } finally {
        setLoading(false)
      }
    }
    fetchDepts()
  }, [])

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <motion.div
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div>
            <h1 className="text-2xl font-display font-bold text-starlight-100">Departments</h1>
              <p className="text-sm text-starlight-400">
                {departments.length > 0
                  ? `${departments.length} department-agents × 6 sub-capabilities`
                  : 'No live department data loaded'}
              </p>
          </div>
          {/* Live status summary — at-a-glance counters before the operator
              has to scan every card. */}
          {!loading && departments.length > 0 && (
            <div className="flex items-center gap-2">
              {(() => {
                const counts = { WORKING: 0, IDLE: 0, OVERLOADED: 0, OFFLINE: 0 } as Record<string, number>
                departments.forEach((d) => {
                  const live = stateByName[d.name]
                  const label = live?.status || 'IDLE'
                  counts[label] = (counts[label] ?? 0) + 1
                })
                return (
                  <>
                    <span className="text-[11px] px-2 py-1 rounded-md bg-status-success/10 text-status-success border border-status-success/20">
                      {counts.WORKING} working
                    </span>
                    <span className="text-[11px] px-2 py-1 rounded-md bg-white/5 text-starlight-300 border border-white/10">
                      {counts.IDLE} idle
                    </span>
                    {counts.OVERLOADED > 0 && (
                      <span className="text-[11px] px-2 py-1 rounded-md bg-status-warning/10 text-status-warning border border-status-warning/20">
                        {counts.OVERLOADED} overloaded
                      </span>
                    )}
                    {counts.OFFLINE > 0 && (
                      <span className="text-[11px] px-2 py-1 rounded-md bg-status-error/10 text-status-error border border-status-error/20">
                        {counts.OFFLINE} offline
                      </span>
                    )}
                  </>
                )
              })()}
            </div>
          )}
        </motion.div>

        {/* Search filter — useful when N grows beyond the seeded 10. */}
        {!loading && departments.length > 4 && (
          <div className="relative max-w-md">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter departments..."
              className="w-full px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
            />
          </div>
        )}

        {loadError && !loading && (
          <div className="px-4 py-3 rounded-xl bg-status-warning/10 border border-status-warning/30 flex items-start gap-3">
            <AlertTriangle size={16} className="text-status-warning shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-status-warning font-medium">Departments offline</p>
              <p className="text-xs text-starlight-400 mt-0.5">{loadError}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => window.location.reload()}>
              Retry
            </Button>
          </div>
        )}

        {loading ? (
          <Shimmer count={10} layout="card-grid" />
        ) : departments.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="No live departments loaded"
            description={loadError || 'The department API returned no rows. This page will not render placeholder agents.'}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {departments
              .filter((d) => !searchQuery.trim() || d.name.toLowerCase().includes(searchQuery.trim().toLowerCase()))
              .map((dept, i) => {
              const meta = DEPT_META[dept.name] || FALLBACK
              return (
                <motion.div
                  key={dept.id}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Card
                    variant="glass"
                    padding="md"
                    className="cursor-pointer hover:border-white/10 hover:bg-white/[0.02] transition-all group"
                    onClick={() => navigate(`/departments/${dept.id}/chat`)}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className={`p-2.5 rounded-lg ${meta.bgColor} ${meta.color}`}>
                        {meta.icon}
                      </div>
                      {(() => {
                        const live = stateByName[dept.name]
                        const label = live?.status ?? (dept.is_active ? 'IDLE' : 'OFFLINE')
                        return (
                          <Badge variant={STATUS_VARIANT[label] ?? 'default'} size="sm">
                            {label}
                            {live && live.queue_depth > 0 ? ` -- ${live.queue_depth}` : ''}
                          </Badge>
                        )
                      })()}
                    </div>
                    <h3 className="text-sm font-display font-semibold text-starlight-100 mb-1">
                      {dept.name}
                    </h3>
                    <p className="text-[11px] text-starlight-500 mb-3 line-clamp-2">
                      {dept.description}
                    </p>

                    {/* Sub-capability dots. Static class names (see
                        DEPT_META.dotColor) so Tailwind JIT compiles
                        them for every department, not just Engineering. */}
                    <div className="flex items-center gap-1 mb-2" title="MIND, EYES, HANDS, VOICE, SHIELD, MEMORY">
                      {SUB_CAPS.map((cap) => (
                        <div
                          key={cap}
                          className={`w-1.5 h-1.5 rounded-full ${meta.dotColor}`}
                          title={cap}
                        />
                      ))}
                      <span className="text-[10px] text-starlight-500 ml-1">6 caps</span>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-starlight-500">
                      <span>{dept.agent_count} agents</span>
                      <span className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity text-primary-400">
                        Chat with department
                        <ChevronRight size={12} />
                      </span>
                    </div>
                    {(() => {
                      const live = stateByName[dept.name]
                      if (!live?.current_task_summary) return null
                      return (
                        <p className="mt-2 text-[10px] text-starlight-400 truncate" title={live.current_task_summary}>
                          Now: {live.current_task_summary}
                        </p>
                      )
                    })()}
                  </Card>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default DepartmentsPage
