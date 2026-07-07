/**
 * AccountPage -- single page with Profile + API Keys stacked.
 * Previously this was a 2-tab sidebar layout, which was overkill for
 * just two sections. Both render inline now; the All-Settings shortcut
 * lives at the top of the page.
 */
import { lazy, Suspense } from 'react'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Settings as SettingsIcon, ChevronLeft } from 'lucide-react'

const AccountDetails = lazy(() => import('./account/AccountDetails').then(m => ({ default: m.AccountDetails })))
const AccountApiKeys = lazy(() => import('./account/AccountApiKeys').then(m => ({ default: m.AccountApiKeys })))
const AccountProviderKeys = lazy(() => import('./account/AccountProviderKeys').then(m => ({ default: m.AccountProviderKeys })))
const AccountOAuthClients = lazy(() => import('./account/AccountOAuthClients').then(m => ({ default: m.AccountOAuthClients })))
const AccountBilling = lazy(() => import('./account/AccountBilling').then(m => ({ default: m.AccountBilling })))

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
  const navigate = useNavigate()

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto p-6 space-y-6">
        {/* Header with back-home + go-to-settings shortcut */}
        <motion.div
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div>
            <button
              onClick={() => navigate('/chat')}
              className="inline-flex items-center gap-1.5 text-xs text-starlight-400 hover:text-starlight-200 transition-colors cursor-pointer mb-2"
            >
              <ChevronLeft size={12} /> Home
            </button>
            <h1 className="text-2xl font-display font-bold text-starlight-100">Account</h1>
            <p className="text-sm text-starlight-400">Profile + API keys. Other configuration lives in Settings.</p>
          </div>
          <button
            onClick={() => navigate('/settings')}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs text-starlight-400 border border-white/10 hover:border-white/20 hover:text-starlight-200 transition-colors cursor-pointer"
          >
            <SettingsIcon size={12} /> All Settings
          </button>
        </motion.div>

        {/* Profile section */}
        <section>
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">Profile</h2>
          <Suspense fallback={<AccountLoader />}>
            <AccountDetails />
          </Suspense>
        </section>

        {/* Plan & Billing section -- current plan + upgrade surface. Anchor id
            "billing" is the deep-link target a gated 402 redirects to
            (/account/billing#billing). */}
        <section id="billing" className="pt-4 border-t border-white/5 scroll-mt-24">
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">Plan &amp; Billing</h2>
          <Suspense fallback={<AccountLoader />}>
            <AccountBilling />
          </Suspense>
        </section>

        {/* API keys section -- Daena's OUTBOUND dna_ keys (clients call Daena) */}
        <section className="pt-4 border-t border-white/5">
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">API Keys</h2>
          <Suspense fallback={<AccountLoader />}>
            <AccountApiKeys />
          </Suspense>
        </section>

        {/* Provider keys section -- INBOUND keys Daena uses to call upstream LLMs.
            Anchor id "provider-keys" is the deep-link target from the
            Connections marketplace Configure button on api_provider cards. */}
        <section
          id="provider-keys"
          className="pt-4 border-t border-white/5 scroll-mt-24"
        >
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">Provider Keys</h2>
          <Suspense fallback={<AccountLoader />}>
            <AccountProviderKeys />
          </Suspense>
        </section>

        {/* OAuth client config -- client_id + client_secret for Google /
            GitHub / Slack / Figma / Canva. Without these, OAuth-backed
            plugin cards stay stuck on "Configure". Anchor id
            "oauth-clients" is the deep-link target from the OAuth
            connect drawer's "Configure in Settings" button. */}
        <section
          id="oauth-clients"
          className="pt-4 border-t border-white/5 scroll-mt-24"
        >
          <h2 className="text-sm font-display font-semibold text-starlight-100 mb-3">OAuth Client Config</h2>
          <Suspense fallback={<AccountLoader />}>
            <AccountOAuthClients />
          </Suspense>
        </section>
      </div>
    </div>
  )
}

export default AccountPage
