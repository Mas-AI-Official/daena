/**
 * OAuthConnectDrawer -- Connect flow for OAuth-backed plugin cards.
 *
 * PR-CONN-OAUTH-CONNECT (2026-05-02). Replaces the read-only Setup
 * Guide for OAuth-app plugin cards where Daena can safely START a
 * Connect flow against an existing oauth_service provider
 * (gmail / google-drive / google-calendar / github / figma / slack /
 * canva).
 *
 * Steps:
 *   1. Show scopes + redirect URI -- the operator sees what they're
 *      consenting to BEFORE the popup opens.
 *   2. Click "Open consent page" -- pops the provider's authorization
 *      URL in a new window. The window listens for postMessage from
 *      Daena's existing /api/v1/connectors/oauth/callback HTML.
 *   3. After receiving the success postMessage, surface "Connected"
 *      and offer Test (which fires the OAuthAppProbe).
 *   4. If the start endpoint returns failure_reason starting with
 *      'configure_required', offer a Configure deep-link to
 *      /account/api-keys instead.
 *
 * Honesty:
 *   - "Connected" pill ONLY after V2 truth callable=true (probe must
 *     succeed). The drawer reflects "tokens received" with a softer
 *     label until the next marketplace-cards poll surfaces the truth.
 *   - Required scopes are listed verbatim; never paraphrased.
 *   - Redirect URI is shown so the operator can double-check it
 *     matches what they registered in the provider's developer portal.
 *   - NEVER asks the user to paste a secret. Client_id / client_secret
 *     live in Settings -> API Keys (vault-backed); access tokens flow
 *     directly from the consent screen to the backend callback.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, ExternalLink,
  Loader2, ShieldCheck, X,
} from 'lucide-react'

import {
  type OAuthStartResponse,
  startMarketplaceOAuth,
} from '@/hooks/useMarketplace'
import { type PluginCard } from './pluginCard'

interface OAuthConnectDrawerProps {
  plugin: PluginCard
  onClose: () => void
  onComplete?: (provider: string) => void
}

type Step = 'preflight' | 'awaiting_consent' | 'success' | 'failed'

export default function OAuthConnectDrawer({
  plugin, onClose, onComplete,
}: OAuthConnectDrawerProps) {
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('preflight')
  const [start, setStart] = useState<OAuthStartResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [popupRef, setPopupRef] = useState<Window | null>(null)
  const [callbackError, setCallbackError] = useState<string | null>(null)

  // Pre-fetch the start payload on open so the operator sees scopes +
  // redirect URI BEFORE clicking "Open consent page".
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    void (async () => {
      const res = await startMarketplaceOAuth(plugin.id)
      if (cancelled) return
      setLoading(false)
      if (res.ok && res.data) {
        setStart(res.data)
        if (!res.data.success) setStep('failed')
      } else {
        setError(res.error ?? 'Failed to start OAuth')
        setStep('failed')
      }
    })()
    return () => { cancelled = true }
  }, [plugin.id])

  // Listen for postMessage from the provider callback page. The
  // existing /api/v1/connectors/oauth/callback HTML posts:
  //   {type: 'oauth_success', connector: '<provider>'}  on success
  //   {type: 'oauth_error', connector: '<provider>', error: '...'}  on failure
  useEffect(() => {
    function onMessage(ev: MessageEvent) {
      const msg = ev.data as { type?: string; connector?: string; error?: string }
      if (!msg || typeof msg.type !== 'string') return
      if (msg.type === 'oauth_success' && msg.connector === start?.provider) {
        setStep('success')
        try { popupRef?.close() } catch (_) { /* may already be closed */ }
        onComplete?.(msg.connector)
      } else if (msg.type === 'oauth_error' && msg.connector === start?.provider) {
        setStep('failed')
        setCallbackError(msg.error ?? 'OAuth callback reported an error')
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [start?.provider, popupRef, onComplete])

  function handleOpenConsent() {
    if (!start?.authorization_url) return
    const popup = window.open(
      start.authorization_url,
      'daena_oauth',
      'width=600,height=700',
    )
    setPopupRef(popup)
    setStep('awaiting_consent')
  }

  function handleConfigure() {
    navigate('/account/api-keys')
    onClose()
  }

  const isConfigureRequired =
    start?.failure_reason?.startsWith('configure_required') ?? false
  const isUnsupported =
    start?.failure_reason?.startsWith('unsupported_provider') ?? false

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
      onClick={onClose}
    >
      <div
        className="max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-white/10 bg-midnight-400/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-white/5 p-5">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
              Connect OAuth app
            </p>
            <h2 className="mt-0.5 text-lg font-semibold text-starlight-100">
              {plugin.name}
            </h2>
            <p className="text-xs text-starlight-400">
              {plugin.vendor} - {plugin.description}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md border border-white/10 bg-white/5 p-1.5 text-starlight-300 hover:bg-white/10"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </header>

        <div className="space-y-5 p-5">
          {loading && (
            <div className="rounded-lg border border-white/5 bg-white/[0.02] py-6 text-center text-xs text-starlight-400">
              <Loader2 size={14} className="mr-2 inline animate-spin" />
              Resolving OAuth start...
            </div>
          )}

          {!loading && step === 'failed' && (
            <FailureBlock
              start={start}
              error={error ?? start?.failure_reason ?? callbackError ?? 'Unknown failure'}
              isConfigureRequired={isConfigureRequired}
              isUnsupported={isUnsupported}
              onConfigure={handleConfigure}
              onClose={onClose}
            />
          )}

          {!loading && start && start.success && step === 'preflight' && (
            <PreflightBlock start={start} onOpenConsent={handleOpenConsent} />
          )}

          {step === 'awaiting_consent' && (
            <Section title="Waiting for consent">
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100">
                <Loader2 size={12} className="mr-1.5 inline animate-spin" />
                <strong>Approve the request in the popup.</strong> Daena
                listens for the callback from the provider and updates
                this drawer the moment tokens are received.
              </div>
              <p className="mt-2 text-[11px] text-starlight-500">
                Closed the popup by accident? Click "Open consent page"
                again to retry -- the start state is still valid.
              </p>
              <button
                onClick={handleOpenConsent}
                className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-[11px] font-medium text-primary-200 hover:bg-primary-500/20"
              >
                <ExternalLink size={11} /> Re-open consent page
              </button>
            </Section>
          )}

          {step === 'success' && (
            <SuccessBlock provider={start?.provider ?? null} onClose={onClose} />
          )}
        </div>
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────
// Sub-blocks
// ──────────────────────────────────────────────────────────────────

function PreflightBlock({
  start, onOpenConsent,
}: { start: OAuthStartResponse; onOpenConsent: () => void }) {
  return (
    <>
      <Section title="What you're consenting to">
        <KV label="Provider" value={start.provider ?? 'unknown'} />
        <KV label="Redirect URI" value={start.redirect_uri ?? '(not set)'} mono />
      </Section>

      <Section title="Requested scopes">
        <ul className="space-y-1">
          {start.scopes.map((scope) => (
            <li
              key={scope}
              className="flex items-start gap-1.5 rounded-md bg-white/[0.03] px-2 py-1.5 text-[11px] text-starlight-200"
            >
              <ShieldCheck size={11} className="mt-0.5 text-emerald-300" />
              <code>{scope}</code>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-starlight-500">
          The provider's consent page lets you reduce these scopes if
          you prefer. Daena never asks for more than what's listed here.
        </p>
      </Section>

      <Section title="What happens next">
        <ol className="list-decimal space-y-1 pl-5 text-[11px] text-starlight-300">
          <li>Click <strong>Open consent page</strong>. A popup opens
            on the provider's site.</li>
          <li>Approve the requested scopes. The provider redirects back
            to Daena's callback URL.</li>
          <li>Daena exchanges the auth code for tokens, encrypts them
            with the existing AES vault, and imports a V2 plugin row.</li>
          <li>Click <strong>Test</strong> on the plugin card to verify
            the token works (probe runs userinfo / equivalent safe call).</li>
        </ol>
      </Section>

      <FooterRow>
        <span className="text-[11px] text-starlight-500">
          Your client_id + client_secret live in Settings -&gt; API Keys.
          Daena never asks you to paste them here.
        </span>
        <button
          onClick={onOpenConsent}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20"
        >
          Open consent page
          <ArrowRight size={11} />
        </button>
      </FooterRow>
    </>
  )
}

function SuccessBlock({
  provider, onClose,
}: { provider: string | null; onClose: () => void }) {
  return (
    <>
      <Section title="Tokens received">
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs text-emerald-200">
          <CheckCircle2 size={12} className="mr-1.5 inline" />
          <strong>Provider authorized.</strong> Daena's existing OAuth
          callback wrote the tokens to the encrypted vault and imported
          a V2 plugin row for {provider ?? 'the provider'}.
        </div>
        <p className="mt-2 text-[11px] text-starlight-500">
          The Plugins grid will refresh on its next poll. Hit
          <strong> Test</strong> on the {provider ?? 'plugin'} card to
          flip the status pill to <strong>Connected</strong> -- the
          probe runs the provider's userinfo endpoint to prove the
          token actually works.
        </p>
      </Section>

      <FooterRow>
        <span className="text-[11px] text-starlight-500">
          Truth ladder: tokens received -&gt; authenticated. Test runs
          to prove callable.
        </span>
        <button
          onClick={onClose}
          className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/30 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-primary-200 hover:bg-primary-500/20"
        >
          Done
        </button>
      </FooterRow>
    </>
  )
}

function FailureBlock({
  start, error, isConfigureRequired, isUnsupported, onConfigure, onClose,
}: {
  start: OAuthStartResponse | null
  error: string
  isConfigureRequired: boolean
  isUnsupported: boolean
  onConfigure: () => void
  onClose: () => void
}) {
  if (isConfigureRequired) {
    return (
      <>
        <Section title="OAuth client not configured">
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-100">
            <AlertTriangle size={12} className="mr-1.5 inline" />
            <strong>Configure your OAuth client first.</strong>
            <p className="mt-1 text-[11px] text-amber-200/80">
              Daena needs the client_id + client_secret you registered
              with the provider before it can start the consent flow.
              These live in Settings -&gt; API Keys (vault-backed).
            </p>
            <p className="mt-1 text-[11px] text-amber-200/60">
              Reason: <code>{error}</code>
            </p>
          </div>
        </Section>
        <FooterRow>
          <button
            onClick={onClose}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
          >
            <ArrowLeft size={11} /> Back
          </button>
          <button
            onClick={onConfigure}
            className="inline-flex items-center gap-1.5 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-xs font-medium text-accent-cyan hover:bg-accent-cyan/20"
          >
            Configure in Settings
            <ExternalLink size={11} />
          </button>
        </FooterRow>
      </>
    )
  }

  if (isUnsupported) {
    return (
      <>
        <Section title="Provider not supported yet">
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-200">
            <AlertTriangle size={12} className="mr-1.5 inline" />
            <strong>This provider is in the catalog but not yet wired
            into Daena's OAuth service.</strong>
            <p className="mt-1 text-[11px] text-rose-200/70">
              Reason: <code>{error}</code>
            </p>
            <p className="mt-2 text-[11px] text-rose-200/70">
              Use the provider's MCP equivalent (with API key auth)
              until OAuth lands. The Setup guide on the plugin card
              has the install steps.
            </p>
          </div>
        </Section>
        <FooterRow>
          <button
            onClick={onClose}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
          >
            Close
          </button>
        </FooterRow>
      </>
    )
  }

  return (
    <>
      <Section title="Could not start OAuth">
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-200">
          <AlertTriangle size={12} className="mr-1.5 inline" />
          {error}
          {start?.redirect_uri && (
            <p className="mt-2 text-[11px] text-rose-200/70">
              Redirect URI Daena uses: <code>{start.redirect_uri}</code>.
              Verify the exact same URI is registered in the provider's
              developer portal.
            </p>
          )}
        </div>
      </Section>
      <FooterRow>
        <button
          onClick={onClose}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-starlight-300 hover:bg-white/10"
        >
          Close
        </button>
      </FooterRow>
    </>
  )
}

// ──────────────────────────────────────────────────────────────────
// Tiny shared layout helpers
// ──────────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
        {title}
      </h3>
      {children}
    </section>
  )
}

function KV({
  label, value, mono = false,
}: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded border border-white/5 bg-white/[0.02] px-2.5 py-1.5">
      <p className="text-[10px] uppercase tracking-wider text-starlight-500">
        {label}
      </p>
      <p className={`max-w-[60%] truncate text-xs text-starlight-200 ${mono ? 'font-mono' : ''}`}>
        {value}
      </p>
    </div>
  )
}

function FooterRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2 border-t border-white/5 pt-3">
      {children}
    </div>
  )
}
