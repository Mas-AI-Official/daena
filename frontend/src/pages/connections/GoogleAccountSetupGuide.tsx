/**
 * GoogleAccountSetupGuide -- Sprint-7 PR-5 (2026-05-04).
 * Extended Sprint-10 PR-1 (2026-05-05) with a LIVE checklist.
 * V3 Phase 1 (2026-05-07): collapsed visual sprawl -- 3 rows instead
 * of (header + 4-step checklist + 2 role cards + Phase-3 hint +
 * footer disclaimer). All underlying logic (readiness probes,
 * status hooks, refresh handler) preserved verbatim.
 *
 * Two distinct accounts, two distinct roles -- the agent must never
 * confuse them:
 *   - masoud.masoori@mas-ai.co  -> founder / operator (you).
 *   - daena@mas-ai.co           -> Daena's own service account
 *                                  (the agent voice that posts
 *                                   on Daena's behalf).
 *
 * Honesty rules:
 *   - Manual step required block. We never start an OAuth flow
 *     automatically and we never ask the operator to paste credentials
 *     anywhere. The actual Connect button stays in OAuthConnectDrawer
 *     (already wired).
 *   - The component reads status only -- no secrets, no client_id /
 *     client_secret values. Backend strips before serializing.
 *   - Phase-3 refusal honesty hint stays reachable behind a "Why this
 *     matters" expander so the audit-trail truth is never silently
 *     dropped from the UI.
 */

import { useEffect, useState } from 'react'
import {
  Activity, AlertTriangle, CheckCircle2, ChevronDown, ChevronRight,
  Circle, ExternalLink, RefreshCw,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import api from '@/lib/api'
import {
  type GoogleAccountStatus, useGoogleSetupStatus,
} from '@/hooks/useGoogleSetupStatus'

// Sprint-16 PR-3: live readiness probe result. Sprint-20 PR-1 added
// next_action so the operator never has to guess what to do for a
// non-connected status.
interface ReadinessResult {
  provider: string
  status: 'connected' | 'expired' | 'insufficient_scope' | 'failed' | 'not_connected'
  reason: string
  next_action?: string
}

interface ReadinessResponse {
  owner_email: string
  results: ReadinessResult[]
  checked_at?: string
}


function StatusIcon({ done }: { done: boolean }) {
  return done
    ? <CheckCircle2 size={14} className="shrink-0 text-emerald-300" data-testid="step-icon-done" />
    : <Circle size={14} className="shrink-0 text-amber-300" data-testid="step-icon-todo" />
}


export default function GoogleAccountSetupGuide() {
  const navigate = useNavigate()
  const { status, loading, error, refresh } = useGoogleSetupStatus()
  const [readinessByEmail, setReadinessByEmail] = useState<
    Record<string, ReadinessResponse | { error: string } | { loading: true }>
  >({})
  const [whyOpen, setWhyOpen] = useState(false)

  const runReadinessTest = async (owner_email: string) => {
    setReadinessByEmail(prev => ({ ...prev, [owner_email]: { loading: true } }))
    try {
      const { data } = await api.post<ReadinessResponse>(
        '/connections/google-readiness-test',
        { owner_email, providers: ['gmail', 'calendar', 'drive'] },
      )
      const stamped: ReadinessResponse = {
        ...data, checked_at: new Date().toISOString(),
      }
      setReadinessByEmail(prev => ({ ...prev, [owner_email]: stamped }))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Readiness probe failed'
      setReadinessByEmail(prev => ({ ...prev, [owner_email]: { error: msg } }))
    }
  }

  // Sprint-20 PR-1: auto-probe both accounts once they're both connected.
  useEffect(() => {
    if (!status) return
    const tasks: Promise<void>[] = []
    if (status.founder_account.connected
        && readinessByEmail[status.founder_account.email] == null) {
      tasks.push(runReadinessTest(status.founder_account.email))
    }
    if (status.agent_account.connected
        && readinessByEmail[status.agent_account.email] == null) {
      tasks.push(runReadinessTest(status.agent_account.email))
    }
    void Promise.all(tasks)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.founder_account.connected, status?.agent_account.connected])

  const clientConfigured = !!status?.client_configured
  const founder = status?.founder_account
  const agent = status?.agent_account

  return (
    <section
      data-testid="google-account-setup-guide"
      className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] text-amber-200">
            Google setup
          </p>
          <h3 className="mt-0.5 text-sm font-semibold text-starlight-100">
            Connect both accounts to unlock Gmail / Drive / Calendar.
          </h3>
        </div>
        <button
          type="button"
          data-testid="google-setup-refresh"
          onClick={() => { void refresh() }}
          disabled={loading}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-starlight-300 hover:bg-white/10 disabled:opacity-50"
          title="Re-fetch Google setup status"
        >
          <RefreshCw size={10} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {error && (
        <p data-testid="google-setup-error" className="mt-2 text-[11px] text-rose-300">
          Could not load setup status: {error}
        </p>
      )}

      {/* 3-row status grid -- the only thing visible by default */}
      <ul className="mt-3 space-y-2">
        <SetupRow
          done={clientConfigured}
          label="OAuth client configured"
          detail={clientConfigured
            ? 'client_id + client_secret present.'
            : 'Paste the Google client_id + client_secret you created at console.cloud.google.com.'}
          action={!clientConfigured ? {
            label: 'Configure',
            onClick: () => navigate('/account#oauth-clients'),
          } : undefined}
          testid="google-step-client"
        />
        {founder && (
          <SetupRow
            done={founder.connected}
            label={`Founder account · ${founder.email}`}
            detail={founder.connected
              ? `Connected · scopes: ${(founder.connected_services.length || 0)} present`
              : 'Click Connect on Gmail / Drive / Calendar below. Sign in as the founder account.'}
            action={founder.connected ? {
              label: 'Test read-only',
              onClick: () => { void runReadinessTest(founder.email) },
              icon: 'activity',
              busy: readinessByEmail[founder.email] != null && 'loading' in readinessByEmail[founder.email]!,
            } : undefined}
            badge={readinessBadge(readinessByEmail[founder.email])}
            testid="google-step-founder"
          />
        )}
        {agent && (
          <SetupRow
            done={agent.connected}
            label={`Agent account · ${agent.email}`}
            detail={agent.connected
              ? `Connected · scopes: ${(agent.connected_services.length || 0)} present`
              : "Click Connect on Gmail / Drive / Calendar below. Sign in as Daena's service account."}
            action={agent.connected ? {
              label: 'Test read-only',
              onClick: () => { void runReadinessTest(agent.email) },
              icon: 'activity',
              busy: readinessByEmail[agent.email] != null && 'loading' in readinessByEmail[agent.email]!,
            } : undefined}
            badge={readinessBadge(readinessByEmail[agent.email])}
            testid="google-step-agent"
          />
        )}
      </ul>

      {/* "Why these are required" expander -- preserves Phase-3 honesty
          surface (Sprint-15 PR-1 refusal hint) and the audit-trail
          rationale for the two-account split, but keeps them out of the
          default visual budget. */}
      <button
        type="button"
        onClick={() => setWhyOpen(v => !v)}
        aria-expanded={whyOpen}
        data-testid="google-setup-why-toggle"
        className="mt-3 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-starlight-500 hover:text-starlight-300"
      >
        {whyOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        Why these are required
      </button>
      {whyOpen && (
        <div className="mt-2 space-y-2 rounded-md border border-white/5 bg-midnight-400/30 p-3 text-[11px] text-starlight-300">
          <p>
            Daena uses two distinct Google accounts and never mixes them.
            The founder account is for read-only operations on your
            personal Gmail / Drive / Calendar; the agent account is the
            service seat that posts or files on the company's behalf so
            the audit trail stays unambiguous.
          </p>
          <div
            data-testid="google-phase3-refusal-hint"
            className="rounded-md border border-rose-500/20 bg-rose-500/5 p-2 text-rose-200"
          >
            <strong>Phase 3 controlled writes refuse without this connection.</strong>{' '}
            Approved <code className="text-starlight-200">gmail.create_draft</code>,{' '}
            <code className="text-starlight-200">gmail.send_existing_draft</code>, and{' '}
            <code className="text-starlight-200">calendar.create_tentative_event_without_invites</code>{' '}
            dispatches refuse with{' '}
            <code className="text-rose-300">oauth_not_connected:google</code>{' '}
            BEFORE any HTTP call to Google when the matching account isn't green.
          </div>
          <p className="text-[10px] text-starlight-500">
            Daena does not start the OAuth flow for you. Sign in to the
            target Google account at{' '}
            <a
              href="https://accounts.google.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-dotted hover:text-starlight-200"
            >
              accounts.google.com
              <ExternalLink size={10} className="ml-1 inline" />
            </a>{' '}
            first if needed, then come back here.
          </p>
        </div>
      )}
    </section>
  )
}


// --- one-row status component, kept inline because it's only used here ---

interface SetupRowAction {
  label: string
  onClick: () => void
  icon?: 'activity'
  busy?: boolean
}

function SetupRow({
  done, label, detail, action, badge, testid,
}: {
  done: boolean
  label: string
  detail: string
  action?: SetupRowAction
  badge?: React.ReactNode
  testid: string
}) {
  return (
    <li
      data-testid={testid}
      className="flex items-start gap-2 rounded-md border border-white/5 bg-midnight-400/30 px-3 py-2"
    >
      <StatusIcon done={done} />
      <div className="min-w-0 flex-1">
        <p className="text-[12px] font-medium text-starlight-100">{label}</p>
        <p className="mt-0.5 text-[11px] text-starlight-400">{detail}</p>
        {badge && <div className="mt-1.5">{badge}</div>}
      </div>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          disabled={action.busy}
          className="shrink-0 inline-flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] text-amber-200 hover:bg-amber-500/20 disabled:opacity-50"
        >
          {action.icon === 'activity' && <Activity size={10} className={action.busy ? 'animate-pulse' : ''} />}
          {action.label}
        </button>
      )}
    </li>
  )
}


// Render the readiness probe result as a compact pill row.
function readinessBadge(
  state: ReadinessResponse | { error: string } | { loading: true } | undefined,
): React.ReactNode | undefined {
  if (!state) return undefined
  if ('loading' in state) return undefined
  if ('error' in state) {
    return <p className="text-[10px] text-rose-300">{state.error}</p>
  }
  const styles: Record<ReadinessResult['status'], string> = {
    connected: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    expired: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    insufficient_scope: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    failed: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    not_connected: 'bg-white/5 text-starlight-400 border-white/10',
  }
  const failing = state.results.filter(r => r.status !== 'connected' && r.next_action)
  return (
    <>
      <div className="flex flex-wrap gap-1">
        {state.results.map(r => (
          <span
            key={r.provider}
            data-testid={`readiness-${r.provider}-${r.status}`}
            className={`rounded border px-1.5 py-0.5 text-[10px] ${styles[r.status]}`}
            title={r.reason}
          >
            {r.provider}: {r.status}
          </span>
        ))}
      </div>
      {failing.length > 0 && (
        <ul className="mt-1 space-y-0.5 text-[10px] text-amber-300">
          {failing.map(r => (
            <li key={r.provider}>
              <span className="font-mono text-starlight-200">{r.provider}</span>
              : {r.next_action}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

// Re-export GoogleAccountStatus so existing test fixtures keep importing
// the type from this file (preserves prior surface).
export type { GoogleAccountStatus }
