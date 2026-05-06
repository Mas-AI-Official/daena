/**
 * GovernanceApprovalsPage — approval queue with filtering, approve/reject actions.
 * Displays pending, approved, rejected, and expired approvals.
 */
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ShieldCheck,
  ShieldAlert,
  Clock,
  CheckCircle2,
  XCircle,
  Timer,
  Filter,
  RefreshCw,
  User,
  Building2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useApprovalsStream } from '@/hooks/useApprovalsStream'
import { Card, Badge, Button, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import { promptDialog } from '@/stores/confirmStore'
import { toast } from '@/stores/toastStore'
import type { ApprovalResponse, ApprovalStatus, ApiResponse } from '@/types/api'
import {
  Phase3ApprovalModal,
  isPhase3ToolId,
  type Phase3ApprovalDetails,
  type Phase3ToolId,
} from '@/components/governance/Phase3ApprovalModal'

const STATUS_CONFIG: Record<ApprovalStatus, { label: string; variant: string; icon: React.ReactNode }> = {
  PENDING: { label: 'Pending', variant: 'warning', icon: <Clock size={12} /> },
  APPROVED: { label: 'Approved', variant: 'success', icon: <CheckCircle2 size={12} /> },
  REJECTED: { label: 'Rejected', variant: 'danger', icon: <XCircle size={12} /> },
  AUTO_APPROVED: { label: 'Auto', variant: 'info', icon: <ShieldCheck size={12} /> },
  EXPIRED: { label: 'Expired', variant: 'default', icon: <Timer size={12} /> },
}

const FILTERS: ApprovalStatus[] = ['PENDING', 'APPROVED', 'REJECTED', 'AUTO_APPROVED', 'EXPIRED']

const VALID_STATUS: ReadonlyArray<ApprovalStatus | 'ALL'> = [
  'ALL', 'PENDING', 'APPROVED', 'REJECTED', 'AUTO_APPROVED', 'EXPIRED',
]

function readStatusFromUrl(searchParams: URLSearchParams): ApprovalStatus | 'ALL' {
  const raw = searchParams.get('status')
  if (raw && (VALID_STATUS as ReadonlyArray<string>).includes(raw)) {
    return raw as ApprovalStatus | 'ALL'
  }
  return 'PENDING'
}

export function GovernanceApprovalsPage() {
  usePageTitle('Approvals')
  const [searchParams, setSearchParams] = useSearchParams()
  const [approvals, setApprovals] = useState<ApprovalResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  // Filter syncs to URL ?status=... so refresh and deep-links preserve view.
  const [activeFilter, _setActiveFilter] = useState<ApprovalStatus | 'ALL'>(() => readStatusFromUrl(searchParams))
  const setActiveFilter = (next: ApprovalStatus | 'ALL') => {
    _setActiveFilter(next)
    setSearchParams((prev) => {
      const sp = new URLSearchParams(prev)
      if (next === 'PENDING') sp.delete('status') // PENDING is the default
      else sp.set('status', next)
      return sp
    }, { replace: true })
  }
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Sync from URL on back/forward.
  useEffect(() => {
    const fromUrl = readStatusFromUrl(searchParams)
    if (fromUrl !== activeFilter) _setActiveFilter(fromUrl)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const fetchApprovals = async () => {
    setLoading(true)
    try {
      const params = activeFilter !== 'ALL' ? `?status=${activeFilter}` : ''
      const { data } = await api.get<ApiResponse<ApprovalResponse[]>>(`/governance/approvals${params}`)
      setApprovals(data.data || [])
      setLoadError(null)
    } catch (err: unknown) {
      setApprovals([])
      const msg =
        (err as { response?: { data?: { detail?: string; error?: { message?: string } } } })
          ?.response?.data?.detail ||
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ||
        'Approval queue unavailable. Check backend health and your role.'
      setLoadError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchApprovals()
  }, [activeFilter])

  // Live SSE bridge: any approval lifecycle event mutates the visible
  // list in place, which removes the latency between an action being
  // dispatched and the queue showing it. The 30s polling backstop
  // below stays in place so a permanent SSE failure still degrades
  // gracefully.
  const { status: streamStatus, reconnectAttempt } = useApprovalsStream({
    enabled: true,
    onPending: (event) => {
      // Only PENDING / ALL views care about a brand-new request.
      if (activeFilter !== 'PENDING' && activeFilter !== 'ALL') return
      setApprovals((curr) => {
        if (curr.some((a) => a.id === event.approval_id)) return curr
        const next: ApprovalResponse = {
          id: event.approval_id,
          tenant_id: event.tenant_id,
          user_id: '',
          action_type: event.action_type,
          action_params: null,
          risk_level: event.risk_level,
          governance_tier: event.tier,
          status: 'PENDING',
          decided_by: null,
          decided_at: null,
          decision_reason: null,
          expires_at: event.expires_at,
          session_id: event.session_id,
          created_at: event.created_at,
          updated_at: event.created_at,
        } as ApprovalResponse
        return [next, ...curr]
      })
    },
    onResolved: (event) => {
      setApprovals((curr) =>
        curr.map((a) =>
          a.id === event.approval_id
            ? {
                ...a,
                status: event.decision as ApprovalStatus,
                decided_at: event.decided_at,
                decision_reason: event.reason,
              }
            : a,
        ),
      )
    },
    onExpired: (event) => {
      setApprovals((curr) =>
        curr.map((a) =>
          a.id === event.approval_id ? { ...a, status: 'EXPIRED' } : a,
        ),
      )
    },
    fallbackPoll: () => fetchApprovals(),
  })

  // Auto-refresh pending approvals every 30s -- but pause when the tab is
  // hidden (tabs in background were burning bandwidth and rate-limit budget
  // on a queue the operator wasn't watching). Resume + immediate refresh
  // on visibility change so the queue is fresh when the operator returns.
  // SSE handles the live path; this polling stays as a graceful-degrade
  // backstop for proxies that drop EventSource.
  useEffect(() => {
    if (activeFilter !== 'PENDING' && activeFilter !== 'ALL') return
    let interval: ReturnType<typeof setInterval> | null = null

    const start = () => {
      if (interval) return
      interval = setInterval(() => { fetchApprovals() }, 30000)
    }
    const stop = () => {
      if (interval) { clearInterval(interval); interval = null }
    }

    if (!document.hidden) start()

    const onVisibility = () => {
      if (document.hidden) {
        stop()
      } else {
        // Tab returned -- refresh once immediately, then resume polling.
        fetchApprovals()
        start()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilter])

  // Sprint-14 PR-6: Phase 3 controlled-execution approvals open the
  // rich modal (payload preview + hash + Asset Shield + rollback)
  // instead of the plain promptDialog. The decision still routes to
  // the same backend endpoint.
  const [phase3Details, setPhase3Details] = useState<Phase3ApprovalDetails | null>(null)
  const phase3Open = phase3Details != null

  const openPhase3Modal = (approval: ApprovalResponse) => {
    if (!isPhase3ToolId(approval.action_type)) return false
    const params = (approval.action_params || {}) as Record<string, unknown>
    // Sprint-15 PR-3: send approvals carry a draft_preview snapshot
    // captured by the upstream send-approval creator (To, Subject,
    // snippet). The modal renders it inside the irrevocability
    // banner so the operator sees what is about to leave Gmail.
    const draftPreviewRaw = params['draft_preview'] as
      | { to?: unknown; subject?: unknown; snippet?: unknown }
      | undefined
    const draft_preview = draftPreviewRaw
      ? {
          to: typeof draftPreviewRaw.to === 'string' ? draftPreviewRaw.to : null,
          subject: typeof draftPreviewRaw.subject === 'string' ? draftPreviewRaw.subject : null,
          snippet: typeof draftPreviewRaw.snippet === 'string' ? draftPreviewRaw.snippet : null,
        }
      : null
    setPhase3Details({
      approval_id: approval.id,
      action_type: approval.action_type as Phase3ToolId,
      owner_email: (params['owner_email'] as string) || null,
      payload: (params['payload'] as Record<string, unknown>) || params,
      payload_hash: (params['payload_hash'] as string) || null,
      asset_shield_pass:
        params['asset_shield_pass'] !== false,
      rollback_or_undo_instruction:
        (params['rollback_or_undo_instruction'] as string) || null,
      draft_preview,
    })
    return true
  }

  const submitPhase3Decision = async (
    decision: 'APPROVED' | 'REJECTED',
    note: string,
  ) => {
    if (!phase3Details) return
    setActionLoading(phase3Details.approval_id)
    try {
      await api.post(`/governance/approvals/${phase3Details.approval_id}/decide`, {
        decision,
        reason: note || null,
      })
      toast.success(
        `Phase 3 request ${decision === 'APPROVED' ? 'approved' : 'rejected'}`,
      )
      setPhase3Details(null)
      await fetchApprovals()
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : 'Failed to record Phase 3 decision',
      )
    } finally {
      setActionLoading(null)
    }
  }

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    // Phase 3 controlled-execution approvals open the rich modal.
    const approval = approvals.find(a => a.id === id)
    if (action === 'approve' && approval && openPhase3Modal(approval)) return

    // Reject ALWAYS requires a reason (audit trail integrity).
    // Approve takes an optional note — typing empty string still proceeds.
    const reason = await promptDialog({
      title: action === 'approve' ? 'Approve this request?' : 'Reject this request',
      message:
        action === 'approve'
          ? 'Optional note for the audit trail (why you approved). Leave blank to approve without notes.'
          : 'Required: why are you rejecting? This is recorded in the audit trail and surfaced to the requesting agent.',
      placeholder: action === 'approve' ? 'e.g. budget verified, client signed off' : 'e.g. out of policy, exceeds limit, needs more context',
      multiline: true,
      maxLength: 500,
      confirmLabel: action === 'approve' ? 'Approve' : 'Reject',
      variant: action === 'approve' ? 'primary' : 'danger',
    })

    // promptDialog returns null on cancel, string (possibly empty) on confirm
    if (reason === null) return
    const trimmed = reason.trim()
    if (action === 'reject' && !trimmed) {
      toast.error('A reason is required when rejecting an approval')
      return
    }

    setActionLoading(id)
    try {
      const decision = action === 'approve' ? 'APPROVED' : 'REJECTED'
      await api.post(`/governance/approvals/${id}/decide`, {
        decision,
        reason: trimmed || null,
      })
      toast.success(`Approval ${action === 'approve' ? 'approved' : 'rejected'}`)
      await fetchApprovals()
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action} approval`)
    } finally {
      setActionLoading(null)
    }
  }

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
            <div className="p-2.5 rounded-lg bg-status-warning/15">
              <ShieldAlert size={22} className="text-status-warning" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold text-starlight-100">Approval Queue</h1>
              <p className="text-sm text-starlight-400">Review and manage governance approvals</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Live SSE indicator: tells the operator the queue is
                actually being kept current vs polling-only. */}
            {streamStatus === 'connected' && (
              <span className="flex items-center gap-1 text-[11px] text-status-success">
                <span className="w-1.5 h-1.5 rounded-full bg-status-success animate-pulse" />
                Live
              </span>
            )}
            {streamStatus === 'reconnecting' && (
              <span className="text-[11px] text-status-warning">
                Reconnecting ({reconnectAttempt}/5)...
              </span>
            )}
            {streamStatus === 'fallback' && (
              <span className="text-[11px] text-starlight-500">
                Polling fallback
              </span>
            )}
            <Button variant="ghost" size="sm" onClick={fetchApprovals}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </Button>
          </div>
        </motion.div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <Filter size={14} className="text-starlight-500" />
          <button
            onClick={() => setActiveFilter('ALL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
              activeFilter === 'ALL'
                ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                : 'text-starlight-400 hover:text-starlight-200 border border-transparent'
            }`}
          >
            All
          </button>
          {FILTERS.map((status) => {
            const cfg = STATUS_CONFIG[status]
            return (
              <button
                key={status}
                onClick={() => setActiveFilter(status)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeFilter === status
                    ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                    : 'text-starlight-400 hover:text-starlight-200 border border-transparent'
                }`}
              >
                {cfg.icon}
                {cfg.label}
              </button>
            )
          })}
        </div>

        {/* Info banner — only Tier 3+ actions require approval */}
        <Card variant="glass" padding="sm" className="flex items-center gap-2 text-xs text-starlight-400">
          <ShieldAlert size={14} className="text-status-warning shrink-0" />
          Only Tier 3+ actions (high-risk, critical) appear here. Routine actions (Tier 0-2) are logged silently in the Audit Log.
        </Card>

        {loadError && !loading && (
          <Card variant="glass" padding="sm" className="border-status-error/20 bg-status-error/5 flex items-start gap-2">
            <ShieldAlert size={14} className="text-status-error shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-status-error">Approval queue not loaded</p>
              <p className="text-[11px] text-starlight-400 mt-0.5">{loadError}</p>
            </div>
          </Card>
        )}

        {/* Approvals list */}
        {loading ? (
          <Shimmer count={3} layout="list" />
        ) : approvals.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title={activeFilter === 'PENDING' ? 'No pending approvals' : 'No approvals match this filter'}
            description={activeFilter === 'PENDING' ? 'All clear! Only Tier 3+ actions require approval.' : undefined}
          />
        ) : (
          <div className="space-y-3">
            <AnimatePresence mode="popLayout">
              {approvals.map((approval, i) => (
                <motion.div
                  key={approval.id}
                  layout
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ delay: i * 0.03 }}
                >
                  <Card variant="glass" padding="md" className="hover:border-white/10 transition-all">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={STATUS_CONFIG[approval.status].variant as 'warning' | 'success' | 'danger' | 'info' | 'default'}>
                            {STATUS_CONFIG[approval.status].label}
                          </Badge>
                          <span className="text-[10px] font-mono text-starlight-500">
                            {approval.governance_tier !== undefined && `Tier ${approval.governance_tier}`}
                          </span>
                          {approval.action_params && Object.keys(approval.action_params).length > 0 && (
                            <button
                              type="button"
                              onClick={() => setExpandedId(expandedId === approval.id ? null : approval.id)}
                              className="ml-auto flex items-center gap-1 text-[10px] text-starlight-500 hover:text-starlight-300 cursor-pointer"
                            >
                              {expandedId === approval.id ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                              {expandedId === approval.id ? 'Hide details' : 'Show details'}
                            </button>
                          )}
                        </div>
                        <p className="text-sm font-medium text-starlight-200 mb-1">
                          {approval.action_type || 'Unknown Action'}
                        </p>
                        {expandedId === approval.id && approval.action_params && (
                          <pre className="text-[10px] text-starlight-300 font-mono bg-midnight-500/60 p-2 rounded mt-2 mb-2 max-h-48 overflow-y-auto whitespace-pre-wrap break-all">
                            {JSON.stringify(approval.action_params, null, 2)}
                          </pre>
                        )}
                        {approval.context?.project_name && (
                          <p className="text-xs text-primary-400 mb-1 flex items-center gap-1">
                            <Building2 size={10} />
                            {approval.context.project_name}
                          </p>
                        )}
                        <div className="flex items-center gap-3 text-xs text-starlight-500 flex-wrap">
                          <span>Risk: {approval.risk_level || 'N/A'}</span>
                          <span>Requested {new Date(approval.created_at).toLocaleString()}</span>
                          {approval.decided_by && (
                            <span className="flex items-center gap-1 text-status-success">
                              <User size={10} />
                              {approval.decided_by}
                              {approval.decided_at && ` at ${new Date(approval.decided_at).toLocaleString()}`}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Action buttons for pending */}
                      {approval.status === 'PENDING' && (
                        <div className="flex items-center gap-2 shrink-0">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleAction(approval.id, 'reject')}
                            disabled={actionLoading === approval.id}
                            className="!text-status-error hover:!bg-status-error/10"
                          >
                            <XCircle size={14} />
                            Reject
                          </Button>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleAction(approval.id, 'approve')}
                            isLoading={actionLoading === approval.id}
                          >
                            <CheckCircle2 size={14} />
                            Approve
                          </Button>
                        </div>
                      )}
                    </div>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Sprint-14 PR-6: Phase 3 controlled-execution approval modal.
          Opens for any approval whose action_type is in PHASE3_TOOL_IDS.
          Shows payload preview, hash, Asset Shield result, rollback. */}
      <Phase3ApprovalModal
        open={phase3Open}
        onClose={() => setPhase3Details(null)}
        details={phase3Details}
        onApprove={(note) => submitPhase3Decision('APPROVED', note)}
        onReject={(note) => submitPhase3Decision('REJECTED', note)}
      />
    </div>
  )
}

export default GovernanceApprovalsPage
