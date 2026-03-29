/**
 * GovernanceApprovalsPage — approval queue with filtering, approve/reject actions.
 * Displays pending, approved, rejected, and expired approvals.
 */
import { useEffect, useMemo, useState } from 'react'
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
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Card, Badge, Button, Shimmer, EmptyState } from '@/components/common'
import { api } from '@/lib/api'
import type { ApprovalResponse, ApprovalStatus, ApiResponse } from '@/types/api'

const STATUS_CONFIG: Record<ApprovalStatus, { label: string; variant: string; icon: React.ReactNode }> = {
  PENDING: { label: 'Pending', variant: 'warning', icon: <Clock size={12} /> },
  APPROVED: { label: 'Approved', variant: 'success', icon: <CheckCircle2 size={12} /> },
  REJECTED: { label: 'Rejected', variant: 'danger', icon: <XCircle size={12} /> },
  AUTO_APPROVED: { label: 'Auto', variant: 'info', icon: <ShieldCheck size={12} /> },
  EXPIRED: { label: 'Expired', variant: 'default', icon: <Timer size={12} /> },
}

const FILTERS: ApprovalStatus[] = ['PENDING', 'APPROVED', 'REJECTED', 'AUTO_APPROVED', 'EXPIRED']

export function GovernanceApprovalsPage() {
  usePageTitle('Approvals')
  const [approvals, setApprovals] = useState<ApprovalResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [activeFilter, setActiveFilter] = useState<ApprovalStatus | 'ALL'>('PENDING')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchApprovals = async () => {
    setLoading(true)
    try {
      const params = activeFilter !== 'ALL' ? `?status=${activeFilter}` : ''
      const { data } = await api.get<ApiResponse<ApprovalResponse[]>>(`/governance/approvals${params}`)
      setApprovals(data.data || [])
    } catch {
      // Graceful degradation
      setApprovals([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchApprovals()
  }, [activeFilter])

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    setActionLoading(id)
    try {
      const decision = action === 'approve' ? 'APPROVED' : 'REJECTED'
      await api.post(`/governance/approvals/${id}/decide`, { decision })
      await fetchApprovals()
    } catch (err: unknown) {
      const { toast } = await import('@/stores/toastStore')
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
          <Button variant="ghost" size="sm" onClick={fetchApprovals}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </Button>
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
                        </div>
                        <p className="text-sm font-medium text-starlight-200 mb-1">
                          {approval.action_type || 'Unknown Action'}
                        </p>
                        <p className="text-xs text-starlight-500">
                          Risk: {approval.risk_level || 'N/A'} · Requested {new Date(approval.created_at).toLocaleString()}
                        </p>
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
    </div>
  )
}

export default GovernanceApprovalsPage
