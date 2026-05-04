/**
 * GoogleAccountSetupGuide -- Sprint-7 PR-5 (2026-05-04).
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
 * Honesty rules:
 *   - This is a MANUAL STEP REQUIRED block. We never start an OAuth
 *     flow automatically and we never ask the operator to paste
 *     credentials anywhere. The actual Connect button stays in
 *     OAuthConnectDrawer (already wired).
 *   - The component reads no secrets, makes no API calls, and emits
 *     no analytics. Pure UI.
 *   - The two-role split is the SHIP rule. A future PR can add a
 *     "switch account" picker once both rows exist.
 */

import { ExternalLink, KeyRound, Mail, ShieldAlert, User } from 'lucide-react'


export default function GoogleAccountSetupGuide() {
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

      <div className="mt-4 rounded-md border border-white/5 bg-midnight-400/30 p-3">
        <h4 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-starlight-300">
          <KeyRound size={12} className="text-amber-200" />
          What you need to do
        </h4>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-starlight-300">
          <li>
            Configure the Google OAuth client in{' '}
            <strong className="text-starlight-100">Settings &rarr; OAuth Clients</strong>{' '}
            (one client is enough for both accounts -- the redirect URI is
            the same).
          </li>
          <li>
            From the Apps tab below, click{' '}
            <strong className="text-starlight-100">Connect</strong> on Gmail
            (or Drive / Calendar). Sign in as{' '}
            <code className="text-starlight-200">masoud.masoori@mas-ai.co</code>.
          </li>
          <li>
            Back in the Apps tab, click Connect a SECOND time. Sign in as{' '}
            <code className="text-starlight-200">daena@mas-ai.co</code>.
          </li>
          <li>
            Both accounts will appear in the V2 row's owner picker. Daena
            asks which account to use before any tool call that writes or
            sends.
          </li>
        </ol>
        <p className="mt-3 text-[10px] text-starlight-400">
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
      </div>
    </section>
  )
}
