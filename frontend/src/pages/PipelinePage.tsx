/**
 * PipelinePage -- Kanban board for the 8-stage project pipeline.
 * Shows projects flowing through: DISCOVERY > QUALIFICATION > PROPOSAL >
 * CONTRACT > EXECUTION > DELIVERY > BILLING > CLOSED
 *
 * Human gates (lock icon) at PROPOSAL, CONTRACT, DELIVERY.
 */
import { useEffect, useMemo, useState, useCallback } from 'react'
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
import { promptDialog } from '@/stores/confirmStore'
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

interface CustomerAcquisitionWorkflowResult {
  mode: 'draft_only'
  external_action_sent: boolean
  requires_founder_approval: boolean
  steps: string[]
  contacts: Array<{
    contact_id: string
    account_id: string | null
    full_name: string
    title: string | null
    email: string | null
    stage: string
  }>
  qualified_contact: {
    contact_id: string
    stage: string
    score: number
  }
  outreach_draft: {
    draft_id: string
    contact_id: string
    channel: string
    subject: string | null
    body: string
    status: string
    template_id: string
  }
  follow_up_task: {
    id: string
    name: string
    status: string
  }
  approval_request: {
    id: string
    status: string
    risk_level: string
    governance_tier: number
  }
}

export function PipelinePage() {
  usePageTitle('Pipeline')
  const [summary, setSummary] = useState<PipelineSummary | null>(null)
  const [projects, setProjects] = useState<PipelineProject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [workflowIcp, setWorkflowIcp] = useState(
    'Founder-led AI and cybersecurity agencies that need governed agents for sales, delivery, reporting, and security workflows',
  )
  const [workflowCompany, setWorkflowCompany] = useState('')
  const [workflowRunning, setWorkflowRunning] = useState(false)
  const [workflowResult, setWorkflowResult] = useState<CustomerAcquisitionWorkflowResult | null>(null)
  // Per-project pending guard for the kanban Advance/Approve button. Mirrors
  // TasksPage's retryingId === task.id per-item idiom. See handleAdvance for why
  // an unguarded double-click is a governance hazard, not just a cosmetic dupe.
  const [advancingId, setAdvancingId] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [sumRes, projRes] = await Promise.allSettled([
        api.get<ApiResponse<PipelineSummary>>('/pipeline/summary'),
        api.get<{ success?: boolean; projects?: PipelineProject[]; data?: { projects?: PipelineProject[] } }>('/pipeline/projects'),
      ])
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data.data || null)
      else setError('Failed to load pipeline summary')
      if (projRes.status === 'fulfilled') {
        // Live backend returns the unwrapped shape { success, projects, pagination };
        // older callers may wrap as { data: { projects } }. Support both.
        const payload = projRes.value.data
        const projects = payload.data?.projects ?? payload.projects ?? []
        setProjects(projects)
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

  const handleRunCustomerAcquisition = async () => {
    if (!workflowIcp.trim()) return
    setWorkflowRunning(true)
    setWorkflowResult(null)
    try {
      const { data } = await api.post<ApiResponse<CustomerAcquisitionWorkflowResult>>(
        '/sales/customer-acquisition/draft-workflow',
        {
          icp_description: workflowIcp.trim(),
          seed_company: workflowCompany.trim() || null,
          limit: 3,
          signer: 'Masoud',
        },
        { silent: false },
      )
      setWorkflowResult(data.data)
      toast.success('Draft workflow created. Approval is waiting in Governance.')
      await fetchData()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string; error?: { message?: string } } } })
          ?.response?.data?.detail ||
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ||
        'Could not run the draft workflow'
      toast.error(msg)
    } finally {
      setWorkflowRunning(false)
    }
  }

  const handleAdvance = async (projectId: string, currentStage: string) => {
    // Single-flight guard. The advance endpoint advances from the project's
    // CURRENT db stage (the body carries no target stage), so a rapid
    // double-click before fetchData re-renders the card would fire a SECOND
    // advance off the now-stale stage -- moving the governed deal two stages on
    // one intent and computing founder_approved from the stale closure. Block
    // any concurrent advance and disable the in-flight card's button below.
    if (advancingId) return
    const needsApproval = HUMAN_GATES.has(currentStage)
    setAdvancingId(projectId)
    try {
      const res = await api.post(`/pipeline/projects/${projectId}/advance`, {
        founder_approved: needsApproval,
        notes: 'Advanced from Pipeline board',
      })
      // The pipeline router returns its errors as an ok-false envelope at HTTP
      // 200 (uniform house contract -- there is no raise HTTPException in
      // pipeline.py), so a rejected transition (including a governance
      // human-gate refusal) never reaches the catch below. Honor the envelope
      // the way WorkstreamsPage.submitRedirect does, or the operator is told
      // "advanced" over a transition the backend actually rejected.
      if (res.data?.success === false) {
        toast.error(res.data?.error?.message || 'Could not advance the project')
        return
      }
      toast.success('Project advanced')
      await fetchData()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message || 'Failed to advance'
      toast.error(msg)
    } finally {
      setAdvancingId(null)
    }
  }

  // Marking a deal lost is deliberately gated behind a reason prompt.
  // The reason flows to the Sales.lost_deal BorderAgent signal so
  // Marketing and Research can aggregate loss patterns without needing
  // to ask the founder after the fact.
  const handleMarkLost = async (projectId: string, title: string) => {
    const reason = await promptDialog({
      title: `Mark "${title}" as lost?`,
      message:
        'Optional: what was the reason? Flows to the Sales.lost_deal signal ' +
        'so Marketing and Research can aggregate loss patterns.',
      placeholder: 'e.g. Budget reallocated, chose competitor, timing slipped...',
      multiline: true,
      maxLength: 200,
      confirmLabel: 'Mark lost',
      variant: 'warning',
    })
    // User cancelled -- do nothing. (promptDialog returns null on cancel
    // to match native window.prompt semantics.)
    if (reason === null) return
    try {
      const res = await api.post(`/pipeline/projects/${projectId}/mark-lost`, {
        reason: reason.trim() || null,
      })
      // Same ok-false-at-200 envelope as advance: a rejected mark-lost (already
      // lost / CLOSED) returns success:false at HTTP 200, never reaching catch.
      if (res.data?.success === false) {
        toast.error(res.data?.error?.message || 'Could not mark the project lost')
        return
      }
      toast.success('Project marked as lost')
      await fetchData()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message || 'Failed to mark lost'
      toast.error(msg)
    }
  }

  // Department filter — when set, kanban shows only projects owned by that department.
  const [deptFilter, setDeptFilter] = useState<string>('')
  const allDepartments = useMemo(() => {
    const set = new Set<string>()
    projects.forEach((p) => { if (p.owner_department) set.add(p.owner_department) })
    return [...set].sort()
  }, [projects])

  const filteredProjects = deptFilter
    ? projects.filter((p) => p.owner_department === deptFilter)
    : projects

  const getProjectsForStage = (stage: string) => filteredProjects.filter(p => p.stage === stage)

  if (loading) return <div className="p-6"><Shimmer count={8} layout="card-grid" /></div>

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-primary-500/15">
              <Kanban size={22} className="text-primary-400" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold text-starlight-100">Project Pipeline</h1>
              <p className="text-sm text-starlight-400">{deptFilter ? filteredProjects.length : (summary?.total || 0)} projects across 8 stages</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {allDepartments.length > 0 && (
              <select
                aria-label="Filter by department"
                value={deptFilter}
                onChange={(e) => setDeptFilter(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm bg-white/5 border border-white/10 text-starlight-200 focus:outline-none focus:border-primary-500/40 cursor-pointer"
              >
                <option value="">All departments</option>
                {allDepartments.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            )}
            <div className="flex items-center gap-2">
              <input
                type="text"
                aria-label="New project name"
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
            <Button variant="ghost" size="sm" aria-label="Refresh pipeline" onClick={() => void fetchData()}>
              <RefreshCw size={14} />
            </Button>
          </div>
        </div>

        <Card variant="glass" padding="md" className="mb-5 border-primary-500/20">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="warning">Draft-only</Badge>
                <Badge variant="info">Founder approval required</Badge>
              </div>
              <h2 className="text-sm font-display font-semibold text-starlight-100">
                Customer acquisition workflow
              </h2>
              <p className="text-xs text-starlight-500 mt-1">
                Creates CRM contacts, qualifies a lead, drafts outreach, creates a task, opens an approval, and logs audit. No external message is sent.
              </p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => void handleRunCustomerAcquisition()}
              disabled={workflowRunning || !workflowIcp.trim()}
              isLoading={workflowRunning}
            >
              Run Draft Workflow
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_240px] gap-3 mt-4">
            <textarea
              value={workflowIcp}
              onChange={(e) => setWorkflowIcp(e.target.value)}
              aria-label="Ideal customer profile"
              className="glass-input min-h-[78px] px-3 py-2 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500 resize-none"
              placeholder="Describe the ideal customer profile..."
            />
            <input
              type="text"
              value={workflowCompany}
              onChange={(e) => setWorkflowCompany(e.target.value)}
              aria-label="Seed company (optional)"
              className="glass-input h-10 px-3 py-2 rounded-lg text-sm text-starlight-200 placeholder:text-starlight-500"
              placeholder="Optional seed company"
            />
          </div>

          {workflowResult && (
            <div className="mt-4 rounded-xl border border-white/10 bg-midnight-500/35 p-3 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="success">Draft saved</Badge>
                <Badge variant="warning">Send blocked until approval</Badge>
                <span className="text-[11px] text-starlight-500">
                  Approval: {workflowResult.approval_request.id.slice(0, 8)}
                </span>
                <span className="text-[11px] text-starlight-500">
                  Task: {workflowResult.follow_up_task.status}
                </span>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div className="rounded-lg bg-white/[0.03] border border-white/5 p-3">
                  <p className="text-xs font-semibold text-starlight-200">
                    {workflowResult.contacts[0]?.full_name || 'Lead created'}
                  </p>
                  <p className="text-[11px] text-starlight-500 mt-0.5">
                    {workflowResult.contacts[0]?.title || 'No title'} · score {workflowResult.qualified_contact.score}
                  </p>
                  <p className="text-[11px] text-starlight-500 mt-0.5">
                    {workflowResult.contacts[0]?.email || 'No email stored'}
                  </p>
                </div>
                <div className="rounded-lg bg-white/[0.03] border border-white/5 p-3">
                  <p className="text-xs font-semibold text-starlight-200 truncate">
                    {workflowResult.outreach_draft.subject || 'Outreach draft'}
                  </p>
                  <p className="text-[11px] text-starlight-500 mt-1 line-clamp-3 whitespace-pre-wrap">
                    {workflowResult.outreach_draft.body}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <a
                  href="/governance/approvals"
                  className="text-xs text-primary-400 hover:text-primary-300 underline underline-offset-2"
                >
                  Open approval queue
                </a>
                <a
                  href="/tasks"
                  className="text-xs text-primary-400 hover:text-primary-300 underline underline-offset-2"
                >
                  Open follow-up task
                </a>
                <a
                  href="/governance/audit"
                  className="text-xs text-primary-400 hover:text-primary-300 underline underline-offset-2"
                >
                  Open audit log
                </a>
              </div>
            </div>
          )}
        </Card>

        {error && (
          <div role="alert" className="mb-4 px-4 py-3 rounded-xl bg-status-error/10 border border-status-error/20 flex items-center gap-2">
            <AlertCircle size={14} className="text-status-error shrink-0" />
            <p className="text-xs text-status-error">{error}</p>
            <button onClick={() => void fetchData()} className="ml-auto text-xs text-status-error hover:text-status-error/80 underline cursor-pointer">Retry</button>
          </div>
        )}

        {!error && projects.length === 0 && (
          <div className="mb-5 px-5 py-4 rounded-xl border border-dashed border-white/10 bg-white/[0.02] flex items-center gap-4">
            <Kanban size={28} className="text-starlight-600 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-starlight-300">No projects in the pipeline yet</p>
              <p className="text-xs text-starlight-500 mt-0.5">
                Type a project name in the field above and press <kbd className="px-1 py-0.5 rounded bg-white/10 text-[10px] font-mono">Enter</kbd> or click <strong>Create</strong> to add your first project.
                It will land in the <span className="text-primary-400">Discovery</span> stage automatically.
              </p>
            </div>
          </div>
        )}

        {/* Kanban board -- the only genuinely 2D surface; it scrolls horizontally
            within its own bounds so the rest of the page reflows to a 320px-wide
            viewport with no page-level horizontal scroll (WCAG SC 1.4.10 Reflow). */}
        <div className="overflow-x-auto pb-1">
          <div className="flex gap-3 min-w-[1200px]">
          {STAGES.map((stage) => {
            const stageProjects = getProjectsForStage(stage)
            const count = deptFilter ? stageProjects.length : (summary?.[stage] || stageProjects.length)
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
                                className="opacity-70 group-hover:opacity-100 flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] bg-status-error/10 text-status-error hover:bg-status-error/20 transition-all cursor-pointer"
                                title="Mark deal as lost"
                              >
                                <XCircle size={8} />
                                Lost
                              </button>
                            )}
                            {stage !== 'CLOSED' && !project.lost_at && (
                              <button
                                onClick={(e) => { e.stopPropagation(); void handleAdvance(project.id, stage) }}
                                disabled={advancingId === project.id}
                                className="opacity-70 group-hover:opacity-100 flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                                title={isGate ? 'Approve and advance' : 'Advance to next stage'}
                              >
                                <ArrowRight size={8} />
                                {advancingId === project.id ? 'Advancing' : isGate ? 'Approve' : 'Advance'}
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
    </div>
  )
}

export default PipelinePage
