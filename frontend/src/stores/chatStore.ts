/**
 * Chat state management — sessions, messages, streaming, WebSocket.
 * Drives the entire ChatPage experience.
 */
import { create } from 'zustand'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { useUiStore } from '@/stores/uiStore'
import type {
  SessionResponse,
  MessageResponse,
  ApiResponse,
  ChatMode,
  RoutingMode,
  GovernanceSlider,
  UpdateSessionRequest,
  DaenaBotActivityEvent,
} from '@/types/api'

// ── Streaming state for active generation ──

interface DaenaBotActivity {
  agent: string
  operation: string
  status: 'executing' | 'completed' | 'failed'
  description: string
}

interface RuntimeActivity {
  runtimeId: string
  displayName: string
  status: 'executing' | 'completed' | 'failed'
  description: string
}

interface PipelineStage {
  label: string
  detail?: string
  status: 'done' | 'active' | 'pending'
}

interface StreamState {
  isStreaming: boolean
  thinkingContent: string
  streamedContent: string
  modelUsed: string | null
  daenabotActivity: DaenaBotActivity | null
  runtimeActivity: RuntimeActivity | null
  runtimeOutput: string
  pipelineStages: PipelineStage[]
}

interface StreamSessionInit {
  mode: ChatMode
  routingMode?: RoutingMode
  governanceSlider?: GovernanceSlider
  departmentId?: string
  autopilot?: boolean
  thinkMode?: boolean
}

interface SendMessageStreamOptions {
  createSession?: StreamSessionInit
  onSessionResolved?: (session: SessionResponse) => void
}

// ── Store shape ──

interface ChatState {
  // Session list
  sessions: SessionResponse[]
  sessionsLoading: boolean

  // Active session
  activeSessionId: string | null
  activeSession: SessionResponse | null

  // Messages for active session
  messages: MessageResponse[]
  messagesLoading: boolean

  // Streaming
  stream: StreamState

  // Error
  error: string | null

  // Retry -- stores last failed message content so user can re-send
  lastFailedMessage: string | null

  // Internal cache tracking (not for external use)
  _sessionsLastFetched: number

  // Actions
  fetchSessions: () => Promise<void>
  createSession: (opts: {
    mode: ChatMode
    routingMode?: RoutingMode
    governanceSlider?: GovernanceSlider
    departmentId?: string
    autopilot?: boolean
    thinkMode?: boolean
  }) => Promise<SessionResponse>
  updateSession: (sessionId: string, fields: UpdateSessionRequest) => Promise<void>
  deleteSession: (sessionId: string) => Promise<void>
  setActiveSession: (sessionId: string) => Promise<void>
  fetchMessages: (sessionId: string) => Promise<void>
  sendMessage: (content: string) => Promise<void>
  sendMessageStream: (
    content: string,
    preferredModel?: string | null,
    governanceSlider?: string | null,
    options?: SendMessageStreamOptions,
  ) => Promise<void>
  editAndRegenerate: (messageId: string, newContent: string) => Promise<void>
  regenerateLastResponse: (assistantMessageId: string) => Promise<void>
  retryLastMessage: () => Promise<void>
  clearError: () => void

  // Streaming controls
  startStream: () => void
  appendThinking: (chunk: string) => void
  appendContent: (chunk: string) => void
  finalizeStream: (msg: MessageResponse) => void
  cancelStream: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  // ── Initial state ──
  sessions: [],
  sessionsLoading: false,
  activeSessionId: null,
  activeSession: null,
  messages: [],
  messagesLoading: false,
  stream: {
    isStreaming: false,
    thinkingContent: '',
    streamedContent: '',
    modelUsed: null,
    daenabotActivity: null,
    runtimeActivity: null,
    runtimeOutput: '',
    pipelineStages: [],
  },
  error: null,
  lastFailedMessage: null,

  // ── Fetch all sessions (with 30s TTL cache to avoid re-fetch on route changes) ──
  _sessionsLastFetched: 0,
  fetchSessions: async (force = false) => {
    const now = Date.now()
    const state = get()
    // Skip re-fetch if data exists and was fetched within 30s (unless forced)
    if (!force && state.sessions.length > 0 && now - state._sessionsLastFetched < 30_000) {
      return
    }
    set({ sessionsLoading: true, error: null })
    try {
      const { data } = await api.get<ApiResponse<SessionResponse[]>>('/chat/sessions?include_archived=true')
      set({ sessions: data.data, sessionsLoading: false, _sessionsLastFetched: now })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load sessions'
      toast.error(msg)
      set({ sessionsLoading: false })
    }
  },

  // ── Create new session ──
  createSession: async ({ mode, routingMode = 'STANDARD', governanceSlider = 'STANDARD', departmentId, autopilot = false, thinkMode = false }) => {
    set({ error: null })
    try {
      const body: Record<string, unknown> = {
        mode,
        routing_mode: routingMode,
        governance_slider: governanceSlider,
        autopilot,
        think_mode: thinkMode,
      }
      if (departmentId) body.department_id = departmentId
      const { data } = await api.post<ApiResponse<SessionResponse>>('/chat/sessions', body)
      const session = data.data
      set((s) => ({ sessions: [session, ...s.sessions] }))
      return session
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create session'
      toast.error(msg)
      throw err
    }
  },

  // ── Update session metadata (PATCH) ──
  updateSession: async (sessionId, fields) => {
    try {
      const { data } = await api.patch<ApiResponse<SessionResponse>>(
        `/chat/sessions/${sessionId}`,
        fields,
      )
      const updated = data.data
      set((s) => ({
        sessions: s.sessions.map((ses) => (ses.id === sessionId ? updated : ses)),
        activeSession: s.activeSessionId === sessionId ? updated : s.activeSession,
      }))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update session'
      toast.error(msg)
    }
  },

  // ── Soft-delete a session (DELETE endpoint, removes from local state) ──
  deleteSession: async (sessionId) => {
    try {
      await api.delete(`/chat/sessions/${sessionId}`)
      set((s) => ({
        sessions: s.sessions.filter((ses) => ses.id !== sessionId),
        activeSessionId: s.activeSessionId === sessionId ? null : s.activeSessionId,
        activeSession: s.activeSessionId === sessionId ? null : s.activeSession,
      }))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete session'
      toast.error(msg)
    }
  },

  // ── Set active session + load messages ──
  setActiveSession: async (sessionId) => {
    // Skip if already active (prevents clearing messages after auto-create + send)
    if (get().activeSessionId === sessionId) return
    // Never reload messages while streaming (prevents user message disappearance)
    if (get().stream.isStreaming) {
      set((s) => ({ activeSessionId: sessionId, activeSession: s.sessions.find((ses) => ses.id === sessionId) || s.activeSession }))
      return
    }

    const { sessions } = get()
    const session = sessions.find((s) => s.id === sessionId) || null
    set({ activeSessionId: sessionId, activeSession: session, messages: [] })
    await get().fetchMessages(sessionId)
  },

  // ── Fetch messages for a session ──
  fetchMessages: async (sessionId) => {
    set({ messagesLoading: true, error: null })
    try {
      const { data } = await api.get<ApiResponse<MessageResponse[]>>(
        `/chat/sessions/${sessionId}/messages`,
      )
      set({ messages: data.data, messagesLoading: false })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load messages'
      toast.error(msg)
      set({ messagesLoading: false })
    }
  },

  // ── Send a message (non-streaming — adds to list, backend processes) ──
  sendMessage: async (content) => {
    const { activeSessionId } = get()
    if (!activeSessionId) return

    // Optimistic: add user message immediately
    const optimistic: MessageResponse = {
      id: `temp-${Date.now()}`,
      session_id: activeSessionId,
      role: 'USER',
      content,
      model_used: null,
      provider_used: null,
      governance_tier: null,
      cost_usd: null,
      latency_ms: null,
      token_count_input: null,
      token_count_output: null,
      created_at: new Date().toISOString(),
    }
    set((s) => ({ messages: [...s.messages, optimistic] }))

    try {
      const { data } = await api.post<ApiResponse<{ user_message: MessageResponse; assistant_message: MessageResponse }>>(
        `/chat/sessions/${activeSessionId}/messages`,
        { content, role: 'USER' },
      )
      // Replace optimistic USER msg with confirmed, append ASSISTANT reply
      set((s) => ({
        messages: [
          ...s.messages.map((m) =>
            m.id === optimistic.id ? data.data.user_message : m,
          ),
          data.data.assistant_message,
        ],
      }))
    } catch (err: unknown) {
      // Roll back optimistic message
      set((s) => ({
        messages: s.messages.filter((m) => m.id !== optimistic.id),
        error: err instanceof Error ? err.message : 'Failed to send message',
      }))
    }
  },

  // ── Edit a user message and regenerate from that point ──
  editAndRegenerate: async (messageId, newContent) => {
    const { activeSessionId, sendMessageStream } = get()
    if (!activeSessionId) return

    try {
      // 1. Truncate DB messages from the edited one onwards (use api instance for auth)
      const { api } = await import('@/lib/api')
      const truncRes = await api.delete(
        `/chat/sessions/${activeSessionId}/messages/truncate`,
        { data: { from_message_id: messageId } },
      )
      if (!truncRes.data?.success) {
        toast.error('Failed to truncate messages for edit')
        return
      }

      // 2. Truncate frontend state to before the edited message
      set((s) => {
        const idx = s.messages.findIndex((m) => m.id === messageId)
        return { messages: idx >= 0 ? s.messages.slice(0, idx) : s.messages }
      })

      // 3. Send the edited content as a fresh message (re-generates response)
      await sendMessageStream(newContent)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Edit failed')
    }
  },

  regenerateLastResponse: async (assistantMessageId) => {
    const { activeSessionId, messages, sendMessageStream } = get()
    if (!activeSessionId) return

    try {
      // Find the user message right before this assistant message
      const assistantIdx = messages.findIndex((m) => m.id === assistantMessageId)
      if (assistantIdx <= 0) return
      const userMsg = messages[assistantIdx - 1]
      if (userMsg.role !== 'USER') return

      const { api } = await import('@/lib/api')

      // 1. Truncate from the assistant message onwards
      await api.delete(
        `/chat/sessions/${activeSessionId}/messages/truncate`,
        { data: { from_message_id: assistantMessageId } },
      )

      // 2. Remove assistant message from frontend state
      set((s) => ({
        messages: s.messages.slice(0, assistantIdx),
      }))

      // 3. Re-send the same user message to get a new response
      await sendMessageStream(userMsg.content)
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Regenerate failed')
    }
  },

  // ── Send a message (streaming — SSE, tokens appear in real-time) ──
  sendMessageStream: async (content, preferredModel, governanceSlider, options) => {
    const { activeSessionId, startStream, appendContent, finalizeStream, cancelStream } = get()
    const createSession = options?.createSession
    const creatingSession = !activeSessionId && Boolean(createSession)
    if (!activeSessionId && !creatingSession) return

    set({ error: null, lastFailedMessage: null })

    if (creatingSession) {
      set({
        activeSessionId: null,
        activeSession: null,
        messages: [],
      })
    }

    // Optimistic user message
    const optimistic: MessageResponse = {
      id: `temp-${Date.now()}`,
      session_id: activeSessionId ?? 'pending-session',
      role: 'USER',
      content,
      model_used: null,
      provider_used: null,
      governance_tier: null,
      cost_usd: null,
      latency_ms: null,
      token_count_input: null,
      token_count_output: null,
      created_at: new Date().toISOString(),
    }
    set((s) => ({ messages: [...s.messages, optimistic] }))

    // Start streaming UI state
    startStream()

    try {
      const token = localStorage.getItem('daena_token')
      const body: Record<string, unknown> = { content, role: 'USER' }
      if (activeSessionId) body.session_id = activeSessionId
      if (preferredModel) body.preferred_model = preferredModel
      const resolvedGovernanceSlider =
        governanceSlider ?? createSession?.governanceSlider ?? null
      if (resolvedGovernanceSlider) body.governance_slider = resolvedGovernanceSlider
      // Always send current UI state on EVERY request so routing/action mode
      // changes mid-session are respected (not just on session creation).
      const uiState = useUiStore.getState()
      body.routing_mode = createSession?.routingMode ?? uiState.routingMode ?? 'STANDARD'
      body.mode = createSession?.mode ?? uiState.chatMode ?? 'CMD'
      body.autopilot = createSession?.autopilot ?? uiState.autopilotActive ?? false
      body.think_mode = createSession?.thinkMode ?? uiState.thinkingVisible ?? false

      if (createSession) {
        if (createSession.departmentId) {
          body.department_id = createSession.departmentId
        }
      }
      const res = await fetch('/api/v1/chat/messages/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        throw new Error(`Stream failed: ${res.status}`)
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No readable stream')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE lines: each event is "data: {...}\n\n"
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || '' // keep incomplete chunk

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const jsonStr = trimmed.slice(6) // strip "data: "

          try {
            const event = JSON.parse(jsonStr)

            if (event.type === 'session_created') {
              const session = event.data as SessionResponse
              set((s) => ({
                activeSessionId: session.id,
                activeSession: session,
                sessions: s.sessions.some((ses) => ses.id === session.id)
                  ? s.sessions.map((ses) => (ses.id === session.id ? session : ses))
                  : [session, ...s.sessions],
                messages: s.messages.map((m) =>
                  m.id === optimistic.id ? { ...m, session_id: session.id } : m,
                ),
              }))
              options?.onSessionResolved?.(session)
            } else if (event.type === 'user_message') {
              // Replace optimistic with confirmed user message
              set((s) => ({
                messages: s.messages.map((m) =>
                  m.id === optimistic.id ? event.data : m,
                ),
              }))
            } else if (event.type === 'thinking') {
              // Pipeline stage updates (analyzing, governance, routing, etc.)
              const stage = event.stage || ''
              const model = event.model ? ` → ${event.model}` : ''
              const STAGE_LABELS: Record<string, string> = {
                analyzing: 'Intent analysis',
                governance: 'Governance check',
                routing: 'Model routing',
                routing_override_unavailable: 'Model unavailable',
                council_synthesizing: 'Consulting models',
                council_completed: 'Synthesis complete',
                fallback_streaming: 'Fallback stream',
              }
              let label = STAGE_LABELS[stage] || stage
              // Enrich council stages with model/expert info
              if (stage === 'council_synthesizing') {
                const models = event.models as string[] | undefined
                if (models && models.length > 0) {
                  label = `Consulting ${models.length} models...`
                }
              } else if (stage === 'council_completed') {
                const count = event.responses as number | undefined
                const experts = event.experts_used as string[] | undefined
                if (experts && experts.length > 0) {
                  label = `${count ?? 0} models + ${experts.length} experts synthesized`
                } else if (count && count > 1) {
                  label = `${count} models synthesized`
                }
              }
              set((s) => {
                // Mark previous active stages as done, add new one as active
                const prev = s.stream.pipelineStages.map((p) =>
                  p.status === 'active' ? { ...p, status: 'done' as const } : p,
                )
                const newStage: PipelineStage = {
                  label,
                  detail: model || event.reason || undefined,
                  status: 'active',
                }
                return {
                  stream: {
                    ...s.stream,
                    thinkingContent: stage + model,
                    pipelineStages: [...prev, newStage],
                  },
                }
              })
            } else if (event.type === 'governance_notice') {
              // Inline governance notification — add as a pipeline stage
              set((s) => {
                const prev = s.stream.pipelineStages.map((p) =>
                  p.status === 'active' ? { ...p, status: 'done' as const } : p,
                )
                return {
                  stream: {
                    ...s.stream,
                    thinkingContent: `Governance: ${event.message}`,
                    pipelineStages: [...prev, {
                      label: `Governance T${event.tier}`,
                      detail: event.message,
                      status: 'done' as const,
                    }],
                  },
                }
              })
            } else if (event.type === 'chunk') {
              appendContent(event.content)
              // Pick up model_id from the first chunk that includes it
              if (event.model_id && !get().stream.modelUsed) {
                set((s) => ({
                  stream: { ...s.stream, modelUsed: event.model_id },
                }))
              }
            } else if (event.type === 'done') {
              // Build assistant message from event.data or synthesize from streamed content
              const assistantMsg: MessageResponse = event.data ?? {
                id: `synth-${Date.now()}`,
                session_id: get().activeSessionId ?? '',
                role: 'ASSISTANT',
                content: get().stream.streamedContent,
                model_used: event.model_id ?? get().stream.modelUsed ?? null,
                provider_used: event.provider ?? null,
                governance_tier: null,
                cost_usd: event.cost_usd ?? null,
                latency_ms: event.latency_ms ?? null,
                token_count_input: null,
                token_count_output: null,
                created_at: new Date().toISOString(),
              }
              finalizeStream(assistantMsg)
              // Pick up auto-generated session title from backend
              if (event.data?._session_title) {
                const title = event.data._session_title as string
                set((s) => ({
                  sessions: s.sessions.map((ses) =>
                    ses.id === get().activeSessionId ? { ...ses, title } : ses,
                  ),
                  activeSession: s.activeSession
                    ? { ...s.activeSession, title }
                    : s.activeSession,
                }))
              }
            } else if (event.type === 'daenabot_activity') {
              // DaenaBot agent activity indicator
              set((s) => ({
                stream: {
                  ...s.stream,
                  daenabotActivity: {
                    agent: event.agent,
                    operation: event.operation,
                    status: event.status,
                    description: event.description,
                  },
                },
              }))
            } else if (event.type === 'runtime_activity') {
              // Runtime adapter status (executing/completed/failed)
              set((s) => ({
                stream: {
                  ...s.stream,
                  runtimeActivity: {
                    runtimeId: event.runtime_id,
                    displayName: event.display_name,
                    status: event.status,
                    description: event.description,
                  },
                },
              }))
              // Add pipeline stage for runtime activity
              if (event.status === 'executing') {
                set((s) => {
                  const prev = s.stream.pipelineStages.map((p) =>
                    p.status === 'active' ? { ...p, status: 'done' as const } : p,
                  )
                  return {
                    stream: {
                      ...s.stream,
                      pipelineStages: [...prev, {
                        label: `Runtime: ${event.display_name}`,
                        detail: event.description,
                        status: 'active' as const,
                      }],
                    },
                  }
                })
              }
            } else if (event.type === 'runtime_output') {
              // Runtime execution output (plain text from adapter)
              const displayContent = event.content || ''
              if (displayContent) {
                appendContent(displayContent)
                set((s) => ({
                  stream: {
                    ...s.stream,
                    runtimeOutput: s.stream.runtimeOutput + displayContent + '\n',
                  },
                }))
              }
            } else if (event.type === 'interactive_prompt') {
              // Agent is pausing for user input -- route to UI store
              const uiStore = await import('@/stores/uiStore')
              uiStore.useUiStore.getState().addPrompt(event as never)
            } else if (event.type === 'error') {
              const errorMsg = event.message || 'Stream error'
              toast.error(errorMsg)
              // Save content for retry if backend says retryable
              if (event.can_retry) {
                set({ lastFailedMessage: optimistic.content })
              }
              cancelStream()
            }
          } catch {
            // Skip malformed JSON lines
          }
        }
      }
    } catch (err: unknown) {
      // Roll back optimistic and cancel stream, but save content for retry
      const msg = err instanceof Error ? err.message : 'Failed to stream message'
      toast.error(msg)
      set((s) => ({
        messages: s.messages.filter((m) => m.id !== optimistic.id),
        lastFailedMessage: optimistic.content,
      }))
      cancelStream()
    }
  },

  retryLastMessage: async () => {
    const { lastFailedMessage, sendMessageStream } = get()
    if (!lastFailedMessage) return
    set({ lastFailedMessage: null })
    await sendMessageStream(lastFailedMessage)
  },

  clearError: () => set({ error: null }),

  // ── Streaming controls (driven by WebSocket or SSE events) ──
  startStream: () =>
    set({
      stream: { isStreaming: true, thinkingContent: '', streamedContent: '', modelUsed: null, daenabotActivity: null, runtimeActivity: null, runtimeOutput: '', pipelineStages: [] },
    }),

  appendThinking: (chunk) =>
    set((s) => ({
      stream: { ...s.stream, thinkingContent: s.stream.thinkingContent + chunk },
    })),

  appendContent: (chunk) =>
    set((s) => ({
      stream: { ...s.stream, streamedContent: s.stream.streamedContent + chunk },
    })),

  finalizeStream: (msg) =>
    set((s) => ({
      messages: [...s.messages, msg],
      stream: { isStreaming: false, thinkingContent: '', streamedContent: '', modelUsed: msg.model_used, daenabotActivity: null, runtimeActivity: null, runtimeOutput: '', pipelineStages: [] },
    })),

  cancelStream: () =>
    set({
      stream: { isStreaming: false, thinkingContent: '', streamedContent: '', modelUsed: null, daenabotActivity: null, runtimeActivity: null, runtimeOutput: '', pipelineStages: [] },
    }),
}))

export default useChatStore
