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

import {
  CheckCircle2, Circle, ExternalLink, KeyRound, Mail,
  ShieldAlert, User,
} from 'lucide-react'

import {
  type GoogleAccountStatus, useGoogleSetupStatus,
} from '@/hooks/useGoogleSetupStatus'


function StepIcon({ done }: { done: boolean }) {
  return done
    ? <CheckCircle2 size={14} className="shrink-0 text-emerald-300" data-testid="step-icon-done" />
    : <Circle size={14} className="shrink-0 text-amber-300" data-testid="step-icon-todo" />
}


function AccountStatusLine({
  account, role,
}: { account: GoogleAccountStatus; role: 'founder' | 'agent' }) {
  if (account.connected) {
    const services = account.connected_services.length > 0
      ? account.connected_services.join(' + ')
      : '(none yet)'
    return (
      <p
        data-testid={`google-${role}-status-connected`}
        className="mt-1 text-[11px] text-emerald-300"
      >
        Connected. Services: {services}.
      </p>
    )
  }
  return (
    <p
      data-testid={`google-${role}-status-todo`}
      className="mt-1 text-[11px] text-amber-300"
    >
      Not connected yet. Open the Apps tab below and click Connect on
      Gmail (or Drive / Calendar). Sign in as{' '}
      <code className="text-starlight-200">{account.email}</code>.
    </p>
  )
}


export default function GoogleAccountSetupGuide() {
  const { status, loading, error } = useGoogleSetupStatus()

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
          {status?.ready && (
            <span
              data-testid="google-setup-ready-pill"
              className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-300"
            >
              Ready
            </span>
          )}
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
        <div
          data-testid="google-role-founder"
          className="rounded-md border border-white/5 bg-midnight-400/40 p-3"
        >
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-200">
            <User size={12} />
            Founder / operator
          </div>
          <p className="mt-2 font-mono text-xs text-starlight-100">
            masoud.masoori@mas-ai.co
          </p>
          <p className="mt-2 text-[11px] text-starlight-300">
            Your personal account. Read-only inbox / calendar / drive when you
            ask Daena to summarize or search. Never used for posting on the
            company's behalf.
          </p>
        </div>
        <div
          data-testid="google-role-agent"
          className="rounded-md border border-white/5 bg-midnight-400/40 p-3"
        >
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-200">
            <Mail size={12} />
            Daena / agent voice
          </div>
          <p className="mt-2 font-mono text-xs text-starlight-100">
            daena@mas-ai.co
          </p>
          <p className="mt-2 text-[11px] text-starlight-300">
            Daena's own Google Workspace seat. Anything Daena sends or files
            on the company's behalf goes through this account so the audit
            trail is unambiguous. Never used to read your personal mail.
          </p>
        </div>
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
