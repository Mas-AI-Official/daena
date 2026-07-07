/**
 * AccountProviderKeys -- LLM provider key paste-and-save surface.
 *
 * PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT (2026-05-03):
 * Sibling of AccountApiKeys (which manages Daena's OUTBOUND dna_ keys
 * for the public API surface). This component manages the INBOUND
 * provider keys Daena uses to call upstream LLMs.
 *
 * Honesty rules:
 *  - GET /account/provider-keys returns ``configured: bool`` +
 *    ``last_updated`` only. Never the value.
 *  - POST /account/provider-keys/{slug} validates via the provider's
 *    real health check BEFORE persisting. A bad key never lands in
 *    the store.
 *  - The component NEVER asks the backend to echo back a saved value.
 *    "Edit" simply means "paste a fresh key." Trash clears.
 *  - After Save, dispatch ``daena:retry-pending`` so the marketplace
 *    cards hook refreshes and the Configure button flips to Test
 *    without a manual reload.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, Check, ExternalLink, Eye, EyeOff, KeyRound,
  Loader2, Save, ShieldCheck, Sparkles, Trash2,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { confirmDialog } from '@/stores/confirmStore'
import { useConnectionsV2 } from '@/hooks/useConnectionsV2'

interface ProviderKeyRow {
  slug: string
  settings_field: string
  display_name: string
  marketplace_id: string
  key_hint: string
  configured: boolean
  last_updated: string
}

interface SaveResponse {
  success: boolean
  slug: string
  configured: boolean
  health: string
  models_discovered: number
  failure_reason: string | null
  last_updated: string | null
}

const PROVIDER_DOC_URL: Record<string, string> = {
  anthropic: 'https://console.anthropic.com/settings/keys',
  openai: 'https://platform.openai.com/api-keys',
  gemini: 'https://aistudio.google.com/app/apikey',
  groq: 'https://console.groq.com/keys',
  perplexity: 'https://www.perplexity.ai/settings/api',
  openrouter: 'https://openrouter.ai/keys',
  together: 'https://api.together.xyz/settings/api-keys',
}

function relativeTime(iso: string): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (!Number.isFinite(t)) return ''
  const delta = Date.now() - t
  if (delta < 60_000) return 'just now'
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m ago`
  if (delta < 86_400_000) return `${Math.floor(delta / 3_600_000)}h ago`
  return new Date(iso).toLocaleDateString()
}

/**
 * CliSubscriptionHint -- PR-CONNECTIONS-FIX-4 (2026-05-06).
 *
 * Anthropic / OpenAI / Gemini paste-an-API-key flow is the wrong path
 * for operators who already have the corresponding CLI runtime
 * authenticated as a subscription (Claude Code, Codex CLI, Gemini
 * CLI). Detect that case from V2 truth and surface a clear "you
 * already have this — go to Connections > Brain" hint instead of
 * silently making them paste a key they don't need.
 *
 * Maps:
 *   anthropic -> Claude Code (subscription)
 *   openai    -> Codex CLI (subscription)
 *   gemini    -> Gemini CLI (subscription)
 */
function CliSubscriptionHint() {
  const { rows: cliRows } = useConnectionsV2('cli_runtime')
  const callable = useMemo(() => {
    const out: { provider: string; cli_label: string }[] = []
    const map: Record<string, string> = {
      claude_code: 'Claude Code subscription (Pro / Max)',
      codex: 'Codex CLI (ChatGPT Plus / Pro)',
      gemini_cli: 'Gemini CLI',
    }
    const providerOf: Record<string, string> = {
      claude_code: 'Anthropic',
      codex: 'OpenAI',
      gemini_cli: 'Google Gemini',
    }
    for (const r of cliRows) {
      const rid = String(r.config?._runtime_id || r.slug || '').toLowerCase()
      if (r.label !== 'healthy' && r.label !== 'healthy_stale') continue
      if (map[rid]) {
        out.push({ provider: providerOf[rid], cli_label: map[rid] })
      }
    }
    return out
  }, [cliRows])

  if (callable.length === 0) return null

  return (
    <div
      className="p-4 rounded-xl bg-gradient-to-br from-violet-500/10 to-cyan-500/10 border border-violet-500/20 max-w-2xl"
      data-testid="cli-subscription-hint"
    >
      <div className="flex items-start gap-3">
        <Sparkles size={18} className="text-violet-300 mt-0.5" />
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-starlight-100">
            You already have a callable CLI subscription — no API key
            needed
          </h3>
          <ul className="mt-1 space-y-0.5 text-xs text-starlight-300">
            {callable.map((c) => (
              <li key={c.provider}>
                <span className="text-violet-200">{c.provider}</span> is
                already callable through{' '}
                <span className="font-mono text-starlight-100">
                  {c.cli_label}
                </span>
                .
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-starlight-400 mt-2">
            Pasting an API key below is a separate path. If you only
            want Daena to use your subscription, skip this page and{' '}
            <Link
              to="/connections"
              className="text-violet-200 underline decoration-dotted hover:text-starlight-100"
            >
              pick the CLI as your Main Brain on the Connections page
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  )
}


export function AccountProviderKeys() {
  const [rows, setRows] = useState<ProviderKeyRow[]>([])
  const [loading, setLoading] = useState(true)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [reveal, setReveal] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [clearing, setClearing] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [loadError, setLoadError] = useState<string | null>(null)

  const fetchRows = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const res = await api.get<ProviderKeyRow[]>('/account/provider-keys')
      setRows(res.data)
    } catch {
      setRows([])
      setLoadError('We could not load your provider keys. Retry to refresh.')
      toast.error('Failed to load provider keys')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchRows() }, [fetchRows])

  // After mount, scroll the section into view if the URL points at us.
  // The Configure deep-link from /connections lands here with hash
  // ``#provider-keys``; AccountPage owns the anchor element id.
  useEffect(() => {
    if (window.location.hash === '#provider-keys') {
      const el = document.getElementById('provider-keys')
      if (el) {
        // Defer one tick so Suspense lazy-load completes the layout.
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
      }
    }
  }, [])

  async function handleSave(row: ProviderKeyRow) {
    const draft = (drafts[row.slug] ?? '').trim()
    if (!draft) {
      setErrors((e) => ({ ...e, [row.slug]: 'Paste a key first.' }))
      return
    }
    setSaving(row.slug)
    setErrors((e) => ({ ...e, [row.slug]: '' }))
    try {
      const res = await api.post<SaveResponse>(
        `/account/provider-keys/${row.slug}`,
        { api_key: draft, test_after_save: true },
      )
      const data = res.data
      if (!data.success) {
        setErrors((e) => ({
          ...e,
          [row.slug]: data.failure_reason || 'Provider rejected the key.',
        }))
        return
      }
      // Wipe the draft + reveal -- never keep a saved key in component state.
      setDrafts((d) => ({ ...d, [row.slug]: '' }))
      setReveal((r) => ({ ...r, [row.slug]: false }))
      toast.success(
        `${row.display_name} key saved -- ${data.models_discovered} models discovered`
      )
      // Refresh local rows and notify the marketplace hook so the card
      // flips Configure -> Test without a manual reload.
      void fetchRows()
      window.dispatchEvent(new CustomEvent('daena:retry-pending'))
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response
          ?.data?.detail ?? 'Save failed'
      setErrors((e) => ({ ...e, [row.slug]: String(detail) }))
    } finally {
      setSaving(null)
    }
  }

  async function handleClear(row: ProviderKeyRow) {
    if (!row.configured) return
    const ok = await confirmDialog({
      title: `Clear the stored ${row.display_name} key?`,
      message: `Daena will immediately stop calling ${row.display_name} until you paste a new key. The stored secret is removed and cannot be recovered -- you would need the original key to re-enter it.`,
      confirmLabel: 'Clear key',
      variant: 'danger',
    })
    if (!ok) return
    setClearing(row.slug)
    try {
      await api.delete(`/account/provider-keys/${row.slug}`)
      toast.success(`${row.display_name} key cleared`)
      void fetchRows()
      window.dispatchEvent(new CustomEvent('daena:retry-pending'))
    } catch {
      toast.error(`Failed to clear ${row.display_name} key`)
    } finally {
      setClearing(null)
    }
  }

  return (
    <div className="space-y-6">
      <CliSubscriptionHint />

      <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-500/10 to-cyan-500/10 border border-emerald-500/20 max-w-2xl">
        <div className="flex items-start gap-3">
          <ShieldCheck size={18} className="text-emerald-300 mt-0.5" />
          <div>
            <h3 className="text-sm font-medium text-starlight-100">
              Provider keys
            </h3>
            <p className="text-xs text-starlight-400 mt-1">
              Paste keys for the LLM providers Daena should call.
              <strong className="text-starlight-200"> Keys are stored
              securely. Daena never displays saved key values.</strong>{' '}
              Saved keys are validated by the provider's health check
              before persisting -- a bad key is rejected and not stored.
            </p>
            <p className="text-[10px] text-starlight-500 mt-2">
              Storage: file-backed (gitignored, chmod 0600 on POSIX).
              Vault migration is planned -- see ADR-002 D-003.
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2 max-w-2xl">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-lg bg-midnight-300/30 animate-pulse" />
          ))}
        </div>
      ) : loadError ? (
        <div className="rounded-lg border border-rose-500/20 bg-rose-500/5 px-6 py-8 text-center max-w-2xl">
          <AlertTriangle size={20} className="mx-auto text-rose-300 mb-2" />
          <p className="text-sm text-rose-200">{loadError}</p>
          <button
            onClick={() => void fetchRows()}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-500/30 text-xs text-rose-200 hover:bg-rose-500/10 cursor-pointer"
          >
            Retry
          </button>
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-white/5 px-6 py-8 text-center text-sm text-starlight-400 max-w-2xl">
          No providers loaded.
        </div>
      ) : (
        <div className="space-y-3 max-w-2xl">
          {rows.map((row) => {
            const draft = drafts[row.slug] ?? ''
            const isRevealed = reveal[row.slug] ?? false
            const isSaving = saving === row.slug
            const isClearing = clearing === row.slug
            const error = errors[row.slug] ?? ''

            return (
              <div
                key={row.slug}
                className={`rounded-xl border p-4 ${
                  row.configured
                    ? 'border-emerald-500/20 bg-emerald-500/[0.04]'
                    : 'border-white/5 bg-midnight-300/30'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <KeyRound size={14} className="text-starlight-500 shrink-0" />
                      <h4 className="text-sm font-medium text-starlight-100">
                        {row.display_name}
                      </h4>
                      {row.configured ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-200">
                          <Check size={10} /> Configured
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-200">
                          Not configured
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-[11px] text-starlight-500">
                      Settings field <code className="text-starlight-400">{row.settings_field}</code>
                      {row.configured && row.last_updated ? (
                        <span> · saved {relativeTime(row.last_updated)}</span>
                      ) : null}
                    </p>
                  </div>
                  {PROVIDER_DOC_URL[row.slug] && (
                    <a
                      href={PROVIDER_DOC_URL[row.slug]}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] text-starlight-500 hover:text-starlight-300"
                      title="Open provider key page"
                    >
                      <ExternalLink size={11} /> Get key
                    </a>
                  )}
                </div>

                <div className="mt-3 flex items-center gap-2">
                  <div className="relative flex-1">
                    <input
                      type={isRevealed ? 'text' : 'password'}
                      value={draft}
                      aria-label={`${row.display_name} API key`}
                      onChange={(e) => {
                        setDrafts((d) => ({ ...d, [row.slug]: e.target.value }))
                        if (errors[row.slug]) {
                          setErrors((er) => ({ ...er, [row.slug]: '' }))
                        }
                      }}
                      placeholder={
                        row.configured
                          ? 'Paste a fresh key to replace (saved key is hidden)'
                          : `Paste ${row.display_name} key (e.g. ${row.key_hint})`
                      }
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && draft.trim()) void handleSave(row)
                      }}
                      className="w-full rounded-lg border border-white/10 bg-midnight-400/50 py-2 pl-3 pr-10 text-sm text-starlight-100 placeholder:text-starlight-600 font-mono focus:border-primary-500/50 focus:outline-none"
                      autoComplete="off"
                      spellCheck={false}
                    />
                    {draft.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setReveal((r) => ({ ...r, [row.slug]: !isRevealed }))}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-starlight-500 hover:text-starlight-300"
                        title={isRevealed ? 'Hide' : 'Reveal'}
                      >
                        {isRevealed ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => void handleSave(row)}
                    disabled={isSaving || isClearing || !draft.trim()}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary-500 text-white text-xs font-medium hover:bg-primary-600 disabled:opacity-40 transition-colors"
                  >
                    {isSaving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                    Save
                  </button>
                  {row.configured && (
                    <button
                      onClick={() => void handleClear(row)}
                      disabled={isClearing || isSaving}
                      className="p-2 rounded-lg border border-white/5 text-starlight-500 hover:bg-rose-500/10 hover:text-rose-300 hover:border-rose-500/30 disabled:opacity-40 transition-colors"
                      title={`Clear ${row.display_name} key`}
                    >
                      {isClearing ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                    </button>
                  )}
                </div>

                {error && (
                  <div
                    role="alert"
                    className="mt-2 flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-2.5 py-1.5 text-[11px] text-rose-200"
                  >
                    <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default AccountProviderKeys
