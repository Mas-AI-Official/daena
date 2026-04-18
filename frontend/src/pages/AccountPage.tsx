/**
 * AccountPage -- User profile management (Profile + API Keys).
 * All other settings live at /settings.
 */
import { lazy, Suspense } from 'react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { User, Code } from 'lucide-react'
import type { ComponentType } from 'react'

const AccountDetails = lazy(() => import('./account/AccountDetails').then(m => ({ default: m.AccountDetails })))
const AccountApiKeys = lazy(() => import('./account/AccountApiKeys').then(m => ({ default: m.AccountApiKeys })))

interface TabDef {
  key: string
  label: string
  icon: ComponentType<{ size?: number }>
  component: ComponentType
}

const TABS: TabDef[] = [
  { key: 'details', label: 'Profile', icon: User, component: AccountDetails },
  { key: 'api-keys', label: 'API Keys', icon: Code, component: AccountApiKeys },
]

function AccountLoader() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-6 w-40 rounded bg-white/5" />
      <div className="h-4 w-64 rounded bg-white/[0.03]" />
      <div className="space-y-3 mt-6">
        {[0.8, 0.6, 0.7].map((w, i) => (
          <div key={i} className="h-12 rounded-lg bg-white/[0.02]" style={{ width: `${w * 100}%` }} />
        ))}
      </div>
    </div>
  )
}

export function AccountPage() {
  usePageTitle('Account')
  const { category } = useParams<{ category?: string }>()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const active = category || 'details'
  const current = TABS.find((t) => t.key === active) || TABS[0]
  const ActiveComponent = current.component

  return (
    <div className="h-full flex overflow-hidden">
      {/* Left sidebar nav */}
      <nav className="w-48 flex-shrink-0 border-r border-white/5 overflow-y-auto py-4 px-2">
        <button
          onClick={() => navigate('/chat')}
          className="flex items-center gap-1.5 px-3 mb-4 text-xs text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
        >
          &lt; Home
        </button>

        <motion.h2
          className="px-3 mb-3 text-xs font-semibold text-starlight-500 uppercase tracking-wider"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          Account
        </motion.h2>

        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = tab.key === active
          return (
            <button
              key={tab.key}
              onClick={() => navigate(tab.key === 'details' ? '/account' : `/account/${tab.key}`)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-sm transition-all mb-0.5 cursor-pointer ${
                isActive
                  ? 'bg-primary-500/10 text-primary-400'
                  : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/[0.03]'
              }`}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          )
        })}

        {/* Link to full settings */}
        <div className="mt-4 pt-4 border-t border-white/5">
          <button
            onClick={() => navigate('/settings')}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs text-starlight-500 hover:text-starlight-300 hover:bg-white/[0.03] transition-all cursor-pointer"
          >
            All Settings
          </button>
        </div>
      </nav>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <motion.div
          key={active}
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.15 }}
          className="max-w-3xl"
        >
          <Suspense fallback={<AccountLoader />}>
            <ActiveComponent />
          </Suspense>
        </motion.div>
      </div>
    </div>
  )
}

export default AccountPage
