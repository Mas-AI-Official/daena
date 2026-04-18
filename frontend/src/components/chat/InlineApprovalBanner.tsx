/**
 * InlineApprovalBanner -- renders pending approvals inline in the chat.
 *
 * Polls /governance/approvals?status=PENDING every 5s and shows a
 * compact Approve/Reject card at the top of messages for each pending
 * approval. Keeps Masoud in the chat context instead of forcing a
 * round-trip to the /governance/approvals page whenever a tool call
 * or security engagement is gated.
 *
 * Data source is the same endpoint the Sidebar badge polls, so the
 * numbers always agree without any additional backend wiring.
 */
import { useCallback, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldAlert, CheckCircle2, XCircle, Loader2, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { ApiResponse } from '@/types/api'

interface PendingApproval {
  id: string
  action_type: string | null
  risk_level: string | null
  governance_tier: number | null
  status: string
  created_at: string | null
  action_params: Record<string, unknown> | null
  context: Record<string, unknown> | null
}

export function InlineApprovalBanner() {
  const [pending, setPending] = useState<PendingApproval[]>([])
  const [acting, setActing] = useState<string | null>(null)

  const fetchPending = useCallback(async () => {
    try {
      const { data } = await api.get<ApiResponse<PendingApproval[]>>(
        '/governance/approvals?status=PENDING&page_size=20',
      )
      setPending(data.data || [])
    } catch {
      // Graceful: keep prior list, do not crash chat.
    }
  }, [])

  useEffect(() => {
    void fetchPending()
    const id = setInterval(() => { void fetchPending() }, 5000)
    return () => clearInterval(id)
  }, [fetchPending])

  const decide = async (id: string, action: 'approve' | 'reject') => {
    setActing(id)
    try {
      const decision = action === 'approve' ? 'APPROVED' : 'REJECTED'
      await api.post(`/governance/approvals/${id}/decide`, { decision })
      // Refetch immediately so the card disappears without waiting on
      // the next poll tick.
      await fetchPending()
      toast.success(`Approval ${decision.toLowerCase()}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to ${action}`)
    } finally {
      setActing(null)
    }
  }

  if (pending.length === 0) return null

  return (
    <div className="space-y-1.5 px-3 pt-2">
      <AnimatePresence initial={false}>
        {pending.slice(0, 3).map((p) => {
          const target = (p.action_params as Record<string, unknown> | null)?.target ||
                         (p.action_params as Record<string, unknown> | null)?.tool_name ||
                         p.action_type ||
                         'Unknown action'
          const tier = p.governance_tier ?? 3
          const risk = p.risk_level || 'HIGH'
          const busy = acting === p.id
          return (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.15 }}
              className="p-2.5 rounded-md border border-status-warning/30 bg-status-warning/5 flex items-center gap-2.5"
            >
              <ShieldAlert size={16} className="text-status-warning shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-starlight-100 truncate">
                  Approval needed -- {p.action_type || 'action'}
                </p>
                <p className="text-[11px] text-starlight-400 truncate">
                  Tier {tier} / {risk} -- {String(target).slice(0, 100)}
                </p>
              </div>
              <button
                onClick={() => void decide(p.id, 'approve')}
                disabled={busy}
                className="px-2 py-1 rounded-md text-[11px] font-medium bg-status-success/20 text-status-success hover:bg-status-success/30 disabled:opacity-50 flex items-center gap-1"
              >
                {busy ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />}
                Approve
              </button>
              <button
                onClick={() => void decide(p.id, 'reject')}
                disabled={busy}
                className="px-2 py-1 rounded-md text-[11px] font-medium bg-status-error/20 text-status-error hover:bg-status-error/30 disabled:opacity-50 flex items-center gap-1"
              >
                <XCircle size={11} /> Reject
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>

      {pending.length > 3 && (
        <Link
          to="/governance/approvals"
          className="flex items-center gap-1 text-[11px] text-starlight-400 hover:text-accent-cyan px-1"
        >
          <ExternalLink size={10} />
          {pending.length - 3} more pending -- view all approvals
        </Link>
      )}
    </div>
  )
}

export default InlineApprovalBanner
