/**
 * useApprovalsStream -- subscribe to live approval lifecycle events.
 *
 * Bridges the backend ``/api/v1/governance/approvals/events`` SSE
 * endpoint to a React component. Events:
 *
 *   - ``approval.pending``  -- prepend to the local list / mark badge
 *   - ``approval.resolved`` -- update status in place
 *   - ``approval.expired``  -- update status in place
 *
 * The hook does NOT fetch or own the approvals list itself -- the
 * page component still hydrates via ``GET /api/v1/governance/approvals``
 * for the initial render. The stream then keeps that list current
 * without polling.
 *
 * If the SSE connection cannot recover after maxRetries, the
 * ``fallbackPoll`` callback runs once so the page still has fresh
 * data (typically calling the same fetch the page used at mount).
 *
 * Usage::
 *
 *   useApprovalsStream({
 *     onPending: (event) => setApprovals(curr => [event, ...curr]),
 *     onResolved: (event) => setApprovals(curr =>
 *       curr.map(a => a.id === event.approval_id ? { ...a, status: event.decision } : a)
 *     ),
 *     onExpired: (event) => setApprovals(curr =>
 *       curr.map(a => a.id === event.approval_id ? { ...a, status: 'EXPIRED' } : a)
 *     ),
 *     fallbackPoll: () => fetchApprovals(),
 *   })
 */
import { useResilientSSE, type SSEEvent } from '@/lib/sse'

export interface ApprovalPendingEvent {
  approval_id: string
  tenant_id: string
  tier: number
  risk_level: string
  action_type: string
  session_id: string | null
  expires_at: string
  created_at: string
}

export interface ApprovalResolvedEvent {
  approval_id: string
  tenant_id: string
  decision: 'APPROVED' | 'REJECTED'
  resolver_user_id: string
  decided_at: string | null
  reason: string | null
}

export interface ApprovalExpiredEvent {
  approval_id: string
  tenant_id: string
  expired_at: string
}

export interface UseApprovalsStreamOptions {
  enabled?: boolean
  onPending?: (event: ApprovalPendingEvent) => void
  onResolved?: (event: ApprovalResolvedEvent) => void
  onExpired?: (event: ApprovalExpiredEvent) => void
  fallbackPoll?: () => Promise<void> | void
}

export function useApprovalsStream(opts: UseApprovalsStreamOptions = {}) {
  const {
    enabled = true,
    onPending,
    onResolved,
    onExpired,
    fallbackPoll,
  } = opts

  // Wiring through useResilientSSE keeps reconnect / heartbeat /
  // backoff logic identical to the chat + scan streams. The hook
  // returns the live status so callers can render a "Reconnecting..."
  // pill near the queue header.
  const { status, reconnectAttempt } = useResilientSSE({
    url: enabled ? '/api/v1/governance/approvals/events' : '',
    eventTypes: ['approval.pending', 'approval.resolved', 'approval.expired', 'ping'],
    onEvent: (ev: SSEEvent) => {
      if (!ev.type || ev.type === 'ping') return
      // Backend wraps every event in ``{ type, data, channel, ts }``.
      // Domain code only cares about ``data``.
      const data = (ev.data as { data?: unknown })?.data ?? ev.data
      switch (ev.type) {
        case 'approval.pending':
          onPending?.(data as ApprovalPendingEvent)
          break
        case 'approval.resolved':
          onResolved?.(data as ApprovalResolvedEvent)
          break
        case 'approval.expired':
          onExpired?.(data as ApprovalExpiredEvent)
          break
        default:
          // Unknown event types silently ignored so future server-side
          // additions don't break older clients.
          break
      }
    },
    fallbackPoll,
  })

  return { status, reconnectAttempt }
}
