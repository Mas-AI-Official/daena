/**
 * DaenaBot execution page -- chat-like interface for computer control commands.
 *
 * Shows command history, governance assessment badges, execution results,
 * and approval prompts for Tier 3+ actions.
 */
import { useEffect, useRef, useState } from 'react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { Badge, Card } from '@/components/common'
import { useDaenaBotStore } from '@/stores/daenabotStore'
import { useUiStore } from '@/stores/uiStore'
import type { DaenaBotMessage } from '@/stores/daenabotStore'
import {
  Terminal,
  File,
  Globe,
  Send,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  HelpCircle,
  Loader2,
  Trash2,
} from 'lucide-react'

function agentIcon(agent: string | null | undefined) {
  if (!agent) return <Terminal size={14} />
  const lower = agent.toLowerCase()
  if (lower.includes('file')) return <File size={14} />
  if (lower.includes('browser')) return <Globe size={14} />
  return <Terminal size={14} />
}

function statusBadge(status: DaenaBotMessage['status'], tier: number) {
  switch (status) {
    case 'executed':
      return <Badge variant="success" size="sm">Executed</Badge>
    case 'pending_approval':
      return <Badge variant="warning" size="sm">Tier {tier}: Approval Required</Badge>
    case 'blocked':
      return <Badge variant="danger" size="sm">Blocked</Badge>
    case 'error':
      return <Badge variant="danger" size="sm">Error</Badge>
    case 'no_match':
      return <Badge variant="default" size="sm">No Match</Badge>
    default:
      return null
  }
}

function statusIcon(status: DaenaBotMessage['status']) {
  switch (status) {
    case 'executed':
      return <CheckCircle size={14} className="text-status-success" />
    case 'pending_approval':
      return <Clock size={14} className="text-accent-amber" />
    case 'blocked':
      return <XCircle size={14} className="text-status-error" />
    case 'error':
      return <AlertTriangle size={14} className="text-status-error" />
    case 'no_match':
      return <HelpCircle size={14} className="text-starlight-500" />
    default:
      return null
  }
}

function MessageItem({
  msg,
  onApprove,
  onReject,
}: {
  msg: DaenaBotMessage
  onApprove: (id: string) => void
  onReject: (id: string) => void
}) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-br-md bg-primary-500/20 border border-primary-500/30 text-sm text-starlight-100">
          {msg.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] space-y-2">
        <div className="px-4 py-2.5 rounded-2xl rounded-bl-md bg-midnight-800/60 border border-white/5">
          {/* Agent + status header */}
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            {msg.agent && (
              <span className="flex items-center gap-1 text-xs text-starlight-400">
                {agentIcon(msg.agent)}
                {msg.agent}
              </span>
            )}
            {msg.operation && (
              <span className="text-[10px] text-starlight-500 font-mono">
                {msg.operation}
              </span>
            )}
            {statusBadge(msg.status, msg.governanceTier ?? 0)}
          </div>

          {/* Description */}
          {msg.description && msg.description !== msg.content && (
            <p className="text-xs text-starlight-400 mb-1">{msg.description}</p>
          )}

          {/* Main content */}
          <p className="text-sm text-starlight-200">{msg.content}</p>

          {/* Result details */}
          {msg.result && msg.status === 'executed' && (
            <details className="mt-2">
              <summary className="text-[10px] text-starlight-500 cursor-pointer hover:text-starlight-300">
                Show result
              </summary>
              <pre className="mt-1 text-[10px] text-starlight-500 bg-midnight-900/40 rounded p-2 overflow-x-auto max-h-48 overflow-y-auto">
                {JSON.stringify(msg.result, null, 2)}
              </pre>
            </details>
          )}
        </div>

        {/* Approval buttons for pending actions */}
        {msg.status === 'pending_approval' && msg.approvalId && (
          <div className="flex gap-2 px-2">
            <button
              onClick={() => onApprove(msg.approvalId!)}
              className="flex items-center gap-1 px-3 py-1 rounded-lg bg-status-success/20 border border-status-success/30 text-xs text-status-success hover:bg-status-success/30 transition-colors cursor-pointer"
            >
              <CheckCircle size={12} /> Approve
            </button>
            <button
              onClick={() => onReject(msg.approvalId!)}
              className="flex items-center gap-1 px-3 py-1 rounded-lg bg-status-error/20 border border-status-error/30 text-xs text-status-error hover:bg-status-error/30 transition-colors cursor-pointer"
            >
              <XCircle size={12} /> Reject
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export function DaenaBotPage() {
  usePageTitle('DaenaBot')
  const {
    messages,
    pendingApprovals,
    isExecuting,
    agents,
    sendCommand,
    approveAction,
    rejectAction,
    fetchAgents,
    clearHistory,
  } = useDaenaBotStore()

  const { daenaBotEnabled } = useUiStore()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    void fetchAgents()
  }, [fetchAgents])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || isExecuting) return
    setInput('')
    void sendCommand(trimmed)
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden max-w-4xl mx-auto w-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/5 shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-display font-semibold text-starlight-100 flex items-center gap-2">
              <Terminal size={20} /> DaenaBot
            </h1>
            <p className="text-xs text-starlight-500 mt-0.5">
              Computer control: files, terminal, browser
            </p>
          </div>
          <div className="flex items-center gap-3">
            {pendingApprovals.length > 0 && (
              <Badge variant="warning" size="sm">
                {pendingApprovals.length} pending
              </Badge>
            )}
            {messages.length > 0 && (
              <button
                onClick={clearHistory}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-starlight-500 hover:text-starlight-300 hover:bg-white/5 transition-colors cursor-pointer"
              >
                <Trash2 size={12} /> Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Message area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3 scrollbar-hide">
        {!daenaBotEnabled && (
          <Card variant="glass" padding="md">
            <div className="flex items-center gap-2 text-accent-amber">
              <AlertTriangle size={16} />
              <p className="text-sm">
                DaenaBot is disabled. Enable it in Settings to use computer control.
              </p>
            </div>
          </Card>
        )}

        {messages.length === 0 && daenaBotEnabled && (
          <div className="text-center py-12 space-y-4">
            <Terminal size={40} className="mx-auto text-starlight-500" />
            <div>
              <p className="text-sm text-starlight-300">Ask Daena to do something on your computer</p>
              <p className="text-xs text-starlight-500 mt-1">
                Examples: "list files in D:\Projects", "run `git status`", "open https://example.com"
              </p>
            </div>

            {/* Agent capabilities */}
            {agents.length > 0 && (
              <div className="grid grid-cols-3 gap-3 max-w-lg mx-auto mt-6">
                {agents.map((a) => (
                  <div
                    key={a.name}
                    className="text-left px-3 py-2.5 rounded-lg bg-midnight-800/40 border border-white/5"
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      {agentIcon(a.name)}
                      <span className="text-xs font-semibold text-starlight-200">{a.name}</span>
                    </div>
                    <p className="text-[10px] text-starlight-500 line-clamp-2">{a.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((msg) => (
          <MessageItem
            key={msg.id}
            msg={msg}
            onApprove={approveAction}
            onReject={rejectAction}
          />
        ))}

        {isExecuting && (
          <div className="flex justify-start">
            <div className="px-4 py-2.5 rounded-2xl rounded-bl-md bg-midnight-800/60 border border-white/5">
              <div className="flex items-center gap-2 text-xs text-starlight-400">
                <Loader2 size={14} className="animate-spin" />
                Executing...
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-6 py-3 border-t border-white/5 shrink-0">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Daena to do something on your computer..."
            disabled={isExecuting || !daenaBotEnabled}
            className="flex-1 bg-midnight-800/60 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-starlight-100 placeholder-starlight-500 focus:outline-none focus:border-primary-500/50 disabled:opacity-50 transition-colors"
          />
          <button
            type="submit"
            disabled={isExecuting || !input.trim() || !daenaBotEnabled}
            className="px-4 py-2.5 rounded-xl bg-primary-500/20 border border-primary-500/30 text-primary-400 hover:bg-primary-500/30 disabled:opacity-40 transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            <Send size={16} />
          </button>
        </div>
      </form>
    </div>
  )
}

export default DaenaBotPage
