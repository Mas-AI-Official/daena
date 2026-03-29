/**
 * MessageList — scrollable container for chat messages.
 * Auto-scrolls to bottom on new messages. Shows empty state.
 */
import React, { memo, useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowDown, RotateCcw } from 'lucide-react'
import { MessageBubble } from './MessageBubble'
import { ThinkingProcess } from './ThinkingProcess'
import { DaenaAvatar } from './DaenaAvatar'
import { useUiStore } from '@/stores/uiStore'
import { useChatStore } from '@/stores/chatStore'
import { speakText } from './VoiceControls'
import type { MessageResponse } from '@/types/api'

interface DaenaBotActivity {
  agent: string
  operation: string
  status: 'executing' | 'completed' | 'failed'
  description: string
}

interface MessageListProps {
  messages: MessageResponse[]
  isStreaming: boolean
  thinkingContent: string
  streamedContent: string
  isLoading: boolean
  /** Model that's currently handling the request */
  modelUsed?: string | null
  /** DaenaBot agent activity during streaming */
  daenabotActivity?: DaenaBotActivity | null
  /** Pipeline stages for ThinkingProcess display */
  pipelineStages?: { label: string; detail?: string; status: 'done' | 'active' | 'pending' }[]
  /** Called when user edits a message — triggers truncate + regenerate */
  onEditMessage?: (messageId: string, newContent: string) => void
  /** Called when user clicks Regenerate on the last assistant message */
  onRegenerateMessage?: (messageId: string) => void
  /** Called when user clicks a quick-action suggestion on the empty state */
  onQuickAction?: (text: string) => void
}

export const MessageList = memo(function MessageList({
  messages,
  isStreaming,
  thinkingContent,
  streamedContent,
  isLoading,
  modelUsed,
  daenabotActivity,
  pipelineStages,
  onEditMessage,
  onRegenerateMessage,
  onQuickAction,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const userScrolledUp = useRef(false)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const chatMode = useUiStore((s) => s.chatMode)
  const routingMode = useUiStore((s) => s.routingMode)
  const thinkingVisible = useUiStore((s) => s.thinkingVisible)
  const persistThinking = useUiStore((s) => s.persistThinking)
  const autoReadResponses = useUiStore((s) => s.autoReadResponses)
  const lastFailedMessage = useChatStore((s) => s.lastFailedMessage)
  const retryLastMessage = useChatStore((s) => s.retryLastMessage)

  // Show thinking panel only when Think toggle is ON or routing is Council/Quintessence
  const showThinking = thinkingVisible || routingMode === 'COUNCIL' || routingMode === 'QUINTESSENCE'

  // Cache thinking state so it persists after streaming completes
  const [completedThinking, setCompletedThinking] = useState<{
    content: string
    stages?: typeof pipelineStages
    model?: string | null
  } | null>(null)
  const thinkingCacheRef = useRef<typeof completedThinking>(null)
  const wasStreamingRef = useRef(false)

  useEffect(() => {
    if (isStreaming) {
      // New stream starting: clear old completed state
      if (!wasStreamingRef.current) {
        setCompletedThinking(null)
      }
      wasStreamingRef.current = true
      // Cache current thinking content during streaming
      if (thinkingContent || pipelineStages?.length) {
        thinkingCacheRef.current = {
          content: thinkingContent,
          stages: pipelineStages,
          model: modelUsed,
        }
      }
    } else if (wasStreamingRef.current) {
      // Streaming just ended: persist cached thinking.
      // Mark any stages still 'active' as 'done' since the stream completed.
      wasStreamingRef.current = false
      if (thinkingCacheRef.current) {
        const finalStages = thinkingCacheRef.current.stages?.map(s =>
          s.status === 'active' ? { ...s, status: 'done' as const } : s,
        )
        setCompletedThinking({
          ...thinkingCacheRef.current,
          stages: finalStages,
        })
        thinkingCacheRef.current = null
      }

      // Auto-read: speak the last assistant message aloud when streaming completes
      if (autoReadResponses && messages.length > 0) {
        const lastMsg = messages[messages.length - 1]
        if (lastMsg.role === 'ASSISTANT' && lastMsg.content) {
          // Strip markdown formatting for cleaner speech
          const plainText = lastMsg.content
            .replace(/```[\s\S]*?```/g, ' code block ')
            .replace(/[*_~`#]/g, '')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            .trim()
          if (plainText.length > 0 && plainText.length < 5000) {
            speakText(plainText)
          }
        }
      }
    }
  }, [isStreaming, thinkingContent, pipelineStages, modelUsed])

  // Track whether user has scrolled away from bottom.
  // Lower thresholds during streaming so the button appears quickly.
  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    userScrolledUp.current = distFromBottom > 80
    setShowScrollButton(distFromBottom > 100)
  }, [])

  const scrollToBottom = useCallback(() => {
    userScrolledUp.current = false
    setShowScrollButton(false)
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // Auto-scroll only when user is near bottom (or on new message from user)
  useEffect(() => {
    if (!userScrolledUp.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages.length, streamedContent, thinkingContent])

  // Always scroll to bottom when a brand-new message arrives (not during streaming)
  useEffect(() => {
    userScrolledUp.current = false
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  if (isLoading) {
    return (
      <div className="flex-1 overflow-hidden">
        <div className="max-w-4xl mx-auto py-4 space-y-4 animate-pulse">
          {/* Skeleton: 3 message-shaped placeholders */}
          {[0.6, 0.8, 0.5].map((w, i) => (
            <div key={i} className={`flex gap-3 px-4 ${i % 2 === 0 ? '' : 'flex-row-reverse'}`}>
              <div className="shrink-0 w-8 h-8 rounded-full bg-white/5" />
              <div className="space-y-2" style={{ width: `${w * 100}%`, maxWidth: '75%' }}>
                <div className="h-4 rounded-lg bg-white/5" />
                <div className="h-4 rounded-lg bg-white/[0.03]" style={{ width: '80%' }} />
                {i === 1 && <div className="h-4 rounded-lg bg-white/[0.03]" style={{ width: '60%' }} />}
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-6 max-w-md text-center px-4">
          <DaenaAvatar state="idle" size={72} chatMode={chatMode} routingMode={routingMode} />
          <div>
            <h3 className="text-lg font-display font-semibold text-starlight-100 mb-2">
              Start a conversation
            </h3>
            <p className="text-sm text-starlight-400 leading-relaxed">
              Ask Daena anything. Your messages are processed through governance tiers,
              and responses come from the best available model for your query.
            </p>
          </div>
          <div className="flex gap-2 flex-wrap justify-center">
            {[
              'Analyze this codebase',
              'Research a topic',
              'Draft a proposal',
              'Debug an error',
              'Explain a concept',
            ].map((s) => (
              <button
                key={s}
                onClick={() => onQuickAction?.(s)}
                className="px-3 py-1.5 rounded-lg text-xs text-starlight-300 border border-white/10
                           hover:border-primary-500/30 hover:text-primary-400 hover:bg-primary-500/5
                           transition-all cursor-pointer active:scale-95"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto relative" ref={scrollContainerRef} onScroll={handleScroll}>
      <div className="max-w-4xl mx-auto py-4">
        <AnimatePresence mode="popLayout">
          {(() => {
            // Compute last assistant index once outside the loop
            let lastAssistantIdx = -1
            for (let j = messages.length - 1; j >= 0; j--) {
              if (messages[j].role === 'ASSISTANT') { lastAssistantIdx = j; break }
            }
            return messages.flatMap((msg, idx) => {
            const elements: React.JSX.Element[] = []

            // Insert completed thinking ABOVE the last AI response
            // Show when Think is ON (showThinking) or when persistThinking setting is enabled
            if (!isStreaming && completedThinking && (showThinking || persistThinking)
                && idx === lastAssistantIdx && msg.role === 'ASSISTANT') {
              elements.push(
                <ThinkingProcess
                  key="completed-thinking"
                  content={completedThinking.content}
                  isActive={false}
                  modelUsed={completedThinking.model || undefined}
                  steps={completedThinking.stages}
                />
              )
            }

            elements.push(
              <MessageBubble
                key={msg.id}
                message={msg}
                onEdit={onEditMessage}
                onRegenerate={onRegenerateMessage}
                isLastAssistant={idx === lastAssistantIdx}
              />
            )
            return elements
          })
          })()}
        </AnimatePresence>

        {/* Active thinking during streaming: above typing/streaming bubble */}
        <AnimatePresence>
          {isStreaming && showThinking && (thinkingContent || pipelineStages?.length) && (
            <ThinkingProcess
              content={thinkingContent}
              isActive={true}
              modelUsed={modelUsed || undefined}
              steps={pipelineStages}
            />
          )}
        </AnimatePresence>

        {/* Typing indicator — shows immediately when streaming starts, before first token */}
        {isStreaming && !streamedContent && (
          <motion.div
            className="flex gap-3 px-4 py-3"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="shrink-0 pt-1">
              <DaenaAvatar state="thinking" size={32} chatMode={chatMode} routingMode={routingMode} />
            </div>
            <div className="flex items-center gap-1.5 px-4 py-3 rounded-2xl glass-card rounded-bl-md">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="w-2 h-2 rounded-full bg-primary-400/60"
                  animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.1, 0.8] }}
                  transition={{ duration: 1, delay: i * 0.2, repeat: Infinity }}
                />
              ))}
            </div>
          </motion.div>
        )}

        {/* Streaming response bubble */}
        {isStreaming && streamedContent && (
          <MessageBubble
            message={{
              id: 'streaming',
              session_id: '',
              role: 'SYSTEM',
              content: '',
              model_used: null,
              provider_used: null,
              governance_tier: null,
              cost_usd: null,
              latency_ms: null,
              token_count_input: null,
              token_count_output: null,
              created_at: new Date().toISOString(),
            }}
            isStreaming
            streamedContent={streamedContent}
            daenabotActivity={daenabotActivity}
          />
        )}

        {/* Retry button — shown when last message failed */}
        {lastFailedMessage && !isStreaming && (
          <motion.div
            className="flex justify-center py-2"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <button
              onClick={() => void retryLastMessage()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                         text-starlight-300 border border-white/10 hover:border-primary-500/30
                         hover:text-primary-400 hover:bg-primary-500/5 transition-all cursor-pointer"
            >
              <RotateCcw size={12} />
              Retry last message
            </button>
          </motion.div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Scroll-to-bottom floating button — prominent during streaming */}
      <AnimatePresence>
        {showScrollButton && (
          <motion.button
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ duration: 0.15 }}
            onClick={scrollToBottom}
            className={`absolute bottom-4 right-6 z-10
                       flex items-center gap-1.5 rounded-full
                       backdrop-blur-sm shadow-lg shadow-black/30 transition-all cursor-pointer ${
                         isStreaming
                           ? 'px-3 py-1.5 bg-primary-500/90 border border-primary-400/40 text-white hover:bg-primary-500'
                           : 'w-9 h-9 justify-center bg-midnight-400/90 border border-white/10 text-starlight-400 hover:text-starlight-100 hover:border-white/20'
                       }`}
            title="Scroll to bottom"
            aria-label="Scroll to bottom"
          >
            <ArrowDown size={isStreaming ? 14 : 16} />
            {isStreaming && <span className="text-xs font-medium">New messages</span>}
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  )
})

export default MessageList
