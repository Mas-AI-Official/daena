import { useLocation, Link, useNavigate } from 'react-router-dom'
import { useEffect, useState, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
// Sidebar cleaned: Perplexity menu items removed 2026-04-13
import {
  MessageSquare,
  Shield,
  ShieldCheck,
  Brain,
  Network,
  Zap,
  Plug,
  Crosshair,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ListTodo,
  FileText,
  Bell,
  Users,
  Building,
  User,
  Settings,
  LogOut,
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
  /** Extra path prefixes that ALSO mark this item active (FM-1/FM-3,
   *  2026-07-02). A merged surface entry (Work, Governance) points `path`
   *  at its default tab but must stay highlighted on every folded route.
   *  Omitted -> highlights on `path` alone (unchanged behavior). */
  matchPaths?: string[]
  /** Hover tooltip explaining what the page does in one sentence.
   *  Added 2026-04-23 so first-time users don't have to click every
   *  link to learn what it is. Kept short (≤120 chars). */
  title?: string
}

interface NavGroup {
  title: string
  color: string
  items: NavItem[]
  /** PR-CONNECTIONS-MINI-SIMPLIFY (2026-05-06): collapsible groups
   *  render their title as a button with a chevron. Default closed.
   *  Open/closed state persists in localStorage. Pending badges still
   *  surface on the collapsed group header so the operator never
   *  misses a real signal. */
  collapsible?: boolean
  /** Stable key for localStorage when collapsible. */
  key?: string
}

const navGroups: NavGroup[] = [
  {
    title: 'Core',
    color: 'text-primary-400',
    items: [
      { label: 'Chat', path: '/chat', icon: <MessageSquare size={18} /> },
      // Brain = the unified cockpit. Dashboard was folded into it 2026-06-25
      // (founder go-ahead): the old /dashboard redirects to /brain and its
      // Control Room panels now live inside the Brain as an "Overview" overlay.
      // Promoted from Intelligence to Core as the single system-overview surface.
      // Renders an honest error state when GET /graph is offline.
      { label: 'Brain', path: '/brain', icon: <Network size={18} />, title: 'The Daena cockpit: a live neural map of departments, agents, the MCP servers each uses, and the backend -- plus an Overview panel with KPIs, system status, governance pulse, and quick actions.' },
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
      // Departments IS the Minds surface now (FM-4, 2026-07-01): each card
      // carries the department's soul persona + a drill-in to the per-Mind
      // detail view, plus the founder-gated "Refine all Minds" control. The
      // standalone /minds gallery was consolidated here; /minds redirects.
      { label: 'Departments', path: '/departments', icon: <Brain size={18} /> },
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
      // Work = one surface, four tabs (FM-3, 2026-07-02). Tasks /
      // Workstreams / Projects / Pipeline were four sibling entries; they
      // are all lenses on the same unit of work, so they fold into ONE
      // tabbed WorkPage. The entry lands on Tasks (the default tab) and
      // stays highlighted across every folded route via matchPaths, so a
      // deep-link to /workstreams or /projects/:id still lights "Work".
      // The approvals-style pending count now rides the Tasks tab, so the
      // badge (tasks) moves to this merged entry. Files stays its own
      // surface (it is a store, not a work lens).
      {
        label: 'Work',
        path: '/tasks',
        icon: <ListTodo size={18} />,
        badgeKey: 'tasks',
        matchPaths: ['/tasks', '/workstreams', '/projects', '/pipeline'],
        title: 'Tasks, live Workstreams, Projects, and the GTM Pipeline in one tabbed surface. Watch, redirect, or queue autonomous work.',
      },
      { label: 'Files', path: '/files', icon: <FileText size={18} />, title: 'Files Daena has read or produced -- uploads, generated artifacts, exported reports.' },
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
    // Group title is "Oversight" (was "Governance") because the merged
    // ITEM below is now named "Governance" -- keeping both the same would
    // read as a duplicate. The collapsible state keys off `key: 'gov'`
    // (localStorage), not the title, so the rename is display-only and
    // does not reset anyone's open/closed preference.
    title: 'Oversight',
    color: 'text-accent-amber',
    collapsible: true,
    key: 'gov',
    items: [
      { label: 'Security Ops', path: '/security', icon: <Shield size={18} /> },
      // Authorized-scope editor: declares which domains/CIDRs YELLOW-
      // tier security tools may run against for this tenant. Founder-
      // only page -- non-founders see an empty-state lock.
      { label: 'Scan Scope', path: '/security/scope', icon: <ShieldCheck size={18} /> },
      // "Engagements" used to live here at /engagements. It was a
      // duplicate of /scan (same T1-T5 launcher). Removed from the
      // visible nav 2026-04-21 per founder feedback. The route still
      // exists in App.tsx so bookmarks and deep-links resolve, but
      // there is now ONE canonical scan entry point: Security Scan
      // under Intelligence above.
      //
      // Governance = one surface, four tabs (FM-1, 2026-07-02). Approvals /
      // Policy Rules / Audit Log / Trust Ladder were four sibling entries;
      // they are the four lenses of the same governance-oversight loop, so
      // they fold into ONE tabbed GovernancePage. The entry lands on
      // Approvals (which carries the pending-approvals SSE badge) and stays
      // highlighted across every folded route via matchPaths, so a deep-link
      // to /policies?tab=... or /governance/audit still lights "Governance".
      // Security Ops + Scan Scope stay separate (v3.7.0 security stack,
      // HANDS-OFF); Opportunities stays its own inbox surface.
      {
        label: 'Governance',
        path: '/governance/approvals',
        icon: <Shield size={18} />,
        badgeKey: 'approvals',
        matchPaths: ['/governance/approvals', '/policies', '/governance/audit', '/governance/trust'],
        title: 'Approvals, Policy Rules, the Audit Log, and the Trust Ladder in one tabbed surface. The pending-approvals count rides this entry.',
      },
      { label: 'Opportunities', path: '/opportunities', icon: <Shield size={18} /> },
      // Analytics folded into the Brain (FM-5, 2026-07-02): usage/cost/
      // governance metrics now open as an "Analytics" overlay from the Brain
      // toolbar (Core > Brain), so the standalone nav entry was removed.
      // /analytics redirects to /brain for old bookmarks.
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

  // PR-CONNECTIONS-MINI-SIMPLIFY (2026-05-06): collapsible group state.
  // Keyed by NavGroup.key (only populated for collapsible groups).
  // Default closed. Hydrated from localStorage on mount so the
  // operator's preference survives reloads.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    for (const g of navGroups) {
      if (g.collapsible && g.key) {
        try {
          initial[g.key] = localStorage.getItem(`daena.sidebar.${g.key}.open`) === 'true'
        } catch {
          initial[g.key] = false
        }
      }
    }
    return initial
  })
  const toggleGroup = useCallback((key: string) => {
    setOpenGroups((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      try {
        localStorage.setItem(`daena.sidebar.${key}.open`, next[key] ? 'true' : 'false')
      } catch {
        // localStorage may be blocked (private mode, test runner) -- the
        // in-memory state still persists for this session.
      }
      return next
    })
  }, [])

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
        {navGroups.map((group) => {
          // PR-CONNECTIONS-MINI-SIMPLIFY (2026-05-06): collapsible group
          // logic. The expanded sidebar shows the title as a clickable
          // header with a chevron + a summary badge if any item carries
          // a pending count. The collapsed sidebar (icon-only) keeps the
          // group dot visible -- the parent never hides routes outright,
          // only the group label.
          const groupOpen = group.collapsible && group.key
            ? openGroups[group.key] === true
            : true
          const itemsVisible = !group.collapsible || groupOpen
          const groupBadgeCount = group.items.reduce((sum, i) => {
            if (!i.badgeKey) return sum
            return sum + (badgeCounts[i.badgeKey] ?? 0)
          }, 0)
        return (
          <div key={group.title}>
            <AnimatePresence>
              {effectiveOpen && (
                group.collapsible && group.key ? (
                  <motion.button
                    type="button"
                    onClick={() => toggleGroup(group.key!)}
                    aria-expanded={groupOpen}
                    data-testid={`sidebar-group-toggle-${group.key}`}
                    className={`flex w-full items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest px-3 mb-1.5 ${group.color} hover:text-starlight-100`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    {groupOpen
                      ? <ChevronDown size={10} className="shrink-0 opacity-70" />
                      : <ChevronRight size={10} className="shrink-0 opacity-70" />}
                    <span>{group.title}</span>
                    {!groupOpen && groupBadgeCount > 0 && (
                      <span
                        data-testid={`sidebar-group-badge-${group.key}`}
                        className="ml-auto px-1.5 py-0.5 rounded-full text-[10px] font-medium min-w-[20px] text-center bg-status-warning/20 text-status-warning normal-case tracking-normal"
                      >
                        {groupBadgeCount}
                      </span>
                    )}
                  </motion.button>
                ) : (
                  <motion.p
                    className={`text-[10px] font-mono uppercase tracking-widest px-3 mb-1.5 ${group.color}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    {group.title}
                  </motion.p>
                )
              )}
            </AnimatePresence>

            <div className={`space-y-0.5 ${itemsVisible ? '' : 'hidden'}`}>
              {group.items.map((item) => {
                // A merged surface (Work, Governance) highlights on any of
                // its folded routes; a plain item still highlights on its
                // own path prefix (unchanged when matchPaths is absent).
                const isActive = (item.matchPaths ?? [item.path]).some((p) =>
                  location.pathname.startsWith(p),
                )
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
                    title={item.title}
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
        )
        })}
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
              onClick={() => menuNavigate('/account/org')}
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
