import { useLocation, Link } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MessageSquare,
  LayoutDashboard,
  Shield,
  Brain,
  Zap,
  Plug,
  Settings,
  ChevronLeft,
  ChevronRight,
  Crown,
  ListTodo,
  Wrench,
  FolderKanban,
  Kanban,
} from 'lucide-react'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { api } from '@/lib/api'

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  badge?: string
  /** Key for dynamic badge count (e.g. 'approvals') */
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
    ],
  },
  {
    title: 'Governance',
    color: 'text-accent-amber',
    items: [
      { label: 'Approvals', path: '/governance/approvals', icon: <Shield size={18} />, badgeKey: 'approvals' },
      { label: 'Audit Log', path: '/governance/audit', icon: <Shield size={18} /> },
    ],
  },
  {
    title: 'Intelligence',
    color: 'text-accent-cyan',
    items: [
      { label: 'Departments', path: '/departments', icon: <Brain size={18} /> },
      { label: 'Skills', path: '/skills', icon: <Zap size={18} /> },
    ],
  },
  {
    title: 'Execution',
    color: 'text-status-success',
    items: [
      { label: 'Tasks', path: '/tasks', icon: <ListTodo size={18} /> },
      { label: 'Projects', path: '/projects', icon: <FolderKanban size={18} /> },
      { label: 'Pipeline', path: '/pipeline', icon: <Kanban size={18} /> },
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
    title: 'System',
    color: 'text-starlight-400',
    items: [
      { label: 'Settings', path: '/settings', icon: <Settings size={18} /> },
    ],
  },
]

interface SidebarProps {
  mobile?: boolean
}

export function Sidebar({ mobile }: SidebarProps = {}) {
  const { sidebarOpen, toggleSidebar } = useUiStore()
  const { user } = useAuthStore()
  const location = useLocation()
  const isFounder = user?.role === 'FOUNDER'
  const [pendingApprovals, setPendingApprovals] = useState(0)

  // Fetch pending approval count for badge
  const fetchPendingCount = useCallback(async () => {
    try {
      const { data } = await api.get('/governance/approvals?status=PENDING&page_size=1')
      setPendingApprovals(data?.pagination?.total ?? 0)
    } catch {
      // Graceful: no badge if endpoint fails
    }
  }, [])

  useEffect(() => {
    fetchPendingCount()
    // Refresh every 30 seconds
    const interval = setInterval(fetchPendingCount, 30_000)
    return () => clearInterval(interval)
  }, [fetchPendingCount])

  // Mobile sidebar is always expanded, desktop sidebar animates
  const effectiveOpen = mobile ? true : sidebarOpen

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
                      {/* Pending badge dot (collapsed sidebar) */}
                      {!effectiveOpen && item.badgeKey === 'approvals' && pendingApprovals > 0 && (
                        <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-status-warning animate-pulse" />
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
                    {/* Badge count (expanded sidebar) */}
                    {effectiveOpen && item.badgeKey === 'approvals' && pendingApprovals > 0 && (
                      <span className="ml-auto px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-status-warning/20 text-status-warning min-w-[20px] text-center">
                        {pendingApprovals}
                      </span>
                    )}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}

        {/* Founder panel removed -- merged into Settings */}
      </nav>

      {/* Collapse toggle (hidden on mobile overlay) */}
      {!mobile && (
        <div className="border-t border-white/5 p-2 shrink-0">
          <button
            onClick={toggleSidebar}
            aria-label={effectiveOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            className="w-full flex items-center justify-center p-2 rounded-lg text-starlight-400 hover:text-starlight-100 hover:bg-white/5 transition-colors cursor-pointer"
          >
            {effectiveOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
          </button>
        </div>
      )}
    </motion.aside>
  )
}

export default Sidebar
