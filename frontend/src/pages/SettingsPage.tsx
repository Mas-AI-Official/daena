/**
 * SettingsPage -- 12 lazy-loaded tabs grouped into Normal vs Advanced.
 *
 * PR-SETTINGS-CLEANUP (2026-05-02) introduced the Normal/Advanced split
 * so the default surface is the seven tabs an operator can trust without
 * understanding the full system (General, Memory, Privacy & Data,
 * Notifications, Voice, Billing & Usage, About). The five advanced tabs
 * (Governance, Models & Runtimes, Daena Heartbeat, Developer, Shortcuts)
 * are surfaced behind a "Show advanced" toggle.
 *
 * CONSOLIDATION (2026-06-18): the former standalone "LLM Providers" tab
 * was folded into "Models & Runtimes" (SettingsModelsRuntimes composes
 * SettingsLLM directly), removing one overlapping advanced tab. Its
 * routing controls are unchanged and still backend-enforced.
 *
 * The toggle persists to localStorage (key
 * "daena.settings.show_advanced") so the founder's preference sticks
 * across reloads. Direct deep-link navigation to an advanced tab
 * (e.g. /settings/heartbeat) auto-flips the toggle on so the sidebar
 * stays in sync; the user is never trapped on a hidden route.
 */
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
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
// SettingsLLM is no longer a standalone tab (2026-06-18) -- it is composed
// inside SettingsModelsRuntimes, which is its sole importer now.
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

type CategoryEntry = {
  key: string
  label: string
  icon: ComponentType<{ size?: number }>
  component: ComponentType
  advanced: boolean
}

const CATEGORIES: readonly CategoryEntry[] = [
  // Normal (operator-facing; trustworthy without explanation)
  { key: 'general', label: 'General', icon: Settings, component: SettingsGeneral, advanced: false },
  { key: 'memory', label: 'Memory', icon: Database, component: SettingsMemory, advanced: false },
  { key: 'privacy', label: 'Privacy & Data', icon: Lock, component: SettingsPrivacy, advanced: false },
  { key: 'notifications', label: 'Notifications', icon: Bell, component: SettingsNotifications, advanced: false },
  { key: 'voice', label: 'Voice', icon: Mic, component: SettingsVoice, advanced: false },
  { key: 'billing', label: 'Billing & Usage', icon: DollarSign, component: SettingsBilling, advanced: false },
  { key: 'about', label: 'About', icon: Info, component: SettingsAbout, advanced: false },
  // Advanced (founder / developer; behind the Show-advanced toggle)
  // 'llm' (LLM Providers) folded into 'models' (Models & Runtimes) 2026-06-18.
  { key: 'governance', label: 'Governance', icon: Shield, component: SettingsGovernance, advanced: true },
  { key: 'models', label: 'Models & Runtimes', icon: Cpu, component: SettingsModelsRuntimes, advanced: true },
  { key: 'heartbeat', label: 'Daena Heartbeat', icon: Heart, component: SettingsHeartbeat, advanced: true },
  { key: 'developer', label: 'Developer', icon: Code, component: SettingsDeveloper, advanced: true },
  { key: 'shortcuts', label: 'Shortcuts', icon: Keyboard, component: SettingsShortcuts, advanced: true },
]

const SHOW_ADVANCED_LS_KEY = 'daena.settings.show_advanced'

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

  // Show-advanced toggle: hydrated from localStorage on mount, persists
  // across reloads. Auto-flips ON when the active tab is advanced so a
  // direct deep-link to /settings/heartbeat (etc.) does not leave the
  // operator on a hidden tab with an empty sidebar.
  const [showAdvanced, setShowAdvanced] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(SHOW_ADVANCED_LS_KEY) === 'true'
  })
  useEffect(() => {
    if (current.advanced && !showAdvanced) {
      setShowAdvanced(true)
    }
    // Only triggers on initial mount + when active tab changes; the
    // user's manual toggle is preserved otherwise.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current.advanced])

  const handleShowAdvancedToggle = () => {
    const next = !showAdvanced
    setShowAdvanced(next)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SHOW_ADVANCED_LS_KEY, String(next))
    }
  }

  // Tab filter -- at 12 tabs the discoverability problem is real ("where
  // do I change my voice?"). Filters by label substring.
  const [search, setSearch] = useState('')
  const visibleByGroup = useMemo(() => {
    return CATEGORIES.filter((c) => showAdvanced || !c.advanced)
  }, [showAdvanced])
  const filtered = search.trim()
    ? visibleByGroup.filter((c) => c.label.toLowerCase().includes(search.trim().toLowerCase()))
    : visibleByGroup

  const normalTabs = filtered.filter((c) => !c.advanced)
  const advancedTabs = filtered.filter((c) => c.advanced)

  const renderTabButton = (cat: CategoryEntry) => {
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
  }

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
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter..."
          className="w-full mb-2 px-2.5 py-1.5 rounded-md text-xs bg-white/5 border border-white/10 text-starlight-200 placeholder:text-starlight-500 focus:outline-none focus:border-primary-500/40"
        />
        {/* Show-advanced toggle (PR-SETTINGS-CLEANUP) */}
        <label
          className="mb-3 flex items-center justify-between gap-2 px-3 py-1.5 rounded-md text-[10px] text-starlight-500 cursor-pointer hover:text-starlight-300"
          title="Hide founder/developer tabs (Governance, Models & Runtimes, Daena Heartbeat, Developer, Shortcuts) so the default Settings surface stays simple. Persists per browser."
        >
          <span>Show advanced</span>
          <input
            type="checkbox"
            checked={showAdvanced}
            onChange={handleShowAdvancedToggle}
            className="w-3 h-3 rounded border-white/20 bg-transparent text-primary-500"
          />
        </label>
        {filtered.length === 0 ? (
          <p className="px-3 py-2 text-xs text-starlight-500 italic">
            No tabs match "{search}"
          </p>
        ) : (
          <>
            {normalTabs.length > 0 && (
              <div>
                {!search.trim() && (
                  <p className="mt-2 mb-1 px-3 text-[9px] uppercase tracking-wider text-starlight-600">
                    Normal
                  </p>
                )}
                {normalTabs.map(renderTabButton)}
              </div>
            )}
            {advancedTabs.length > 0 && (
              <div className="mt-3">
                {!search.trim() && (
                  <p className="mt-1 mb-1 px-3 text-[9px] uppercase tracking-wider text-starlight-600">
                    Advanced
                  </p>
                )}
                {advancedTabs.map(renderTabButton)}
              </div>
            )}
          </>
        )}
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
