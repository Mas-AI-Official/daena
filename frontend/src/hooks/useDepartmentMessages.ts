/**
 * useDepartmentMessages: inbox + outbox + answer actions for one department.
 *
 * Session C of the "Daena as a Living Company" plan. Provides the
 * state the DepartmentInbox page needs:
 *   - inbox:  messages addressed to this department
 *   - outbox: messages this department sent (to poll for answers)
 *   - sendMessage: dispatch a new ASK
 *   - answer: reply to one in the inbox
 *   - refresh: manual re-poll
 *
 * Polling cadence: 10s. Slower than the Company Dashboard (5s)
 * because message volume per dept is lower than state transitions,
 * and the auto-acknowledge side-effect means we do not want to
 * spam the ACKNOWLEDGED flip on every tab refresh.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '@/lib/api'

export type MessageStatus = 'SENT' | 'ACKNOWLEDGED' | 'ANSWERED' | 'EXPIRED'

export interface DepartmentMessage {
  id: string
  from_department: string
  to_department: string
  subject: string
  body: string
  context_ref: string | null
  status: MessageStatus
  answer: string | null
  created_at: string | null
  acknowledged_at: string | null
  answered_at: string | null
  expires_at: string | null
}

export interface SendMessageInput {
  from_department: string
  to_department: string
  subject: string
  body: string
  context_ref?: string
  ttl_seconds?: number
}

interface UseDepartmentMessagesReturn {
  inbox: DepartmentMessage[]
  outbox: DepartmentMessage[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  sendMessage: (input: SendMessageInput) => Promise<DepartmentMessage | null>
  answer: (messageId: string, body: string) => Promise<DepartmentMessage | null>
}

const POLL_MS = 10_000

export function useDepartmentMessages(department: string): UseDepartmentMessagesReturn {
  const [inbox, setInbox] = useState<DepartmentMessage[]>([])
  const [outbox, setOutbox] = useState<DepartmentMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    if (!department) {
      setInbox([])
      setOutbox([])
      setLoading(false)
      return
    }
    try {
      const encoded = encodeURIComponent(department)
      // Include closed messages on outbox so the sender can see its
      // answered requests without toggling; inbox stays open-only.
      const [inRes, outRes] = await Promise.all([
        api.get<DepartmentMessage[]>(`/department-messages/inbox?department=${encoded}`),
        api.get<DepartmentMessage[]>(`/department-messages/outbox?department=${encoded}&include_closed=true`),
      ])
      setInbox(inRes.data)
      setOutbox(outRes.data)
      setError(null)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load messages'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [department])

  const sendMessage = useCallback(async (input: SendMessageInput): Promise<DepartmentMessage | null> => {
    try {
      const res = await api.post<DepartmentMessage>('/department-messages', input)
      // Optimistic refresh so the caller sees the new row immediately
      void refresh()
      return res.data
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Send failed'
      setError(msg)
      return null
    }
  }, [refresh])

  const answer = useCallback(async (messageId: string, body: string): Promise<DepartmentMessage | null> => {
    try {
      const res = await api.post<DepartmentMessage>(
        `/department-messages/${encodeURIComponent(messageId)}/answer`,
        { body },
      )
      void refresh()
      return res.data
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Answer failed'
      setError(msg)
      return null
    }
  }, [refresh])

  useEffect(() => {
    void refresh()
    intervalRef.current = setInterval(() => {
      void refresh()
    }, POLL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [refresh])

  return {
    inbox,
    outbox,
    loading,
    error,
    refresh,
    sendMessage,
    answer,
  }
}
