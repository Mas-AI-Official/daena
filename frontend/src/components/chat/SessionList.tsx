/**
 * SessionList — chat session sidebar with:
 * - New Chat button
 * - Active sessions list with context menu (rename, export, archive)
 * - Batch select mode with floating action bar
 * - Collapsible "Archived" section with un-archive
 * - Inline rename with auto-title display
 * - Error toast for failed actions
 */
import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Archive,
  ArchiveRestore,
  Download,
  X,
  Check,
  CheckSquare,
  Square,
  ChevronDown,
  Trash2,
  AlertTriangle,
} from 'lucide-react'
import { useChatStore } from '@/stores/chatStore'
import { useUiStore } from '@/stores/uiStore'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

// ── Context menu state ──

interface MenuState {
  sessionId: string
  x: number
  y: number
}

// Department badge colors (matches DepartmentsPage)
const DEPT_BADGE_COLORS: Record<string, string> = {
  Engineering: 'bg-primary-500/20 text-primary-400',
  Product: 'bg-accent-purple/20 text-accent-purple',
  Marketing: 'bg-status-success/20 text-status-success',
  Sales: 'bg-accent-cyan/20 text-accent-cyan',
  Finance: 'bg-status-warning/20 text-status-warning',
  Operations: 'bg-accent-amber/20 text-accent-amber',
  Research: 'bg-blue-500/20 text-blue-400',
  'Legal & Compliance': 'bg-status-error/20 text-status-error',
  'Skill Governance': 'bg-fuchsia-500/20 text-fuchsia-400',
  'Security Operations': 'bg-pink-500/20 text-pink-400',
}

interface SessionListProps {
  departmentId?: string
}

export function SessionList({ departmentId }: SessionListProps = {}) {
  const navigate = useNavigate()
  const { sessionId } = useParams()
  // Individual selectors instead of whole-store destructure - SessionList
  // appears next to ChatPage, so any whole-store subscription cascades
  // re-renders on every stream tick.
  const sessions = useChatStore((s) => s.sessions)
  const sessionsLoading = useChatStore((s) => s.sessionsLoading)
  const fetchSessions = useChatStore((s) => s.fetchSessions)
  const createSession = useChatStore((s) => s.createSession)
  const setActiveSession = useChatStore((s) => s.setActiveSession)
  const deleteSession = useChatStore((s) => s.deleteSession)
  const messages = useChatStore((s) => s.messages)
  const { chatMode } = useUiStore()

  // Context menu
  const [menu, setMenu] = useState<MenuState | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Inline rename
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const renameInputRef = useRef<HTMLInputElement>(null)

  // Batch select
  const [selectMode, setSelectMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Archived section
  const [showArchived, setShowArchived] = useState(false)

  // Action error (inline toast)
  // actionError removed — now uses global toast system

  // Confirm delete dialog
  const [confirmDelete, setConfirmDelete] = useState<string[] | null>(null)

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  useEffect(() => {
    if (sessionId) {
      setActiveSession(sessionId)
    }
  }, [sessionId, setActiveSession])

  // Close context menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenu(null)
      }
    }
    if (menu) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [menu])

  // Focus rename input when entering rename mode
  useEffect(() => {
    if (renamingId) renameInputRef.current?.focus()
  }, [renamingId])

  // Exit select mode on Escape
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && selectMode) {
        setSelectMode(false)
        setSelectedIds(new Set())
      }
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [selectMode])

  // ── Error toast helper — delegates to global toast system ──
  const showError = useCallback((msg: string) => {
    toast.error(msg)
  }, [])

  // ── Navigation ──

  const handleNewChat = async () => {
    try {
      const ui = useUiStore.getState()
      const session = await createSession({
        mode: ui.chatMode,
        routingMode: ui.routingMode,
        departmentId,
        autopilot: ui.autopilotActive,
        thinkMode: ui.thinkingVisible,
      })
      if (departmentId) {
        navigate(`/departments/${departmentId}/chat/${session.id}`)
      } else {
        navigate(`/chat/${session.id}`)
      }
    } catch {
      showError('Failed to create new chat')
    }
  }

  const handleSelectSession = (id: string) => {
    if (selectMode) {
      toggleSelected(id)
      return
    }
    // Route to department chat if session has a department
    const session = sessions.find((s) => s.id === id)
    if (departmentId) {
      navigate(`/departments/${departmentId}/chat/${id}`)
    } else if (session?.department_id) {
      navigate(`/departments/${session.department_id}/chat/${id}`)
    } else {
      navigate(`/chat/${id}`)
    }
  }

  // ── Context menu ──

  const handleContextMenu = (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    setMenu({ sessionId: id, x: e.clientX, y: e.clientY })
  }

  const openMenuFromDots = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    setMenu({ sessionId: id, x: rect.right, y: rect.top })
  }

  // ── Batch select ──

  const toggleSelected = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      // Exit select mode if nothing selected
      if (next.size === 0) setSelectMode(false)
      return next
    })
  }

  const selectAll = () => {
    const ids = activeSessions.map((s) => s.id)
    setSelectedIds(new Set(ids))
  }

  const enterSelectMode = (id?: string) => {
    setSelectMode(true)
    if (id) setSelectedIds(new Set([id]))
    setMenu(null)
  }

  // ── Actions ──

  const startRename = (id: string) => {
    const session = sessions.find((s) => s.id === id)
    setRenameValue(session?.title || '')
    setRenamingId(id)
    setMenu(null)
  }

  const confirmRename = async () => {
    if (!renamingId || !renameValue.trim()) {
      setRenamingId(null)
      return
    }
    try {
      await api.patch(`/chat/sessions/${renamingId}`, { title: renameValue.trim() })
      useChatStore.setState((s) => ({
        sessions: s.sessions.map((ses) =>
          ses.id === renamingId ? { ...ses, title: renameValue.trim() } : ses,
        ),
      }))
    } catch {
      showError('Failed to rename session')
    }
    setRenamingId(null)
  }

  const archiveSession = async (id: string) => {
    setMenu(null)
    try {
      await api.patch(`/chat/sessions/${id}`, { is_archived: true })
      useChatStore.setState((s) => ({
        sessions: s.sessions.map((ses) =>
          ses.id === id ? { ...ses, is_archived: true } : ses,
        ),
      }))
      if (id === sessionId) navigate('/chat')
    } catch {
      showError('Failed to archive session')
    }
  }

  const unarchiveSession = async (id: string) => {
    try {
      await api.patch(`/chat/sessions/${id}`, { is_archived: false })
      useChatStore.setState((s) => ({
        sessions: s.sessions.map((ses) =>
          ses.id === id ? { ...ses, is_archived: false } : ses,
        ),
      }))
    } catch {
      showError('Failed to restore session')
    }
  }

  const batchArchive = async () => {
    const ids = [...selectedIds]
    try {
      await Promise.all(ids.map((id) => api.patch(`/chat/sessions/${id}`, { is_archived: true })))
      useChatStore.setState((s) => ({
        sessions: s.sessions.map((ses) =>
          ids.includes(ses.id) ? { ...ses, is_archived: true } : ses,
        ),
      }))
      if (sessionId && ids.includes(sessionId)) navigate('/chat')
    } catch {
      showError(`Failed to archive ${ids.length} session(s)`)
    }
    setSelectMode(false)
    setSelectedIds(new Set())
  }

  const batchDelete = async (ids: string[]) => {
    try {
      await Promise.all(ids.map((id) => deleteSession(id)))
      if (sessionId && ids.includes(sessionId)) navigate('/chat')
    } catch {
      showError(`Failed to delete ${ids.length} session(s)`)
    }
    setConfirmDelete(null)
    setSelectMode(false)
    setSelectedIds(new Set())
  }

  const exportSession = (id: string) => {
    setMenu(null)
    const session = sessions.find((s) => s.id === id)
    const currentMessages = id === sessionId ? messages : []
    const payload = {
      session: { id, title: session?.title, mode: session?.mode, created_at: session?.created_at },
      messages: currentMessages.map((m) => ({
        role: m.role,
        content: m.content,
        model_used: m.model_used,
        created_at: m.created_at,
      })),
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `daena-chat-${(session?.title || id).slice(0, 30)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Derived lists — filter by department when in department context ──

  const filteredSessions = departmentId
    ? sessions.filter((s) => s.department_id === departmentId)
    : sessions
  const activeSessions = filteredSessions.filter((s) => !s.is_archived).slice(0, 50)
  const archivedSessions = filteredSessions.filter((s) => s.is_archived)

  // ── Render helpers ──

  const renderSessionRow = (session: typeof sessions[0], isArchived = false) => {
    const isActive = session.id === sessionId
    const isRenaming = session.id === renamingId
    const isSelected = selectedIds.has(session.id)

    return (
      <motion.div
        key={session.id}
        layout
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -8, height: 0 }}
        className="relative group"
      >
        <button
          onClick={() =>
            isArchived ? unarchiveSession(session.id) : handleSelectSession(session.id)
          }
          onContextMenu={(e) => !isArchived && handleContextMenu(e, session.id)}
          className={`w-full flex items-start gap-2 px-3 py-2.5 rounded-lg text-left mb-0.5
            transition-all cursor-pointer ${
              isSelected
                ? 'bg-primary-500/15 text-starlight-100 border border-primary-500/30'
                : isActive
                  ? 'bg-primary-500/10 text-starlight-100 border border-primary-500/20'
                  : 'text-starlight-300 hover:bg-white/5 border border-transparent'
            } ${isArchived ? 'opacity-60' : ''}`}
        >
          {/* Checkbox in select mode */}
          {selectMode && !isArchived && (
            <span
              className="shrink-0 mt-0.5"
              onClick={(e) => {
                e.stopPropagation()
                toggleSelected(session.id)
              }}
            >
              {isSelected ? (
                <CheckSquare size={14} className="text-primary-400" />
              ) : (
                <Square size={14} className="text-starlight-500" />
              )}
            </span>
          )}

          {/* Icon */}
          {!selectMode && (
            <MessageSquare
              size={14}
              className={`shrink-0 mt-0.5 ${
                isArchived
                  ? 'text-starlight-600'
                  : isActive
                    ? 'text-primary-400'
                    : 'text-starlight-500'
              }`}
            />
          )}

          {/* Content */}
          <div className="flex-1 min-w-0">
            {isRenaming ? (
              <div className="flex items-center gap-1">
                <input
                  ref={renameInputRef}
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') confirmRename()
                    if (e.key === 'Escape') setRenamingId(null)
                  }}
                  onBlur={confirmRename}
                  className="flex-1 bg-transparent border-b border-primary-400 text-xs
                             text-starlight-100 outline-none py-0.5"
                  onClick={(e) => e.stopPropagation()}
                />
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    confirmRename()
                  }}
                  className="text-status-success cursor-pointer"
                  aria-label="Confirm rename"
                >
                  <Check size={12} />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setRenamingId(null)
                  }}
                  className="text-starlight-500 cursor-pointer"
                  aria-label="Cancel rename"
                >
                  <X size={12} />
                </button>
              </div>
            ) : (
              <>
                <p className="text-xs font-medium truncate">
                  {session.title || 'Untitled Chat'}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  {/* Department badge — only shown in main chat view, not when already filtered */}
                  {!departmentId && session.department_name && (
                    <span
                      className={`inline-flex items-center px-1.5 py-0 rounded text-[9px] font-medium ${
                        DEPT_BADGE_COLORS[session.department_name] || 'bg-white/10 text-starlight-400'
                      }`}
                    >
                      {session.department_name}
                    </span>
                  )}
                  <p className="text-[10px] text-starlight-500">
                    {session.message_count} msgs ·{' '}
                    {new Date(session.updated_at || session.created_at).toLocaleDateString()}
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Actions — three-dot menu or un-archive icon */}
          {isArchived ? (
            <span
              role="button"
              title="Restore from archive"
              aria-label="Restore from archive"
              onClick={(e) => {
                e.stopPropagation()
                unarchiveSession(session.id)
              }}
              className="shrink-0 mt-0.5 p-0.5 rounded opacity-0 group-hover:opacity-100
                         hover:bg-white/10 transition-all cursor-pointer"
            >
              <ArchiveRestore size={13} className="text-status-success" />
            </span>
          ) : (
            !isRenaming &&
            !selectMode && (
              <span
                role="button"
                aria-label="Session options"
                onClick={(e) => openMenuFromDots(e, session.id)}
                className="shrink-0 mt-0.5 p-0.5 rounded opacity-0 group-hover:opacity-100
                           hover:bg-white/10 transition-all cursor-pointer"
              >
                <MoreHorizontal size={14} className="text-starlight-500" />
              </span>
            )
          )}
        </button>
      </motion.div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* ── Header: New Chat + Select toggle ── */}
      <div className="p-3 space-y-2">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg
                     border border-white/10 text-sm text-starlight-200
                     hover:border-primary-500/30 hover:bg-primary-500/5 hover:text-primary-400
                     transition-all cursor-pointer"
        >
          <Plus size={16} />
          New Chat
        </button>

        {/* Select mode toggle — always visible when sessions exist */}
        {activeSessions.length > 0 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                if (selectMode) {
                  setSelectMode(false)
                  setSelectedIds(new Set())
                } else {
                  enterSelectMode()
                }
              }}
              className={`flex-1 flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11px]
                         transition-all cursor-pointer ${
                           selectMode
                             ? 'bg-primary-500/10 text-primary-400 border border-primary-500/20'
                             : 'text-starlight-500 hover:text-starlight-300 hover:bg-white/5 border border-transparent'
                         }`}
            >
              <CheckSquare size={12} />
              {selectMode ? `${selectedIds.size} selected` : 'Select'}
            </button>
            {selectMode && (
              <button
                onClick={selectAll}
                className="px-2 py-1.5 text-[11px] text-primary-400 hover:text-primary-300
                           hover:underline transition-colors cursor-pointer"
              >
                All
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Session list ── */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {sessionsLoading ? (
          <div className="space-y-1.5 animate-pulse px-1 py-2">
            {[0.75, 0.6, 0.85, 0.5, 0.7].map((w, i) => (
              <div key={i} className="flex items-start gap-2 px-3 py-2.5 rounded-lg">
                <div className="shrink-0 w-3.5 h-3.5 rounded bg-white/5 mt-0.5" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-3 rounded bg-white/5" style={{ width: `${w * 100}%` }} />
                  <div className="h-2.5 rounded bg-white/[0.03]" style={{ width: '50%' }} />
                </div>
              </div>
            ))}
          </div>
        ) : activeSessions.length === 0 && archivedSessions.length === 0 ? (
          <p className="text-xs text-starlight-500 text-center py-8 px-4">
            No conversations yet. Start a new chat!
          </p>
        ) : (
          <>
            {/* Active sessions */}
            <AnimatePresence mode="popLayout">
              {activeSessions.map((session) => renderSessionRow(session))}
            </AnimatePresence>

            {/* Archived section — collapsible */}
            {archivedSessions.length > 0 && (
              <div className="mt-3 pt-2 border-t border-white/5">
                <button
                  onClick={() => setShowArchived(!showArchived)}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-starlight-500
                             hover:text-starlight-300 transition-colors cursor-pointer"
                >
                  <Archive size={11} />
                  <span>Archived ({archivedSessions.length})</span>
                  <ChevronDown
                    size={11}
                    className={`ml-auto transition-transform ${showArchived ? 'rotate-180' : ''}`}
                  />
                </button>

                <AnimatePresence>
                  {showArchived && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      {archivedSessions.map((session) => renderSessionRow(session, true))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Batch action toolbar ── */}
      <AnimatePresence>
        {selectMode && selectedIds.size > 0 && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            className="shrink-0 border-t border-white/10 bg-midnight-400/90 backdrop-blur-sm p-2 space-y-1"
          >
            <div className="flex gap-1">
              <button
                onClick={batchArchive}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md
                           text-[11px] text-starlight-200 bg-white/5 hover:bg-white/10
                           transition-colors cursor-pointer"
              >
                <Archive size={12} /> Archive
              </button>
              <button
                onClick={() => setConfirmDelete([...selectedIds])}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md
                           text-[11px] text-status-error bg-status-error/5 hover:bg-status-error/10
                           transition-colors cursor-pointer"
              >
                <Trash2 size={12} /> Delete
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Confirm delete dialog ── */}
      <AnimatePresence>
        {confirmDelete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 flex items-center justify-center bg-midnight-900/80 backdrop-blur-sm"
          >
            <motion.div
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
              className="mx-4 p-4 rounded-xl border border-white/10 bg-midnight-400 shadow-2xl max-w-[220px]"
            >
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={16} className="text-status-error" />
                <h4 className="text-sm font-semibold text-starlight-100">Delete {confirmDelete.length} chat{confirmDelete.length > 1 ? 's' : ''}?</h4>
              </div>
              <p className="text-[11px] text-starlight-400 mb-4 leading-relaxed">
                {confirmDelete.length === 1
                  ? 'Delete this conversation? It will be moved to the archive.'
                  : `Delete ${confirmDelete.length} conversations? They will be moved to the archive.`}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setConfirmDelete(null)}
                  className="flex-1 py-1.5 rounded-md text-[11px] text-starlight-300 bg-white/5
                             hover:bg-white/10 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={() => batchDelete(confirmDelete)}
                  className="flex-1 py-1.5 rounded-md text-[11px] text-white bg-status-error/80
                             hover:bg-status-error transition-colors cursor-pointer"
                >
                  Delete
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Context menu portal ── */}
      {menu && (
        <div
          ref={menuRef}
          className="fixed z-50 min-w-[150px] rounded-lg border border-white/10
                     bg-midnight-400/95 backdrop-blur-md shadow-xl py-1"
          style={{ top: menu.y, left: menu.x }}
        >
          <button
            onClick={() => startRename(menu.sessionId)}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-starlight-200
                       hover:bg-white/5 transition-colors cursor-pointer"
          >
            <Pencil size={12} /> Rename
          </button>
          <button
            onClick={() => exportSession(menu.sessionId)}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-starlight-200
                       hover:bg-white/5 transition-colors cursor-pointer"
          >
            <Download size={12} /> Export JSON
          </button>
          <button
            onClick={() => enterSelectMode(menu.sessionId)}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-starlight-200
                       hover:bg-white/5 transition-colors cursor-pointer"
          >
            <CheckSquare size={12} /> Select
          </button>
          <div className="border-t border-white/5 my-1" />
          <button
            onClick={() => {
              const id = menu.sessionId
              setMenu(null)
              setConfirmDelete([id])
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-status-error/80
                       hover:bg-status-error/10 transition-colors cursor-pointer"
          >
            <Archive size={12} /> Delete
          </button>
        </div>
      )}
    </div>
  )
}

export default SessionList
