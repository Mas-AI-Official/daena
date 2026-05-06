/**
 * MessageBubble — renders a single chat message.
 * User messages: right-aligned, primary color, with inline edit on hover + avatar initial.
 * System/Daena messages: left-aligned with NeuralOrb avatar, glass style.
 * Renders markdown via react-markdown (bold, lists, headers, code blocks).
 */
import { memo, useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark-dimmed.min.css'
import { Clock, Copy, Cpu, Zap, Pencil, Check, X, RotateCcw, ChevronDown, ChevronUp, Terminal, FileText, Globe, AlertCircle, Maximize2, Minimize2, ThumbsUp, ThumbsDown, Building2 } from 'lucide-react'
import { DaenaAvatar } from './DaenaAvatar'
import { VPCommandCard } from './VPCommandCard'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import type { MessageResponse } from '@/types/api'

interface DaenaBotActivity {
  agent: string
  operation: string
  status: 'executing' | 'completed' | 'failed'
  description: string
}

interface MessageBubbleProps {
  message: MessageResponse
  isStreaming?: boolean
  streamedContent?: string
  daenabotActivity?: DaenaBotActivity | null
  /** Called when user submits an edit — triggers truncate + regenerate */
  onEdit?: (messageId: string, newContent: string) => void
  /** Called when user clicks Regenerate on the last assistant message */
  onRegenerate?: (messageId: string) => void
  /** Whether this is the last assistant message (shows Regenerate button) */
  isLastAssistant?: boolean
}

/** User avatar — shows first initial in a circle */
function UserAvatar() {
  const user = useAuthStore((s) => s.user)
  const initial = user?.display_name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || 'U'

  return (
    <div className="shrink-0 w-8 h-8 rounded-full bg-primary-500/25 border border-primary-500/30 flex items-center justify-center">
      <span className="text-xs font-semibold text-primary-400">{initial}</span>
    </div>
  )
}

/** Collapsible model metadata row — only shown when user manually selected a model */
function ModelMeta({ message }: { message: MessageResponse }) {
  const [open, setOpen] = useState(false)
  const selectedModel = useUiStore((s) => s.selectedModel)

  // Hide model details when routing is Auto/Standard (no explicit model selection)
  if (!message.model_used || !selectedModel) return null

  return (
    <div className="mt-2 pt-2 border-t border-white/5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] text-starlight-500 hover:text-starlight-300 transition-colors cursor-pointer"
      >
        <Cpu size={10} />
        <span>{message.model_used}</span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.15 }}>
          <ChevronDown size={10} />
        </motion.span>
      </button>

      {open && (
        <div className="flex items-center gap-3 mt-1 text-[10px] text-starlight-500">
          {message.latency_ms != null && (
            <span className="flex items-center gap-1">
              <Clock size={10} />
              {message.latency_ms}ms
            </span>
          )}
          {message.cost_usd != null && message.cost_usd > 0 && (
            <span className="flex items-center gap-1">
              <Zap size={10} />
              ${message.cost_usd.toFixed(4)}
            </span>
          )}
          {message.provider_used && (
            <span className="text-starlight-500/60">{message.provider_used}</span>
          )}
        </div>
      )}
    </div>
  )
}

/** Agent activity indicator — shows which DaenaBot agent is executing */
function DaenaBotActivityBadge({ activity }: { activity: DaenaBotActivity }) {
  const agentIcon = () => {
    const name = activity.agent.toLowerCase()
    if (name.includes('file')) return <FileText size={12} />
    if (name.includes('terminal')) return <Terminal size={12} />
    if (name.includes('browser')) return <Globe size={12} />
    return <Zap size={12} />
  }

  const statusColor = activity.status === 'executing'
    ? 'text-accent-cyan'
    : activity.status === 'completed'
      ? 'text-status-success'
      : 'text-status-error'

  return (
    <motion.div
      className={`flex items-center gap-1.5 px-3 py-1.5 mb-1 rounded-lg bg-midnight-500/40 border border-white/5 text-xs ${statusColor}`}
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {agentIcon()}
      <span className="font-medium">{activity.agent}</span>
      <span className="text-starlight-500">&middot;</span>
      <span className="text-starlight-400">{activity.description}</span>
      {activity.status === 'executing' && (
        <motion.span
          className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-accent-cyan"
          animate={{ opacity: [1, 0.3] }}
          transition={{ duration: 0.6, repeat: Infinity }}
        />
      )}
      {activity.status === 'completed' && <Check size={12} className="ml-1" />}
      {activity.status === 'failed' && <AlertCircle size={12} className="ml-1" />}
    </motion.div>
  )
}

/** Code block wrapper with copy button */
function CodeBlock({ children }: { children: React.ReactNode }) {
  const [copied, setCopied] = useState(false)
  const preRef = useRef<HTMLPreElement>(null)

  const handleCopy = async () => {
    const text = preRef.current?.textContent ?? ''
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard not available */ }
  }

  return (
    <div className="relative group/code my-2">
      <pre
        ref={preRef}
        className="rounded-md bg-midnight-950/80 border border-white/5 p-3 overflow-x-auto"
      >
        {children}
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1 rounded text-[10px] font-mono
                   text-starlight-500 hover:text-starlight-200 bg-midnight-400/80
                   hover:bg-midnight-300/80 border border-white/10
                   opacity-0 group-hover/code:opacity-100 transition-all cursor-pointer"
        title="Copy code"
        aria-label="Copy code"
      >
        {copied ? <Check size={12} className="text-status-success" /> : <Copy size={12} />}
      </button>
    </div>
  )
}

/** Copy-to-clipboard button with check feedback */
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard not available */ }
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px]
                 text-starlight-500 hover:text-starlight-200 hover:bg-white/5
                 transition-all cursor-pointer"
      title="Copy response"
      aria-label="Copy response"
    >
      {copied ? <Check size={10} className="text-status-success" /> : <Copy size={10} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

/** Thumbs up/down feedback — sends to backend for quality tracking */
function FeedbackButtons({ messageId }: { messageId: string }) {
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)

  const sendFeedback = async (type: 'up' | 'down') => {
    if (feedback === type) {
      setFeedback(null)
      return
    }
    setFeedback(type)
    try {
      const token = localStorage.getItem('daena_token')
      await fetch(`/api/v1/chat/messages/${messageId}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ rating: type === 'up' ? 1 : -1 }),
      })
    } catch {
      // Silent fail — feedback is non-critical
    }
  }

  return (
    <div className="flex items-center gap-0.5">
      <button
        onClick={() => sendFeedback('up')}
        className={`p-1 rounded transition-all cursor-pointer ${
          feedback === 'up'
            ? 'text-status-success bg-status-success/10'
            : 'text-starlight-500 hover:text-starlight-200 hover:bg-white/5'
        }`}
        title="Good response"
        aria-label="Thumbs up"
      >
        <ThumbsUp size={11} />
      </button>
      <button
        onClick={() => sendFeedback('down')}
        className={`p-1 rounded transition-all cursor-pointer ${
          feedback === 'down'
            ? 'text-status-error bg-status-error/10'
            : 'text-starlight-500 hover:text-starlight-200 hover:bg-white/5'
        }`}
        title="Poor response"
        aria-label="Thumbs down"
      >
        <ThumbsDown size={11} />
      </button>
    </div>
  )
}

/** Threshold for collapsing long messages (line count) */
const COLLAPSE_LINE_THRESHOLD = 30
/** How many lines to show when collapsed */
const COLLAPSED_PREVIEW_LINES = 12

export const MessageBubble = memo(function MessageBubble({ message, isStreaming, streamedContent, daenabotActivity, onEdit, onRegenerate, isLastAssistant }: MessageBubbleProps) {
  const chatMode = useUiStore((s) => s.chatMode)
  const routingMode = useUiStore((s) => s.routingMode)
  const isUser = message.role === 'USER'
  const content = isStreaming && streamedContent ? streamedContent : message.content

  // Collapse state for long messages
  const lineCount = content.split('\n').length
  const isLongMessage = !isUser && !isStreaming && lineCount > COLLAPSE_LINE_THRESHOLD
  const [isCollapsed, setIsCollapsed] = useState(true) // Start collapsed for long messages
  const displayContent = isLongMessage && isCollapsed
    ? content.split('\n').slice(0, COLLAPSED_PREVIEW_LINES).join('\n') + '\n...'
    : content

  // Edit state — only for USER messages
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(content)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Focus + auto-size on enter edit mode
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      const ta = textareaRef.current
      ta.focus()
      ta.style.height = 'auto'
      ta.style.height = `${ta.scrollHeight}px`
      ta.selectionStart = ta.selectionEnd = ta.value.length
    }
  }, [isEditing])

  const handleEditStart = () => {
    setEditValue(content)
    setIsEditing(true)
  }

  const handleEditConfirm = () => {
    const trimmed = editValue.trim()
    if (trimmed && onEdit) {
      // Always regenerate on confirm (like ChatGPT) even if text unchanged.
      // User clicking confirm = "I want a new response from this point."
      onEdit(message.id, trimmed)
    }
    setIsEditing(false)
  }

  const handleEditCancel = () => {
    setIsEditing(false)
    setEditValue(content)
  }

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleEditConfirm()
    }
    if (e.key === 'Escape') {
      handleEditCancel()
    }
  }

  return (
    <motion.div
      className={`flex gap-3 px-4 py-3 group ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      {/* Avatar */}
      {isUser ? (
        <div className="shrink-0 pt-1">
          <UserAvatar />
        </div>
      ) : (
        <div className="shrink-0 pt-1">
          <DaenaAvatar state={isStreaming ? 'speaking' : 'idle'} size={32} chatMode={chatMode} routingMode={routingMode} />
        </div>
      )}

      {/* Bubble + edit actions */}
      <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'} max-w-[75%]`}>
        {/* DaenaBot activity indicator */}
        {!isUser && isStreaming && daenabotActivity && (
          <DaenaBotActivityBadge activity={daenabotActivity} />
        )}

        {isEditing ? (
          /* ── Inline edit mode ── */
          <div className="w-full min-w-[280px]">
            <textarea
              ref={textareaRef}
              value={editValue}
              onChange={(e) => {
                setEditValue(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = `${e.target.scrollHeight}px`
              }}
              onKeyDown={handleEditKeyDown}
              className="w-full resize-none rounded-2xl rounded-br-md bg-primary-500/10 border border-primary-500/30
                         text-sm text-starlight-100 px-4 py-3 focus:outline-none
                         focus:ring-1 focus:ring-primary-500/60 leading-relaxed"
              rows={1}
            />
            <div className="flex items-center gap-1.5 mt-1 justify-end">
              <span className="text-[10px] text-starlight-500">Enter to send · Esc to cancel</span>
              <button
                onClick={handleEditCancel}
                className="p-1 rounded text-starlight-400 hover:text-starlight-100 hover:bg-white/5 transition-colors cursor-pointer"
                title="Cancel"
                aria-label="Cancel edit"
              >
                <X size={13} />
              </button>
              <button
                onClick={handleEditConfirm}
                disabled={!editValue.trim()}
                className="p-1 rounded text-status-success hover:bg-status-success/10 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                title="Send & regenerate"
                aria-label="Send and regenerate"
              >
                <Check size={13} />
              </button>
            </div>
          </div>
        ) : (
          /* ── Normal display ── */
          <div
            className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              isUser
                ? 'bg-primary-500/20 text-starlight-100 border border-primary-500/20 rounded-br-md'
                : 'glass-card text-starlight-200 rounded-bl-md'
            }`}
          >
            {/* Long message header bar */}
            {isLongMessage && (
              <div className="flex items-center gap-2 mb-2 pb-2 border-b border-white/5">
                <FileText size={12} className="text-starlight-500" />
                <span className="text-[10px] font-mono text-starlight-500">
                  {lineCount} lines
                </span>
                <button
                  onClick={() => setIsCollapsed(!isCollapsed)}
                  className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded text-[10px]
                             text-primary-400 hover:text-primary-300 hover:bg-primary-500/10
                             transition-all cursor-pointer"
                >
                  {isCollapsed ? <Maximize2 size={10} /> : <Minimize2 size={10} />}
                  {isCollapsed ? 'Show full' : 'Collapse'}
                </button>
              </div>
            )}

            {/* VP-command card (Sprint-MORNING PR-1): when the chat preflight
                matched a deterministic VP-work intent, render the structured
                card instead of the markdown body. */}
            {message.vp_command_result ? (
              <VPCommandCard result={message.vp_command_result} />
            ) : (
            <div className={`prose-daena break-words ${isLongMessage && isCollapsed ? 'relative' : ''}`}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
                  code: ({ className, children, ...props }) => {
                    const isBlock = className?.includes('language-') || className?.includes('hljs')
                    if (isBlock) {
                      const lang = className?.replace(/language-|hljs\s*/g, '').trim()
                      return (
                        <>
                          {lang && (
                            <span className="block text-[10px] font-mono text-starlight-500 mb-1 uppercase">
                              {lang}
                            </span>
                          )}
                          <code className={`text-xs font-mono leading-relaxed ${className ?? ''}`} {...props}>
                            {children}
                          </code>
                        </>
                      )
                    }
                    return (
                      <code
                        className="px-1.5 py-0.5 rounded bg-midnight-500/60 text-accent-cyan font-mono text-[0.85em]"
                        {...props}
                      >
                        {children}
                      </code>
                    )
                  },
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-0.5">{children}</ul>,
                  ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-0.5">{children}</ol>,
                  li: ({ children }) => <li className="text-sm">{children}</li>,
                  h1: ({ children }) => <h1 className="text-base font-bold mb-2 text-starlight-100">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-sm font-bold mb-1.5 text-starlight-100">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 text-starlight-100">{children}</h3>,
                  strong: ({ children }) => <strong className="font-semibold text-starlight-100">{children}</strong>,
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:underline">
                      {children}
                    </a>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-primary-500/30 pl-3 my-2 text-starlight-300 italic">
                      {children}
                    </blockquote>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-2">
                      <table className="min-w-full text-xs border border-white/10">{children}</table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="px-2 py-1 border border-white/10 bg-midnight-400/40 text-left font-medium text-starlight-200">{children}</th>
                  ),
                  td: ({ children }) => (
                    <td className="px-2 py-1 border border-white/10 text-starlight-300">{children}</td>
                  ),
                }}
              >
                {displayContent}
              </ReactMarkdown>

              {/* Fade overlay when collapsed */}
              {isLongMessage && isCollapsed && (
                <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-midnight-500/95 to-transparent pointer-events-none" />
              )}
            </div>
            )}

            {/* Expand bar at bottom of collapsed messages */}
            {isLongMessage && isCollapsed && (
              <button
                onClick={() => setIsCollapsed(false)}
                className="flex items-center justify-center gap-1.5 w-full mt-1 pt-2 pb-1
                           text-[11px] text-primary-400 hover:text-primary-300
                           border-t border-white/5 hover:bg-primary-500/5
                           transition-all cursor-pointer rounded-b-lg"
              >
                <ChevronDown size={12} />
                Show full response ({lineCount} lines)
              </button>
            )}

            {/* Collapsible model metadata */}
            {!isUser && <ModelMeta message={message} />}

            {/* Streaming cursor */}
            {isStreaming && (
              <motion.span
                className="inline-block w-2 h-4 bg-primary-400 ml-1 align-middle rounded-sm"
                animate={{ opacity: [1, 0] }}
                transition={{ duration: 0.5, repeat: Infinity }}
              />
            )}
          </div>
        )}

        {/* Action row: timestamp + edit/copy.
          * USER rows stay hover-only (edit is destructive, reduces clutter).
          * ASSISTANT rows are persistently visible at 60% opacity so Copy +
          * Feedback are always discoverable (touch devices have no hover
          * event, and founders reported "there is no copy button"). */}
        {!isEditing && !isStreaming && (
          <div
            className={`flex items-center gap-2 transition-all ${isUser ? 'flex-row-reverse' : ''} ${
              isUser
                ? 'opacity-0 group-hover:opacity-100'
                : 'opacity-60 group-hover:opacity-100'
            }`}
          >
            {/* Timestamp */}
            {message.created_at && (
              <span className="text-[10px] text-starlight-600">
                {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            {/* Copy button — USER messages too. Critical when a reply
                fails: operator can re-grab their prompt without retyping. */}
            {isUser && (
              <CopyButton text={content} />
            )}
            {/* Edit button — USER messages only */}
            {isUser && onEdit && (
              <button
                onClick={handleEditStart}
                className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px]
                           text-starlight-500 hover:text-starlight-200 hover:bg-white/5
                           transition-all cursor-pointer"
                title="Edit & regenerate"
                aria-label="Edit and regenerate"
              >
                <RotateCcw size={10} />
                <Pencil size={10} />
                Edit
              </button>
            )}
            {/* Copy + Feedback + Regenerate — ASSISTANT messages only */}
            {!isUser && (
              <>
                {/* Department indicator — shows which department handled this */}
                {(message as unknown as Record<string, unknown>).department_name && (
                  <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] text-primary-400/80 bg-primary-500/8">
                    <Building2 size={9} />
                    {String((message as unknown as Record<string, unknown>).department_name)}
                  </span>
                )}
                <CopyButton text={content} />
                <FeedbackButtons messageId={message.id} />
                {isLastAssistant && onRegenerate && (
                  <button
                    onClick={() => onRegenerate(message.id)}
                    className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px]
                               text-starlight-500 hover:text-starlight-200 hover:bg-white/5
                               transition-all cursor-pointer"
                    title="Regenerate response"
                    aria-label="Regenerate response"
                  >
                    <RotateCcw size={10} />
                    Regenerate
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </motion.div>
  )
})

export default MessageBubble
