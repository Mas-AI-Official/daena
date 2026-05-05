/**
 * SkillExecuteModal -- confirmation modal for Phase 2 read-only skill
 * execution.
 *
 * PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY (2026-05-03).
 *
 * Honesty contract (founder rules 9-16):
 *   - Modal renders only when SkillBundleSection has confirmed the
 *     (plugin, skill) pair is in the Phase 2 allowlist AND the plugin
 *     readiness is "ready".
 *   - Operator must explicitly fill required_inputs + click "Run
 *     read-only skill" to invoke. No auto-run, no prefill from
 *     anywhere outside the modal's input fields.
 *   - Modal shows the explicit no-writes/no-sends/no-payments
 *     statement BEFORE the Run button so consent is informed.
 *   - On submit: POST /api/v1/connections/v2/skills/execute. Phase 2
 *     ALWAYS returns status="planned" -- the result is surfaced as a
 *     read-only preview + a draft prompt the operator can carry into
 *     chat for follow-up.
 *   - Operator inputs NEVER persist beyond the modal session. Closing
 *     the modal clears the input state.
 *
 * Out of scope for this PR (deferred to Phase 3+):
 *   - Streaming actual tool output (Phase 2 returns planned preview only)
 *   - Asset Shield consent dialogs for high-risk reads
 *   - Multi-step skill plans
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, ArrowRight, Loader2, Lock, Play, ShieldCheck, User, X,
} from 'lucide-react'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { draftMessage } from '@/lib/composerBridge'

// PR-CONN-FRONTEND-ACCOUNT-PROFILE-PICKER (Sprint-5 PR-2):
// plugin_id -> provider slug for the owner_email account picker. Only
// OAuth-backed plugins map; non-OAuth (mcp-*) plugins skip the picker
// entirely and the modal renders identically to before.
const PLUGIN_TO_OAUTH_PROVIDER: Record<string, string> = {
  'app-gmail': 'gmail',
  'app-google-drive': 'google-drive',
  'app-google-calendar': 'google-calendar',
  'app-slack': 'slack',
  'app-github': 'github',
}

interface OAuthAccount {
  instance_id: string
  owner_email: string | null
  status: string
}

export interface Phase2AllowlistRow {
  plugin_id: string
  skill_id: string
  backend_surface: 'mcp' | 'oauth' | 'internal' | 'none'
  read_only: boolean
  execution_mode: 'planned_only' | 'mcp_tool'
  required_inputs: string[]
  reads_summary: string
}

export interface SkillExecutionResultDTO {
  accepted: boolean
  status:
    | 'planned' | 'executed' | 'blocked'
    | 'needs_connection' | 'needs_inputs' | 'unsupported'
    | 'needs_consent'
  summary: string
  audit_event_id: string | null
  required_inputs: string[]
  tool_calls: Array<{
    backend_surface: string
    tool_name: string
    argument_shape: Record<string, string>
    read_only: boolean
    plugin_id: string
    skill_id: string
  }>
  result_preview: string
  blocked_reason: string
}

// PR-CONN-CONSENT-API-AND-UI (Sprint-5 PR-4):
// 6 categories the operator can grant consent against. Mirrors the
// backend SkillConsentCategory enum exactly. Default category for the
// modal is write_external (the executor's categorize_skill default).
const CONSENT_CATEGORIES = [
  { code: 'read_sensitive', label: 'Read sensitive data' },
  { code: 'write_external', label: 'Write external resource' },
  { code: 'send_message', label: 'Send a message' },
  { code: 'payment', label: 'Payment / financial' },
  { code: 'browser_action', label: 'Browser automation' },
  { code: 'security_scan', label: 'Security scan' },
] as const

interface SkillExecuteModalProps {
  pluginId: string
  pluginName: string
  skillId: string
  /** The Phase 2 allowlist row for this (plugin, skill) pair.
   * Caller already proved it's allowlisted -- modal does not re-fetch. */
  allowlistRow: Phase2AllowlistRow
  onClose: () => void
}

function humanize(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function SkillExecuteModal({
  pluginId, pluginName, skillId, allowlistRow, onClose,
}: SkillExecuteModalProps) {
  const navigate = useNavigate()
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<SkillExecutionResultDTO | null>(null)
  const [error, setError] = useState<string | null>(null)

  // PR-CONN-FRONTEND-ACCOUNT-PROFILE-PICKER (Sprint-5 PR-2):
  // for OAuth-backed plugins, fetch the connected accounts so the
  // operator can pick which Google profile (e.g. masoud@... vs
  // daena@...) the skill should run as. The picker:
  //   - is invisible for non-OAuth plugins (mcp-*)
  //   - auto-selects the only account when there's just one
  //   - REQUIRES explicit selection when multiple are connected
  //   - shows a "no account connected" message when there's none
  const oauthProvider =
    allowlistRow.backend_surface === 'oauth'
      ? PLUGIN_TO_OAUTH_PROVIDER[pluginId] ?? null
      : null
  const [accounts, setAccounts] = useState<OAuthAccount[] | null>(null)
  const [accountsLoading, setAccountsLoading] = useState(false)
  const [selectedOwnerEmail, setSelectedOwnerEmail] = useState<string | null>(null)

  // PR-CONN-CONSENT-API-AND-UI (Sprint-5 PR-4):
  // when result.status === 'needs_consent' the modal exposes a small
  // form letting the operator pick the right category and mint a
  // single-use grant. Phase 2 still blocks writes -- the UI states
  // this explicitly so the operator never thinks consent unblocks.
  const [consentCategory, setConsentCategory] = useState<string>('write_external')
  const [grantingConsent, setGrantingConsent] = useState(false)
  const [consentNotice, setConsentNotice] = useState<string | null>(null)

  // Reset state on (plugin, skill) change so reusing the same modal
  // for a different skill doesn't carry old inputs across.
  useEffect(() => {
    setInputs({})
    setSubmitting(false)
    setResult(null)
    setError(null)
    setAccounts(null)
    setSelectedOwnerEmail(null)
    setConsentCategory('write_external')
    setGrantingConsent(false)
    setConsentNotice(null)
  }, [pluginId, skillId])

  // Fetch OAuth accounts when the plugin is OAuth-backed.
  useEffect(() => {
    if (!oauthProvider) return
    let cancelled = false
    setAccountsLoading(true)
    api.get<{ data: { provider: string; accounts: OAuthAccount[] } }>(
      `/connectors/oauth/accounts?provider=${encodeURIComponent(oauthProvider)}`,
    ).then((res) => {
      if (cancelled) return
      const list = res.data?.data?.accounts ?? []
      // Only show CONNECTED accounts in the picker -- DISCONNECTED /
      // NEEDS_REAUTH rows would just confuse the operator.
      const connected = list.filter(a => a.status === 'CONNECTED')
      setAccounts(connected)
      // Auto-select the only one. If multiple, leave null so the
      // operator must explicitly pick (the run button gates on this).
      if (connected.length === 1) {
        setSelectedOwnerEmail(connected[0].owner_email)
      }
    }).catch(() => {
      if (cancelled) return
      setAccounts([])
    }).finally(() => {
      if (!cancelled) setAccountsLoading(false)
    })
    return () => { cancelled = true }
  }, [oauthProvider])

  const allInputsSupplied = allowlistRow.required_inputs.every(
    f => (inputs[f] ?? '').trim().length > 0,
  )

  // OAuth picker gate:
  //   - non-OAuth plugin -> always satisfied (true)
  //   - OAuth plugin with 0 accounts -> never satisfied
  //   - OAuth plugin with 1 account -> auto-selected
  //   - OAuth plugin with N accounts -> requires explicit selection
  // Note: a NULL owner_email (orphan from failed identity fetch in
  // PR-1) still counts as "selected" if the operator picks it -- the
  // executor will resolve via instance_id/credentials fallback.
  const accountSatisfied =
    !oauthProvider
    || (accounts !== null
        && accounts.length > 0
        && (accounts.length === 1 || selectedOwnerEmail !== null
            || accounts.some(a => a.owner_email === selectedOwnerEmail)))
  const canRun = allInputsSupplied && accountSatisfied && !accountsLoading

  async function handleRun() {
    setSubmitting(true)
    setError(null)
    try {
      // PR-CONN-FRONTEND-ACCOUNT-PROFILE-PICKER (Sprint-5 PR-2):
      // attach `_owner_email` to operator_inputs so the executor's
      // _find_oauth_instance gate can disambiguate when the operator
      // has multiple Google accounts connected. Empty/null owner_email
      // (orphan from failed identity fetch) still gets passed as
      // empty string -- the executor falls back to credentials lookup.
      const operator_inputs: Record<string, string> = { ...inputs }
      if (oauthProvider && selectedOwnerEmail) {
        operator_inputs._owner_email = selectedOwnerEmail
      }
      const res = await api.post<SkillExecutionResultDTO>(
        '/connections/v2/skills/execute',
        {
          plugin_id: pluginId,
          skill_id: skillId,
          operator_inputs,
        },
      )
      setResult(res.data)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response
          ?.data?.detail ?? 'Execute failed'
      setError(String(msg))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleGrantConsent() {
    setGrantingConsent(true)
    setError(null)
    setConsentNotice(null)
    try {
      const grantRes = await api.post<{ data: {
        grant_id: string; expires_at: number;
        write_blocking_active: boolean; operator_notice: string;
      }}>('/connections/v2/skill-consent/grant', {
        plugin_id: pluginId,
        skill_id: skillId,
        category: consentCategory,
      })
      setConsentNotice(grantRes.data?.data?.operator_notice ?? 'Consent recorded.')
      // Re-run the skill so the executor consumes the grant. If the
      // skill is write-class, the read_only defense will still block;
      // the operator will see the new blocked_reason explaining that
      // consent alone doesn't unblock writes.
      setResult(null)
      await handleRun()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response
          ?.data?.detail ?? 'Grant failed'
      setError(String(msg))
    } finally {
      setGrantingConsent(false)
    }
  }

  function handleDraftFollowup() {
    if (!result || !result.tool_calls.length) return
    const tc = result.tool_calls[0]
    const inputLines = Object.entries(inputs)
      .filter(([, v]) => (v ?? '').trim())
      .map(([k, v]) => `- ${k}: ${v.trim()}`)
      .join('\n')
    const followup =
      `I want ${pluginName} to run skill "${humanize(skillId)}". `
      + `It would call read-only tool '${tc.tool_name}' to read: `
      + `${allowlistRow.reads_summary}\n\n`
      + `Inputs I provided:\n${inputLines}\n\n`
      + `Once you can call the tool live, run it and summarize the result. `
      + `Until then, treat this as planning context.`
    draftMessage(followup, {
      surface: 'connections.skill_chip',
      plugin_id: pluginId,
      plugin_name: pluginName,
    })
    toast.success(`Drafted follow-up from ${pluginName} -- opening chat...`)
    onClose()
    setTimeout(() => navigate('/chat'), 80)
  }

  // ── Render ──

  const phaseStatusPill = result && (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
        result.status === 'planned'
          ? 'bg-emerald-500/15 text-emerald-200'
          : result.status === 'needs_inputs'
            ? 'bg-amber-500/15 text-amber-200'
            : 'bg-rose-500/15 text-rose-200'
      }`}
    >
      {result.status}
    </span>
  )

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-midnight-900/80 px-4"
      onClick={onClose}
    >
      <div
        className="max-h-[88vh] w-full max-w-xl overflow-y-auto rounded-xl border border-white/10 bg-midnight-400/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="flex items-start justify-between gap-4 border-b border-white/5 p-5">
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.2em] text-accent-cyan">
              Run read-only skill (Phase 2)
            </p>
            <h2 className="mt-0.5 text-lg font-semibold text-starlight-100">
              {humanize(skillId)}
            </h2>
            <p className="text-xs text-starlight-400">
              {pluginName} - {allowlistRow.backend_surface.toUpperCase()} backend
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

        <div className="space-y-4 p-5">
          {/* What this reads */}
          <section>
            <h3 className="mb-1.5 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
              What Daena will read
            </h3>
            <p className="rounded-md border border-emerald-500/20 bg-emerald-500/[0.04] px-3 py-2 text-[12px] text-emerald-100">
              {allowlistRow.reads_summary}
            </p>
          </section>

          {/* Safety statement.
              Sprint-7 acceptance fix: spelled out per the local-usable brief.
              Read-only, no writes, no deletes, no external network, local only.
              Each phrase is a separate hard rule so the operator can scan it. */}
          <section
            data-testid="skill-execute-safety-statement"
            className="flex items-start gap-2 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2"
          >
            <ShieldCheck size={13} className="mt-0.5 shrink-0 text-emerald-300" />
            <p className="text-[11px] text-starlight-300">
              <strong className="text-starlight-100">
                Read-only. No writes. No deletes. No external network. Local only.
              </strong>{' '}
              Phase 2 runs read-only tools through an allowlist. The backend
              cannot post messages, modify external state, send payments, or
              invoke browser actions on this code path. An audit row is written
              for every attempt.
            </p>
          </section>

          {/* OAuth account picker (Sprint-5 PR-2) */}
          {oauthProvider && !result && (
            <section data-testid="oauth-account-picker">
              <h3 className="mb-1.5 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
                Run as account
              </h3>
              {accountsLoading && (
                <p className="text-[11px] text-starlight-400">
                  Loading connected accounts...
                </p>
              )}
              {!accountsLoading && accounts !== null && accounts.length === 0 && (
                <p className="rounded-md border border-amber-500/30 bg-amber-500/[0.05] px-3 py-2 text-[11px] text-amber-200">
                  No {oauthProvider} account connected. Open the connector and
                  connect your Google account before running this skill.
                </p>
              )}
              {!accountsLoading && accounts !== null && accounts.length === 1 && (
                <p className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/20 bg-emerald-500/[0.05] px-2.5 py-1 text-[11px] text-emerald-100">
                  <User size={11} />
                  {accounts[0].owner_email ?? '(account profile unknown)'}
                </p>
              )}
              {!accountsLoading && accounts !== null && accounts.length > 1 && (
                <div className="space-y-1">
                  <p className="text-[11px] text-starlight-400">
                    Multiple {oauthProvider} accounts are connected. Pick which
                    one Daena should use for this run.
                  </p>
                  {accounts.map((a) => {
                    const label = a.owner_email ?? '(account profile unknown)'
                    const checked = selectedOwnerEmail === a.owner_email
                    return (
                      <label
                        key={a.instance_id}
                        className={`flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-[11px] ${
                          checked
                            ? 'border-primary-500/50 bg-primary-500/10 text-primary-100'
                            : 'border-white/10 bg-white/[0.03] text-starlight-200 hover:bg-white/[0.06]'
                        }`}
                      >
                        <input
                          type="radio"
                          name="oauth-account"
                          value={a.owner_email ?? ''}
                          checked={checked}
                          onChange={() => setSelectedOwnerEmail(a.owner_email)}
                          className="accent-primary-400"
                        />
                        <User size={11} />
                        <span>{label}</span>
                      </label>
                    )
                  })}
                </div>
              )}

              {/* Sprint-6 PR-4: orphan account reclaim. owner_email=NULL
                  rows are usually leftovers from a failed userinfo fetch
                  during the OAuth callback, or pre-Sprint-5 legacy
                  instances. Surface them so the operator can choose to
                  reconnect (safer) or archive the orphan (no row delete;
                  just hides from default lists). */}
              {!accountsLoading && accounts !== null && accounts.some(a => a.owner_email === null) && (
                <OrphanReclaimSection
                  oauthProvider={oauthProvider}
                  accounts={accounts}
                  onArchived={(archivedId) => {
                    setAccounts((prev) =>
                      prev ? prev.filter(a => a.instance_id !== archivedId) : prev,
                    )
                  }}
                />
              )}
            </section>
          )}

          {/* Required inputs */}
          {allowlistRow.required_inputs.length > 0 && !result && (
            <section>
              <h3 className="mb-2 text-[10px] uppercase tracking-[0.16em] text-starlight-500">
                Required inputs
              </h3>
              <div className="space-y-2">
                {allowlistRow.required_inputs.map((field) => (
                  <div key={field}>
                    <label
                      htmlFor={`skill-input-${field}`}
                      className="text-[10px] uppercase tracking-wider text-starlight-500"
                    >
                      {field}
                    </label>
                    <input
                      id={`skill-input-${field}`}
                      type="text"
                      value={inputs[field] ?? ''}
                      onChange={(e) => setInputs((s) => ({ ...s, [field]: e.target.value }))}
                      className="mt-0.5 w-full rounded-md border border-white/10 bg-midnight-500/50 px-2.5 py-1.5 text-sm text-starlight-100 placeholder:text-starlight-600 focus:border-primary-500/50 focus:outline-none"
                      placeholder={`Provide ${field}...`}
                      autoComplete="off"
                      spellCheck={false}
                      disabled={submitting}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Result block */}
          {result && (
            <section>
              <div className="flex items-center justify-between">
                <h3 className="text-[10px] uppercase tracking-[0.16em] text-starlight-500">
                  Result
                </h3>
                {phaseStatusPill}
              </div>
              <p className="mt-1.5 rounded-md border border-white/10 bg-midnight-500/50 px-3 py-2 text-[12px] text-starlight-200">
                {result.summary}
              </p>
              {result.result_preview && (
                <p className="mt-2 text-[11px] text-starlight-400">
                  {result.result_preview}
                </p>
              )}
              {result.tool_calls.length > 0 && (
                <div className="mt-2 rounded-md border border-white/5 bg-white/[0.02] px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wider text-starlight-500">
                    Planned tool call (no real invocation in Phase 2)
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-starlight-200">
                    {result.tool_calls[0].backend_surface.toUpperCase()}.{result.tool_calls[0].tool_name}
                  </p>
                  <p className="mt-1 text-[10px] text-starlight-500">
                    Argument provenance:{' '}
                    {Object.entries(result.tool_calls[0].argument_shape)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(', ')}
                  </p>
                </div>
              )}
              {result.audit_event_id && (
                <p className="mt-2 text-[10px] text-starlight-500">
                  Audit event id: <code>{result.audit_event_id.slice(0, 8)}...</code>
                </p>
              )}
              {result.required_inputs.length > 0 && (
                <p className="mt-2 inline-flex items-start gap-1 rounded-md border border-amber-500/20 bg-amber-500/[0.05] px-2 py-1 text-[11px] text-amber-200">
                  <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                  Missing inputs: {result.required_inputs.join(', ')}
                </p>
              )}
              {result.blocked_reason && (
                <p className="mt-2 inline-flex items-start gap-1 rounded-md border border-rose-500/20 bg-rose-500/[0.05] px-2 py-1 text-[11px] text-rose-200">
                  <Lock size={11} className="mt-0.5 shrink-0" />
                  {result.blocked_reason}
                </p>
              )}
              {/* PR-CONN-CONSENT-API-AND-UI (Sprint-5 PR-4): mint a
                  consent grant when status === 'needs_consent'. Phase 2
                  still blocks writes -- the notice + the post-grant
                  re-run make this transparent to the operator. */}
              {result.status === 'needs_consent' && (
                <div
                  data-testid="consent-grant-form"
                  className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/[0.05] px-3 py-2 text-[11px] text-amber-100 space-y-2"
                >
                  <div className="flex items-start gap-1.5">
                    <ShieldCheck size={11} className="mt-0.5 shrink-0" />
                    <p>
                      <strong>This skill needs consent.</strong>{' '}
                      Granting consent records your approval and lets the
                      executor pass the consent gate. <em>It does NOT
                      enable writes</em> -- Phase 2 still blocks any
                      non-read-only skill via the read_only defense.
                    </p>
                  </div>
                  <div>
                    <label
                      htmlFor="consent-category"
                      className="text-[10px] uppercase tracking-wider text-starlight-500"
                    >
                      Risk category
                    </label>
                    <select
                      id="consent-category"
                      value={consentCategory}
                      onChange={(e) => setConsentCategory(e.target.value)}
                      className="mt-0.5 w-full rounded-md border border-white/10 bg-midnight-500/50 px-2 py-1 text-[11px] text-starlight-100"
                      disabled={grantingConsent}
                    >
                      {CONSENT_CATEGORIES.map((c) => (
                        <option key={c.code} value={c.code}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    onClick={() => void handleGrantConsent()}
                    disabled={grantingConsent}
                    className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/15 px-3 py-1.5 text-[11px] font-medium text-amber-50 hover:bg-amber-500/25 disabled:opacity-40"
                  >
                    {grantingConsent
                      ? <Loader2 size={11} className="animate-spin" />
                      : <ShieldCheck size={11} />}
                    Grant consent (Phase 2 still blocks writes)
                  </button>
                  {consentNotice && (
                    <p className="text-[10px] text-amber-200">
                      {consentNotice}
                    </p>
                  )}
                </div>
              )}
            </section>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-2.5 py-1.5 text-[11px] text-rose-200">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Footer actions */}
          <footer className="flex items-center justify-between gap-2 border-t border-white/5 pt-3">
            <span className="text-[10px] text-starlight-500">
              Phase 2 spine: planned-only. Real tool invocation arms in
              follow-up PRs.
            </span>
            <div className="flex items-center gap-2">
              {result?.status === 'planned' && (
                <button
                  onClick={handleDraftFollowup}
                  className="inline-flex items-center gap-1.5 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-3 py-1.5 text-[11px] font-medium text-accent-cyan hover:bg-accent-cyan/20"
                >
                  Draft follow-up in chat <ArrowRight size={11} />
                </button>
              )}
              {!result && (
                <button
                  onClick={() => void handleRun()}
                  disabled={submitting || !canRun}
                  className="inline-flex items-center gap-1.5 rounded-md border border-primary-500/40 bg-primary-500/15 px-3 py-1.5 text-[11px] font-medium text-primary-100 hover:bg-primary-500/25 disabled:opacity-40"
                  title={
                    !allInputsSupplied
                      ? 'Fill in all required inputs.'
                      : oauthProvider && (accounts?.length ?? 0) === 0
                        ? `No ${oauthProvider} account is connected.`
                        : oauthProvider && (accounts?.length ?? 0) > 1 && !selectedOwnerEmail
                          ? `Pick which ${oauthProvider} account to use.`
                          : 'Run the skill.'
                  }
                >
                  {submitting ? (
                    <Loader2 size={11} className="animate-spin" />
                  ) : (
                    <Play size={11} />
                  )}
                  Run read-only skill
                </button>
              )}
            </div>
          </footer>
        </div>
      </div>
    </div>
  )
}


// ──────────────────────────────────────────────────────────────────
// Sprint-6 PR-4: OrphanReclaimSection
// ──────────────────────────────────────────────────────────────────
//
// Renders one row per ConnectorInstance with owner_email=NULL. The
// operator can:
//   * Reconnect: opens the existing OAuth start endpoint in a new
//     tab (same-tab redirect would lose modal state).
//   * Archive orphan: posts to the existing
//     /connections/instances/{id}/archive endpoint with
//     {confirm: true}. The backend marks the row ARCHIVED (no row
//     deletion -- per founder rule, archive is the strongest
//     soft-removal lane).
//
// Confirmation: an inline window.confirm() is the simplest two-step
// gate that still works inside the modal context. The backend ALSO
// requires {confirm: true} -- two-layer defense, same as the
// existing OAuthLifecyclePanel disconnect/archive flow.

function OrphanReclaimSection({
  oauthProvider, accounts, onArchived,
}: {
  oauthProvider: string
  accounts: OAuthAccount[]
  onArchived: (archivedInstanceId: string) => void
}) {
  const orphans = accounts.filter(a => a.owner_email === null)
  if (orphans.length === 0) return null

  async function handleArchive(instanceId: string) {
    const ok = window.confirm(
      'Archive this orphan account? It will be hidden from default lists '
      + 'but the row is preserved (no delete).',
    )
    if (!ok) return
    try {
      await api.post(`/connections/instances/${instanceId}/archive`, {
        confirm: true,
      })
      onArchived(instanceId)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail ?? 'Archive failed'
      window.alert(`Archive failed: ${msg}`)
    }
  }

  function handleReconnect() {
    // Open a new tab so the modal state is preserved. The existing
    // OAuth start endpoint redirects through the provider; on
    // success a new ConnectorInstance is created with the captured
    // owner_email (Sprint-5 PR-1).
    const url = `/api/v1/connectors/${encodeURIComponent(oauthProvider)}/oauth/start`
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div
      data-testid="orphan-reclaim-section"
      className="mt-3 rounded-md border border-slate-500/20 bg-slate-500/[0.04] px-3 py-2"
    >
      <h4 className="text-[10px] uppercase tracking-wider text-slate-300">
        Orphan accounts ({orphans.length})
      </h4>
      <p className="mt-1 text-[11px] text-starlight-400">
        These rows lost their account profile (failed userinfo fetch
        or pre-Sprint-5 legacy). Reconnect to capture the email, or
        archive to hide them from the picker.
      </p>
      <ul className="mt-2 space-y-1">
        {orphans.map((o) => (
          <li
            key={o.instance_id}
            className="flex items-center justify-between gap-2 rounded-md border border-white/5 bg-white/[0.02] px-2 py-1.5"
          >
            <div className="min-w-0">
              <p className="text-[11px] text-starlight-200">
                Unknown account profile
              </p>
              <p className="truncate text-[10px] text-starlight-500">
                {o.instance_id} - status: {o.status}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button
                onClick={handleReconnect}
                className="rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-2 py-0.5 text-[10px] text-accent-cyan hover:bg-accent-cyan/20"
              >
                Reconnect
              </button>
              <button
                onClick={() => void handleArchive(o.instance_id)}
                className="rounded-md border border-rose-500/30 bg-rose-500/[0.08] px-2 py-0.5 text-[10px] text-rose-200 hover:bg-rose-500/[0.15]"
              >
                Archive orphan
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
