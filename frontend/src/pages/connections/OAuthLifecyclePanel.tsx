/**
 * OAuthLifecyclePanel -- Refresh / Disconnect / Archive controls for an
 * OAuth-backed plugin card.
 *
 * PR-CONN-OAUTH-LIFECYCLE-FRONTEND (2026-05-03):
 * Wires the three backend endpoints shipped in
 * PR-CONN-OAUTH-REFRESH-DISCONNECT into the Connections UI. Slotted
 * into PluginDetailDrawer beneath the existing action area.
 *
 * Visibility rules:
 *   - Renders nothing unless plugin.auth_type === 'oauth'.
 *   - Renders nothing until at least one CONNECTED ConnectorInstance
 *     matches this plugin's connector (no instance -> nothing to
 *     refresh / disconnect / archive).
 *
 * Safety:
 *   - Refresh is single-click + toast (idempotent, non-destructive).
 *   - Disconnect + Archive open a confirmation modal that REQUIRES
 *     explicit operator click. Backend also requires {confirm: true}
 *     in the body -- two-layer defense.
 *   - The component never renders or stores token values. Only
 *     status, expires_at, and outcome reasons.
 */

import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle, Archive, CheckCircle2, Loader2, RefreshCw, X,
} from 'lucide-react'

import { api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { PluginCard } from './pluginCard'

interface ConnectorInstance {
  id: string
  connector_id: string
  status: string
  connector_name: string | null
}

type ActionState = 'idle' | 'loading' | 'success' | 'error'
type ConfirmKind = 'disconnect' | 'archive'

/** Map plugin.id (e.g. "app-gmail", "mcp-google-drive") to the
 * connector_id the OAuth provider table uses (e.g. "gmail",
 * "google-drive"). Mirrors the OAUTH_PROVIDERS keys in
 * backend/app/services/integrations/oauth_service.py. */
function pluginIdToProviderKey(pluginId: string): string | null {
  // Strip "app-" / "mcp-" prefix
  const stripped = pluginId.replace(/^(app|mcp)-/, '')
  // Allowed providers (must match OAUTH_PROVIDERS keys)
  const allowed = new Set([
    'gmail', 'google-calendar', 'google-drive',
    'github', 'figma', 'slack', 'canva',
  ])
  return allowed.has(stripped) ? stripped : null
}

interface Props {
  plugin: PluginCard
}

export default function OAuthLifecyclePanel({ plugin }: Props) {
  // ── Visibility gate ──
  const providerKey = pluginIdToProviderKey(plugin.id)
  const isOAuth = plugin.auth_type === 'oauth' && providerKey !== null

  const [instance, setInstance] = useState<ConnectorInstance | null>(null)
  const [loading, setLoading] = useState(false)
  const [refreshState, setRefreshState] = useState<ActionState>('idle')
  const [confirmKind, setConfirmKind] = useState<ConfirmKind | null>(null)
  const [confirmBusy, setConfirmBusy] = useState(false)
  const [refreshExpiresAt, setRefreshExpiresAt] = useState<string | null>(null)

  // Fetch the user's CONNECTED instances and pick the best match for
  // this plugin. The list endpoint already excludes ARCHIVED rows by
  // default (PR-da23dd7), so a successful match means "currently
  // connected, refreshable".
  async function loadInstance() {
    if (!isOAuth || !providerKey) return
    setLoading(true)
    try {
      const res = await api.get<{ success: boolean; data: ConnectorInstance[] }>(
        '/connections/instances',
      )
      const items = res.data?.data ?? []
      const match = items.find(
        (i) =>
          i.status === 'CONNECTED' &&
          (i.connector_id === providerKey ||
            i.connector_name?.toLowerCase().includes(providerKey)),
      ) ?? null
      setInstance(match)
    } catch {
      // Silent: panel just doesn't render the buttons.
      setInstance(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOAuth) void loadInstance()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plugin.id, isOAuth])

  if (!isOAuth) return null
  if (loading) {
    return (
      <div className="rounded-md border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px] text-starlight-400">
        <Loader2 size={11} className="mr-1 inline animate-spin" />
        Checking OAuth connection state...
      </div>
    )
  }
  if (!instance) {
    // No connected instance to manage. Don't render -- avoids implying
    // there's something to disconnect when there isn't.
    return null
  }

  // ── Action handlers ──

  async function handleRefresh() {
    if (!instance) return
    setRefreshState('loading')
    setRefreshExpiresAt(null)
    try {
      const res = await api.post<{
        success: boolean
        data: { success: boolean; expires_at: string | null; reason: string }
      }>(`/connections/instances/${instance.id}/refresh-token`)
      const data = res.data?.data
      if (data?.success) {
        setRefreshState('success')
        setRefreshExpiresAt(data.expires_at)
        toast.success(
          data.expires_at
            ? `Token refreshed. Valid until ${data.expires_at}.`
            : 'Token refreshed.',
        )
      } else {
        setRefreshState('error')
        toast.error(`Refresh failed: ${data?.reason ?? 'unknown'}`)
      }
    } catch (err: unknown) {
      setRefreshState('error')
      const msg = err instanceof Error ? err.message : 'Refresh failed'
      toast.error(msg)
    }
  }

  function openConfirm(kind: ConfirmKind) {
    setConfirmKind(kind)
  }

  async function handleConfirm() {
    if (!instance || !confirmKind) return
    setConfirmBusy(true)
    const url = `/connections/instances/${instance.id}/${confirmKind}`
    try {
      await api.post(url, { confirm: true })
      toast.success(
        confirmKind === 'disconnect'
          ? 'Disconnected. Local credentials cleared.'
          : 'Archived. Hidden from default list.',
      )
      setConfirmKind(null)
      // Reload state -- after disconnect/archive, the instance is gone
      // from the default list and the panel will hide.
      await loadInstance()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Action failed'
      toast.error(msg)
    } finally {
      setConfirmBusy(false)
    }
  }

  // ── Render ──

  return (
    <div className="rounded-md border border-accent-cyan/15 bg-accent-cyan/[0.04] px-3 py-3">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-accent-cyan">
          OAuth lifecycle
        </h4>
        <span className="text-[10px] text-starlight-500">
          Connected as {instance.connector_name ?? providerKey}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshState === 'loading'}
          className="inline-flex items-center gap-1.5 rounded-md border border-accent-cyan/30 bg-accent-cyan/10 px-2.5 py-1 text-[11px] font-medium text-accent-cyan hover:bg-accent-cyan/20 disabled:opacity-50"
        >
          {refreshState === 'loading' ? (
            <Loader2 size={11} className="animate-spin" />
          ) : refreshState === 'success' ? (
            <CheckCircle2 size={11} />
          ) : (
            <RefreshCw size={11} />
          )}
          Refresh token
        </button>

        <button
          type="button"
          onClick={() => openConfirm('disconnect')}
          className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-100 hover:bg-amber-500/20"
        >
          <X size={11} />
          Disconnect
        </button>

        <button
          type="button"
          onClick={() => openConfirm('archive')}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium text-starlight-300 hover:bg-white/[0.08]"
        >
          <Archive size={11} />
          Archive
        </button>
      </div>

      {refreshExpiresAt && refreshState === 'success' && (
        <p className="mt-2 text-[10px] text-starlight-400">
          Next expiry: {refreshExpiresAt}
        </p>
      )}

      {confirmKind && (
        <ConfirmDialog
          kind={confirmKind}
          provider={providerKey}
          busy={confirmBusy}
          onCancel={() => setConfirmKind(null)}
          onConfirm={handleConfirm}
        />
      )}
    </div>
  )
}

/** Modal-style confirmation. Same UX shape as SkillExecuteModal so
 * the operator's mental model is consistent. */
function ConfirmDialog({
  kind, provider, busy, onCancel, onConfirm,
}: {
  kind: ConfirmKind
  provider: string | null
  busy: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const isArchive = kind === 'archive'
  const title = isArchive ? 'Archive this connection?' : 'Disconnect this connection?'
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)
  // PR-A11Y-PHASE32: confirm-dialog focus contract -- focus into the panel on
  // open, restore to the opener on close; Escape cancels (WCAG 2.4.3 / 2.1.2).
  useEffect(() => {
    previousFocusRef.current = document.activeElement as HTMLElement | null
    const focusTimer = setTimeout(() => {
      const panel = panelRef.current
      if (panel && !panel.contains(document.activeElement)) panel.focus()
    }, 50)
    return () => { clearTimeout(focusTimer); previousFocusRef.current?.focus?.() }
  }, [])
  const verb = isArchive ? 'Archive' : 'Disconnect'
  const consequence = isArchive
    ? 'The connection will be hidden from the default list (audit history preserved). You can re-connect any time -- a fresh OAuth flow will create a new instance.'
    : 'Local credentials will be cleared. Daena will attempt to revoke the token at the provider (best-effort -- some providers do not expose a server-side revoke endpoint). You will need to re-connect to use this provider again.'

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
      <div
        ref={panelRef}
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); onCancel() } }}
        className="w-full max-w-md rounded-lg border border-white/10 bg-night-950 p-5 shadow-xl focus:outline-none"
      >
        <div className="mb-3 flex items-start gap-2">
          <AlertTriangle
            size={16}
            className={isArchive ? 'mt-0.5 text-starlight-400' : 'mt-0.5 text-amber-400'}
          />
          <div>
            <h3 className="text-sm font-semibold text-white">{title}</h3>
            {provider && (
              <p className="mt-0.5 text-[11px] text-starlight-400">
                Provider: {provider}
              </p>
            )}
          </div>
        </div>
        <p className="mb-4 text-[12px] leading-relaxed text-starlight-300">
          {consequence}
        </p>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-white/10 px-3 py-1.5 text-[12px] font-medium text-starlight-300 hover:bg-white/5 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium ${
              isArchive
                ? 'bg-white/10 text-white hover:bg-white/20'
                : 'bg-amber-500/80 text-night-950 hover:bg-amber-500'
            } disabled:opacity-50`}
          >
            {busy && <Loader2 size={11} className="animate-spin" />}
            {verb}
          </button>
        </div>
      </div>
    </div>
  )
}
