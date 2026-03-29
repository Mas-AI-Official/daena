/**
 * ChatPage — main chat experience with session sidebar,
 * message list, thinking display, and input composer.
 * Sidebar is collapsible via toggle button.
 */
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useChatStore } from '@/stores/chatStore'
import { useModelRegistryStore } from '@/stores/modelRegistryStore'
import { useUiStore } from '@/stores/uiStore'
import { MessageList } from '@/components/chat/MessageList'
import { ChatInput } from '@/components/chat/ChatInput'
import { ExecutionPanel } from '@/components/execution/ExecutionPanel'
import { InteractivePromptDisplay } from '@/components/chat/InteractivePrompt'
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
  const selectedModel = useUiStore((s) => s.selectedModel)
  const thinkingVisible = useUiStore((s) => s.thinkingVisible)
  const governanceSlider = useUiStore((s) => s.governanceSlider)
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
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchActiveTasks = useCallback(async () => {
    try {
      const res = await api.get('/execution/tasks', { params: { status: 'running', page_size: 20 } })
      const tasks = res.data?.data ?? []
      // Map backend task objects to SubTaskResponse shape
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
    } catch {
      // Graceful -- don't spam errors when backend is unreachable
    }
  }, [])

  useEffect(() => {
    if (chatMode === 'EXE') {
      // Immediate fetch + poll every 5s
      void fetchActiveTasks()
      pollRef.current = setInterval(() => void fetchActiveTasks(), 5000)
    } else {
      setSubtasks([])
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [chatMode, fetchActiveTasks])

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
    useChatStore.setState({
      activeSessionId: null,
      activeSession: null,
      messages: [],
    })
  }, [sessionId, setActiveSession])

  const handleSend = async (content: string) => {
    if (!sessionId) {
      const store = useChatStore.getState()
      const ui = useUiStore.getState()
      // Explicit: general chat creates sessions with NO department
      void store.sendMessageStream(content, effectiveModel, governanceSlider, {
        createSession: {
          mode: ui.chatMode,
          routingMode: ui.routingMode,
          governanceSlider: ui.governanceSlider,
          autopilot: ui.autopilotActive,
          thinkMode: ui.thinkingVisible,
          departmentId: undefined, // force null — prevent department context leak
        },
        onSessionResolved: (session) => {
          navigate(`/chat/${session.id}`, { replace: true })
        },
      })
      return
    }
    void sendMessageStream(content, effectiveModel, governanceSlider)
  }

  return (
    <div className="h-full flex relative">
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

      {/* Toggle button */}
      <button
        onClick={toggleHistorySidebar}
        className="absolute top-2 z-20 p-1.5 rounded-md border border-white/10
                   bg-midnight-400/80 backdrop-blur-sm text-starlight-400
                   hover:text-starlight-100 hover:border-white/20
                   transition-all cursor-pointer"
        style={{ left: historySidebarOpen ? 248 : 8, transition: 'left 200ms ease' }}
        title={historySidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
      >
        {historySidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
      </button>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Autopilot banner */}
        {autopilotActive && !autopilotBannerDismissed && (
          <div className="shrink-0 pl-14 pr-6 py-2.5 bg-status-success/5 border-b border-status-success/10 flex items-center justify-between gap-4">
            <p className="text-[11px] text-status-success/80 leading-relaxed">
              Autopilot active. Non-critical actions auto-approved by internal governance. Critical actions will ask for your approval.
            </p>
            <button
              onClick={() => setAutopilotBannerDismissed(true)}
              className="text-[10px] text-starlight-500 hover:text-starlight-300 shrink-0 cursor-pointer px-2 py-1 rounded hover:bg-white/5"
            >
              Dismiss
            </button>
          </div>
        )}

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
          onEditMessage={editAndRegenerate}
          onRegenerateMessage={regenerateLastResponse}
          onQuickAction={handleSend}
        />

        {/* Execution Panel (visible in EXE mode or when subtasks exist) */}
        {(chatMode === 'EXE' || subtasks.length > 0) && (
          <div className="shrink-0 border-t border-white/5 px-4 py-2">
            <ExecutionPanel
              subtasks={subtasks}
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
    </div>
  )
}

export default ChatPage
