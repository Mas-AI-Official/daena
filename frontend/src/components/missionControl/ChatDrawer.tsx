import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Plus, MessageSquare } from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useUiStore } from '@/stores/uiStore'
import { useModelRegistryStore } from '@/stores/modelRegistryStore'
import { useGraphStore } from '@/stores/graphStore'
import { MessageList } from '@/components/chat/MessageList'
import { ChatInput } from '@/components/chat/ChatInput'
import type { GraphNode } from '@/lib/graphApi'

// Slide-over sits beside the NodeDetailPanel (which is right-0, w-[360px]) when a
// node is selected, so it offsets left by exactly that width.
const DETAIL_PANEL_WIDTH = 360

/**
 * Derive the department UUID a chat should be scoped to from the selected graph
 * node. Department nodes carry the id directly; other kinds (agent, project,
 * workstream, ...) carry department_id. Returns undefined for org-wide scope.
 */
function deriveDepartmentId(node: GraphNode | null): string | undefined {
  if (!node) return undefined
  if (node.kind === 'department') return node.id.split(':')[1]
  if (node.department_id) return node.department_id
  return undefined
}

interface ChatDrawerProps {
  open: boolean
  onClose: () => void
}

/**
 * Mission Control chat drawer. Reuses the canonical streaming chat surface
 * (MessageList + ChatInput) bound to chatStore/uiStore, so CMD/EXE mode,
 * routing, model selection, and thinking visibility behave exactly as in the
 * main chat. The selected graph node's department pre-scopes the next session
 * (PR-2 ragx routing keys off the same department_id).
 *
 * Lazy-create gate (chatStore): a dept-scoped session is created only when no
 * session is active. So the drawer clears the session on open and on "New", and
 * the header states honestly (Rule 17) that a live conversation ignores a new
 * scope until you start a new chat.
 */
export default function ChatDrawer({ open, onClose }: ChatDrawerProps) {
  const messages = useChatStore((s) => s.messages)
  const messagesLoading = useChatStore((s) => s.messagesLoading)
  const stream = useChatStore((s) => s.stream)
  const editAndRegenerate = useChatStore((s) => s.editAndRegenerate)
  const cancelStream = useChatStore((s) => s.cancelStream)
  const activeSessionId = useChatStore((s) => s.activeSessionId)

  const selectedModel = useUiStore((s) => s.selectedModel)
  const chatMode = useUiStore((s) => s.chatMode)
  const setChatMode = useUiStore((s) => s.setChatMode)
  const registry = useModelRegistryStore((s) => s.registry)
  const fetchRegistry = useModelRegistryStore((s) => s.fetchRegistry)

  const data = useGraphStore((s) => s.data)
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId)

  const selectedNode = data?.nodes.find((n) => n.id === selectedNodeId) ?? null
  const departmentId = deriveDepartmentId(selectedNode)
  const scopeDeptNode = departmentId
    ? data?.nodes.find((n) => n.id === `department:${departmentId}`) ?? null
    : null
  const scopeLabel =
    scopeDeptNode?.label ?? (departmentId ? 'Department' : 'Daena (all departments)')

  // Only honor a selected model the live registry still marks selectable;
  // otherwise let the backend pick (mirrors DepartmentChatPage).
  const selectedModelAvailable = selectedModel
    ? (registry?.models ?? []).some((m) => m.model_id === selectedModel && m.selectable)
    : false
  const effectiveModel = selectedModelAvailable ? selectedModel : null

  useEffect(() => {
    void fetchRegistry(true)
  }, [fetchRegistry])

  // Respect the lazy-create gate: a fresh drawer session starts with no active
  // session so the first message is created scoped to the selected department.
  // Without this, a stale session carried over from the main chat would swallow
  // the message and silently ignore departmentId.
  useEffect(() => {
    if (open) {
      useChatStore.setState({ activeSessionId: null, activeSession: null, messages: [] })
    }
  }, [open])

  const handleNewChat = () => {
    useChatStore.setState({ activeSessionId: null, activeSession: null, messages: [] })
  }

  const handleSend = (content: string) => {
    const store = useChatStore.getState()
    const ui = useUiStore.getState()
    if (!store.activeSessionId) {
      void store.sendMessageStream(content, effectiveModel, {
        createSession: {
          mode: ui.chatMode,
          routingMode: ui.routingMode,
          departmentId,
          autopilot: ui.autopilotActive,
          thinkMode: ui.thinkingVisible,
        },
      })
      return
    }
    void store.sendMessageStream(content, effectiveModel)
  }

  return (
    <div
      className="absolute top-0 h-full"
      style={{
        right: selectedNodeId ? DETAIL_PANEL_WIDTH : 0,
        transition: 'right 200ms ease',
        zIndex: 30,
        pointerEvents: open ? 'auto' : 'none',
      }}
    >
      <AnimatePresence>
        {open ? (
          <motion.aside
            key="chat-drawer"
            initial={{ x: 440, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 440, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            className="flex h-full w-[440px] flex-col border-l border-white/10 bg-black/80 backdrop-blur"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
              <div className="flex min-w-0 items-center gap-2">
                <MessageSquare size={16} className="shrink-0 text-white/50" />
                <div className="min-w-0">
                  <div className="text-sm font-medium text-white">Mission Control Chat</div>
                  <div className="truncate text-xs text-white/40">
                    {activeSessionId
                      ? 'Conversation active - New chat to switch scope'
                      : `Scope: ${scopeLabel}`}
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  onClick={handleNewChat}
                  className="flex items-center gap-1 rounded px-2 py-1 text-xs text-white/60 hover:bg-white/10 hover:text-white"
                  title="Start a new chat scoped to the selected node"
                >
                  <Plus size={14} /> New
                </button>
                <button
                  onClick={onClose}
                  className="rounded p-1 text-white/50 hover:bg-white/10 hover:text-white"
                  aria-label="Close chat drawer"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* CMD/EXE mode toggle - preserves the per-message mode contract */}
            <div className="flex items-center gap-1 border-b border-white/10 px-4 py-2">
              {(['CMD', 'EXE'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setChatMode(m)}
                  className={
                    chatMode === m
                      ? 'rounded bg-white/10 px-2 py-1 text-xs font-medium text-white'
                      : 'rounded px-2 py-1 text-xs text-white/40 hover:text-white'
                  }
                >
                  {m}
                </button>
              ))}
              <span className="ml-2 text-[10px] text-white/30">
                {chatMode === 'CMD' ? 'Plan / converse' : 'Execute work'}
              </span>
            </div>

            {/* Messages - MessageList owns its own empty / loading / streaming states */}
            <MessageList
              messages={messages}
              isStreaming={stream.isStreaming}
              thinkingContent={stream.thinkingContent}
              streamedContent={stream.streamedContent}
              isLoading={messagesLoading}
              modelUsed={stream.modelUsed}
              daenabotActivity={stream.daenabotActivity}
              onEditMessage={editAndRegenerate}
              onQuickAction={handleSend}
            />

            {/* Composer */}
            <ChatInput
              onSend={handleSend}
              onCancel={cancelStream}
              isStreaming={stream.isStreaming}
              placeholder={`Message ${scopeLabel}...`}
            />
          </motion.aside>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
