/**
 * DaenaBot store — manages computer-control command state.
 *
 * Tracks command history, pending approvals, and execution status
 * for the DaenaBot interface page.
 */
import { create } from 'zustand'
import { api } from '@/lib/api'
import type { ApiResponse } from '@/types/api'

// ── Types ──

export interface DaenaBotMessage {
  id: string
  role: 'user' | 'system'
  content: string
  timestamp: number
  // Only for system messages (responses)
  status?: 'executed' | 'pending_approval' | 'blocked' | 'error' | 'no_match'
  agent?: string | null
  operation?: string | null
  description?: string | null
  governanceTier?: number
  result?: Record<string, unknown> | null
  approvalId?: string | null
}

export interface DaenaBotAgent {
  name: string
  description: string
  operations: string[]
}

interface DaenaBotState {
  messages: DaenaBotMessage[]
  pendingApprovals: DaenaBotMessage[]
  isExecuting: boolean
  agents: DaenaBotAgent[]
  agentsLoaded: boolean

  // Actions
  sendCommand: (command: string) => Promise<void>
  approveAction: (approvalId: string) => Promise<void>
  rejectAction: (approvalId: string) => void
  fetchAgents: () => Promise<void>
  clearHistory: () => void
}

export const useDaenaBotStore = create<DaenaBotState>((set, get) => ({
  messages: [],
  pendingApprovals: [],
  isExecuting: false,
  agents: [],
  agentsLoaded: false,

  sendCommand: async (command: string) => {
    const userMsg: DaenaBotMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: command,
      timestamp: Date.now(),
    }

    set((s) => ({
      messages: [...s.messages, userMsg],
      isExecuting: true,
    }))

    try {
      const { data } = await api.post<ApiResponse<{
        status: string
        agent: string | null
        operation: string | null
        description: string | null
        governance_tier: number
        result: Record<string, unknown> | null
        approval_id: string | null
        message: string | null
      }>>('/daenabot/execute', { command })

      const resp = data.data ?? data
      const sysMsg: DaenaBotMessage = {
        id: crypto.randomUUID(),
        role: 'system',
        content: resp.message ?? resp.description ?? 'Command processed.',
        timestamp: Date.now(),
        status: resp.status as DaenaBotMessage['status'],
        agent: resp.agent,
        operation: resp.operation,
        description: resp.description,
        governanceTier: resp.governance_tier,
        result: resp.result,
        approvalId: resp.approval_id,
      }

      set((s) => {
        const updated: Partial<DaenaBotState> = {
          messages: [...s.messages, sysMsg],
          isExecuting: false,
        }
        if (resp.status === 'pending_approval') {
          updated.pendingApprovals = [...s.pendingApprovals, sysMsg]
        }
        return updated as DaenaBotState
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Command failed'
      const errMsg: DaenaBotMessage = {
        id: crypto.randomUUID(),
        role: 'system',
        content: message,
        timestamp: Date.now(),
        status: 'error',
      }
      set((s) => ({
        messages: [...s.messages, errMsg],
        isExecuting: false,
      }))
    }
  },

  approveAction: async (approvalId: string) => {
    try {
      await api.post(`/governance/approvals/${approvalId}/decide`, {
        decision: 'APPROVED',
        reason: 'User approved from DaenaBot UI',
      })
      set((s) => ({
        pendingApprovals: s.pendingApprovals.filter(
          (m) => m.approvalId !== approvalId,
        ),
        messages: s.messages.map((m) =>
          m.approvalId === approvalId
            ? { ...m, status: 'executed' as const, content: 'Approved and executed.' }
            : m,
        ),
      }))
    } catch (err) {
      console.error('Governance approval failed:', err)
    }
  },

  rejectAction: async (approvalId: string) => {
    try {
      await api.post(`/governance/approvals/${approvalId}/decide`, {
        decision: 'REJECTED',
        reason: 'User rejected from DaenaBot UI',
      })
    } catch (err) {
      console.error('Governance rejection failed:', err)
    }
    set((s) => ({
      pendingApprovals: s.pendingApprovals.filter(
        (m) => m.approvalId !== approvalId,
      ),
      messages: s.messages.map((m) =>
        m.approvalId === approvalId
          ? { ...m, status: 'blocked' as const, content: 'Action rejected by user.' }
          : m,
      ),
    }))
  },

  fetchAgents: async () => {
    if (get().agentsLoaded) return
    try {
      const { data } = await api.get<{ agents: DaenaBotAgent[] }>('/daenabot/agents')
      const agents = data.agents ?? []
      set({ agents, agentsLoaded: true })
    } catch {
      // Non-critical
    }
  },

  clearHistory: () => set({ messages: [], pendingApprovals: [] }),
}))

export default useDaenaBotStore
