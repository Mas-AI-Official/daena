/**
 * SettingsPage -- 13 clean tabs, professional ordering.
 * Each tab is lazy-loaded so only the active one is downloaded.
 *
 * Tab order (locked):
 *   General > LLM Providers > Governance > Models & Runtimes > Memory >
 *   Billing & Usage > Privacy & Data > Notifications > Voice >
 *   Developer > Daena Heartbeat > Shortcuts > About
 */
import { lazy, Suspense } from 'react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Settings,
  Cpu,
  Shield,
  Database,
  // Plug removed -- Connections moved to dedicated nav page
  Heart,
  DollarSign,
  Lock,
  Keyboard,
  Bell,
  Code,
  Info,
  Mic,
} from 'lucide-react'
import type { ComponentType } from 'react'

// Lazy-load each settings tab
const SettingsGeneral = lazy(() => import('./settings/SettingsGeneral').then(m => ({ default: m.SettingsGeneral })))
// Appearance merged into General
const SettingsLLM = lazy(() => import('./settings/SettingsLLM').then(m => ({ default: m.SettingsLLM })))
const SettingsModelsRuntimes = lazy(() => import('./settings/SettingsModelsRuntimes').then(m => ({ default: m.SettingsModelsRuntimes })))
const SettingsGovernance = lazy(() => import('./settings/SettingsGovernance').then(m => ({ default: m.SettingsGovernance })))
const SettingsMemory = lazy(() => import('./settings/SettingsMemory').then(m => ({ default: m.SettingsMemory })))
const SettingsVoice = lazy(() => import('./settings/SettingsVoice').then(m => ({ default: m.SettingsVoice })))
// Connections removed from settings -- lives at /connections nav page
const SettingsBilling = lazy(() => import('./settings/SettingsBilling').then(m => ({ default: m.SettingsBilling })))
const SettingsPrivacy = lazy(() => import('./settings/SettingsPrivacy').then(m => ({ default: m.SettingsPrivacy })))
const SettingsNotifications = lazy(() => import('./settings/SettingsNotifications').then(m => ({ default: m.SettingsNotifications })))
const SettingsShortcuts = lazy(() => import('./settings/SettingsShortcuts').then(m => ({ default: m.SettingsShortcuts })))
const SettingsHeartbeat = lazy(() => import('./settings/SettingsHeartbeat').then(m => ({ default: m.SettingsHeartbeat })))
// DaenaBot always ON -- removed from settings
const SettingsDeveloper = lazy(() => import('./settings/SettingsDeveloper').then(m => ({ default: m.SettingsDeveloper })))
const SettingsAbout = lazy(() => import('./settings/SettingsAbout').then(m => ({ default: m.SettingsAbout })))

const CATEGORIES: readonly { key: string; label: string; icon: ComponentType<{ size?: number }>; component: ComponentType }[] = [
  { key: 'general', label: 'General', icon: Settings, component: SettingsGeneral },
  { key: 'llm', label: 'LLM Providers', icon: Cpu, component: SettingsLLM },
  { key: 'governance', label: 'Governance', icon: Shield, component: SettingsGovernance },
  { key: 'models', label: 'Models & Runtimes', icon: Cpu, component: SettingsModelsRuntimes },
  { key: 'memory', label: 'Memory', icon: Database, component: SettingsMemory },
  { key: 'billing', label: 'Billing & Usage', icon: DollarSign, component: SettingsBilling },
  { key: 'privacy', label: 'Privacy & Data', icon: Lock, component: SettingsPrivacy },
  { key: 'notifications', label: 'Notifications', icon: Bell, component: SettingsNotifications },
  { key: 'voice', label: 'Voice', icon: Mic, component: SettingsVoice },
  { key: 'developer', label: 'Developer', icon: Code, component: SettingsDeveloper },
  { key: 'heartbeat', label: 'Daena Heartbeat', icon: Heart, component: SettingsHeartbeat },
  { key: 'shortcuts', label: 'Shortcuts', icon: Keyboard, component: SettingsShortcuts },
  { key: 'about', label: 'About', icon: Info, component: SettingsAbout },
]

/** Skeleton for lazy-loading settings tabs */
function SettingsLoader() {
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

export function SettingsPage() {
  usePageTitle('Settings')
  const { category } = useParams<{ category?: string }>()
  const navigate = useNavigate()
  const active = category || 'general'
  const current = CATEGORIES.find((c) => c.key === active) || CATEGORIES[0]
  const ActiveComponent = current.component

  return (
    <div className="h-full flex overflow-hidden">
      {/* Sidebar nav */}
      <nav className="w-48 flex-shrink-0 border-r border-white/5 overflow-y-auto py-4 px-2">
        <motion.h2
          className="px-3 mb-3 text-xs font-semibold text-starlight-500 uppercase tracking-wider"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          Settings
        </motion.h2>
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon
          const isActive = cat.key === active
          return (
            <button
              key={cat.key}
              onClick={() => navigate(cat.key === 'general' ? '/settings' : `/settings/${cat.key}`)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-sm transition-all mb-0.5 cursor-pointer ${
                isActive
                  ? 'bg-primary-500/10 text-primary-400'
                  : 'text-starlight-400 hover:text-starlight-200 hover:bg-white/[0.03]'
              }`}
            >
              <Icon size={14} />
              {cat.label}
            </button>
          )
        })}
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
          <Suspense fallback={<SettingsLoader />}>
            <ActiveComponent />
          </Suspense>
        </motion.div>
      </div>
    </div>
  )
}

export default SettingsPage
