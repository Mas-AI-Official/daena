/**
 * DepartmentChatPage — chat interface scoped to a specific department.
 * Reuses ChatPage layout with department-branded header.
 * Messages are sent through the same streaming pipeline but the session
 * carries a department_id, biasing Daena's orchestrator toward that department.
 */
import { lazy, Suspense, useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  ArrowLeft,
  Wrench,
  Layers,
  Megaphone,
  TrendingUp,
  Calculator,
  Settings,
  Microscope,
  Scale,
  GraduationCap,
  ShieldCheck,
  Bot,
} from 'lucide-react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useChatStore } from '@/stores/chatStore'
import { useModelRegistryStore } from '@/stores/modelRegistryStore'
import { useUiStore } from '@/stores/uiStore'
import { MessageList } from '@/components/chat/MessageList'
import { ChatInput } from '@/components/chat/ChatInput'
import { GovernanceEventStrip } from '@/components/chat/GovernanceEventStrip'
import { PeerSignalsPane } from '@/components/chat/PeerSignalsPane'
import { api } from '@/lib/api'
import type { DepartmentResponse, ApiResponse } from '@/types/api'

const SessionList = lazy(() => import('@/components/chat/SessionList'))

// Department icon mapping (mirrors DepartmentsPage)
const DEPT_ICONS: Record<string, React.ReactNode> = {
  Engineering: <Wrench size={18} />,
  Product: <Layers size={18} />,
  Marketing: <Megaphone size={18} />,
  Sales: <TrendingUp size={18} />,
  Finance: <Calculator size={18} />,
  Operations: <Settings size={18} />,
  Research: <Microscope size={18} />,
  'Legal & Compliance': <Scale size={18} />,
  'Skill Governance': <GraduationCap size={18} />,
  'Security Operations': <ShieldCheck size={18} />,
}

const DEPT_COLORS: Record<string, string> = {
  Engineering: 'text-primary-400',
  Product: 'text-accent-purple',
  Marketing: 'text-status-success',
  Sales: 'text-accent-cyan',
  Finance: 'text-status-warning',
  Operations: 'text-accent-amber',
  Research: 'text-blue-400',
  'Legal & Compliance': 'text-status-error',
  'Skill Governance': 'text-fuchsia-400',
  'Security Operations': 'text-pink-400',
}

export function DepartmentChatPage() {
  usePageTitle('Department Chat')
  const { departmentId, sessionId } = useParams()
  const navigate = useNavigate()
  const {
    messages,
    messagesLoading,
    stream,
    sendMessageStream,
    editAndRegenerate,
    cancelStream,
    setActiveSession,
  } = useChatStore()

  const historySidebarOpen = useUiStore((s) => s.historySidebarOpen)
  const toggleHistorySidebar = useUiStore((s) => s.toggleHistorySidebar)
  const peerSignalsPaneOpen = useUiStore((s) => s.peerSignalsPaneOpen)
  const togglePeerSignalsPane = useUiStore((s) => s.togglePeerSignalsPane)
  const selectedModel = useUiStore((s) => s.selectedModel)
  const thinkingVisible = useUiStore((s) => s.thinkingVisible)
  const registry = useModelRegistryStore((s) => s.registry)
  const fetchRegistry = useModelRegistryStore((s) => s.fetchRegistry)
  const selectedModelAvailable = selectedModel
    ? (registry?.models ?? []).some(
        (model) => model.model_id === selectedModel && model.selectable,
      )
    : false
  const effectiveModel = selectedModelAvailable ? selectedModel : null

  const [department, setDepartment] = useState<DepartmentResponse | null>(null)

  useEffect(() => {
    void fetchRegistry(true)
  }, [fetchRegistry])

  // Fetch department info
  useEffect(() => {
    if (!departmentId) return
    api
      .get<ApiResponse<DepartmentResponse[]>>('/agents/departments')
      .then(({ data }) => {
        const dept = data.data.find((d) => d.id === departmentId)
        if (dept) setDepartment(dept)
      })
      .catch(() => {})
  }, [departmentId])

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

  const deptName = department?.name || 'Department'
  const deptIcon = DEPT_ICONS[deptName] || <Bot size={18} />
  const deptColor = DEPT_COLORS[deptName] || 'text-primary-400'

  const handleSend = async (content: string) => {
    if (!sessionId) {
      const store = useChatStore.getState()
      const ui = useUiStore.getState()
      void store.sendMessageStream(content, effectiveModel, {
        createSession: {
          mode: ui.chatMode,
          routingMode: ui.routingMode,
          departmentId,
          autopilot: ui.autopilotActive,
          thinkMode: ui.thinkingVisible,
        },
        onSessionResolved: (session) => {
          navigate(`/departments/${departmentId}/chat/${session.id}`, { replace: true })
        },
      })
      return
    }
    void sendMessageStream(content, effectiveModel)
  }

  return (
    <div className="h-full flex relative">
      {/* Session sidebar — filtered to this department */}
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
            <SessionList departmentId={departmentId} />
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
        {/* Department header bar */}
        <div className="shrink-0 flex items-center gap-3 px-4 py-2.5 border-b border-white/5 bg-midnight-300/20">
          <Link
            to="/departments"
            className="p-1 rounded-md text-starlight-500 hover:text-starlight-200 hover:bg-white/5 transition-colors"
          >
            <ArrowLeft size={16} />
          </Link>
          <span className={`${deptColor}`}>{deptIcon}</span>
          <div>
            <h2 className="text-sm font-display font-semibold text-starlight-100">
              {deptName}
            </h2>
            <p className="text-[10px] text-starlight-500">
              {department?.description || 'Department chat — Daena orchestrates across all departments'}
            </p>
          </div>
        </div>

        {/* Live governance-event strip (SSE-driven). Mirrors the
            top-chat pattern so department chats also surface
            approvals, blocks, and VP routing events instantly. */}
        <div className="px-3 pt-2">
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
          onEditMessage={editAndRegenerate}
        />

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          onCancel={cancelStream}
          isStreaming={stream.isStreaming}
          placeholder={`Message ${deptName} department...`}
        />
      </div>

      {/* Right-side toggle for the peer-signals pane. Matches the
          history-sidebar collapse pattern so the chat column can
          reclaim the width when the user isn't tracking peers. */}
      <button
        onClick={togglePeerSignalsPane}
        className="absolute top-3 z-20 p-1 rounded-md text-starlight-500
                   hover:text-starlight-200 hover:bg-white/5
                   transition-all cursor-pointer"
        style={{
          right: peerSignalsPaneOpen ? 328 : 8,
          transition: 'right 200ms ease',
        }}
        title={peerSignalsPaneOpen ? 'Collapse peer signals' : 'Show peer signals'}
      >
        {peerSignalsPaneOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
      </button>

      {/* Peer Signals pane -- shows relevance-filtered events from other
          departments via this department's BorderAgent. Replaces the
          deleted DepartmentInbox page with a room-native feed. */}
      <div
        className="shrink-0 overflow-hidden"
        style={{
          width: peerSignalsPaneOpen ? 320 : 0,
          transition: 'width 200ms ease',
        }}
      >
        {peerSignalsPaneOpen && <PeerSignalsPane departmentName={deptName} />}
      </div>
    </div>
  )
}

export default DepartmentChatPage
