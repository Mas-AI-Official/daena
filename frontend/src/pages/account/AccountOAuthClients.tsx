/**
 * AccountOAuthClients -- OAuth client_id + client_secret paste-and-save
 * surface.
 *
 * PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS (2026-05-03):
 * Sibling of AccountProviderKeys (LLM API keys). This component manages
 * the OAuth APP credentials (client_id + client_secret) that Daena
 * needs to start consent flows for Google / GitHub / Slack / Figma /
 * Canva. Without these, OAuth-backed plugin cards stay stuck on
 * "Configure" forever -- with these, the card flips to "Connect" and
 * the operator can run the consent popup.
 *
 * Honesty rules:
 *  - GET /account/oauth-clients returns ``configured: bool`` +
 *    ``client_id_present: bool`` + ``last_updated`` only. NEVER the
 *    secret. NEVER the client_id value either (only the presence bit).
 *  - POST /account/oauth-clients/{slug} accepts {client_id,
 *    client_secret} and stores both atomically. Response shape carries
 *    metadata only, never the values.
 *  - Save dispatches ``daena:retry-pending`` so the marketplace cards
 *    hook re-fetches and the OAuth-backed cards flip Configure ->
 *    Connect without a manual reload.
 *  - This component does NOT start the OAuth flow. The operator clicks
 *    Connect on the marketplace card next, which opens
 *    OAuthConnectDrawer. Two-step UX so a wrong client_id doesn't
 *    immediately open a popup that errors.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle, Check, ExternalLink, Eye, EyeOff, KeyRound,
  Loader2, Save, ShieldCheck, Trash2,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'

interface OAuthClientRow {
  slug: string
  display_name: string
  client_id_field: string
  client_secret_field: string
  provider_ids: string[]
  console_url: string
  client_id_hint: string
  configured: boolean
  client_id_present: boolean
  last_updated: string
}

interface SaveResponse {
  success: boolean
  slug: string
  configured: boolean
  client_id_present: boolean
  last_updated: string
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

interface DraftPair {
  client_id: string
  client_secret: string
}

const EMPTY_DRAFT: DraftPair = { client_id: '', client_secret: '' }

export function AccountOAuthClients() {
  const [rows, setRows] = useState<OAuthClientRow[]>([])
  const [loading, setLoading] = useState(true)
  const [drafts, setDrafts] = useState<Record<string, DraftPair>>({})
  const [revealSecret, setRevealSecret] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [clearing, setClearing] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const fetchRows = useCallback(async () => {
    try {
      const res = await api.get<OAuthClientRow[]>('/account/oauth-clients')
      setRows(res.data)
    } catch {
      toast.error('Failed to load OAuth client config')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchRows() }, [fetchRows])

  // Mirror AccountProviderKeys: scroll into view if the URL anchor
  // points at us. The Configure deep-link from /connections's OAuth
  // drawer lands here with hash ``#oauth-clients``.
  useEffect(() => {
    if (window.location.hash === '#oauth-clients') {
      const el = document.getElementById('oauth-clients')
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
      }
    }
  }, [])

  function getDraft(slug: string): DraftPair {
    return drafts[slug] ?? EMPTY_DRAFT
  }

  function updateDraft(slug: string, patch: Partial<DraftPair>) {
    setDrafts((d) => ({
      ...d,
      [slug]: { ...(d[slug] ?? EMPTY_DRAFT), ...patch },
    }))
    if (errors[slug]) {
      setErrors((er) => ({ ...er, [slug]: '' }))
    }
  }

  async function handleSave(row: OAuthClientRow) {
    const draft = getDraft(row.slug)
    const cid = draft.client_id.trim()
    const csec = draft.client_secret.trim()
    if (!cid || !csec) {
      setErrors((e) => ({
        ...e,
        [row.slug]: 'Paste both the client_id and the client_secret.',
      }))
      return
    }
    setSaving(row.slug)
    setErrors((e) => ({ ...e, [row.slug]: '' }))
    try {
      const res = await api.post<SaveResponse>(
        `/account/oauth-clients/${row.slug}`,
        { client_id: cid, client_secret: csec },
      )
      const data = res.data
      if (!data.success) {
        setErrors((e) => ({
          ...e,
          [row.slug]: 'Save failed.',
        }))
        return
      }
      // Wipe drafts + reveal -- never keep saved values in component state.
      setDrafts((d) => ({ ...d, [row.slug]: { ...EMPTY_DRAFT } }))
      setRevealSecret((r) => ({ ...r, [row.slug]: false }))
      toast.success(`${row.display_name} OAuth client saved`)
      // Refresh local rows + notify the marketplace hook so OAuth
      // cards flip Configure -> Connect without a manual reload.
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

  async function handleClear(row: OAuthClientRow) {
    if (!row.configured && !row.client_id_present) return
    setClearing(row.slug)
    try {
      await api.delete(`/account/oauth-clients/${row.slug}`)
      toast.success(`${row.display_name} OAuth client cleared`)
      void fetchRows()
      window.dispatchEvent(new CustomEvent('daena:retry-pending'))
    } catch {
      toast.error(`Failed to clear ${row.display_name} client`)
    } finally {
      setClearing(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl bg-gradient-to-br from-amber-500/10 to-emerald-500/10 border border-amber-500/20 max-w-2xl">
        <div className="flex items-start gap-3">
          <ShieldCheck size={18} className="text-amber-300 mt-0.5" />
          <div>
            <h3 className="text-sm font-medium text-starlight-100">
              OAuth client config
            </h3>
            <p className="text-xs text-starlight-400 mt-1">
              Paste the OAuth client_id + client_secret you registered on
              each provider's developer console. Daena uses these to
              start consent flows when you click <strong>Connect</strong>{' '}
              on an OAuth-backed plugin card.{' '}
              <strong className="text-starlight-200">
                OAuth client secrets are stored securely and never
                displayed after saving.
              </strong>
            </p>
            <p className="text-[10px] text-starlight-500 mt-2">
              Storage: file-backed (gitignored, chmod 0600 on POSIX).
              Vault migration is planned -- see ADR-002 D-003. Tokens
              from the consent flow live separately in the encrypted
              ConnectorInstance.credentials column.
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2 max-w-2xl">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 rounded-lg bg-midnight-300/30 animate-pulse" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-white/5 px-6 py-8 text-center text-sm text-starlight-400 max-w-2xl">
          No OAuth providers loaded.
        </div>
      ) : (
        <div className="space-y-3 max-w-2xl">
          {rows.map((row) => {
            const draft = getDraft(row.slug)
            const isRevealed = revealSecret[row.slug] ?? false
            const isSaving = saving === row.slug
            const isClearing = clearing === row.slug
            const error = errors[row.slug] ?? ''
            const partial = row.client_id_present && !row.configured

            return (
              <div
                key={row.slug}
                className={`rounded-xl border p-4 ${
                  row.configured
                    ? 'border-emerald-500/20 bg-emerald-500/[0.04]'
                    : partial
                      ? 'border-amber-500/20 bg-amber-500/[0.04]'
                      : 'border-white/5 bg-midnight-300/30'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <KeyRound size={14} className="text-starlight-500 shrink-0" />
                      <h4 className="text-sm font-medium text-starlight-100">
                        {row.display_name}
                      </h4>
                      {row.configured ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-200">
                          <Check size={10} /> Configured
                        </span>
                      ) : partial ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-200">
                          Half-configured (secret missing)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-200">
                          Not configured
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-[11px] text-starlight-500">
                      Powers{' '}
                      <span className="text-starlight-400">
                        {row.provider_ids.join(', ')}
                      </span>
                      {row.configured && row.last_updated ? (
                        <span> · saved {relativeTime(row.last_updated)}</span>
                      ) : null}
                    </p>
                  </div>
                  {row.console_url && (
                    <a
                      href={row.console_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] text-starlight-500 hover:text-starlight-300 shrink-0"
                      title="Open provider developer console"
                    >
                      <ExternalLink size={11} /> Console
                    </a>
                  )}
                </div>

                {/* client_id paste row */}
                <div className="mt-3">
                  <label className="text-[10px] uppercase tracking-wider text-starlight-500">
                    client_id
                  </label>
                  <input
                    type="text"
                    value={draft.client_id}
                    onChange={(e) => updateDraft(row.slug, { client_id: e.target.value })}
                    placeholder={
                      row.client_id_present
                        ? 'Paste a fresh client_id to replace (saved value is hidden)'
                        : `Paste ${row.display_name} client_id (e.g. ${row.client_id_hint})`
                    }
                    className="mt-1 w-full rounded-lg border border-white/10 bg-midnight-400/50 py-2 px-3 text-sm text-starlight-100 placeholder:text-starlight-600 font-mono focus:border-primary-500/50 focus:outline-none"
                    autoComplete="off"
                    spellCheck={false}
                  />
                </div>

                {/* client_secret paste row (with reveal toggle) */}
                <div className="mt-3">
                  <label className="text-[10px] uppercase tracking-wider text-starlight-500">
                    client_secret
                  </label>
                  <div className="relative mt-1">
                    <input
                      type={isRevealed ? 'text' : 'password'}
                      value={draft.client_secret}
                      onChange={(e) => updateDraft(row.slug, { client_secret: e.target.value })}
                      placeholder={
                        row.configured
                          ? 'Paste a fresh client_secret to replace (saved value is hidden)'
                          : 'Paste client_secret'
                      }
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && draft.client_id.trim() && draft.client_secret.trim()) {
                          void handleSave(row)
                        }
                      }}
                      className="w-full rounded-lg border border-white/10 bg-midnight-400/50 py-2 pl-3 pr-10 text-sm text-starlight-100 placeholder:text-starlight-600 font-mono focus:border-primary-500/50 focus:outline-none"
                      autoComplete="off"
                      spellCheck={false}
                    />
                    {draft.client_secret.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setRevealSecret((r) => ({ ...r, [row.slug]: !isRevealed }))}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-starlight-500 hover:text-starlight-300"
                        title={isRevealed ? 'Hide' : 'Reveal'}
                      >
                        {isRevealed ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    )}
                  </div>
                </div>

                {/* Action row */}
                <div className="mt-3 flex items-center justify-end gap-2">
                  <button
                    onClick={() => void handleSave(row)}
                    disabled={isSaving || !draft.client_id.trim() || !draft.client_secret.trim()}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary-500 text-white text-xs font-medium hover:bg-primary-600 disabled:opacity-40 transition-colors"
                  >
                    {isSaving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                    Save
                  </button>
                  {(row.configured || row.client_id_present) && (
                    <button
                      onClick={() => void handleClear(row)}
                      disabled={isClearing}
                      className="p-2 rounded-lg border border-white/5 text-starlight-500 hover:bg-rose-500/10 hover:text-rose-300 hover:border-rose-500/30 disabled:opacity-40 transition-colors"
                      title={`Clear ${row.display_name} OAuth client`}
                    >
                      {isClearing ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                    </button>
                  )}
                </div>

                {error && (
                  <div className="mt-2 flex items-start gap-2 rounded-md border border-rose-500/30 bg-rose-500/5 px-2.5 py-1.5 text-[11px] text-rose-200">
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

export default AccountOAuthClients
