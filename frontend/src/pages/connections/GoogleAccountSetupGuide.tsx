/**
 * GoogleAccountSetupGuide -- Sprint-7 PR-5 (2026-05-04).
 * Extended Sprint-10 PR-1 (2026-05-05) with a LIVE checklist.
 *
 * Static, informational-only guide explaining HOW Masoud should
 * connect his Google accounts. Two distinct accounts, two distinct
 * roles -- the agent must never confuse them:
 *
 *   - masoud.masoori@mas-ai.co  -> founder / operator (you).
 *   - daena@mas-ai.co           -> Daena's own service account
 *                                  (the agent voice that posts
 *                                   on Daena's behalf).
 *
 * Sprint-10 PR-1 adds a live four-step checklist powered by
 * useGoogleSetupStatus. Each row carries a pass/fail badge plus an
 * inline next-action hint. The component still NEVER starts an OAuth
 * flow on its own: every action is a navigation hint or a click on
 * an existing manual button elsewhere in the UI.
 *
 * Honesty rules:
 *   - Manual step required block. We never start an OAuth flow
 *     automatically and we never ask the operator to paste credentials
 *     anywhere. The actual Connect button stays in OAuthConnectDrawer
 *     (already wired).
 *   - The component reads status only -- no secrets, no client_id /
 *     client_secret values. Backend strips before serializing.
 *   - The two-role split is the SHIP rule. A future PR can add a
 *     "switch account" picker once both rows exist.
 */

import { useState } from 'react'
import {
  CheckCircle2, Circle, ExternalLink, KeyRound, Mail,
  RefreshCw, ShieldAlert, User, Activity,
} from 'lucide-react'

import api from '@/lib/api'
import {
  type GoogleAccountStatus, useGoogleSetupStatus,
} from '@/hooks/useGoogleSetupStatus'

// Sprint-16 PR-3: live readiness probe result.
interface ReadinessResult {
  provider: string
  status: 'connected' | 'expired' | 'insufficient_scope' | 'failed' | 'not_connected'
  reason: string
}

interface ReadinessResponse {
  owner_email: string
  results: ReadinessResult[]
}


// Sprint-15 PR-1: per-provider granularity for the two pinned accounts.
// The backend payload returns `connected_services` as a list of slugs;
// the wizard renders one pill per Phase-3-relevant provider so the
// operator sees exactly which Google scopes are present.
const PHASE3_PROVIDERS = [
  { slug: 'gmail',            label: 'Gmail' },
  { slug: 'google-calendar',  label: 'Calendar' },
  { slug: 'google-drive',     label: 'Drive' },
] as const


function StepIcon({ done }: { done: boolean }) {
  return done
    ? <CheckCircle2 size={14} className="shrink-0 text-emerald-300" data-testid="step-icon-done" />
    : <Circle size={14} className="shrink-0 text-amber-300" data-testid="step-icon-todo" />
}


function ProviderPills({
  services, role,
}: { services: string[]; role: 'founder' | 'agent' }) {
  return (
    <div
      data-testid={`google-${role}-provider-pills`}
      className="mt-1 flex flex-wrap gap-1"
    >
      {PHASE3_PROVIDERS.map(p => {
        const present = services.includes(p.slug)
        return (
          <span
            key={p.slug}
            data-testid={`google-${role}-provider-${p.slug}-${present ? 'on' : 'off'}`}
            className={
              present
                ? 'rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300'
                : 'rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-starlight-400'
            }
          >
            {p.label}
          </span>
        )
      })}
    </div>
  )
}


function AccountStatusLine({
  account, role,
}: { account: GoogleAccountStatus; role: 'founder' | 'agent' }) {
  if (account.connected) {
    return (
      <>
        <p
          data-testid={`google-${role}-status-connected`}
          className="mt-1 text-[11px] text-emerald-300"
        >
          Connected.
        </p>
        <ProviderPills services={account.connected_services} role={role} />
      </>
    )
  }
  return (
    <>
      <p
        data-testid={`google-${role}-status-todo`}
        className="mt-1 text-[11px] text-amber-300"
      >
        Not connected yet. Open the Apps tab below and click Connect on
        Gmail (or Drive / Calendar). Sign in as{' '}
        <code className="text-starlight-200">{account.email}</code>.
      </p>
      <ProviderPills services={[]} role={role} />
    </>
  )
}


function ReadinessBadge({ result }: { result: ReadinessResult }) {
  const styles: Record<ReadinessResult['status'], string> = {
    connected: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    expired: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    insufficient_scope: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    failed: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    not_connected: 'bg-white/5 text-starlight-400 border-white/10',
  }
  return (
    <span
      data-testid={`readiness-${result.provider}-${result.status}`}
      className={`rounded border px-2 py-0.5 text-[10px] ${styles[result.status]}`}
      title={result.reason}
    >
      {result.provider}: {result.status}
    </span>
  )
}


export default function GoogleAccountSetupGuide() {
  const { status, loading, error, refresh } = useGoogleSetupStatus()
  // Sprint-16 PR-3: per-account live readiness probe state.
  const [readinessByEmail, setReadinessByEmail] = useState<
    Record<string, ReadinessResponse | { error: string } | { loading: true }>
  >({})

  const runReadinessTest = async (owner_email: string) => {
    setReadinessByEmail(prev => ({ ...prev, [owner_email]: { loading: true } }))
    try {
      const { data } = await api.post<ReadinessResponse>(
        '/connections/google-readiness-test',
        { owner_email, providers: ['gmail', 'calendar', 'drive'] },
      )
      setReadinessByEmail(prev => ({ ...prev, [owner_email]: data }))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Readiness probe failed'
      setReadinessByEmail(prev => ({ ...prev, [owner_email]: { error: msg } }))
    }
  }

  return (
    <section
      data-testid="google-account-setup-guide"
      className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-md bg-amber-500/15 text-amber-200">
          <ShieldAlert size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] uppercase tracking-[0.22em] text-amber-200">
            Manual step required
          </p>
          <h3 className="mt-1 text-sm font-semibold text-starlight-100">
            Google accounts: connect each role separately
          </h3>
          <p className="mt-1 max-w-2xl text-xs text-starlight-300">
            Daena uses two distinct Google accounts and never mixes them.
            Connect each one through its own OAuth flow. Daena will ask which
            account to act as before any tool call that touches Gmail / Drive
            / Calendar.
          </p>
        </div>
      </div>

      {/* Live checklist (Sprint-10 PR-1) */}
      <div
        data-testid="google-setup-checklist"
        className="mt-4 rounded-md border border-white/5 bg-midnight-400/30 p-3"
      >
        <div className="flex items-center justify-between">
          <h4 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-starlight-300">
            <KeyRound size={12} className="text-amber-200" />
            Live setup checklist
          </h4>
          <div className="flex items-center gap-2">
            {status?.ready && (
              <span
                data-testid="google-setup-ready-pill"
                className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-300"
              >
                Ready
              </span>
            )}
            <button
              type="button"
              data-testid="google-setup-refresh"
              onClick={() => { void refresh() }}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-starlight-300 hover:bg-white/10 disabled:opacity-50"
              title="Re-fetch Google setup status"
            >
              <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
              Refresh status
            </button>
          </div>
        </div>
        {loading && (
          <p className="mt-2 text-[11px] text-starlight-400">
            Checking current status...
          </p>
        )}
        {error && (
          <p
            data-testid="google-setup-error"
            className="mt-2 text-[11px] text-rose-300"
          >
            Could not load setup status: {error}.
          </p>
        )}
        {status && (
          <ol className="mt-2 space-y-2 text-xs text-starlight-300">
            <li
              data-testid="google-step-client"
              className="flex items-start gap-2"
            >
              <StepIcon done={status.client_configured} />
              <div className="min-w-0 flex-1">
                <p>
                  <strong className="text-starlight-100">
                    OAuth client configured
                  </strong>
                  {status.client_configured
                    ? ' — client_id + client_secret present.'
                    : ' — open Settings → OAuth Clients and paste the Google client_id + client_secret you created at console.cloud.google.com.'}
                </p>
              </div>
            </li>
            <li
              data-testid="google-step-founder"
              className="flex items-start gap-2"
            >
              <StepIcon done={status.founder_account.connected} />
              <div className="min-w-0 flex-1">
                <p>
                  <strong className="text-starlight-100">
                    Founder account
                  </strong>{' '}
                  <code className="text-starlight-200">
                    {status.founder_account.email}
                  </code>
                </p>
                <AccountStatusLine
                  account={status.founder_account}
                  role="founder"
                />
              </div>
            </li>
            <li
              data-testid="google-step-agent"
              className="flex items-start gap-2"
            >
              <StepIcon done={status.agent_account.connected} />
              <div className="min-w-0 flex-1">
                <p>
                  <strong className="text-starlight-100">
                    Agent account
                  </strong>{' '}
                  <code className="text-starlight-200">
                    {status.agent_account.email}
                  </code>
                </p>
                <AccountStatusLine
                  account={status.agent_account}
                  role="agent"
                />
              </div>
            </li>
            <li
              data-testid="google-step-ready"
              className="flex items-start gap-2"
            >
              <StepIcon done={status.ready} />
              <div className="min-w-0 flex-1">
                <p>
                  <strong className="text-starlight-100">
                    Both accounts ready
                  </strong>
                  {status.ready
                    ? ' — Daena will ask which account to use before any Gmail / Drive / Calendar call.'
                    : ' — finish the steps above; this row flips green when both accounts are connected and the OAuth client is configured.'}
                </p>
              </div>
            </li>
          </ol>
        )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {[
          { email: 'masoud.masoori@mas-ai.co', role: 'founder', label: 'Founder / operator', icon: <User size={12} />, blurb: "Your personal account. Read-only inbox / calendar / drive when you ask Daena to summarize or search. Never used for posting on the company's behalf." },
          { email: 'daena@mas-ai.co', role: 'agent', label: 'Daena / agent voice', icon: <Mail size={12} />, blurb: "Daena's own Google Workspace seat. Anything Daena sends or files on the company's behalf goes through this account so the audit trail is unambiguous. Never used to read your personal mail." },
        ].map(({ email, role, label, icon, blurb }) => {
          const probeState = readinessByEmail[email]
          const isLoadingProbe = probeState != null && 'loading' in probeState
          const probeError = probeState && 'error' in probeState ? probeState.error : null
          const probeResults = probeState && 'results' in probeState ? probeState.results : null
          return (
            <div
              key={email}
              data-testid={`google-role-${role}`}
              className="rounded-md border border-white/5 bg-midnight-400/40 p-3"
            >
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-200">
                {icon}
                {label}
              </div>
              <p className="mt-2 font-mono text-xs text-starlight-100">{email}</p>
              <p className="mt-2 text-[11px] text-starlight-300">{blurb}</p>
              {/* Sprint-16 PR-3: Test read-only button + probe result */}
              <div className="mt-3 border-t border-white/5 pt-2">
                <button
                  type="button"
                  data-testid={`readiness-test-${role}`}
                  onClick={() => { void runReadinessTest(email) }}
                  disabled={isLoadingProbe}
                  className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-starlight-300 hover:bg-white/10 disabled:opacity-50"
                  title="Live read-only probe of Gmail / Calendar / Drive"
                >
                  <Activity size={10} className={isLoadingProbe ? 'animate-pulse' : ''} />
                  Test read-only
                </button>
                {probeError && (
                  <p className="mt-2 text-[10px] text-rose-300">{probeError}</p>
                )}
                {probeResults && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {probeResults.map(r => (
                      <ReadinessBadge key={r.provider} result={r} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Sprint-15 PR-1: Phase-3 refusal hint. When a controlled write
          fails with `oauth_not_connected:google`, the operator returns
          here. We surface the exact refusal code so the audit trail
          maps to a visible action. */}
      <div
        data-testid="google-phase3-refusal-hint"
        className="mt-4 rounded-md border border-rose-500/20 bg-rose-500/5 p-3 text-[11px] text-starlight-300"
      >
        <p className="font-semibold text-rose-300">
          Phase 3 controlled writes refuse without this connection
        </p>
        <p className="mt-1">
          Any approved <code className="text-starlight-200">gmail.create_draft</code>,{' '}
          <code className="text-starlight-200">gmail.send_existing_draft</code>, or{' '}
          <code className="text-starlight-200">calendar.create_tentative_event_without_invites</code>{' '}
          dispatch refuses with{' '}
          <code className="text-rose-300">oauth_not_connected:google</code>{' '}
          if the matching account above is not green. Daena never silently
          fails — the dispatch refuses BEFORE any HTTP call to Google.
        </p>
      </div>

      <p className="mt-4 text-[10px] text-starlight-400">
        Daena does NOT start the OAuth flow for you and does NOT ask you
        to paste credentials anywhere. Everything happens through Google's
        own consent screens. If you're not signed in to a browser as the
        target Google account, sign in at{' '}
        <a
          href="https://accounts.google.com"
          target="_blank"
          rel="noopener noreferrer"
          className="underline decoration-dotted hover:text-starlight-200"
        >
          accounts.google.com
          <ExternalLink size={10} className="ml-1 inline" />
        </a>{' '}
        first, then come back here.
      </p>
    </section>
  )
}
