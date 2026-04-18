/**
 * PipelinePage -- Kanban board for the 8-stage project pipeline.
 * Shows projects flowing through: DISCOVERY > QUALIFICATION > PROPOSAL >
 * CONTRACT > EXECUTION > DELIVERY > BILLING > CLOSED
 *
 * Human gates (lock icon) at PROPOSAL, CONTRACT, DELIVERY.
 */
import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Kanban,
  Plus,
  Lock,
  ArrowRight,
  RefreshCw,
  DollarSign,
  Clock,
  Star,
  ChevronRight,
  AlertCircle,
  XCircle,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { ApiResponse } from '@/types/api'

const STAGES = [
  'DISCOVERY', 'QUALIFICATION', 'PROPOSAL', 'CONTRACT',
  'EXECUTION', 'DELIVERY', 'BILLING', 'CLOSED',
] as const

const HUMAN_GATES = new Set(['PROPOSAL', 'CONTRACT', 'DELIVERY'])

const STAGE_SHORT_LABELS: Record<string, string> = {
  DISCOVERY: 'Discovery',
  QUALIFICATION: 'Qualify',
  PROPOSAL: 'Proposal',
  CONTRACT: 'Contract',
  EXECUTION: 'Execute',
  DELIVERY: 'Deliver',
  BILLING: 'Billing',
  CLOSED: 'Closed',
}

const STAGE_COLORS: Record<string, string> = {
  DISCOVERY: 'border-accent-cyan/30',
  QUALIFICATION: 'border-accent-amber/30',
  PROPOSAL: 'border-accent-purple/30',
  CONTRACT: 'border-accent-red/30',
  EXECUTION: 'border-primary-500/30',
  DELIVERY: 'border-status-success/30',
  BILLING: 'border-accent-amber/30',
  CLOSED: 'border-starlight-500/30',
}

interface PipelineProject {
  id: string
  title: string
  stage: string
  owner_department: string
  overall_score: number | null
  budget_usd: number | null
  client_name: string | null
  source: string | null
  created_at: string
  // Loss tracking -- orthogonal to the 8-stage flow.
  // lost_at null = active project; populated = lost.
  lost_at?: string | null
  lost_reason?: string | null
}

interface PipelineSummary {
  [stage: string]: number
  total: number
}

export function PipelinePage() {
  usePageTitle('Pipeline')
  const [summary, setSummary] = useState<PipelineSummary | null>(null)
  const [projects, setProjects] = useState<PipelineProject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [newTitle, setNewTitle] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [sumRes, projRes] = await Promise.allSettled([
        api.get<ApiResponse<PipelineSummary>>('/pipeline/summary'),
        api.get<ApiResponse<{ projects: PipelineProject[] }>>('/pipeline/projects'),
      ])
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data.data || null)
      else setError('Failed to load pipeline summary')
      if (projRes.status === 'fulfilled') {
        const p = projRes.value.data
        setProjects((p as any).projects || (p as any).data?.projects || [])
      } else if (!error) setError('Failed to load pipeline projects')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pipeline data')
    }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void fetchData() }, [fetchData])

  useEffect(() => {
    const interval = setInterval(() => { void fetchData() }, 60000)
    return () => clearInterval(interval)
  }, [fetchData])

  const handleCreateProject = async () => {
    if (!newTitle.trim()) return
    setCreating(true)
    try {
      await api.post('/pipeline/projects', { title: newTitle.trim(), source: 'manual' })
      setNewTitle('')
      toast.success('Project created in DISCOVERY')
      await fetchData()
    } catch { toast.error('Failed to create project') }
    finally { setCreating(false) }
  }

  const handleAdvance = async (projectId: string, currentStage: string) => {
    const needsApproval = HUMAN_GATES.has(currentStage)
    try {
      await api.post(`/pipeline/projects/${projectId}/advance`, {
        founder_approved: needsApproval,
        notes: 'Advanced from Pipeline board',
      })
      toast.success('Project advanced')
      await fetchData()
    } catch (err: unknown) {
      const msg = (err as any)?.response?.data?.error?.message || 'Failed to advance'
      toast.error(msg)
    }
  }

  // Marking a deal lost is deliberately gated behind a reason prompt.
  // The reason flows to the Sales.lost_deal BorderAgent signal so
  // Marketing and Research can aggregate loss patterns without needing
  // to ask the founder after the fact.
  const handleMarkLost = async (projectId: string, title: string) => {
    const reason = window.prompt(
      `Mark "${title}" as lost. What was the reason? (optional, under 200 chars)`
    )
    // User cancelled the prompt -- do nothing.
    if (reason === null) return
    try {
      await api.post(`/pipeline/projects/${projectId}/mark-lost`, {
        reason: reason.trim() || null,
      })
      toast.success('Project marked as lost')
      await fetchData()
    } catch (err: unknown) {
      const msg =
        (err as any)?.response?.data?.error?.message || 'Failed to mark lost'
      toast.error(msg)
    }
  }

  const getProjectsForStage = (stage: string) => projects.filter(p => p.stage === stage)

  if (loading) return <div className="p-6"><Shimmer count={8} layout="card-grid" /></div>

  return (
    <div className="h-full overflow-x-auto">
      <div className="p-6 min-w-[1200px]">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-primary-500/15">
              <Kanban size={22} className="text-primary-400" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold text-starlight-100">Project Pipeline</h1>
              <p className="text-sm text-starlight-400">{summary?.total || 0} projects across 8 stages</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="New project name..."
                className="glass-input px-3 py-2 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500 w-48"
                onKeyDown={(e) => e.key === 'Enter' && void handleCreateProject()}
              />
              <Button variant="primary" size="sm" onClick={() => void handleCreateProject()} disabled={creating || !newTitle.trim()}>
                <Plus size={14} /> Create
              </Button>
            </div>
            <Button variant="ghost" size="sm" onClick={() => void fetchData()}>
              <RefreshCw size={14} />
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 rounded-xl bg-status-error/10 border border-status-error/20 flex items-center gap-2">
            <AlertCircle size={14} className="text-status-error shrink-0" />
            <p className="text-xs text-status-error">{error}</p>
            <button onClick={() => void fetchData()} className="ml-auto text-xs text-status-error hover:text-status-error/80 underline cursor-pointer">Retry</button>
          </div>
        )}

        {/* Kanban board */}
        <div className="flex gap-3">
          {STAGES.map((stage) => {
            const stageProjects = getProjectsForStage(stage)
            const count = summary?.[stage] || stageProjects.length
            const isGate = HUMAN_GATES.has(stage)

            return (
              <div key={stage} className={`flex-1 min-w-[140px] rounded-xl border ${STAGE_COLORS[stage]} bg-midnight-400/20 p-2`}>
                {/* Column header */}
                <div className="flex items-center justify-between px-2 py-1.5 mb-2">
                  <div className="flex items-center gap-1.5">
                    {isGate && <Lock size={10} className="text-accent-amber" />}
                    <span className="text-[10px] font-semibold text-starlight-300">
                      {STAGE_SHORT_LABELS[stage] || stage}
                    </span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/5 text-starlight-500">
                    {count}
                  </span>
                </div>

                {/* Project cards */}
                <div className="space-y-2 min-h-[100px]">
                  {stageProjects.map((project) => (
                    <motion.div
                      key={project.id}
                      layout
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                    >
                      <Card
                        variant="glass"
                        padding="sm"
                        className={`group cursor-pointer hover:border-white/10 ${
                          project.lost_at ? 'opacity-50' : ''
                        }`}
                      >
                        <div className="flex items-start gap-1.5">
                          <p className={`flex-1 text-xs font-medium text-starlight-200 truncate ${
                            project.lost_at ? 'line-through' : ''
                          }`}>{project.title}</p>
                          {project.lost_at && (
                            <span
                              title={project.lost_reason || 'Marked lost'}
                              className="shrink-0 text-[8px] px-1 py-0.5 rounded bg-status-error/15 text-status-error"
                            >
                              LOST
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 mt-1 text-[9px] text-starlight-500">
                          {project.overall_score != null && (
                            <span className="flex items-center gap-0.5">
                              <Star size={8} className="text-accent-amber" />
                              {project.overall_score}
                            </span>
                          )}
                          {project.budget_usd != null && (
                            <span className="flex items-center gap-0.5">
                              <DollarSign size={8} />
                              ${Math.round(project.budget_usd)}
                            </span>
                          )}
                          {project.source && (
                            <span>{project.source}</span>
                          )}
                        </div>
                        <div className="flex items-center justify-between mt-1.5">
                          <span className="text-[9px] text-starlight-600">{project.owner_department}</span>
                          <div className="flex items-center gap-1">
                            {/* Mark-lost is visible for any active project regardless of stage.
                                Once a deal is lost, it stays at whatever stage it reached (for
                                the historical record) but earns the LOST badge. */}
                            {stage !== 'CLOSED' && !project.lost_at && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  void handleMarkLost(project.id, project.title)
                                }}
                                className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] bg-status-error/10 text-status-error hover:bg-status-error/20 transition-all cursor-pointer"
                                title="Mark deal as lost"
                              >
                                <XCircle size={8} />
                                Lost
                              </button>
                            )}
                            {stage !== 'CLOSED' && !project.lost_at && (
                              <button
                                onClick={(e) => { e.stopPropagation(); void handleAdvance(project.id, stage) }}
                                className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 transition-all cursor-pointer"
                                title={isGate ? 'Approve and advance' : 'Advance to next stage'}
                              >
                                <ArrowRight size={8} />
                                {isGate ? 'Approve' : 'Advance'}
                              </button>
                            )}
                          </div>
                        </div>
                      </Card>
                    </motion.div>
                  ))}

                  {stageProjects.length === 0 && (
                    <div className="text-[10px] text-starlight-600 text-center py-4 italic">Empty</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default PipelinePage
