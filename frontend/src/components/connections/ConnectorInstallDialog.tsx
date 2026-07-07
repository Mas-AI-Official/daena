/**
 * ConnectorInstallDialog
 *
 * Codex-style install card. One dialog, three install paths under the
 * hood (oauth_managed / mcp_remote_oauth / api_token / none). Owns the
 * fetch of `/connectors/{slug}/install/info`, the install button, and
 * the inline token form for api_token connectors.
 *
 * Layout mirrors the Codex "Install Cloudflare" picture: brand logo +
 * Daena logo at top with a connector dot, display name, developer
 * subtitle, About copy, Includes section (Skills + MCP servers),
 * Capabilities pills, big Install button.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X,
  Plug,
  Loader2,
  ShieldCheck,
  ExternalLink,
  Key,
  CheckCircle2,
  Sparkles,
  Wrench,
} from 'lucide-react'
import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import { CONNECTOR_ICONS } from '@/components/icons/BrandIcons'
import {
  startInstall,
  completeApiTokenInstall,
  type InstallStartResponse,
} from '@/pages/connections/installFlow'

interface CatalogSkill {
  id: string
  name: string
  description?: string
  source?: string
}

interface CatalogInterface {
  displayName?: string
  shortDescription?: string
  longDescription?: string
  developerName?: string
  websiteURL?: string
  privacyPolicyURL?: string
  termsOfServiceURL?: string
  brandColor?: string
  capabilities?: string[]
  defaultPrompts?: string[] | string
  logoPath?: string
}

interface CatalogConnector {
  name: string
  slug: string
  description?: string
  category?: string
  interface?: CatalogInterface
  skills?: CatalogSkill[]
  mcp_servers?: Record<string, { type?: string; url?: string; note?: string }>
  auth?: { method?: string; token_settings_url?: string }
  tools?: Array<string | { name: string; description?: string }>
}

interface Props {
  slug: string | null
  open: boolean
  onClose: () => void
  onConnected?: (slug: string) => void
}

export default function ConnectorInstallDialog({ slug, open, onClose, onConnected }: Props) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<CatalogConnector | null>(null)
  const [installing, setInstalling] = useState(false)
  const [tokenForm, setTokenForm] = useState<InstallStartResponse['form'] | null>(null)
  const [tokenValues, setTokenValues] = useState<Record<string, string>>({})
  const [submittingToken, setSubmittingToken] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  // PR-A11Y-PHASE43: dialog keyboard semantics -- Escape closes (WCAG 2.1.2);
  // focus moves into the panel on open and returns to the opener on close
  // (WCAG 2.4.3). Mirrors the house Modal primitive (components/common/Modal.tsx).
  useEffect(() => {
    if (!open) return
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [open, onClose])

  useEffect(() => {
    if (!open) return
    previousFocusRef.current = document.activeElement as HTMLElement | null
    const focusTimer = setTimeout(() => {
      const panel = panelRef.current
      if (panel && !panel.contains(document.activeElement)) panel.focus()
    }, 50)
    return () => { clearTimeout(focusTimer); previousFocusRef.current?.focus?.() }
  }, [open])

  useEffect(() => {
    if (!open || !slug) {
      setData(null)
      setTokenForm(null)
      setTokenValues({})
      return
    }
    setLoading(true)
    api.get(`/connectors/${slug}/install/info`)
      .then((res) => setData(res.data as CatalogConnector))
      .catch((err) => {
        const msg = err instanceof Error ? err.message : 'Failed to load connector'
        toast.error(`Could not load connector info: ${msg}`)
        onClose()
      })
      .finally(() => setLoading(false))
  }, [open, slug, onClose])

  const Icon = useMemo(() => {
    if (!slug) return Plug
    return CONNECTOR_ICONS[slug] || Plug
  }, [slug])

  const brandColor = data?.interface?.brandColor || '#7B6CFF'
  const displayName = data?.interface?.displayName || data?.name || slug || 'Connector'
  const developer = data?.interface?.developerName || data?.name || ''
  const longDesc = data?.interface?.longDescription || data?.description || ''
  const skills = data?.skills || []
  const mcp = data?.mcp_servers ? Object.values(data.mcp_servers)[0] : null
  const caps = data?.interface?.capabilities || []
  const prompts = (() => {
    const p = data?.interface?.defaultPrompts
    if (!p) return []
    return Array.isArray(p) ? p : [p]
  })()

  const handleInstall = async () => {
    if (!slug || !data) return
    setInstalling(true)
    setTokenForm(null)
    setTokenValues({})
    const response = await startInstall(slug, displayName, {
      onSuccess: () => {
        setInstalling(false)
        onConnected?.(slug)
        onClose()
      },
      onError: () => setInstalling(false),
      onShowTokenForm: (form) => {
        setTokenForm(form)
        setTokenValues({})
        setInstalling(false)
      },
    })
    if (!response || response.popup) setInstalling(false)
  }

  const handleTokenSubmit = async () => {
    if (!slug || !tokenForm) return
    // Validate required fields are filled in the dialog.
    const missing = tokenForm.fields
      .filter((f) => f.required !== false && !tokenValues[f.key]?.trim())
      .map((f) => f.label)
    if (missing.length) {
      toast.error(`Fill in: ${missing.join(', ')}`)
      return
    }
    setSubmittingToken(true)
    const ok = await completeApiTokenInstall(slug, displayName, tokenValues, {
      onSuccess: () => {
        onConnected?.(slug)
        onClose()
      },
    })
    setSubmittingToken(false)
    if (!ok) return
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={data ? `Install ${data.interface?.displayName ?? data.name}` : 'Install connector'}
            tabIndex={-1}
            className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-midnight-500 border border-white/10 shadow-2xl focus:outline-none"
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 320, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close */}
            <button
              type="button"
              onClick={onClose}
              className="absolute top-4 right-4 p-2 rounded-lg text-starlight-400 hover:bg-white/5 hover:text-starlight-100 transition-colors z-10"
              aria-label="Close"
            >
              <X size={18} />
            </button>

            {loading ? (
              <div className="p-12 flex items-center justify-center text-starlight-400">
                <Loader2 className="animate-spin mr-3" size={20} />
                Loading connector...
              </div>
            ) : !data ? null : (
              <>
                {/* Header band: brand + Daena handshake */}
                <div
                  className="px-8 pt-8 pb-6 rounded-t-2xl border-b border-white/5"
                  style={{
                    background: `linear-gradient(135deg, ${brandColor}18 0%, transparent 80%)`,
                  }}
                >
                  <div className="flex items-center gap-3 mb-5">
                    <div className="w-12 h-12 rounded-xl bg-midnight-400 flex items-center justify-center border border-white/10">
                      <Sparkles size={22} className="text-primary-400" />
                    </div>
                    <div className="flex items-center gap-1 text-starlight-500">
                      <span className="w-1 h-1 rounded-full bg-starlight-500" />
                      <span className="w-1 h-1 rounded-full bg-starlight-500" />
                      <span className="w-1 h-1 rounded-full bg-starlight-500" />
                    </div>
                    <div
                      className="w-12 h-12 rounded-xl flex items-center justify-center border border-white/10"
                      style={{ backgroundColor: `${brandColor}1f` }}
                    >
                      <Icon size={22} style={{ color: brandColor }} />
                    </div>
                  </div>
                  <h2 className="text-2xl font-semibold text-starlight-100">
                    Install {displayName}
                  </h2>
                  {developer ? (
                    <p className="text-sm text-starlight-400 mt-1">
                      Developed by {developer}
                    </p>
                  ) : null}
                </div>

                {/* Body */}
                <div className="px-8 py-6 space-y-6">
                  {/* Identity row */}
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    {developer ? (
                      <span className="px-2.5 py-1 rounded-md bg-white/5 text-starlight-300">
                        By {developer}
                      </span>
                    ) : null}
                    {data.category ? (
                      <span className="px-2.5 py-1 rounded-md bg-white/5 text-starlight-300">
                        Category: {data.category}
                      </span>
                    ) : null}
                    {caps.length ? (
                      <span className="px-2.5 py-1 rounded-md bg-primary-500/10 text-primary-300 border border-primary-500/20">
                        {caps.join(' + ')}
                      </span>
                    ) : null}
                  </div>

                  {/* About */}
                  {longDesc ? (
                    <section>
                      <h3 className="text-sm font-medium text-starlight-200 mb-2">About</h3>
                      <p className="text-sm text-starlight-300 leading-relaxed">{longDesc}</p>
                    </section>
                  ) : null}

                  {/* Includes: Skills + MCP servers */}
                  {(skills.length || mcp) ? (
                    <section>
                      <h3 className="text-sm font-medium text-starlight-200 mb-3">Includes</h3>

                      {skills.length ? (
                        <>
                          <div className="text-[11px] uppercase tracking-wider text-starlight-500 mb-2">
                            Skills
                          </div>
                          <div className="flex flex-wrap gap-1.5 mb-4">
                            {skills.map((s) => (
                              <span
                                key={s.id}
                                title={s.description}
                                className="text-xs px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-starlight-200"
                              >
                                {s.name}
                              </span>
                            ))}
                          </div>
                        </>
                      ) : null}

                      {mcp ? (
                        <>
                          <div className="text-[11px] uppercase tracking-wider text-starlight-500 mb-2">
                            MCP Servers
                          </div>
                          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/10">
                            <ShieldCheck size={14} className="text-accent-green" />
                            <span className="text-xs text-starlight-200 font-mono">
                              {mcp.url || mcp.type || 'configured'}
                            </span>
                          </div>
                        </>
                      ) : null}
                    </section>
                  ) : null}

                  {/* Default prompts */}
                  {prompts.length ? (
                    <section>
                      <h3 className="text-sm font-medium text-starlight-200 mb-2">Try saying</h3>
                      <div className="space-y-1.5">
                        {prompts.map((p, i) => (
                          <div
                            key={i}
                            className="text-xs px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5 text-starlight-300 italic"
                          >
                            {p}
                          </div>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  {/* Token form (revealed after Install for api_token) */}
                  {tokenForm ? (
                    <section className="border border-primary-500/20 rounded-lg p-4 bg-primary-500/[0.03]">
                      <div className="flex items-center gap-2 mb-3">
                        <Key size={14} className="text-primary-400" />
                        <h3 className="text-sm font-medium text-starlight-100">
                          Connect your account
                        </h3>
                      </div>
                      {tokenForm.help ? (
                        <p className="text-xs text-starlight-400 mb-3">{tokenForm.help}</p>
                      ) : null}
                      {tokenForm.settings_url ? (
                        <a
                          href={tokenForm.settings_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300 mb-3"
                        >
                          Open token settings <ExternalLink size={11} />
                        </a>
                      ) : null}
                      <div className="space-y-3">
                        {tokenForm.fields.map((f) => (
                          <div key={f.key}>
                            <label htmlFor={`connector-field-${f.key}`} className="block text-[11px] uppercase tracking-wider text-starlight-400 mb-1">
                              {f.label}
                            </label>
                            <input
                              id={`connector-field-${f.key}`}
                              type={f.type === 'password' ? 'password' : 'text'}
                              value={tokenValues[f.key] || ''}
                              onChange={(e) =>
                                setTokenValues({ ...tokenValues, [f.key]: e.target.value })
                              }
                              placeholder={f.help || ''}
                              className="w-full px-3 py-2 text-sm rounded-lg bg-midnight-400 border border-white/10 text-starlight-100 placeholder-starlight-500 focus:outline-none focus:border-primary-500/50"
                              autoComplete="off"
                            />
                            {f.help ? (
                              <p className="text-[11px] text-starlight-500 mt-1">{f.help}</p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  {/* Trust footer */}
                  {(data.interface?.privacyPolicyURL || data.interface?.termsOfServiceURL) ? (
                    <p className="text-[11px] text-starlight-500">
                      By installing, you accept the connector&apos;s
                      {data.interface?.privacyPolicyURL ? (
                        <>
                          {' '}
                          <a
                            href={data.interface.privacyPolicyURL}
                            target="_blank"
                            rel="noreferrer"
                            className="text-primary-400 hover:underline"
                          >
                            privacy policy
                          </a>
                        </>
                      ) : null}
                      {data.interface?.privacyPolicyURL && data.interface?.termsOfServiceURL ? ' and ' : ''}
                      {data.interface?.termsOfServiceURL ? (
                        <a
                          href={data.interface.termsOfServiceURL}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary-400 hover:underline"
                        >
                          terms of service
                        </a>
                      ) : null}
                      .
                    </p>
                  ) : null}
                </div>

                {/* Footer: install button */}
                <div className="px-8 py-5 border-t border-white/5 bg-midnight-600/40 rounded-b-2xl flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 text-sm text-starlight-300 hover:text-starlight-100 hover:bg-white/5 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  {tokenForm ? (
                    <button
                      type="button"
                      onClick={handleTokenSubmit}
                      disabled={submittingToken}
                      className="px-5 py-2 text-sm font-medium text-midnight-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                      style={{ backgroundColor: brandColor }}
                    >
                      {submittingToken ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          Connecting...
                        </>
                      ) : (
                        <>
                          <CheckCircle2 size={14} />
                          Connect account
                        </>
                      )}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={handleInstall}
                      disabled={installing}
                      className="px-5 py-2 text-sm font-medium text-midnight-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                      style={{ backgroundColor: brandColor }}
                    >
                      {installing ? (
                        <>
                          <Loader2 size={14} className="animate-spin" />
                          Starting...
                        </>
                      ) : (
                        <>
                          <Wrench size={14} />
                          Install {displayName}
                        </>
                      )}
                    </button>
                  )}
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
