/**
 * CommandPalette: Ctrl+K fuzzy search for sessions and pages.
 * Opens as an overlay modal with instant filtering.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, MessageSquare, LayoutDashboard, Shield, Brain, Settings, Bot, Zap, X, FolderKanban, Plug, Crown, Wrench, FileText, BarChart3, User, Kanban } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useChatStore } from '@/stores/chatStore'

interface PaletteItem {
  id: string
  label: string
  detail?: string
  icon: React.ReactNode
  action: () => void
  section: 'session' | 'page'
}

const PAGES: Omit<PaletteItem, 'action'>[] = [
  { id: 'p-chat', label: 'Chat', icon: <MessageSquare size={14} />, section: 'page' },
  { id: 'p-dashboard', label: 'Dashboard', icon: <LayoutDashboard size={14} />, section: 'page' },
  { id: 'p-projects', label: 'Projects', icon: <FolderKanban size={14} />, section: 'page' },
  { id: 'p-pipeline', label: 'Pipeline', icon: <Kanban size={14} />, section: 'page' },
  { id: 'p-approvals', label: 'Governance Approvals', icon: <Shield size={14} />, section: 'page' },
  { id: 'p-audit', label: 'Audit Log', icon: <Shield size={14} />, section: 'page' },
  { id: 'p-departments', label: 'Departments', icon: <Brain size={14} />, section: 'page' },
  { id: 'p-skills', label: 'Skills', icon: <Wrench size={14} />, section: 'page' },
  { id: 'p-tasks', label: 'Tasks', icon: <Bot size={14} />, section: 'page' },
  { id: 'p-files', label: 'Files', icon: <FileText size={14} />, section: 'page' },
  { id: 'p-connections', label: 'Connections', icon: <Plug size={14} />, section: 'page' },
  { id: 'p-analytics', label: 'Analytics', icon: <BarChart3 size={14} />, section: 'page' },
  { id: 'p-account', label: 'Account Settings', icon: <User size={14} />, section: 'page' },
  { id: 'p-account-usage', label: 'Usage & Credits', icon: <BarChart3 size={14} />, section: 'page' },
  { id: 'p-account-assistant', label: 'Assistant (LLM)', icon: <Bot size={14} />, section: 'page' },
  { id: 'p-account-org', label: 'Organization Settings', icon: <Settings size={14} />, section: 'page' },
]

const PAGE_PATHS: Record<string, string> = {
  'p-chat': '/chat',
  'p-dashboard': '/dashboard',
  'p-projects': '/projects',
  'p-pipeline': '/pipeline',
  'p-approvals': '/governance/approvals',
  'p-audit': '/governance/audit',
  'p-departments': '/departments',
  'p-skills': '/skills',
  'p-tasks': '/tasks',
  'p-files': '/files',
  'p-connections': '/connections',
  'p-analytics': '/analytics',
  'p-account': '/account/details',
  'p-account-usage': '/account/usage',
  'p-account-assistant': '/account/assistant',
  'p-account-org': '/account/org',
}

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  const navigate = useNavigate()
  const sessions = useChatStore((s) => s.sessions)

  // Build filtered items list
  const lowerQuery = query.toLowerCase()
  const sessionItems: PaletteItem[] = sessions
    .filter(s => !query || s.title.toLowerCase().includes(lowerQuery))
    .slice(0, 8)
    .map(s => ({
      id: s.id,
      label: s.title || 'Untitled',
      detail: `${s.message_count} msgs`,
      icon: <MessageSquare size={14} className="text-primary-400" />,
      section: 'session' as const,
      action: () => { navigate(`/chat/${s.id}`); onClose() },
    }))

  const pageItems: PaletteItem[] = PAGES
    .filter(p => !query || p.label.toLowerCase().includes(lowerQuery))
    .map(p => ({
      ...p,
      action: () => { navigate(PAGE_PATHS[p.id]); onClose() },
    }))

  const items = [...pageItems, ...sessionItems]

  // Reset selection on query change
  useEffect(() => setSelectedIndex(0), [query])

  // Focus input on open; on close restore focus to the trigger so keyboard /
  // screen-reader users keep their place when the palette is dismissed without
  // navigating (Escape / backdrop click). If an item was selected the trigger is
  // unmounted by the route change and the guarded restore is a safe no-op.
  useEffect(() => {
    if (!isOpen) return
    previousFocusRef.current = document.activeElement as HTMLElement | null
    setQuery('')
    setSelectedIndex(0)
    const id = setTimeout(() => inputRef.current?.focus(), 50)
    return () => {
      clearTimeout(id)
      previousFocusRef.current?.focus?.()
    }
  }, [isOpen])

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => Math.min(i + 1, items.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && items[selectedIndex]) {
      e.preventDefault()
      items[selectedIndex].action()
    } else if (e.key === 'Escape') {
      onClose()
    }
  }, [items, selectedIndex, onClose])

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
          // Bind pointerEvents to the open/exit state, not just opacity. If framer-motion
          // leaves this exit node mounted at opacity 0 (safeToRemove failing to fire -- a
          // known React.StrictMode dev double-invoke interaction with AnimatePresence), an
          // opacity-0 fixed inset-0 overlay would otherwise be an invisible full-viewport
          // click trap over the destination page. pointer-events is inherited, so the
          // backdrop + dialog cascade from here: 'auto' while open keeps backdrop-click-to-
          // close working, 'none' on exit makes any lingering node click-through.
          initial={{ opacity: 0, pointerEvents: 'none' }}
          animate={{ opacity: 1, pointerEvents: 'auto' }}
          exit={{ opacity: 0, pointerEvents: 'none' }}
          transition={{ duration: 0.1 }}
        >
          {/* Backdrop */}
          <motion.div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Palette */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            className="relative w-full max-w-lg mx-4 bg-midnight-300/95 backdrop-blur-md
                       border border-white/10 rounded-xl shadow-2xl overflow-hidden"
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ duration: 0.12 }}
          >
            {/* Search input */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-white/5">
              <Search size={16} className="text-starlight-500 shrink-0" />
              <input
                ref={inputRef}
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                aria-label="Search pages and sessions"
                placeholder="Search pages and sessions..."
                className="flex-1 bg-transparent text-sm text-starlight-100 placeholder:text-starlight-500
                           focus:outline-none"
              />
              <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded
                             bg-midnight-500/50 border border-white/10 text-[10px] text-starlight-500">
                ESC
              </kbd>
              <button onClick={onClose} aria-label="Close" className="p-1 text-starlight-500 hover:text-starlight-200 cursor-pointer">
                <X size={14} />
              </button>
            </div>

            {/* Results */}
            <div className="max-h-[320px] overflow-y-auto py-1">
              {items.length === 0 && (
                <div className="px-4 py-8 text-center text-xs text-starlight-500">
                  No results for &ldquo;{query}&rdquo;
                </div>
              )}

              {/* Pages section */}
              {pageItems.length > 0 && (
                <>
                  <div className="px-4 py-1 text-[9px] font-mono uppercase tracking-wider text-starlight-600">
                    Pages
                  </div>
                  {pageItems.map((item) => {
                    const idx = items.indexOf(item)
                    return (
                      <button
                        key={item.id}
                        onClick={item.action}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={`w-full flex items-center gap-3 px-4 py-2 text-left text-sm transition-colors cursor-pointer ${
                          idx === selectedIndex
                            ? 'bg-primary-500/10 text-primary-300'
                            : 'text-starlight-300 hover:bg-white/5'
                        }`}
                      >
                        {item.icon}
                        <span className="truncate">{item.label}</span>
                      </button>
                    )
                  })}
                </>
              )}

              {/* Sessions section */}
              {sessionItems.length > 0 && (
                <>
                  <div className="px-4 py-1 mt-1 text-[9px] font-mono uppercase tracking-wider text-starlight-600">
                    Chat Sessions
                  </div>
                  {sessionItems.map((item) => {
                    const idx = items.indexOf(item)
                    return (
                      <button
                        key={item.id}
                        onClick={item.action}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={`w-full flex items-center gap-3 px-4 py-2 text-left text-sm transition-colors cursor-pointer ${
                          idx === selectedIndex
                            ? 'bg-primary-500/10 text-primary-300'
                            : 'text-starlight-300 hover:bg-white/5'
                        }`}
                      >
                        {item.icon}
                        <span className="truncate flex-1">{item.label}</span>
                        {item.detail && (
                          <span className="text-[10px] text-starlight-600 shrink-0">{item.detail}</span>
                        )}
                      </button>
                    )
                  })}
                </>
              )}
            </div>

            {/* Footer hint */}
            <div className="px-4 py-2 border-t border-white/5 flex items-center gap-4 text-[10px] text-starlight-600">
              <span><kbd className="px-1 py-0.5 rounded bg-midnight-500/50 border border-white/10">↑↓</kbd> Navigate</span>
              <span><kbd className="px-1 py-0.5 rounded bg-midnight-500/50 border border-white/10">↵</kbd> Open</span>
              <span><kbd className="px-1 py-0.5 rounded bg-midnight-500/50 border border-white/10">Esc</kbd> Close</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export default CommandPalette
