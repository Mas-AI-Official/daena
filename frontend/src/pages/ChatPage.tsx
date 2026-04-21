/**
 * ChatPage — main chat experience with session sidebar,
 * message list, thinking display, and input composer.
 * Sidebar is collapsible via toggle button.
 */
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Keyboard, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { usePageTitle } from '@/hooks/usePageTitle'
import { FounderModeBanner } from '@/components/chat/FounderModeBanner'
import { useChatStore } from '@/stores/chatStore'
import { useModelRegistryStore } from '@/stores/modelRegistryStore'
import { useUiStore } from '@/stores/uiStore'
import { MessageList } from '@/components/chat/MessageList'
import { ChatInput } from '@/components/chat/ChatInput'
import { InlineApprovalBanner } from '@/components/chat/InlineApprovalBanner'
import { GovernanceEventStrip } from '@/components/chat/GovernanceEventStrip'
import { ExecutionPanel } from '@/components/execution/ExecutionPanel'
import { InteractivePromptDisplay } from '@/components/chat/InteractivePrompt'
// Daena's wildcard BorderAgent inbox surfaces here as the VP / company-
// wide activity feed. Matches what Stage 6.4 injects into the prompt
// context, giving the founder both visual + prompt-level awareness.
import { PeerSignalsPane } from '@/components/chat/PeerSignalsPane'
import { api } from '@/lib/api'
import type { SubTaskResponse } from '@/types/api'

const SessionList = lazy(() => import('@/components/chat/SessionList'))

export function ChatPage() {
  usePageTitle('Chat')
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const {
    messages,
    messagesLoading,
    stream,
    sendMessageStream,
    editAndRegenerate,
    regenerateLastResponse,
    cancelStream,
    setActiveSession,
  } = useChatStore()

  const historySidebarOpen = useUiStore((s) => s.historySidebarOpen)
  const toggleHistorySidebar = useUiStore((s) => s.toggleHistorySidebar)
  const peerSignalsPaneOpen = useUiStore((s) => s.peerSignalsPaneOpen)
  const togglePeerSignalsPane = useUiStore((s) => s.togglePeerSignalsPane)
  const selectedModel = useUiStore((s) => s.selectedModel)
  const thinkingVisible = useUiStore((s) => s.thinkingVisible)
  const chatMode = useUiStore((s) => s.chatMode)
  const executionViewVisible = useUiStore((s) => s.executionViewVisible)
  const toggleExecutionView = useUiStore((s) => s.toggleExecutionView)
  const autopilotActive = useUiStore((s) => s.autopilotActive)
  const activePrompt = useUiStore((s) => s.activePrompt)
  const dismissPrompt = useUiStore((s) => s.dismissPrompt)
  const [autopilotBannerDismissed, setAutopilotBannerDismissed] = useState(false)
  const registry = useModelRegistryStore((s) => s.registry)
  const fetchRegistry = useModelRegistryStore((s) => s.fetchRegistry)

  // Execution panel subtasks -- poll /execution/tasks?status=running in EXE mode
  const [subtasks, setSubtasks] = useState<SubTaskResponse[]>([])
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollDelayRef = useRef(5000)

  const fetchActiveTasks = useCallback(async () => {
    try {
      const res = await api.get('/execution/tasks', { params: { status: 'running', page_size: 20 } })
      const tasks = res.data?.data ?? []
      const mapped: SubTaskResponse[] = tasks.map((t: Record<string, unknown>) => ({
        id: String(t.id ?? ''),
        description: String(t.description ?? t.name ?? 'Task'),
        assigned_runtime: String(t.runtime_id ?? 'auto'),
        status: String(t.status ?? 'pending') as SubTaskResponse['status'],
        estimated_cost_usd: Number(t.estimated_cost_usd ?? 0),
        actual_cost_usd: t.actual_cost_usd != null ? Number(t.actual_cost_usd) : undefined,
        duration_ms: t.duration_ms != null ? Number(t.duration_ms) : undefined,
        result_data: t.result_data ?? null,
      }))
      setSubtasks(mapped)
      pollDelayRef.current = 5000 // Reset to normal on success
    } catch {
      pollDelayRef.current = Math.min(pollDelayRef.current * 2, 60000) // Backoff to 60s max
    }
  }, [])

  useEffect(() => {
    if (chatMode !== 'EXE') { setSubtasks([]); return }
    let cancelled = false
    const poll = async () => {
      await fetchActiveTasks()
      if (!cancelled) pollRef.current = setTimeout(poll, pollDelayRef.current)
    }
    void poll()
    return () => { cancelled = true; if (pollRef.current) clearTimeout(pollRef.current) }
  }, [chatMode, fetchActiveTasks])

  // Merge SSE tool_call events (real-time) with polled subtasks (background)
  // SSE events appear instantly during streaming; polling catches background tasks
  const mergedSubtasks = useMemo<SubTaskResponse[]>(() => {
    const sseEntries: SubTaskResponse[] = stream.toolCalls.map((tc, i) => ({
      id: `sse-${tc.tool}-${tc.iteration}-${i}`,
      description: tc.tool.replace(/_/g, ' '),
      task_type: 'tool_call',
      assigned_runtime: 'daenabot',
      fallback_runtime: null,
      depends_on: [],
      estimated_tokens: 0,
      estimated_cost_usd: 0,
      status: tc.status === 'calling' ? 'running' as const
        : tc.status === 'done' ? 'complete' as const
        : 'failed' as const,
      result_data: tc.result ?? null,
      duration_ms: null,
      actual_cost_usd: null,
    }))
    // SSE events first (most recent activity), then polled tasks
    // Deduplicate: if a polled task has same tool name as SSE, keep SSE version
    const sseToolNames = new Set(sseEntries.map((e) => e.description))
    const polledOnly = subtasks.filter((s) => !sseToolNames.has(s.description))
    return [...sseEntries, ...polledOnly]
  }, [stream.toolCalls, subtasks])

  useEffect(() => {
    void fetchRegistry(true)
  }, [fetchRegistry])

  const selectedModelAvailable = selectedModel
    ? (registry?.models ?? []).some(
        (model) => model.model_id === selectedModel && model.selectable,
      )
    : false

  // Think mode is resolved on the backend against the live registry.
  const effectiveModel = selectedModelAvailable ? selectedModel : null

  // Load session on mount / URL change
  useEffect(() => {
    if (sessionId) {
      void setActiveSession(sessionId)
      return
    }
    // ChatGPT-style: auto-load most recent session instead of blank page.
    // Only create a new session on explicit "New Chat" click.
    const tryLoadRecent = () => {
      const { sessions } = useChatStore.getState()
      const recentGeneral = sessions.find((s) => !s.department_id && !s.is_archived)
      if (recentGeneral) {
        navigate(`/chat/${recentGeneral.id}`, { replace: true })
        return true
      }
      return false
    }
    // Sessions may not be loaded yet — try now, retry once after 500ms
    if (!tryLoadRecent()) {
      const timer = setTimeout(() => tryLoadRecent(), 500)
      return () => clearTimeout(timer)
    }
  }, [sessionId, setActiveSession, navigate])

  /** Auto-name a session from the first message content */
  const autoNameSession = useCallback(async (sessionIdToName: string, firstMessage: string) => {
    // Generate a short title: first 50 chars, trim to last word boundary
    const raw = firstMessage.replace(/\n/g, ' ').trim()
    let title = raw.slice(0, 50)
    if (raw.length > 50) {
      const lastSpace = title.lastIndexOf(' ')
      if (lastSpace > 20) title = title.slice(0, lastSpace)
      title += '...'
    }
    if (!title) return
    try {
      const token = localStorage.getItem('daena_token')
      await fetch(`/api/v1/chat/sessions/${sessionIdToName}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ title }),
      })
      // Update in store
      useChatStore.getState().updateSession(sessionIdToName, { title })
    } catch {
      // Non-critical — session works fine without a title
    }
  }, [])

  const handleSend = async (content: string) => {
    if (!sessionId) {
      const store = useChatStore.getState()
      const ui = useUiStore.getState()
      // Explicit: general chat creates sessions with NO department
      void store.sendMessageStream(content, effectiveModel, {
        createSession: {
          mode: ui.chatMode,
          routingMode: ui.routingMode,
          autopilot: ui.autopilotActive,
          thinkMode: ui.thinkingVisible,
          departmentId: undefined, // force null — prevent department context leak
        },
        onSessionResolved: (session) => {
          navigate(`/chat/${session.id}`, { replace: true })
          // Auto-name the new session from the first message
          void autoNameSession(session.id, content)
        },
      })
      return
    }
    void sendMessageStream(content, effectiveModel)
  }

  // Keyboard shortcuts overlay
  const [showShortcuts, setShowShortcuts] = useState(false)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // ? key (without modifier) when not focused on input
      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        const tag = (e.target as HTMLElement)?.tagName
        if (tag === 'TEXTAREA' || tag === 'INPUT') return
        e.preventDefault()
        setShowShortcuts((prev) => !prev)
      }
      if (e.key === 'Escape' && showShortcuts) {
        setShowShortcuts(false)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [showShortcuts])

  return (
    <div className="h-full flex relative">
      {/* Keyboard shortcuts overlay */}
      <AnimatePresence>
        {showShortcuts && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowShortcuts(false)}
          >
            <motion.div
              className="bg-midnight-300 border border-white/10 rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Keyboard size={18} className="text-primary-400" />
                  <h3 className="text-sm font-semibold text-starlight-100">Keyboard Shortcuts</h3>
                </div>
                <button onClick={() => setShowShortcuts(false)} className="p-1 rounded hover:bg-white/10 text-starlight-400 cursor-pointer">
                  <X size={16} />
                </button>
              </div>
              <div className="space-y-2">
                {[
                  ['Enter', 'Send message'],
                  ['Shift + Enter', 'New line'],
                  ['Esc', 'Cancel edit / Close'],
                  ['/', 'Slash commands'],
                  ['?', 'Toggle this overlay'],
                  ['Ctrl + Shift + S', 'Toggle sidebar'],
                  ['Ctrl + Shift + E', 'Toggle execution view'],
                  ['Ctrl + Shift + N', 'New session'],
                ].map(([key, desc]) => (
                  <div key={key} className="flex items-center justify-between py-1">
                    <span className="text-xs text-starlight-300">{desc}</span>
                    <kbd className="px-2 py-0.5 rounded bg-midnight-500 border border-white/10 text-[10px] font-mono text-starlight-400">{key}</kbd>
                  </div>
                ))}
              </div>
              <p className="text-[10px] text-starlight-600 mt-4 text-center">Press ? anywhere to toggle</p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Session sidebar — collapsible via inline width for reliable CSS transition */}
      <div
        className="shrink-0 bg-midnight-300/30 overflow-hidden"
        style={{
          width: historySidebarOpen ? 256 : 0,
          borderRight: historySidebarOpen ? '1px solid rgba(255,255,255,0.05)' : 'none',
          transition: 'width 200ms ease, border-right 200ms ease',
        }}
      >
        {historySidebarOpen && (
          <Suspense fallback={<div className="h-full animate-pulse bg-white/[0.03]" />}>
            <SessionList />
          </Suspense>
        )}
      </div>

      {/* Toggle button -- minimal sidebar toggle */}
      <button
        onClick={toggleHistorySidebar}
        className="absolute top-3 z-20 p-1 rounded-md text-starlight-500
                   hover:text-starlight-200 hover:bg-white/5
                   transition-all cursor-pointer"
        style={{ left: historySidebarOpen ? 248 : 8, transition: 'left 200ms ease' }}
        title={historySidebarOpen ? 'Collapse history' : 'Show history'}
      >
        {historySidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
      </button>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Founder elevated-mode banner (only renders for FOUNDER
            with active elevated mode; dismissible; auto-resurfaces
            on the next activation). */}
        <FounderModeBanner />
        {/* Autopilot banner -- minimal */}
        {autopilotActive && !autopilotBannerDismissed && (
          <div className="shrink-0 pl-14 pr-6 py-1.5 bg-status-success/[0.03] flex items-center justify-between gap-4">
            <p className="text-[10px] text-status-success/60 leading-relaxed">
              Autopilot active -- non-critical actions auto-approved, critical actions require approval
            </p>
            <button
              onClick={() => setAutopilotBannerDismissed(true)}
              className="text-[10px] text-starlight-600 hover:text-starlight-300 shrink-0 cursor-pointer px-1.5 py-0.5 rounded hover:bg-white/5"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Inline approval banner -- surfaces any pending approvals in chat
            so Masoud doesn't have to navigate to /governance/approvals */}
        <InlineApprovalBanner />

        {/* Live governance-event strip -- responds to SSE events during
            the stream (governance_approval_pending, tool_blocked,
            daena_vp_plan, vp_subtasks_created). Complements the poll-
            based InlineApprovalBanner above: banner is eventually
            consistent (5s poll), strip is instant. Both mounted so an
            approval surfaced mid-stream is visible without waiting. */}
        <div className="px-3">
          <GovernanceEventStrip />
        </div>

        {/* Messages */}
        <MessageList
          messages={messages}
          isStreaming={stream.isStreaming}
          thinkingContent={stream.thinkingContent}
          streamedContent={stream.streamedContent}
          isLoading={messagesLoading}
          modelUsed={stream.modelUsed}
          daenabotActivity={stream.daenabotActivity}
          pipelineStages={stream.pipelineStages}
          toolCalls={stream.toolCalls}
          onEditMessage={editAndRegenerate}
          onRegenerateMessage={regenerateLastResponse}
          onQuickAction={handleSend}
        />

        {/* Execution Panel (visible in EXE mode or when subtasks exist) */}
        {(chatMode === 'EXE' || mergedSubtasks.length > 0) && (
          <div className="shrink-0 px-4 py-2">
            <ExecutionPanel
              subtasks={mergedSubtasks}
              visible={executionViewVisible}
              onToggle={toggleExecutionView}
            />
          </div>
        )}

        {/* Interactive prompt (agent asking user) */}
        <InteractivePromptDisplay
          prompt={activePrompt}
          onDismiss={dismissPrompt}
        />

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          onCancel={cancelStream}
          isStreaming={stream.isStreaming}
        />
      </div>

      {/* Right-side toggle -- mirrors the history sidebar's pattern.
          Collapsed by default so the chat column stays wide; one click
          exposes Daena's company-wide feed without leaving the page. */}
      <button
        onClick={togglePeerSignalsPane}
        className="absolute top-3 z-20 p-1 rounded-md text-starlight-500
                   hover:text-starlight-200 hover:bg-white/5
                   transition-all cursor-pointer"
        style={{
          right: peerSignalsPaneOpen ? 328 : 8,
          transition: 'right 200ms ease',
        }}
        title={peerSignalsPaneOpen ? 'Collapse company-wide activity' : 'Show company-wide activity'}
      >
        {peerSignalsPaneOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
      </button>

      {/* VP lens: Daena's wildcard inbox. Shows the same signals that
          Stage 6.4 will inject into the prompt, but visible at a
          glance without needing to send a message. Animated collapse
          matches the left history sidebar so the chat canvas can
          expand to fill the window. */}
      <div
        className="shrink-0 overflow-hidden"
        style={{
          width: peerSignalsPaneOpen ? 320 : 0,
          transition: 'width 200ms ease',
        }}
      >
        {peerSignalsPaneOpen && (
          <PeerSignalsPane departmentName="Daena" title="Company-wide" />
        )}
      </div>
    </div>
  )
}

export default ChatPage
