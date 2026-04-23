import { useLocation, Link, useNavigate } from 'react-router-dom'
import { useEffect, useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
// Sidebar cleaned: Perplexity menu items removed 2026-04-13
import {
  MessageSquare,
  LayoutDashboard,
  Shield,
  ShieldCheck,
  Brain,
  Zap,
  Plug,
  Crosshair,
  ChevronLeft,
  ChevronRight,
  ListTodo,
  FolderKanban,
  Kanban,
  FileText,
  BarChart3,
  Bell,
  Users,
  Building,
  User,
  Settings,
  LogOut,
  Sparkles,
  Rocket,
} from 'lucide-react'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  badge?: string
  badgeKey?: string
}

interface NavGroup {
  title: string
  color: string
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    title: 'Core',
    color: 'text-primary-400',
    items: [
      { label: 'Chat', path: '/chat', icon: <MessageSquare size={18} /> },
      { label: 'Dashboard', path: '/dashboard', icon: <LayoutDashboard size={18} /> },
      // Company + Inbox removed 2026-04-17 -- /departments is the single
      // source of truth for the 10-department model. Inter-department
      // messaging happens through each department's chat room.
    ],
  },
  {
    title: 'Intelligence',
    color: 'text-accent-cyan',
    items: [
      { label: 'Security Scan', path: '/scan', icon: <Crosshair size={18} /> },
      { label: 'Departments', path: '/departments', icon: <Brain size={18} /> },
      // Minds = per-department soul personas. Cards open the live soul
      // body + founder-gated refinement loop. Lives next to Departments
      // because they're two lenses on the same 10-unit model.
      { label: 'Minds', path: '/minds', icon: <Sparkles size={18} /> },
      { label: 'Skills', path: '/skills', icon: <Zap size={18} /> },
    ],
  },
  {
    title: 'Go-to-market',
    color: 'text-status-success',
    items: [
      // Company Mode = one-click activation of Daena as an AI
      // marketing+sales agency. Founder-gated on the backend; the page
      // self-blocks non-FOUNDER roles with an empty state instead of
      // hiding the link so operators know the capability exists.
      { label: 'Company Mode', path: '/company-mode', icon: <Rocket size={18} /> },
    ],
  },
  {
    title: 'Execution',
    color: 'text-status-success',
    items: [
      { label: 'Tasks', path: '/tasks', icon: <ListTodo size={18} />, badgeKey: 'tasks' },
      { label: 'Projects', path: '/projects', icon: <FolderKanban size={18} /> },
      { label: 'Pipeline', path: '/pipeline', icon: <Kanban size={18} /> },
      { label: 'Files', path: '/files', icon: <FileText size={18} /> },
    ],
  },
  {
    title: 'Connections',
    color: 'text-accent-purple',
    items: [
      { label: 'Connections', path: '/connections', icon: <Plug size={18} /> },
    ],
  },
  {
    title: 'Governance',
    color: 'text-accent-amber',
    items: [
      { label: 'Security Ops', path: '/security', icon: <Shield size={18} /> },
      // Authorized-scope editor: declares which domains/CIDRs YELLOW-
      // tier security tools may run against for this tenant. Founder-
      // only page -- non-founders see an empty-state lock.
      { label: 'Authorized Scope', path: '/security/scope', icon: <ShieldCheck size={18} /> },
      // "Engagements" used to live here at /engagements. It was a
      // duplicate of /scan (same T1-T5 launcher). Removed from the
      // visible nav 2026-04-21 per founder feedback. The route still
      // exists in App.tsx so bookmarks and deep-links resolve, but
      // there is now ONE canonical scan entry point: Security Scan
      // under Intelligence above.
      { label: 'Approvals', path: '/governance/approvals', icon: <Shield size={18} />, badgeKey: 'approvals' },
      { label: 'Policy Rules', path: '/policies', icon: <Shield size={18} /> },
      { label: 'Audit Log', path: '/governance/audit', icon: <Shield size={18} /> },
      { label: 'Analytics', path: '/analytics', icon: <BarChart3 size={18} /> },
    ],
  },
]

interface SidebarProps {
  mobile?: boolean
}

export function Sidebar({ mobile }: SidebarProps = {}) {
  const { sidebarOpen, toggleSidebar } = useUiStore()
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()
  const isAdmin = user?.role === 'FOUNDER' || user?.role === 'ADMIN'
  const [pendingApprovals, setPendingApprovals] = useState(0)
  const [activeTasks, setActiveTasks] = useState(0)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const pollDelayRef = useRef(30_000)
  const fetchNotificationCounts = useCallback(async () => {
    // Parallel-fetch approvals (PENDING) and tasks (RUNNING + PENDING).
    // Keeps the sidebar badge source-of-truth in sync so Masoud sees
    // the full pipeline state without opening individual pages.
    try {
      const [approvalsRes, runningRes, pendingRes] = await Promise.all([
        api.get('/governance/approvals?status=PENDING&page_size=1'),
        api.get('/execution/tasks?status=RUNNING&page_size=1'),
        api.get('/execution/tasks?status=PENDING&page_size=1'),
      ])
      setPendingApprovals(approvalsRes.data?.pagination?.total ?? 0)
      const running = runningRes.data?.pagination?.total ?? 0
      const pending = pendingRes.data?.pagination?.total ?? 0
      setActiveTasks(running + pending)
      pollDelayRef.current = 30_000 // Reset on success
    } catch {
      pollDelayRef.current = Math.min(pollDelayRef.current * 2, 120_000) // Backoff to 2min max
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      await fetchNotificationCounts()
      if (!cancelled) timer = setTimeout(poll, pollDelayRef.current)
    }
    void poll()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [fetchNotificationCounts])

  // Map badgeKey → count for the nav render loop below.
  const badgeCounts: Record<string, number> = {
    approvals: pendingApprovals,
    tasks: activeTasks,
  }

  // Close user menu on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    if (userMenuOpen) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [userMenuOpen])

  // Close menu on route change
  useEffect(() => {
    setUserMenuOpen(false)
  }, [location.pathname])

  const effectiveOpen = mobile ? true : sidebarOpen

  const menuNavigate = (path: string) => {
    setUserMenuOpen(false)
    navigate(path)
  }

  return (
    <motion.aside
      role="complementary"
      aria-label="Sidebar navigation"
      className={`h-full bg-midnight-200/80 border-r border-white/5 flex flex-col overflow-hidden ${mobile ? '' : 'hidden sm:flex'}`}
      animate={{ width: mobile ? 256 : effectiveOpen ? 256 : 72 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
    >
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2">
          <motion.img
            src="/daena-blue.png"
            alt="Daena"
            className="w-9 h-9 rounded-lg object-contain select-none"
            style={{ filter: 'drop-shadow(0 0 6px rgba(0,212,255,0.3))' }}
            animate={{ scale: [1, 1.04, 1] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            draggable={false}
          />
          <AnimatePresence>
            {effectiveOpen && (
              <motion.span
                className="font-display font-semibold text-lg text-starlight-100 whitespace-nowrap"
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.2 }}
              >
                Daena
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Nav groups */}
      <nav className="flex-1 overflow-y-auto scrollbar-hide py-3 px-2 space-y-4">
        {navGroups.map((group) => (
          <div key={group.title}>
            <AnimatePresence>
              {effectiveOpen && (
                <motion.p
                  className={`text-[10px] font-mono uppercase tracking-widest px-3 mb-1.5 ${group.color}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  {group.title}
                </motion.p>
              )}
            </AnimatePresence>

            <div className="space-y-0.5">
              {group.items.map((item) => {
                const isActive = location.pathname.startsWith(item.path)
                const badgeCount = item.badgeKey ? badgeCounts[item.badgeKey] ?? 0 : 0
                const showBadge = badgeCount > 0
                // Task badge uses info (teal), approval badge uses warning (amber).
                const badgeTone = item.badgeKey === 'tasks' ? 'info' : 'warning'
                const dotClass = badgeTone === 'info' ? 'bg-status-info' : 'bg-status-warning'
                const pillClass = badgeTone === 'info'
                  ? 'bg-status-info/20 text-status-info'
                  : 'bg-status-warning/20 text-status-warning'
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`
                      flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200 active:scale-[0.97]
                      ${
                        isActive
                          ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30 shadow-[var(--shadow-glow-sm)]'
                          : 'text-starlight-300 hover:text-starlight-100 hover:bg-white/5 border border-transparent'
                      }
                    `}
                  >
                    <span className="shrink-0 relative">
                      {item.icon}
                      {!effectiveOpen && showBadge && (
                        <span className={`absolute -top-1 -right-1 w-2 h-2 rounded-full ${dotClass} animate-pulse`} />
                      )}
                    </span>
                    <AnimatePresence>
                      {effectiveOpen && (
                        <motion.span
                          className="whitespace-nowrap overflow-hidden flex-1"
                          initial={{ opacity: 0, width: 0 }}
                          animate={{ opacity: 1, width: 'auto' }}
                          exit={{ opacity: 0, width: 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          {item.label}
                        </motion.span>
                      )}
                    </AnimatePresence>
                    {effectiveOpen && showBadge && (
                      <span className={`ml-auto px-1.5 py-0.5 rounded-full text-[10px] font-medium min-w-[20px] text-center ${pillClass}`}>
                        {badgeCount}
                      </span>
                    )}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom: User avatar + Org row (Perplexity-style) */}
      <div className="border-t border-white/5 shrink-0" ref={menuRef}>
        {/* User Menu Dropdown (pops UP from bottom) */}
        <AnimatePresence>
          {userMenuOpen && effectiveOpen && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.97 }}
              transition={{ duration: 0.12 }}
              className="mx-2 mb-1 bg-midnight-400/95 backdrop-blur-md border border-white/10 rounded-xl shadow-xl overflow-hidden"
            >
              {/* User info header */}
              <div className="px-4 py-3 border-b border-white/5">
                <p className="text-xs font-medium text-starlight-100">{user?.display_name || 'User'}</p>
                <p className="text-[10px] text-starlight-500">{user?.email || ''}</p>
              </div>

              {/* Menu items */}
              <div className="py-1">
                <MenuButton icon={<User size={14} />} label="Profile" onClick={() => menuNavigate('/account')} />
                <MenuButton icon={<Settings size={14} />} label="Settings" onClick={() => menuNavigate('/settings')} />
                <MenuButton icon={<Plug size={14} />} label="Connections" onClick={() => menuNavigate('/connections')} />
              </div>

              <div className="border-t border-white/5 py-1">
                <button
                  onClick={() => { setUserMenuOpen(false); logout() }}
                  className="w-full flex items-center gap-3 px-4 py-2 text-xs text-status-error/80 hover:text-status-error hover:bg-status-error/5 transition-colors cursor-pointer"
                >
                  <LogOut size={14} />
                  <span>Sign out</span>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Avatar row (always visible) */}
        <div className="p-2 space-y-1">
          <button
            onClick={() => effectiveOpen ? setUserMenuOpen(!userMenuOpen) : navigate('/account/details')}
            className="w-full flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
          >
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-accent-purple flex items-center justify-center text-xs font-bold text-white shrink-0">
              {user?.display_name?.charAt(0)?.toUpperCase() || 'D'}
            </div>
            <AnimatePresence>
              {effectiveOpen && (
                <motion.div
                  className="flex-1 min-w-0 text-left"
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: 'auto' }}
                  exit={{ opacity: 0, width: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <p className="text-xs font-medium text-starlight-100 truncate">{user?.display_name || 'User'}</p>
                </motion.div>
              )}
            </AnimatePresence>
            {effectiveOpen && (
              <Bell size={14} className="text-starlight-400 shrink-0" />
            )}
          </button>

          {/* Org row */}
          {effectiveOpen && (
            <button
              onClick={() => menuNavigate('/account/org/details')}
              className="w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
            >
              <Building size={16} className="text-starlight-400 shrink-0" />
              <span className="text-[11px] text-starlight-400 truncate flex-1 text-left">
                {user?.tenant_name || 'Mas-AI Tech...'}
              </span>
              <Users size={12} className="text-starlight-500 shrink-0" />
            </button>
          )}

          {/* Collapse toggle */}
          {!mobile && (
            <button
              onClick={toggleSidebar}
              aria-label={effectiveOpen ? 'Collapse sidebar' : 'Expand sidebar'}
              className="w-full flex items-center justify-center p-1.5 rounded-lg text-starlight-400 hover:text-starlight-100 hover:bg-white/5 transition-colors cursor-pointer"
            >
              {effectiveOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
            </button>
          )}
        </div>
      </div>
    </motion.aside>
  )
}

/** Reusable menu button for avatar dropdown */
function MenuButton({ icon, label, onClick, suffix }: { icon: React.ReactNode; label: string; onClick: () => void; suffix?: string }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-4 py-2 text-xs text-starlight-300 hover:text-starlight-100 hover:bg-white/[0.03] transition-colors cursor-pointer"
    >
      {icon}
      <span className="flex-1 text-left">{label}</span>
      {suffix && <span className="text-[10px] text-starlight-500">{suffix}</span>}
    </button>
  )
}

export default Sidebar
