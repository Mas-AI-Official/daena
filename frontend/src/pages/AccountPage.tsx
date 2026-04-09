/**
 * AccountPage -- Perplexity-style account settings with Personal / API / Enterprise sections.
 * Left sidebar nav + lazy-loaded tab content.
 * Routes: /account/:category, /account/org/:category
 */
import { lazy, Suspense } from 'react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import {
  User,
  Settings,
  Sparkles,
  Bot,
  Keyboard,
  Bell,
  CreditCard,
  Plug,
  FileText,
  Mic,
  Code,
  Building,
  Heart,
  Users,
  Shield,
  Zap,
  FolderOpen,
  BarChart3,
  Activity,
  Cpu,
  Database,
  Lock,
  Monitor,
} from 'lucide-react'
import type { ComponentType } from 'react'

// Personal tabs -- lazy loaded
const AccountDetails = lazy(() => import('./account/AccountDetails').then(m => ({ default: m.AccountDetails })))
const AccountPersonalize = lazy(() => import('./account/AccountPersonalize').then(m => ({ default: m.AccountPersonalize })))
const AccountApiKeys = lazy(() => import('./account/AccountApiKeys').then(m => ({ default: m.AccountApiKeys })))
const AccountConnectors = lazy(() => import('./account/AccountConnectors').then(m => ({ default: m.AccountConnectors })))
const AccountFiles = lazy(() => import('./account/AccountFiles').then(m => ({ default: m.AccountFiles })))

// Re-import existing settings tabs
const SettingsGeneral = lazy(() => import('./settings/SettingsGeneral').then(m => ({ default: m.SettingsGeneral })))
const SettingsLLM = lazy(() => import('./settings/SettingsLLM').then(m => ({ default: m.SettingsLLM })))
const SettingsShortcuts = lazy(() => import('./settings/SettingsShortcuts').then(m => ({ default: m.SettingsShortcuts })))
const SettingsNotifications = lazy(() => import('./settings/SettingsNotifications').then(m => ({ default: m.SettingsNotifications })))
const SettingsBilling = lazy(() => import('./settings/SettingsBilling').then(m => ({ default: m.SettingsBilling })))
const SettingsVoice = lazy(() => import('./settings/SettingsVoice').then(m => ({ default: m.SettingsVoice })))

// Org tabs -- lazy loaded
const OrgDetails = lazy(() => import('./account/OrgDetails').then(m => ({ default: m.OrgDetails })))
const OrgBilling = lazy(() => import('./account/OrgBilling').then(m => ({ default: m.OrgBilling })))
const OrgComputer = lazy(() => import('./account/OrgComputer').then(m => ({ default: m.OrgComputer })))
const OrgMembers = lazy(() => import('./account/OrgMembers').then(m => ({ default: m.OrgMembers })))
const OrgConnectors = lazy(() => import('./account/OrgConnectors').then(m => ({ default: m.OrgConnectors })))
const OrgSkills = lazy(() => import('./account/OrgSkills').then(m => ({ default: m.OrgSkills })))
const OrgFiles = lazy(() => import('./account/OrgFiles').then(m => ({ default: m.OrgFiles })))
const OrgAnalytics = lazy(() => import('./account/OrgAnalytics').then(m => ({ default: m.OrgAnalytics })))
const OrgTelemetry = lazy(() => import('./account/OrgTelemetry').then(m => ({ default: m.OrgTelemetry })))

// Re-import org-level existing settings
const SettingsGovernance = lazy(() => import('./settings/SettingsGovernance').then(m => ({ default: m.SettingsGovernance })))
const SettingsModelsRuntimes = lazy(() => import('./settings/SettingsModelsRuntimes').then(m => ({ default: m.SettingsModelsRuntimes })))
const SettingsMemory = lazy(() => import('./settings/SettingsMemory').then(m => ({ default: m.SettingsMemory })))
const SettingsPrivacy = lazy(() => import('./settings/SettingsPrivacy').then(m => ({ default: m.SettingsPrivacy })))
const SettingsHeartbeat = lazy(() => import('./settings/SettingsHeartbeat').then(m => ({ default: m.SettingsHeartbeat })))
const SettingsDeveloper = lazy(() => import('./settings/SettingsDeveloper').then(m => ({ default: m.SettingsDeveloper })))

interface TabDef {
  key: string
  label: string
  icon: ComponentType<{ size?: number }>
  component: ComponentType
}

interface SectionDef {
  title: string
  tabs: TabDef[]
}

const PERSONAL_TABS: TabDef[] = [
  { key: 'details', label: 'Account', icon: User, component: AccountDetails },
  { key: 'preferences', label: 'Preferences', icon: Settings, component: SettingsGeneral },
  { key: 'personalize', label: 'Personalization', icon: Sparkles, component: AccountPersonalize },
  { key: 'assistant', label: 'Assistant', icon: Bot, component: SettingsLLM },
  { key: 'shortcuts', label: 'Shortcuts', icon: Keyboard, component: SettingsShortcuts },
  { key: 'notifications', label: 'Notifications', icon: Bell, component: SettingsNotifications },
  { key: 'usage', label: 'Usage & credits', icon: CreditCard, component: SettingsBilling },
  { key: 'connectors', label: 'Connectors', icon: Plug, component: AccountConnectors },
  { key: 'files', label: 'Files', icon: FileText, component: AccountFiles },
  { key: 'voice', label: 'Voice', icon: Mic, component: SettingsVoice },
]

const API_TABS: TabDef[] = [
  { key: 'api-keys', label: 'API Platform', icon: Code, component: AccountApiKeys },
]

const ENTERPRISE_TABS: TabDef[] = [
  { key: 'org/details', label: 'Organization', icon: Building, component: OrgDetails },
  { key: 'org/billing', label: 'Organization credits', icon: CreditCard, component: OrgBilling },
  { key: 'org/computer', label: 'Computer', icon: Monitor, component: OrgComputer },
  { key: 'org/heartbeat', label: 'Daena Heartbeat', icon: Heart, component: SettingsHeartbeat },
  { key: 'org/members', label: 'Members', icon: Users, component: OrgMembers },
  { key: 'org/permissions', label: 'Permissions', icon: Shield, component: SettingsGovernance },
  { key: 'org/connectors', label: 'Connectors', icon: Plug, component: OrgConnectors },
  { key: 'org/skills', label: 'Skills', icon: Zap, component: OrgSkills },
  { key: 'org/files', label: 'Organization files', icon: FolderOpen, component: OrgFiles },
  { key: 'org/analytics', label: 'Analytics', icon: BarChart3, component: OrgAnalytics },
  { key: 'org/telemetry', label: 'Heartbeat telemetry', icon: Activity, component: OrgTelemetry },
  { key: 'org/models', label: 'Models & Runtimes', icon: Cpu, component: SettingsModelsRuntimes },
  { key: 'org/memory', label: 'Memory', icon: Database, component: SettingsMemory },
  { key: 'org/privacy', label: 'Privacy & Data', icon: Lock, component: SettingsPrivacy },
  { key: 'org/developer', label: 'Developer', icon: Code, component: SettingsDeveloper },
]

const ALL_TABS = [...PERSONAL_TABS, ...API_TABS, ...ENTERPRISE_TABS]

const SECTIONS: SectionDef[] = [
  { title: '', tabs: PERSONAL_TABS },
  { title: 'API', tabs: API_TABS },
  { title: 'Enterprise', tabs: ENTERPRISE_TABS },
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
  const { category, '*': wildcard } = useParams<{ category?: string; '*'?: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'FOUNDER' || user?.role === 'ADMIN'

  // Parse the active key from the URL path
  const pathAfterAccount = location.pathname.replace('/account/', '').replace('/account', '')
  const active = pathAfterAccount || 'details'

  const current = ALL_TABS.find((t) => t.key === active) || ALL_TABS[0]
  const ActiveComponent = current.component

  const handleTabClick = (key: string) => {
    navigate(key === 'details' ? '/account' : `/account/${key}`)
  }

  return (
    <div className="h-full flex overflow-hidden">
      {/* Left sidebar nav */}
      <nav className="w-52 flex-shrink-0 border-r border-white/5 overflow-y-auto py-4 px-2">
        <button
          onClick={() => navigate('/chat')}
          className="flex items-center gap-1.5 px-3 mb-4 text-xs text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer"
        >
          &lt; Home
        </button>

        {SECTIONS.map((section, si) => {
          // Hide Enterprise section for non-admin users
          if (section.title === 'Enterprise' && !isAdmin) return null

          return (
            <div key={si}>
              {section.title && (
                <p className="px-3 mt-4 mb-2 text-[10px] font-mono uppercase tracking-widest text-starlight-500">
                  {section.title}
                </p>
              )}
              {section.tabs.map((tab) => {
                const Icon = tab.icon
                const isActive = tab.key === active
                return (
                  <button
                    key={tab.key}
                    onClick={() => handleTabClick(tab.key)}
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
            </div>
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
          <Suspense fallback={<AccountLoader />}>
            <ActiveComponent />
          </Suspense>
        </motion.div>
      </div>
    </div>
  )
}

export default AccountPage
